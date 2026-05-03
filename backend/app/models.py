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
    owner: Mapped[str] = mapped_column(String(120))
    team: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[AgentStatus] = mapped_column(SqlEnum(AgentStatus), default=AgentStatus.ACTIVE)
    default_risk_tier: Mapped[RiskTier] = mapped_column(SqlEnum(RiskTier), default=RiskTier.LOW)
    is_kill_switched: Mapped[bool] = mapped_column(Boolean, default=False)
    model_name: Mapped[str] = mapped_column(String(120), default="gpt-4.1-mini")
    token_budget_daily: Mapped[int] = mapped_column(Integer, default=100000)
    cost_budget_daily: Mapped[float] = mapped_column(Float, default=20.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tools: Mapped[list["AgentTool"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    runs: Mapped[list["Run"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    usage_snapshots: Mapped[list["UsageSnapshot"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )

    @property
    def owner_name(self) -> str:
        return self.owner

    @property
    def team_name(self) -> str:
        return self.team

    @property
    def risk_tier(self) -> RiskTier:
        return self.default_risk_tier

    @property
    def allowed_tools(self) -> list[str]:
        return [tool.tool_name for tool in self.tools if tool.allowed]


class AgentTool(Base):
    __tablename__ = "agent_tools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    tool_name: Mapped[str] = mapped_column(String(120), index=True)
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)

    agent: Mapped[Agent] = relationship(back_populates="tools")


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text)
    applies_to_risk_tier: Mapped[RiskTier] = mapped_column(SqlEnum(RiskTier), index=True)
    allowed_tools: Mapped[list[str]] = mapped_column(JSON, default=list)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=False)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_tier: Mapped[RiskTier | None] = mapped_column(SqlEnum(RiskTier), nullable=True)
    status: Mapped[WorkflowRunStatus] = mapped_column(SqlEnum(WorkflowRunStatus), default=WorkflowRunStatus.PENDING)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_status: Mapped[ApprovalStatus] = mapped_column(SqlEnum(ApprovalStatus), default=ApprovalStatus.PENDING)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    workflow_name: Mapped[str] = mapped_column(String(120), default="document_governance_workflow")
    request_type: Mapped[str] = mapped_column(String(120), default="document_intake")
    requested_tool: Mapped[str | None] = mapped_column(String(120), nullable=True)
    current_node: Mapped[str] = mapped_column(String(120), default="intake_node")
    state_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    transition_history: Mapped[list[dict]] = mapped_column(JSON, default=list)
    classification_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reasoning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_output: Mapped[dict] = mapped_column(JSON, default=dict)

    agent: Mapped[Agent] = relationship(back_populates="runs")
    approvals: Mapped[list["Approval"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    events: Mapped[list["RunEvent"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    usage_snapshots: Mapped[list["UsageSnapshot"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    reviewer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decision: Mapped[ApprovalStatus] = mapped_column(SqlEnum(ApprovalStatus), default=ApprovalStatus.PENDING)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    workflow_name: Mapped[str] = mapped_column(String(120), default="document_governance_workflow")
    action_name: Mapped[str] = mapped_column(String(120), default="review_action")
    requested_by: Mapped[str] = mapped_column(String(120), default="system")

    run: Mapped[Run] = relationship(back_populates="approvals")

    @property
    def agent_id(self) -> int:
        return self.run.agent_id

    @property
    def status(self) -> ApprovalStatus:
        return self.decision

    @status.setter
    def status(self, value: ApprovalStatus) -> None:
        self.decision = value

    @property
    def decided_by(self) -> str | None:
        return self.reviewer

    @decided_by.setter
    def decided_by(self, value: str | None) -> None:
        self.reviewer = value

    @property
    def rejection_reason(self) -> str | None:
        return self.reason if self.decision == ApprovalStatus.REJECTED else None

    @rejection_reason.setter
    def rejection_reason(self, value: str | None) -> None:
        self.reason = value


class RunEvent(Base):
    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    event_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    level: Mapped[LogLevel] = mapped_column(SqlEnum(LogLevel), default=LogLevel.INFO)
    message: Mapped[str] = mapped_column(Text, default="")

    run: Mapped[Run] = relationship(back_populates="events")

    @property
    def agent_id(self) -> int:
        return self.run.agent_id

    @property
    def workflow_name(self) -> str:
        return self.run.workflow_name

    @property
    def payload(self) -> dict:
        return self.event_payload


class UsageSnapshot(Base):
    __tablename__ = "usage_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id"), index=True, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    window_label: Mapped[str] = mapped_column(String(80), default="daily")
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    agent: Mapped[Agent] = relationship(back_populates="usage_snapshots")
    run: Mapped["Run | None"] = relationship(back_populates="usage_snapshots")


@property
def _run_risk_label(self: Run) -> RiskTier | None:
    return self.risk_tier


@property
def _run_updated_at(self: Run) -> datetime:
    return self.finished_at or self.started_at


@property
def _run_completed_at(self: Run) -> datetime | None:
    return self.finished_at


Run.risk_label = _run_risk_label  # type: ignore[attr-defined]
Run.updated_at = _run_updated_at  # type: ignore[attr-defined]
Run.completed_at = _run_completed_at  # type: ignore[attr-defined]


# Compatibility aliases for the current PoC service layer.
WorkflowRun = Run
ApprovalCheckpoint = Approval
RuntimeLog = RunEvent
