from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, DateTime, Enum as SqlEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AgentStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    KILLED = "killed"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class LogLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class WorkflowRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_HUMAN_APPROVAL = "awaiting_human_approval"
    SUCCESS = "success"
    FAILED = "failed"
    POLICY_VIOLATION = "policy_violation"
    STOPPED = "stopped"


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text)
    owner_name: Mapped[str] = mapped_column(String(120))
    team_name: Mapped[str] = mapped_column(String(120))
    risk_tier: Mapped[RiskTier] = mapped_column(SqlEnum(RiskTier), default=RiskTier.LOW)
    status: Mapped[AgentStatus] = mapped_column(SqlEnum(AgentStatus), default=AgentStatus.ACTIVE)
    is_kill_switched: Mapped[bool] = mapped_column(Boolean, default=False)
    model_name: Mapped[str] = mapped_column(String(120), default="gpt-4.1-mini")
    allowed_tools: Mapped[list[str]] = mapped_column(JSON, default=list)
    token_budget_daily: Mapped[int] = mapped_column(Integer, default=100000)
    cost_budget_daily: Mapped[float] = mapped_column(Float, default=20.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    runtime_logs: Mapped[list["RuntimeLog"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    approvals: Mapped[list["ApprovalCheckpoint"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )
    workflow_runs: Mapped[list["WorkflowRun"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )
    usage_snapshots: Mapped[list["UsageSnapshot"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )


class RuntimeLog(Base):
    __tablename__ = "runtime_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("workflow_runs.id"), index=True, nullable=True)
    workflow_name: Mapped[str] = mapped_column(String(120))
    event_type: Mapped[str] = mapped_column(String(120))
    level: Mapped[LogLevel] = mapped_column(SqlEnum(LogLevel), default=LogLevel.INFO)
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    agent: Mapped[Agent] = relationship(back_populates="runtime_logs")
    run: Mapped["WorkflowRun | None"] = relationship(back_populates="runtime_logs")


class ApprovalCheckpoint(Base):
    __tablename__ = "approval_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("workflow_runs.id"), index=True, nullable=True)
    workflow_name: Mapped[str] = mapped_column(String(120))
    action_name: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[ApprovalStatus] = mapped_column(SqlEnum(ApprovalStatus), default=ApprovalStatus.PENDING)
    requested_by: Mapped[str] = mapped_column(String(120), default="system")
    decided_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    agent: Mapped[Agent] = relationship(back_populates="approvals")
    run: Mapped["WorkflowRun | None"] = relationship(back_populates="approval_checkpoints")


class UsageSnapshot(Base):
    __tablename__ = "usage_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("workflow_runs.id"), index=True, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    window_label: Mapped[str] = mapped_column(String(80), default="daily")
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    agent: Mapped[Agent] = relationship(back_populates="usage_snapshots")
    run: Mapped["WorkflowRun | None"] = relationship(back_populates="usage_snapshots")


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    workflow_name: Mapped[str] = mapped_column(String(120), default="document_governance_workflow")
    request_type: Mapped[str] = mapped_column(String(120))
    requested_tool: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[WorkflowRunStatus] = mapped_column(SqlEnum(WorkflowRunStatus), default=WorkflowRunStatus.PENDING)
    current_node: Mapped[str] = mapped_column(String(120), default="intake_node")
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    state_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    transition_history: Mapped[list[dict]] = mapped_column(JSON, default=list)
    classification_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    risk_label: Mapped[RiskTier | None] = mapped_column(SqlEnum(RiskTier), nullable=True)
    reasoning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_output: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    agent: Mapped[Agent] = relationship(back_populates="workflow_runs")
    runtime_logs: Mapped[list[RuntimeLog]] = relationship(back_populates="run", cascade="all, delete-orphan")
    approval_checkpoints: Mapped[list[ApprovalCheckpoint]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    usage_snapshots: Mapped[list[UsageSnapshot]] = relationship(back_populates="run", cascade="all, delete-orphan")
