from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypedDict

from app.models import RiskTier, WorkflowRunStatus


WorkflowNodeName = Literal[
    "intake_node",
    "classification_node",
    "policy_check_node",
    "approval_gate_node",
    "tool_execution_node",
    "kill_switch_node",
    "finalize_node",
]


class WorkflowState(TypedDict, total=False):
    run_id: int
    workflow_name: str
    agent_id: int
    agent_name: str
    owner_name: str
    team_name: str
    agent_risk_tier: str
    request_type: str
    request_payload: dict[str, Any]
    requested_tool: str
    requested_action: str
    requested_by: str
    request_timestamp: str
    classification_label: str
    classification_summary: str
    reasoning_summary: str
    effective_risk_tier: str
    policy_allowed: bool
    policy_violation_reason: str
    approval_required: bool
    approval_checkpoint_id: int | None
    approval_decision: str | None
    execution_status: str
    execution_result: dict[str, Any]
    structured_output: dict[str, Any]
    current_node: WorkflowNodeName
    final_message: str
    logs: list[dict[str, Any]]
    state_version: int
    status: str
    stop_requested: bool
    stop_reason: str | None


def iso_utc_now() -> str:
    return datetime.utcnow().isoformat()


def build_initial_state(agent_id: int, agent_name: str, owner_name: str, team_name: str, agent_risk_tier: RiskTier, payload: dict[str, Any]) -> WorkflowState:
    requested_tool = str(payload.get("requested_tool", ""))
    requested_action = str(payload.get("requested_action", ""))
    request_type = str(payload.get("request_type", "document_intake"))
    requested_by = str(payload.get("requested_by", "demo-user"))

    return WorkflowState(
        workflow_name="document_governance_workflow",
        agent_id=agent_id,
        agent_name=agent_name,
        owner_name=owner_name,
        team_name=team_name,
        agent_risk_tier=agent_risk_tier.value,
        request_type=request_type,
        request_payload=payload,
        requested_tool=requested_tool,
        requested_action=requested_action,
        requested_by=requested_by,
        request_timestamp=iso_utc_now(),
        classification_label="unclassified",
        classification_summary="",
        reasoning_summary="",
        effective_risk_tier=agent_risk_tier.value,
        policy_allowed=False,
        policy_violation_reason="",
        approval_required=False,
        approval_checkpoint_id=None,
        approval_decision=None,
        execution_status="not_started",
        execution_result={},
        structured_output={},
        current_node="intake_node",
        final_message="Workflow created.",
        logs=[],
        state_version=1,
        status=WorkflowRunStatus.PENDING.value,
        stop_requested=False,
        stop_reason=None,
    )
