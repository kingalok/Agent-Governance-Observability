#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_DB_PATH = REPO_ROOT / "smoke_test.db"

os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGSMITH_API_KEY", "")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("API_CORS_ORIGINS", '["http://localhost:3000"]')
os.environ["DATABASE_URL"] = f"sqlite:///{SMOKE_DB_PATH}"

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.seed import seed_demo_data  # noqa: E402


def reset_db() -> None:
    if SMOKE_DB_PATH.exists():
        SMOKE_DB_PATH.unlink()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)


def main() -> None:
    reset_db()

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200

        agents = client.get("/api/v1/agents")
        assert agents.status_code == 200
        high_agent_id = next(agent["id"] for agent in agents.json() if agent["risk_tier"] == "high")

        sample_payloads = client.get("/api/v1/workflows/demo/sample-payloads")
        assert sample_payloads.status_code == 200
        payload = sample_payloads.json()["high_risk"]

        create_run = client.post(f"/api/v1/runs?agent_id={high_agent_id}", json=payload)
        assert create_run.status_code == 200
        created = create_run.json()
        assert created["status"] == "awaiting_human_approval"
        run_id = created["run_id"]

        pending = client.get("/api/v1/approvals/pending")
        assert pending.status_code == 200
        assert any(item["run_id"] == run_id for item in pending.json())

        approve = client.post(f"/api/v1/approvals/{run_id}/approve", json={"reviewer_name": "smoke.reviewer"})
        assert approve.status_code == 200
        approved = approve.json()
        assert approved["status"] == "success"

        detail = client.get(f"/api/v1/runs/{run_id}")
        assert detail.status_code == 200
        detailed_run = detail.json()
        assert detailed_run["final_output"]["execution_result"]["tool"] == "send_email"
        assert detailed_run["graph_state"]["approval_decision"] == "approved"

        events = client.get(f"/api/v1/runs/{run_id}/events")
        assert events.status_code == 200
        assert any(event["event_type"] == "finalize_node" for event in events.json())

    print("Smoke test passed: high-risk run paused, approved, resumed, and finalized successfully.")


if __name__ == "__main__":
    main()
