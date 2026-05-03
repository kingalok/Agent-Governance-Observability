from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Agent, AgentStatus, ApprovalCheckpoint, ApprovalStatus, RiskTier, RuntimeLog, UsageSnapshot


def list_agents(db: Session) -> list[Agent]:
    return list(db.scalars(select(Agent).order_by(Agent.risk_tier.desc(), Agent.name)).all())


def get_agent(db: Session, agent_id: int) -> Agent | None:
    return db.get(Agent, agent_id)


def update_agent_status(db: Session, agent: Agent, action: str) -> Agent:
    if action == "pause":
        agent.status = AgentStatus.PAUSED
    elif action == "resume":
        agent.status = AgentStatus.ACTIVE
        agent.is_kill_switched = False
    elif action == "kill":
        agent.status = AgentStatus.KILLED
        agent.is_kill_switched = True
    else:
        raise ValueError(f"Unsupported action: {action}")

    agent.updated_at = datetime.utcnow()
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def get_runtime_logs(db: Session, limit: int = 50) -> list[RuntimeLog]:
    return list(db.scalars(select(RuntimeLog).order_by(RuntimeLog.created_at.desc()).limit(limit)).all())


def get_pending_approvals(db: Session) -> list[ApprovalCheckpoint]:
    return list(
        db.scalars(
            select(ApprovalCheckpoint).order_by(ApprovalCheckpoint.created_at.desc())
        ).all()
    )


def get_usage_snapshots(db: Session) -> list[UsageSnapshot]:
    return list(db.scalars(select(UsageSnapshot).order_by(UsageSnapshot.captured_at.desc())).all())


def get_dashboard_summary(db: Session) -> dict:
    total_agents = db.scalar(select(func.count()).select_from(Agent)) or 0
    active_agents = db.scalar(select(func.count()).select_from(Agent).where(Agent.status == AgentStatus.ACTIVE)) or 0
    paused_agents = db.scalar(select(func.count()).select_from(Agent).where(Agent.status == AgentStatus.PAUSED)) or 0
    killed_agents = db.scalar(select(func.count()).select_from(Agent).where(Agent.status == AgentStatus.KILLED)) or 0
    high_risk_agents = (
        db.scalar(select(func.count()).select_from(Agent).where(Agent.risk_tier == RiskTier.HIGH)) or 0
    )
    pending_approvals = db.scalar(
        select(func.count()).select_from(ApprovalCheckpoint).where(ApprovalCheckpoint.status == ApprovalStatus.PENDING)
    ) or 0

    return {
        "total_agents": total_agents,
        "active_agents": active_agents,
        "paused_agents": paused_agents,
        "killed_agents": killed_agents,
        "pending_approvals": pending_approvals,
        "high_risk_agents": high_risk_agents,
    }
