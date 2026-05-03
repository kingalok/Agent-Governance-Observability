from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Agent, ApprovalStatus, RiskTier, WorkflowRunStatus
from app.sample_payloads import HIGH_RISK_SAMPLE_PAYLOAD, LOW_RISK_SAMPLE_PAYLOAD, POLICY_VIOLATION_SAMPLE_PAYLOAD
from app.services.workflow import get_run_approval_checkpoint, resume_workflow, run_workflow


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    return session_local()


def build_agent(allowed_tools: list[str]) -> Agent:
    return Agent(
        name="Demo Agent",
        description="Test agent",
        owner_name="Test Owner",
        team_name="Platform",
        risk_tier=RiskTier.LOW,
        allowed_tools=allowed_tools,
        model_name="gpt-4.1-mini",
        token_budget_daily=1000,
        cost_budget_daily=5.0,
    )


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
    assert resumed_run.final_output["execution_result"]["tool"] == "send_email"
