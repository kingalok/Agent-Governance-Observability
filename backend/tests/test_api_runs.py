import os

from fastapi.testclient import TestClient

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGSMITH_API_KEY"] = ""
os.environ["API_CORS_ORIGINS"] = '["http://localhost:3000"]'
os.environ["DATABASE_URL"] = "sqlite:///./agent_governance_api_test.db"
os.environ["AUTH_ENABLED"] = "false"

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.services.seed import seed_demo_data  # noqa: E402
from app.main import app  # noqa: E402


def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)


def test_runs_and_approvals_api_flow() -> None:
    reset_db()

    with TestClient(app) as client:
        agents = client.get("/api/v1/agents")
        assert agents.status_code == 200
        agent_list = agents.json()
        high_agent_id = next(agent["id"] for agent in agent_list if agent["risk_tier"] == "high")

        sample_payloads = client.get("/api/v1/workflows/demo/sample-payloads")
        assert sample_payloads.status_code == 200

        create_run = client.post(
            f"/api/v1/runs?agent_id={high_agent_id}",
            json=sample_payloads.json()["high_risk"],
        )
        assert create_run.status_code == 200
        assert create_run.json()["status"] == "awaiting_human_approval"
        run_id = create_run.json()["run_id"]

        runs = client.get("/api/v1/runs")
        assert runs.status_code == 200
        assert any(run["run_id"] == run_id for run in runs.json())

        run_detail = client.get(f"/api/v1/runs/{run_id}")
        assert run_detail.status_code == 200
        assert run_detail.json()["graph_state"]["current_node"] == "approval_gate_node"
        assert "x-request-id" in run_detail.headers

        pending = client.get("/api/v1/approvals/pending")
        assert pending.status_code == 200
        assert any(item["run_id"] == run_id for item in pending.json())

        approve = client.post(f"/api/v1/approvals/{run_id}/approve", json={"reviewer_name": "security.lead"})
        assert approve.status_code == 200
        assert approve.json()["status"] == "success"
        assert approve.json()["graph_state"]["current_node"] == "finalize_node"

        events = client.get(f"/api/v1/runs/{run_id}/events")
        assert events.status_code == 200
        event_payload = events.json()
        assert len(event_payload) >= 5
        assert event_payload[0]["event_type"] == "intake_node"
        assert any(event["event_type"] == "approval_gate_node" for event in event_payload)
        assert any(event["event_type"] == "finalize_node" for event in event_payload)


def test_api_response_structure_for_run_resources() -> None:
    reset_db()

    with TestClient(app) as client:
        agents = client.get("/api/v1/agents").json()
        low_agent_id = next(agent["id"] for agent in agents if agent["risk_tier"] == "low")
        payload = client.get("/api/v1/workflows/demo/sample-payloads").json()["low_risk"]

        create_run = client.post(f"/api/v1/runs?agent_id={low_agent_id}", json=payload)
        assert create_run.status_code == 200
        run_summary = create_run.json()
        assert set(
            [
                "run_id",
                "agent_id",
                "workflow_name",
                "agent_name",
                "status",
                "current_node",
                "state",
                "graph_state",
                "risk_tier",
                "requested_tool",
                "approval_required",
                "message",
            ]
        ).issubset(run_summary.keys())

        run_id = run_summary["run_id"]
        detail = client.get(f"/api/v1/runs/{run_id}")
        assert detail.status_code == 200
        run_detail = detail.json()
        assert set(
            [
                "id",
                "agent_id",
                "workflow_name",
                "request_type",
                "requested_tool",
                "status",
                "current_node",
                "input_payload",
                "state_payload",
                "transition_history",
                "final_output",
                "graph_state",
                "started_at",
                "updated_at",
            ]
        ).issubset(run_detail.keys())
        assert run_detail["final_output"]["status"] == "success"


def test_reject_endpoint_records_reason() -> None:
    reset_db()

    with TestClient(app) as client:
        agents = client.get("/api/v1/agents").json()
        high_agent_id = next(agent["id"] for agent in agents if agent["risk_tier"] == "high")
        payload = client.get("/api/v1/workflows/demo/sample-payloads").json()["high_risk"]

        create_run = client.post(f"/api/v1/runs?agent_id={high_agent_id}", json=payload).json()
        run_id = create_run["run_id"]

        reject = client.post(
            f"/api/v1/approvals/{run_id}/reject",
            json={"reviewer_name": "security.lead", "rejection_reason": "Export request denied."},
        )
        assert reject.status_code == 200
        assert reject.json()["status"] == "stopped"
        assert reject.json()["message"] == "Export request denied."

        detail = client.get(f"/api/v1/runs/{run_id}")
        assert detail.status_code == 200
        assert detail.json()["graph_state"]["stop_reason"] == "Export request denied."


def test_kill_endpoint_stops_waiting_run() -> None:
    reset_db()

    with TestClient(app) as client:
        agents = client.get("/api/v1/agents").json()
        high_agent_id = next(agent["id"] for agent in agents if agent["risk_tier"] == "high")
        payload = client.get("/api/v1/workflows/demo/sample-payloads").json()["high_risk"]

        create_run = client.post(f"/api/v1/runs?agent_id={high_agent_id}", json=payload).json()
        run_id = create_run["run_id"]

        kill = client.post(f"/api/v1/runs/{run_id}/kill")
        assert kill.status_code == 200
        assert kill.json()["status"] == "stopped"
        assert kill.json()["graph_state"]["current_node"] == "finalize_node"


def test_run_events_endpoint_404_for_unknown_run() -> None:
    reset_db()

    with TestClient(app) as client:
        response = client.get("/api/v1/runs/999999/events")
        assert response.status_code == 404


def test_health_endpoint_exposes_runtime_flags() -> None:
    reset_db()

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["environment"] == "development"
        assert "version" in payload


def test_auth_placeholder_rejects_when_enabled() -> None:
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["DEMO_API_KEY"] = "test-key"
    from app.config import get_settings  # noqa: WPS433

    get_settings.cache_clear()
    reset_db()

    try:
        with TestClient(app) as client:
            unauthorized = client.get("/api/v1/runs")
            assert unauthorized.status_code == 401

            authorized = client.get("/api/v1/runs", headers={"X-API-Key": "test-key"})
            assert authorized.status_code == 200
    finally:
        os.environ["AUTH_ENABLED"] = "false"
        os.environ["DEMO_API_KEY"] = "change-me"
        get_settings.cache_clear()
