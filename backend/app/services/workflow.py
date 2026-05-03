from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Agent,
    AgentTool,
    AgentStatus,
    ApprovalCheckpoint,
    ApprovalStatus,
    LogLevel,
    Policy,
    RiskTier,
    RuntimeLog,
    UsageSnapshot,
    WorkflowRun,
    WorkflowRunStatus,
)
from app.runtime import get_request_id
from app.sample_payloads import HIGH_RISK_SAMPLE_PAYLOAD, LOW_RISK_SAMPLE_PAYLOAD, POLICY_VIOLATION_SAMPLE_PAYLOAD
from app.services.classifier import ClassificationResult, GovernanceTaskClassifier
from app.services.mock_tools import execute_mock_tool
from app.services.tracing import (
    build_trace_metadata,
    trace_approval_decision,
    trace_final_output,
    trace_graph_run,
    trace_tool_call,
    update_current_trace,
)
from app.workflows.state import WorkflowNodeName, WorkflowState, build_initial_state, iso_utc_now

logger = logging.getLogger("app.workflow")

DEFAULT_ALLOWED_ACTIONS_BY_RISK: dict[str, set[str]] = {
    RiskTier.LOW.value: {"triage_and_route", "summarize", "classify"},
    RiskTier.MEDIUM.value: {"triage_and_route", "summarize", "classify", "create_internal_ticket"},
    RiskTier.HIGH.value: {"triage_and_route", "summarize", "classify", "finalize_external_delivery", "modify_vendor_record"},
}


def _get_agent_tool(db: Session, agent_id: int, tool_name: str) -> AgentTool | None:
    return db.scalar(
        select(AgentTool).where(AgentTool.agent_id == agent_id, AgentTool.tool_name == tool_name).limit(1)
    )


def _get_policy_for_risk(db: Session, risk_tier: str) -> Policy | None:
    return db.scalar(select(Policy).where(Policy.applies_to_risk_tier == RiskTier(risk_tier)).limit(1))


def serialize_state(state: WorkflowState) -> dict[str, Any]:
    return dict(state)


def build_run_response(run: WorkflowRun, agent: Agent) -> dict[str, Any]:
    state = run.state_payload or {}
    return {
        "run_id": run.id,
        "agent_id": run.agent_id,
        "workflow_name": run.workflow_name,
        "agent_name": agent.name,
        "status": run.status,
        "current_node": run.current_node,
        "state": run.status.value,
        "graph_state": state,
        "risk_tier": state.get("effective_risk_tier", agent.risk_tier.value),
        "requested_tool": run.requested_tool,
        "approval_required": bool(state.get("approval_required", False)),
        "message": state.get("final_message", "Workflow processed."),
    }


def _append_log(state: WorkflowState, event_type: str, message: str, level: str = LogLevel.INFO.value, payload: dict[str, Any] | None = None) -> None:
    state.setdefault("logs", []).append(
        {
            "timestamp": iso_utc_now(),
            "event_type": event_type,
            "level": level,
            "message": message,
            "payload": payload or {},
        }
    )


def _is_terminal_status(status: WorkflowRunStatus) -> bool:
    return status in {
        WorkflowRunStatus.SUCCESS,
        WorkflowRunStatus.FAILED,
        WorkflowRunStatus.POLICY_VIOLATION,
        WorkflowRunStatus.STOPPED,
    }


def _persist_run_state(
    db: Session,
    run_id: int,
    node_name: WorkflowNodeName,
    state: WorkflowState,
    *,
    log_level: LogLevel = LogLevel.INFO,
    log_message: str | None = None,
) -> None:
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise ValueError(f"Workflow run {run_id} not found")

    run.current_node = node_name
    run.status = WorkflowRunStatus(state["status"])
    run.approval_required = bool(state.get("approval_required", False))
    run.approval_status = (
        ApprovalStatus(state["approval_decision"])
        if state.get("approval_decision") in {ApprovalStatus.APPROVED.value, ApprovalStatus.REJECTED.value}
        else ApprovalStatus.PENDING
    )
    run.requested_tool = state.get("requested_tool")
    run.classification_label = state.get("classification_label")
    risk_value = state.get("effective_risk_tier")
    run.risk_tier = RiskTier(risk_value) if risk_value else None
    run.reasoning_summary = state.get("reasoning_summary")
    run.state_payload = serialize_state(state)
    run.final_output = state.get("structured_output", {})

    history = list(run.transition_history or [])
    history.append(
        {
            "node": node_name,
            "status": state["status"],
            "timestamp": iso_utc_now(),
            "message": state.get("final_message", ""),
        }
    )
    run.transition_history = history

    if _is_terminal_status(run.status):
        run.finished_at = datetime.utcnow()

    event_payload = {
        "status": state["status"],
        "requested_tool": state.get("requested_tool"),
        "risk_tier": state.get("effective_risk_tier"),
        "approval_required": state.get("approval_required", False),
        "request_id": get_request_id(),
    }
    db.add(run)
    db.add(
        RuntimeLog(
            run_id=run.id,
            event_type=node_name,
            level=log_level,
            message=log_message or state.get("final_message", ""),
            event_payload=event_payload,
        )
    )
    db.commit()
    logger.info(
        "workflow_state_persisted",
        extra={
            "run_id": run.id,
            "agent_id": run.agent_id,
            "event_type": node_name,
            "request_id": get_request_id(),
        },
    )


def _should_stop(agent: Agent) -> tuple[bool, str | None]:
    if agent.is_kill_switched or agent.status == AgentStatus.KILLED:
        return True, "Agent kill switch engaged."
    if agent.status == AgentStatus.PAUSED:
        return True, "Agent is paused by operator."
    return False, None


def _refresh_stop_state(agent: Agent, state: WorkflowState, db: Session) -> None:
    db.refresh(agent)
    should_stop, reason = _should_stop(agent)
    if should_stop:
        state["stop_requested"] = True
        state["stop_reason"] = reason
        state["status"] = WorkflowRunStatus.STOPPED.value
        state["final_message"] = reason or "Workflow stopped."


def route_from_state(state: WorkflowState) -> WorkflowNodeName:
    if state.get("stop_requested"):
        return "kill_switch_node"
    if state.get("status") == WorkflowRunStatus.AWAITING_HUMAN_APPROVAL.value:
        return "approval_gate_node"
    current_node = state.get("current_node")
    if current_node == "approval_gate_node":
        return "approval_gate_node"
    if current_node == "tool_execution_node":
        return "tool_execution_node"
    if current_node == "finalize_node":
        return "finalize_node"
    if current_node == "kill_switch_node":
        return "kill_switch_node"
    return "intake_node"


def route_after_policy_check(state: WorkflowState) -> str:
    if state.get("stop_requested"):
        return "kill"
    if not state.get("policy_allowed", False):
        return "finalize"
    if state.get("approval_required", False):
        return "approval"
    return "execute"


def route_after_approval_gate(state: WorkflowState) -> str:
    if state.get("stop_requested"):
        return "kill"
    if state.get("status") == WorkflowRunStatus.AWAITING_HUMAN_APPROVAL.value:
        return "awaiting_approval"
    if state.get("approval_decision") == ApprovalStatus.REJECTED.value:
        return "kill"
    return "execute"


def route_after_execution(state: WorkflowState) -> str:
    return "kill" if state.get("stop_requested") else "finalize"


def route_after_linear_step(state: WorkflowState) -> str:
    return "kill" if state.get("stop_requested") else "continue"


def build_poc_workflow(
    db: Session,
    agent: Agent,
    classifier: GovernanceTaskClassifier | None = None,
) -> Any:
    classifier = classifier or GovernanceTaskClassifier()

    def intake_node(state: WorkflowState) -> WorkflowState:
        _refresh_stop_state(agent, state, db)
        state["current_node"] = "intake_node"
        if state.get("stop_requested"):
            _append_log(state, "workflow_stopped", state["final_message"], LogLevel.WARNING.value)
            _persist_run_state(db, state["run_id"], "intake_node", state, log_level=LogLevel.WARNING)
            return state

        payload = state["request_payload"]
        state["agent_id"] = agent.id
        state["owner_name"] = agent.owner_name
        state["agent_risk_tier"] = agent.risk_tier.value
        state["request_type"] = str(payload.get("request_type", state.get("request_type", "document_intake")))
        state["request_timestamp"] = iso_utc_now()
        state["status"] = WorkflowRunStatus.RUNNING.value
        state["final_message"] = "Request intake completed."
        _append_log(
            state,
            "intake_completed",
            state["final_message"],
            payload={
                "agent_id": agent.id,
                "owner": agent.owner_name,
                "risk_tier": agent.risk_tier.value,
                "request_type": state["request_type"],
            },
        )
        _persist_run_state(db, state["run_id"], "intake_node", state, log_message="Workflow intake completed.")
        return state

    def classification_node(state: WorkflowState) -> WorkflowState:
        _refresh_stop_state(agent, state, db)
        state["current_node"] = "classification_node"
        if state.get("stop_requested"):
            _append_log(state, "workflow_stopped", state["final_message"], LogLevel.WARNING.value)
            _persist_run_state(db, state["run_id"], "classification_node", state, log_level=LogLevel.WARNING)
            return state

        result: ClassificationResult = classifier.classify(state["request_payload"])
        state["classification_label"] = result.label
        state["classification_summary"] = result.summary
        state["reasoning_summary"] = result.reasoning_summary
        # The stricter of agent tier vs task tier wins.
        effective_risk = max(
            [agent.risk_tier, result.risk_tier],
            key=lambda risk: [RiskTier.LOW, RiskTier.MEDIUM, RiskTier.HIGH].index(risk),
        )
        state["effective_risk_tier"] = effective_risk.value
        state["approval_required"] = effective_risk == RiskTier.HIGH
        update_current_trace(
            metadata={
                "risk_tier": effective_risk.value,
                "approval_required": state["approval_required"],
            }
        )
        state["final_message"] = "Task classified and risk-labeled."
        _append_log(
            state,
            "classification_completed",
            state["final_message"],
            payload={
                "label": result.label,
                "risk_tier": effective_risk.value,
                "reasoning_summary": result.reasoning_summary,
            },
        )
        _persist_run_state(db, state["run_id"], "classification_node", state)
        return state

    def policy_check_node(state: WorkflowState) -> WorkflowState:
        _refresh_stop_state(agent, state, db)
        state["current_node"] = "policy_check_node"
        if state.get("stop_requested"):
            _append_log(state, "workflow_stopped", state["final_message"], LogLevel.WARNING.value)
            _persist_run_state(db, state["run_id"], "policy_check_node", state, log_level=LogLevel.WARNING)
            return state

        requested_tool = state.get("requested_tool", "")
        requested_action = state.get("requested_action", "")
        agent_tool = _get_agent_tool(db, agent.id, requested_tool)
        policy = _get_policy_for_risk(db, state["effective_risk_tier"])
        allowed_for_agent = bool(agent_tool and agent_tool.allowed)
        allowed_by_policy_tool = True if policy is None else requested_tool in policy.allowed_tools
        allowed_actions = DEFAULT_ALLOWED_ACTIONS_BY_RISK.get(state["effective_risk_tier"], set())
        allowed_by_policy = requested_action in allowed_actions
        state["policy_allowed"] = allowed_for_agent and allowed_by_policy and allowed_by_policy_tool
        if agent_tool and agent_tool.requires_approval:
            state["approval_required"] = True
        if policy and policy.requires_human_approval:
            state["approval_required"] = True
        if not state["policy_allowed"]:
            reasons = []
            if not allowed_for_agent:
                reasons.append(f"Tool '{requested_tool}' is not allowed for agent '{agent.name}'.")
            if not allowed_by_policy_tool:
                reasons.append(
                    f"Tool '{requested_tool}' is blocked by policy '{policy.name if policy else 'unknown'}' for risk tier '{state['effective_risk_tier']}'."
                )
            if not allowed_by_policy:
                reasons.append(
                    f"Action '{requested_action}' is not permitted for risk tier '{state['effective_risk_tier']}'."
                )
            state["policy_violation_reason"] = " ".join(reasons)
            state["status"] = WorkflowRunStatus.POLICY_VIOLATION.value
            state["execution_status"] = "blocked"
            state["final_message"] = "Policy violation blocked the requested action."
            _append_log(
                state,
                "policy_violation",
                state["policy_violation_reason"],
                LogLevel.ERROR.value,
                payload={"requested_tool": requested_tool, "requested_action": requested_action},
            )
            _persist_run_state(
                db,
                state["run_id"],
                "policy_check_node",
                state,
                log_level=LogLevel.ERROR,
                log_message=state["policy_violation_reason"],
            )
            return state

        state["final_message"] = "Policy check passed."
        _append_log(
            state,
            "policy_check_passed",
            state["final_message"],
            payload={"requested_tool": requested_tool, "requested_action": requested_action},
        )
        _persist_run_state(db, state["run_id"], "policy_check_node", state)
        return state

    def approval_gate_node(state: WorkflowState) -> WorkflowState:
        _refresh_stop_state(agent, state, db)
        state["current_node"] = "approval_gate_node"
        if state.get("stop_requested"):
            _append_log(state, "workflow_stopped", state["final_message"], LogLevel.WARNING.value)
            _persist_run_state(db, state["run_id"], "approval_gate_node", state, log_level=LogLevel.WARNING)
            return state

        if not state.get("approval_required", False):
            state["final_message"] = "Approval not required for this request."
            _append_log(state, "approval_skipped", state["final_message"])
            _persist_run_state(db, state["run_id"], "approval_gate_node", state)
            return state

        if state.get("approval_decision") == ApprovalStatus.APPROVED.value:
            trace_approval_decision(
                {
                    "run_id": state["run_id"],
                    "decision": ApprovalStatus.APPROVED.value,
                    "reviewer": state["request_payload"].get("reviewer_name"),
                }
            )
            state["status"] = WorkflowRunStatus.RUNNING.value
            state["final_message"] = "Human approval recorded. Resuming workflow."
            _append_log(state, "approval_approved", state["final_message"])
            _persist_run_state(db, state["run_id"], "approval_gate_node", state)
            return state

        if state.get("approval_decision") == ApprovalStatus.REJECTED.value:
            trace_approval_decision(
                {
                    "run_id": state["run_id"],
                    "decision": ApprovalStatus.REJECTED.value,
                    "reviewer": state["request_payload"].get("reviewer_name"),
                    "rejection_reason": state["request_payload"].get("rejection_reason"),
                }
            )
            state["status"] = WorkflowRunStatus.STOPPED.value
            state["stop_requested"] = True
            rejection_reason = state["request_payload"].get("rejection_reason") or "Human approval rejected the request."
            state["stop_reason"] = rejection_reason
            state["final_message"] = state["stop_reason"]
            _append_log(state, "approval_rejected", state["final_message"], LogLevel.WARNING.value)
            _persist_run_state(db, state["run_id"], "approval_gate_node", state, log_level=LogLevel.WARNING)
            return state

        checkpoint = ApprovalCheckpoint(
            run_id=state["run_id"],
            workflow_name=state["workflow_name"],
            action_name=state.get("requested_action", "finalize_request"),
            reason=state["reasoning_summary"] or "High-risk request requires human approval.",
            decision=ApprovalStatus.PENDING,
            requested_by=state.get("requested_by", "system"),
        )
        db.add(checkpoint)
        db.commit()
        db.refresh(checkpoint)

        state["approval_checkpoint_id"] = checkpoint.id
        state["status"] = WorkflowRunStatus.AWAITING_HUMAN_APPROVAL.value
        state["final_message"] = "Workflow paused for human approval."
        _append_log(
            state,
            "approval_requested",
            state["final_message"],
            LogLevel.WARNING.value,
            payload={"approval_checkpoint_id": checkpoint.id},
        )
        _persist_run_state(db, state["run_id"], "approval_gate_node", state, log_level=LogLevel.WARNING)
        return state

    def tool_execution_node(state: WorkflowState) -> WorkflowState:
        _refresh_stop_state(agent, state, db)
        state["current_node"] = "tool_execution_node"
        if state.get("stop_requested"):
            _append_log(state, "workflow_stopped", state["final_message"], LogLevel.WARNING.value)
            _persist_run_state(db, state["run_id"], "tool_execution_node", state, log_level=LogLevel.WARNING)
            return state

        requested_tool = state.get("requested_tool", "")
        agent_tool = _get_agent_tool(db, agent.id, requested_tool)
        policy = _get_policy_for_risk(db, state["effective_risk_tier"])
        tool_result = execute_mock_tool(
            db=db,
            run_id=state["run_id"],
            agent=agent,
            tool=agent_tool,
            policy=policy,
            tool_name=requested_tool,
            payload=state["request_payload"],
            risk_tier=state["effective_risk_tier"],
            approval_required=bool(state.get("approval_required", False)),
            approval_status=state.get("approval_decision"),
        )

        state["execution_result"] = trace_tool_call(requested_tool, state["request_payload"], tool_result.response)
        state["final_message"] = tool_result.message
        if not tool_result.allowed or not tool_result.executed:
            state["execution_status"] = "blocked"
            state["policy_allowed"] = tool_result.allowed
            state["policy_violation_reason"] = tool_result.response.get("reason", "")
            if not tool_result.allowed:
                state["status"] = WorkflowRunStatus.POLICY_VIOLATION.value
            _append_log(
                state,
                tool_result.event_type,
                state["final_message"],
                tool_result.level.value,
                payload=tool_result.response,
            )
            _persist_run_state(
                db,
                state["run_id"],
                "tool_execution_node",
                state,
                log_level=tool_result.level,
                log_message=state["final_message"],
            )
            return state

        state["execution_status"] = "completed"
        _append_log(
            state,
            tool_result.event_type,
            state["final_message"],
            payload=state["execution_result"],
        )
        _persist_run_state(db, state["run_id"], "tool_execution_node", state)
        return state

    def kill_switch_node(state: WorkflowState) -> WorkflowState:
        state["current_node"] = "kill_switch_node"
        state["status"] = WorkflowRunStatus.STOPPED.value
        state["execution_status"] = "terminated"
        if not state.get("stop_reason"):
            state["stop_reason"] = "Workflow terminated by kill switch."
        state["final_message"] = state["stop_reason"]
        _append_log(state, "workflow_terminated", state["final_message"], LogLevel.WARNING.value)
        _persist_run_state(db, state["run_id"], "kill_switch_node", state, log_level=LogLevel.WARNING)
        return state

    def finalize_node(state: WorkflowState) -> WorkflowState:
        state["current_node"] = "finalize_node"
        if state["status"] == WorkflowRunStatus.RUNNING.value:
            state["status"] = WorkflowRunStatus.SUCCESS.value
        elif state["status"] == WorkflowRunStatus.PENDING.value:
            state["status"] = WorkflowRunStatus.FAILED.value

        state["structured_output"] = {
            "run_id": state["run_id"],
            "agent_id": state["agent_id"],
            "status": state["status"],
            "classification_label": state.get("classification_label"),
            "risk_tier": state.get("effective_risk_tier"),
            "requested_tool": state.get("requested_tool"),
            "approval_required": state.get("approval_required"),
            "approval_checkpoint_id": state.get("approval_checkpoint_id"),
            "execution_result": state.get("execution_result", {}),
            "policy_violation_reason": state.get("policy_violation_reason", ""),
            "final_message": state.get("final_message"),
        }
        trace_final_output(state["structured_output"])
        _append_log(state, "workflow_finalized", "Workflow finalized with structured output.", payload=state["structured_output"])
        log_level = LogLevel.INFO
        if state["status"] in {WorkflowRunStatus.POLICY_VIOLATION.value, WorkflowRunStatus.FAILED.value}:
            log_level = LogLevel.ERROR
        if state["status"] == WorkflowRunStatus.STOPPED.value:
            log_level = LogLevel.WARNING
        _persist_run_state(db, state["run_id"], "finalize_node", state, log_level=log_level)
        return state

    graph = StateGraph(WorkflowState)
    graph.add_node("intake_node", intake_node)
    graph.add_node("classification_node", classification_node)
    graph.add_node("policy_check_node", policy_check_node)
    graph.add_node("approval_gate_node", approval_gate_node)
    graph.add_node("tool_execution_node", tool_execution_node)
    graph.add_node("kill_switch_node", kill_switch_node)
    graph.add_node("finalize_node", finalize_node)

    graph.add_conditional_edges(
        START,
        route_from_state,
        {
            "intake_node": "intake_node",
            "approval_gate_node": "approval_gate_node",
            "tool_execution_node": "tool_execution_node",
            "kill_switch_node": "kill_switch_node",
            "finalize_node": "finalize_node",
        },
    )
    graph.add_conditional_edges(
        "intake_node",
        route_after_linear_step,
        {
            "kill": "kill_switch_node",
            "continue": "classification_node",
        },
    )
    graph.add_conditional_edges(
        "classification_node",
        route_after_linear_step,
        {
            "kill": "kill_switch_node",
            "continue": "policy_check_node",
        },
    )
    graph.add_conditional_edges(
        "policy_check_node",
        route_after_policy_check,
        {
            "kill": "kill_switch_node",
            "approval": "approval_gate_node",
            "execute": "tool_execution_node",
            "finalize": "finalize_node",
        },
    )
    graph.add_conditional_edges(
        "approval_gate_node",
        route_after_approval_gate,
        {
            "awaiting_approval": END,
            "execute": "tool_execution_node",
            "kill": "kill_switch_node",
        },
    )
    graph.add_conditional_edges(
        "tool_execution_node",
        route_after_execution,
        {
            "kill": "kill_switch_node",
            "finalize": "finalize_node",
        },
    )
    graph.add_edge("kill_switch_node", "finalize_node")
    graph.add_edge("finalize_node", END)
    return graph.compile()


def create_workflow_run(db: Session, agent: Agent, payload: dict[str, Any]) -> WorkflowRun:
    state = build_initial_state(agent.id, agent.name, agent.owner_name, agent.team_name, agent.risk_tier, payload)
    run = WorkflowRun(
        agent_id=agent.id,
        workflow_name=state["workflow_name"],
        request_type=state["request_type"],
        requested_tool=state.get("requested_tool"),
        status=WorkflowRunStatus.PENDING,
        current_node="intake_node",
        input_payload=payload,
        state_payload=serialize_state(state),
        transition_history=[],
        final_output={},
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    state["run_id"] = run.id
    run.state_payload = serialize_state(state)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def hydrate_state(run: WorkflowRun) -> WorkflowState:
    return WorkflowState(**dict(run.state_payload))


def _record_usage_snapshot(db: Session, run: WorkflowRun, state: WorkflowState) -> None:
    existing_snapshot = db.scalar(
        select(UsageSnapshot).where(UsageSnapshot.run_id == run.id, UsageSnapshot.window_label == "workflow-run").limit(1)
    )
    if existing_snapshot is not None:
        return

    risk_multiplier = {
        RiskTier.LOW.value: (900, 220, 0.07),
        RiskTier.MEDIUM.value: (1400, 300, 0.14),
        RiskTier.HIGH.value: (2200, 480, 0.31),
    }
    input_tokens, output_tokens, estimated_cost = risk_multiplier.get(
        state.get("effective_risk_tier", RiskTier.LOW.value),
        (900, 220, 0.07),
    )
    db.add(
        UsageSnapshot(
            agent_id=run.agent_id,
            run_id=run.id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost,
            window_label="workflow-run",
        )
    )
    db.commit()


def run_workflow(db: Session, agent: Agent, payload: dict[str, Any]) -> WorkflowRun:
    run = create_workflow_run(db, agent, payload)
    state = hydrate_state(run)
    workflow = build_poc_workflow(db, agent)
    result = trace_graph_run(
        workflow.invoke,
        state,
        langsmith_extra={
            "metadata": build_trace_metadata(
                agent=agent,
                run_id=run.id,
                approval_required=bool(state.get("approval_required", False)),
                risk_tier=state.get("effective_risk_tier", agent.risk_tier.value),
            )
        },
    )
    db.refresh(run)
    if result.get("status") != WorkflowRunStatus.AWAITING_HUMAN_APPROVAL.value:
        _record_usage_snapshot(db, run, result)
        db.refresh(run)
    return run


def resume_workflow(db: Session, run: WorkflowRun, approval: ApprovalCheckpoint, decision: ApprovalStatus, decided_by: str) -> WorkflowRun:
    if _is_terminal_status(run.status):
        if approval.status == decision:
            return run
        raise ValueError("Workflow run is already terminal and cannot be resumed again.")

    if run.status != WorkflowRunStatus.AWAITING_HUMAN_APPROVAL:
        raise ValueError("Only runs awaiting human approval can be resumed.")

    if approval.status == decision and approval.decided_by == decided_by:
        return run
    if approval.status in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED} and approval.status != decision:
        raise ValueError("Approval decision has already been recorded for this run.")

    approval.status = decision
    approval.decided_by = decided_by
    approval.decided_at = datetime.utcnow()
    db.add(approval)
    db.commit()
    db.refresh(approval)

    agent = db.get(Agent, run.agent_id)
    if agent is None:
        raise ValueError("Agent not found for workflow run")

    state = hydrate_state(run)
    state["approval_decision"] = decision.value
    state["approval_checkpoint_id"] = approval.id
    state["request_payload"]["reviewer_name"] = decided_by
    state["status"] = WorkflowRunStatus.RUNNING.value if decision == ApprovalStatus.APPROVED else WorkflowRunStatus.STOPPED.value
    state["current_node"] = "approval_gate_node"

    workflow = build_poc_workflow(db, agent)
    result = trace_graph_run(
        workflow.invoke,
        state,
        langsmith_extra={
            "metadata": build_trace_metadata(
                agent=agent,
                run_id=run.id,
                approval_required=bool(state.get("approval_required", False)),
                risk_tier=state.get("effective_risk_tier", agent.risk_tier.value),
            )
        },
    )
    db.refresh(run)
    if result.get("status") != WorkflowRunStatus.AWAITING_HUMAN_APPROVAL.value:
        _record_usage_snapshot(db, run, result)
        db.refresh(run)
    return run


def reject_workflow(
    db: Session,
    run: WorkflowRun,
    approval: ApprovalCheckpoint,
    reviewer_name: str,
    rejection_reason: str,
) -> WorkflowRun:
    if not rejection_reason.strip():
        raise ValueError("Rejection reason is required")
    if _is_terminal_status(run.status):
        if approval.status == ApprovalStatus.REJECTED:
            return run
        raise ValueError("Workflow run is already terminal and cannot be rejected again.")
    if run.status != WorkflowRunStatus.AWAITING_HUMAN_APPROVAL:
        raise ValueError("Only runs awaiting human approval can be rejected.")
    if approval.status == ApprovalStatus.REJECTED and approval.decided_by == reviewer_name and approval.rejection_reason == rejection_reason:
        return run
    if approval.status == ApprovalStatus.APPROVED:
        raise ValueError("Approval has already been granted for this run.")

    approval.status = ApprovalStatus.REJECTED
    approval.decided_by = reviewer_name
    approval.decided_at = datetime.utcnow()
    approval.rejection_reason = rejection_reason
    db.add(approval)
    db.commit()
    db.refresh(approval)

    agent = db.get(Agent, run.agent_id)
    if agent is None:
        raise ValueError("Agent not found for workflow run")

    state = hydrate_state(run)
    state["approval_decision"] = ApprovalStatus.REJECTED.value
    state["approval_checkpoint_id"] = approval.id
    state["request_payload"]["rejection_reason"] = rejection_reason
    state["request_payload"]["reviewer_name"] = reviewer_name
    state["current_node"] = "approval_gate_node"
    state["status"] = WorkflowRunStatus.STOPPED.value

    workflow = build_poc_workflow(db, agent)
    result = trace_graph_run(
        workflow.invoke,
        state,
        langsmith_extra={
            "metadata": build_trace_metadata(
                agent=agent,
                run_id=run.id,
                approval_required=bool(state.get("approval_required", False)),
                risk_tier=state.get("effective_risk_tier", agent.risk_tier.value),
            )
        },
    )
    db.refresh(run)
    if result.get("status") != WorkflowRunStatus.AWAITING_HUMAN_APPROVAL.value:
        _record_usage_snapshot(db, run, result)
        db.refresh(run)
    return run


def kill_workflow_run(db: Session, run: WorkflowRun, stop_reason: str = "Run killed by reviewer.") -> WorkflowRun:
    if _is_terminal_status(run.status):
        return run

    agent = db.get(Agent, run.agent_id)
    if agent is None:
        raise ValueError("Agent not found for workflow run")

    state = hydrate_state(run)
    state["stop_requested"] = True
    state["stop_reason"] = stop_reason
    state["status"] = WorkflowRunStatus.STOPPED.value

    workflow = build_poc_workflow(db, agent)
    result = trace_graph_run(
        workflow.invoke,
        state,
        langsmith_extra={
            "metadata": build_trace_metadata(
                agent=agent,
                run_id=run.id,
                approval_required=bool(state.get("approval_required", False)),
                risk_tier=state.get("effective_risk_tier", agent.risk_tier.value),
            )
        },
    )
    db.refresh(run)
    if result.get("status") != WorkflowRunStatus.AWAITING_HUMAN_APPROVAL.value:
        _record_usage_snapshot(db, run, result)
        db.refresh(run)
    return run


def get_workflow_run(db: Session, run_id: int) -> WorkflowRun | None:
    return db.get(WorkflowRun, run_id)


def list_workflow_runs(db: Session) -> list[WorkflowRun]:
    return db.query(WorkflowRun).order_by(WorkflowRun.started_at.desc()).all()


def get_run_approval_checkpoint(db: Session, run_id: int) -> ApprovalCheckpoint | None:
    return (
        db.query(ApprovalCheckpoint)
        .filter(ApprovalCheckpoint.run_id == run_id)
        .order_by(ApprovalCheckpoint.created_at.desc())
        .first()
    )


def list_pending_approvals(db: Session) -> list[ApprovalCheckpoint]:
    return (
        db.query(ApprovalCheckpoint)
        .filter(ApprovalCheckpoint.decision == ApprovalStatus.PENDING)
        .order_by(ApprovalCheckpoint.created_at.desc())
        .all()
    )


def get_sample_payloads() -> dict[str, dict[str, Any]]:
    return {
        "low_risk": LOW_RISK_SAMPLE_PAYLOAD,
        "high_risk": HIGH_RISK_SAMPLE_PAYLOAD,
        "policy_violation": POLICY_VIOLATION_SAMPLE_PAYLOAD,
    }
