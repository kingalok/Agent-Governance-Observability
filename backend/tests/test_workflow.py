from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Agent, AgentTool, ApprovalStatus, RiskTier, RunEvent, UsageSnapshot, WorkflowRunStatus
from app.sample_payloads import HIGH_RISK_SAMPLE_PAYLOAD, LOW_RISK_SAMPLE_PAYLOAD, POLICY_VIOLATION_SAMPLE_PAYLOAD
from app.services.workflow import get_run_approval_checkpoint, kill_workflow_run, reject_workflow, resume_workflow, run_workflow


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    return session_local()


def build_agent(allowed_tools: list[str]) -> Agent:
    agent = Agent(
        name="Demo Agent",
        owner="Test Owner",
        team="Platform",
        description="Test agent",
        default_risk_tier=RiskTier.LOW,
        model_name="gpt-4.1-mini",
        token_budget_daily=1000,
        cost_budget_daily=5.0,
    )
    agent.tools = [AgentTool(tool_name=tool_name, allowed=True, requires_approval=False) for tool_name in allowed_tools]
    return agent


def test_low_risk_allowed_request_succeeds() -> None:
    db = build_session()
    agent = build_agent(["create_ticket"])
    db.add(agent)
    db.commit()
    db.refresh(agent)

    run = run_workflow(db, agent, LOW_RISK_SAMPLE_PAYLOAD)

    assert run.status == WorkflowRunStatus.SUCCESS
    assert run.current_node == "finalize_node"
    assert run.final_output["requested_tool"] == "create_ticket"
    assert run.final_output["status"] == WorkflowRunStatus.SUCCESS.value
    assert run.final_output["execution_result"]["allowed"] is True
    assert run.final_output["execution_result"]["executed"] is True
    assert run.final_output["execution_result"]["execution_time_ms"] >= 0
    assert run.final_output["execution_result"]["simulated_cost_usd"] > 0

    audit_event = db.query(RunEvent).filter(RunEvent.run_id == run.id, RunEvent.event_type == "tool_call_audit").first()
    assert audit_event is not None
    assert audit_event.event_payload["tool"] == "create_ticket"


def test_high_risk_request_pauses_for_approval() -> None:
    db = build_session()
    agent = build_agent(["send_email"])
    db.add(agent)
    db.commit()
    db.refresh(agent)

    run = run_workflow(db, agent, HIGH_RISK_SAMPLE_PAYLOAD)
    approval = get_run_approval_checkpoint(db, run.id)

    assert run.status == WorkflowRunStatus.AWAITING_HUMAN_APPROVAL
    assert run.current_node == "approval_gate_node"
    assert run.state_payload["approval_required"] is True
    assert run.state_payload["effective_risk_tier"] == RiskTier.HIGH.value
    assert approval is not None
    assert approval.status == ApprovalStatus.PENDING


def test_policy_violation_blocks_disallowed_tool() -> None:
    db = build_session()
    agent = build_agent(["create_ticket"])
    db.add(agent)
    db.commit()
    db.refresh(agent)

    run = run_workflow(db, agent, POLICY_VIOLATION_SAMPLE_PAYLOAD)

    assert run.status == WorkflowRunStatus.POLICY_VIOLATION
    assert "not allowed" in run.state_payload["policy_violation_reason"].lower()
    assert run.state_payload["execution_status"] == "blocked"
    assert run.final_output["execution_result"] == {}


def test_approved_high_risk_run_resumes_to_success() -> None:
    db = build_session()
    agent = build_agent(["send_email"])
    db.add(agent)
    db.commit()
    db.refresh(agent)

    paused_run = run_workflow(db, agent, HIGH_RISK_SAMPLE_PAYLOAD)
    approval = get_run_approval_checkpoint(db, paused_run.id)
    assert approval is not None

    resumed_run = resume_workflow(db, paused_run, approval, ApprovalStatus.APPROVED, "security.lead")

    assert resumed_run.status == WorkflowRunStatus.SUCCESS
    assert resumed_run.current_node == "finalize_node"
    assert resumed_run.state_payload["approval_decision"] == ApprovalStatus.APPROVED.value
    assert resumed_run.state_payload["current_node"] == "finalize_node"
    assert resumed_run.final_output["execution_result"]["tool"] == "send_email"
    assert resumed_run.final_output["execution_result"]["requires_approval"] is True
    assert resumed_run.final_output["execution_result"]["approval_satisfied"] is True

    resumed_again = resume_workflow(db, resumed_run, approval, ApprovalStatus.APPROVED, "security.lead")
    assert resumed_again.id == resumed_run.id

    usage_snapshots = db.query(UsageSnapshot).filter(UsageSnapshot.run_id == resumed_run.id).all()
    assert len(usage_snapshots) == 1


def test_rejected_high_risk_run_stores_reason_and_stops() -> None:
    db = build_session()
    agent = build_agent(["send_email"])
    db.add(agent)
    db.commit()
    db.refresh(agent)

    paused_run = run_workflow(db, agent, HIGH_RISK_SAMPLE_PAYLOAD)
    approval = get_run_approval_checkpoint(db, paused_run.id)
    assert approval is not None

    rejected_run = reject_workflow(db, paused_run, approval, "security.lead", "Sensitive export denied.")

    assert rejected_run.status == WorkflowRunStatus.STOPPED
    assert rejected_run.current_node == "finalize_node"
    assert rejected_run.state_payload["approval_decision"] == ApprovalStatus.REJECTED.value
    assert rejected_run.final_output["final_message"] == "Sensitive export denied."
    assert approval.rejection_reason == "Sensitive export denied."


def test_kill_paused_run_terminates_cleanly() -> None:
    db = build_session()
    agent = build_agent(["send_email"])
    db.add(agent)
    db.commit()
    db.refresh(agent)

    paused_run = run_workflow(db, agent, HIGH_RISK_SAMPLE_PAYLOAD)
    killed_run = kill_workflow_run(db, paused_run, "Run killed by reviewer.")

    assert killed_run.status == WorkflowRunStatus.STOPPED
    assert killed_run.current_node == "finalize_node"
    assert killed_run.state_payload["stop_requested"] is True
    assert killed_run.final_output["final_message"] == "Run killed by reviewer."
