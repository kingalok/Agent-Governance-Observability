from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Agent, ApprovalCheckpoint, ApprovalStatus, LogLevel, RiskTier, RuntimeLog, UsageSnapshot


def seed_demo_data(db: Session) -> None:
    existing = db.scalar(select(Agent.id).limit(1))
    if existing is not None:
        return

    agents = [
        Agent(
            name="Vendor Risk Copilot",
            description="Reviews third-party vendor requests and flags governance concerns.",
            owner_name="Priya Shah",
            team_name="Security Engineering",
            risk_tier=RiskTier.MEDIUM,
            allowed_tools=["slack_notify", "ticket_lookup", "policy_search"],
            model_name="gpt-4.1",
            token_budget_daily=150000,
            cost_budget_daily=35.0,
        ),
        Agent(
            name="PII Export Agent",
            description="Coordinates regulated customer data export requests with approval controls.",
            owner_name="Marcus Lee",
            team_name="Data Platform",
            risk_tier=RiskTier.HIGH,
            allowed_tools=["warehouse_query", "export_package", "email_notify"],
            model_name="gpt-4.1",
            token_budget_daily=250000,
            cost_budget_daily=60.0,
        ),
        Agent(
            name="Knowledge Base Curator",
            description="Maintains internal knowledge summaries for go-to-market teams.",
            owner_name="Hannah Brooks",
            team_name="Revenue Operations",
            risk_tier=RiskTier.LOW,
            allowed_tools=["docs_search", "cms_publish"],
            model_name="gpt-4.1-mini",
            token_budget_daily=90000,
            cost_budget_daily=12.0,
        ),
    ]
    db.add_all(agents)
    db.flush()

    logs = [
        RuntimeLog(
            agent_id=agents[0].id,
            workflow_name="vendor_review",
            event_type="policy_scan_completed",
            level=LogLevel.INFO,
            message="Policy evaluation completed without escalation.",
            payload={"risk_score": 0.39},
        ),
        RuntimeLog(
            agent_id=agents[1].id,
            workflow_name="regulated_export",
            event_type="approval_requested",
            level=LogLevel.WARNING,
            message="High-risk export requires human approval before release.",
            payload={"records_requested": 1245, "destination": "external_requestor"},
        ),
        RuntimeLog(
            agent_id=agents[2].id,
            workflow_name="knowledge_sync",
            event_type="publish_success",
            level=LogLevel.INFO,
            message="Knowledge package published to internal workspace.",
            payload={"documents_updated": 18},
        ),
    ]
    db.add_all(logs)

    approval = ApprovalCheckpoint(
        agent_id=agents[1].id,
        workflow_name="regulated_export",
        action_name="release_customer_export",
        reason="Customer data export exceeds automatic approval threshold.",
        status=ApprovalStatus.PENDING,
        requested_by="workflow-engine",
    )
    db.add(approval)

    usage = [
        UsageSnapshot(agent_id=agents[0].id, input_tokens=1800, output_tokens=430, estimated_cost_usd=0.19),
        UsageSnapshot(agent_id=agents[1].id, input_tokens=3500, output_tokens=710, estimated_cost_usd=0.54),
        UsageSnapshot(agent_id=agents[2].id, input_tokens=1200, output_tokens=280, estimated_cost_usd=0.08),
    ]
    db.add_all(usage)
    db.commit()
