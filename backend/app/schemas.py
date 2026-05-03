from datetime import datetime

from pydantic import BaseModel, Field

from app.models import AgentStatus, ApprovalStatus, LogLevel, RiskTier, WorkflowRunStatus


class AgentBase(BaseModel):
    name: str
    description: str
    owner_name: str
    team_name: str
    risk_tier: RiskTier
    allowed_tools: list[str]
    model_name: str
    token_budget_daily: int
    cost_budget_daily: float


class AgentResponse(AgentBase):
    id: int
    status: AgentStatus
    is_kill_switched: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RuntimeLogResponse(BaseModel):
    id: int
    agent_id: int
    workflow_name: str
    event_type: str
    level: LogLevel
    message: str
    payload: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalResponse(BaseModel):
    id: int
    agent_id: int
    run_id: int | None
    workflow_name: str
    action_name: str
    reason: str
    status: ApprovalStatus
    requested_by: str
    decided_by: str | None
    rejection_reason: str | None
    created_at: datetime
    decided_at: datetime | None

    model_config = {"from_attributes": True}


class UsageSnapshotResponse(BaseModel):
    id: int
    agent_id: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    window_label: str
    captured_at: datetime

    model_config = {"from_attributes": True}


class AgentControlRequest(BaseModel):
    action: str


class ApprovalDecisionRequest(BaseModel):
    decision: ApprovalStatus
    decided_by: str


class DashboardSummaryResponse(BaseModel):
    total_agents: int
    active_agents: int
    paused_agents: int
    killed_agents: int
    pending_approvals: int
    high_risk_agents: int


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    database: str
    auth_enabled: bool
    langsmith_tracing_enabled: bool


class ApiErrorDetail(BaseModel):
    event_id: str | None = None


class ApiErrorEnvelope(BaseModel):
    error: dict


class WorkflowRunResponse(BaseModel):
    run_id: int
    agent_id: int
    workflow_name: str
    agent_name: str
    status: WorkflowRunStatus
    current_node: str
    state: str
    graph_state: dict
    risk_tier: str
    requested_tool: str | None
    approval_required: bool
    message: str


class WorkflowRunRequest(BaseModel):
    request_type: str = "document_intake"
    requested_action: str = "triage_and_route"
    requested_tool: str = "create_ticket"
    requested_by: str = "demo-user"
    document_title: str = "Untitled document"
    document_text: str = "Summarize and route this document."
    external_destination: bool = False
    contains_pii: bool = False
    destination: str | None = None
    record_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class WorkflowResumeRequest(BaseModel):
    decision: ApprovalStatus
    decided_by: str


class ApprovalActionRequest(BaseModel):
    reviewer_name: str
    rejection_reason: str | None = None


class WorkflowRunDetailResponse(BaseModel):
    id: int
    agent_id: int
    workflow_name: str
    request_type: str
    requested_tool: str | None
    status: WorkflowRunStatus
    current_node: str
    input_payload: dict
    state_payload: dict
    transition_history: list[dict]
    classification_label: str | None
    risk_label: RiskTier | None
    reasoning_summary: str | None
    final_output: dict
    graph_state: dict = Field(default_factory=dict)
    started_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
