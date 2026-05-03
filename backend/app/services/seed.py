from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Agent, AgentTool, Approval, ApprovalStatus, LogLevel, Policy, RiskTier, Run, RunEvent, UsageSnapshot


def seed_demo_data(db: Session) -> None:
    existing = db.scalar(select(Agent.id).limit(1))
    if existing is not None:
        return

    agents = [
        Agent(
            name="Knowledge Base Curator",
            owner="Hannah Brooks",
            team="Revenue Operations",
            description="Maintains internal knowledge summaries for go-to-market teams.",
            status="active",
            default_risk_tier=RiskTier.LOW,
            model_name="gpt-4.1-mini",
            token_budget_daily=90000,
            cost_budget_daily=12.0,
        ),
        Agent(
            name="PII Export Agent",
            owner="Marcus Lee",
            team="Data Platform",
            description="Coordinates regulated customer data export requests with approval controls.",
            status="active",
            default_risk_tier=RiskTier.HIGH,
            model_name="gpt-4.1",
            token_budget_daily=250000,
            cost_budget_daily=60.0,
        ),
    ]
    db.add_all(agents)
    db.flush()

    tools = [
        AgentTool(agent_id=agents[0].id, tool_name="create_ticket", allowed=True, requires_approval=False),
        AgentTool(agent_id=agents[1].id, tool_name="send_email", allowed=True, requires_approval=True),
        AgentTool(agent_id=agents[1].id, tool_name="update_vendor_record", allowed=True, requires_approval=True),
    ]
    db.add_all(tools)

    policy = Policy(
        name="Block Email Without Approval",
        description="Sending email from a high-risk workflow requires human approval before execution.",
        applies_to_risk_tier=RiskTier.HIGH,
        allowed_tools=["send_email", "update_vendor_record"],
        requires_human_approval=True,
    )
    db.add(policy)
    db.flush()

    low_run = Run(
        agent_id=agents[0].id,
        input_payload={"request_type": "document_intake", "requested_tool": "create_ticket"},
        risk_tier=RiskTier.LOW,
        status="success",
        approval_required=False,
        approval_status=ApprovalStatus.APPROVED,
        workflow_name="knowledge_sync",
        request_type="document_intake",
        requested_tool="create_ticket",
        current_node="finalize_node",
        final_output={"status": "success"},
    )
    high_run = Run(
        agent_id=agents[1].id,
        input_payload={"request_type": "document_intake", "requested_tool": "send_email"},
        risk_tier=RiskTier.HIGH,
        status="awaiting_human_approval",
        approval_required=True,
        approval_status=ApprovalStatus.PENDING,
        workflow_name="regulated_export",
        request_type="document_intake",
        requested_tool="send_email",
        current_node="approval_gate_node",
        final_output={},
    )
    db.add_all([low_run, high_run])
    db.flush()

    logs = [
        RunEvent(
            run_id=low_run.id,
            event_type="policy_scan_completed",
            level=LogLevel.INFO,
            message="Policy evaluation completed without escalation.",
            event_payload={"risk_score": 0.18},
        ),
        RunEvent(
            run_id=high_run.id,
            event_type="approval_requested",
            level=LogLevel.WARNING,
            message="High-risk export requires human approval before release.",
            event_payload={"records_requested": 1245, "destination": "external_requestor"},
        ),
    ]
    db.add_all(logs)

    approval = Approval(
        run_id=high_run.id,
        workflow_name="regulated_export",
        action_name="release_customer_export",
        reason="Customer data export exceeds automatic approval threshold.",
        decision=ApprovalStatus.PENDING,
        requested_by="workflow-engine",
    )
    db.add(approval)

    usage = [
        UsageSnapshot(agent_id=agents[0].id, run_id=low_run.id, input_tokens=1200, output_tokens=280, estimated_cost_usd=0.08),
        UsageSnapshot(agent_id=agents[1].id, run_id=high_run.id, input_tokens=3500, output_tokens=710, estimated_cost_usd=0.54),
    ]
    db.add_all(usage)
    db.commit()
