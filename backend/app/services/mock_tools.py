from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from sqlalchemy.orm import Session

from app.models import Agent, AgentTool, ApprovalStatus, LogLevel, Policy, RunEvent


@dataclass
class MockToolResult:
    allowed: bool
    executed: bool
    requires_approval: bool
    approval_satisfied: bool
    tool_name: str
    event_type: str
    level: LogLevel
    message: str
    response: dict[str, Any]


TOOL_COSTS_USD: dict[str, float] = {
    "send_email": 0.02,
    "create_ticket": 0.01,
    "update_vendor_record": 0.03,
}


def _build_success_payload(tool_name: str, payload: dict[str, Any], run_id: int) -> dict[str, Any]:
    if tool_name == "send_email":
        return {
            "recipient": payload.get("destination", "external-requestor@example.com"),
            "subject": payload.get("document_title", "Governance Notification"),
            "delivery_status": "queued",
        }
    if tool_name == "create_ticket":
        return {
            "ticket_id": f"TKT-{run_id:04d}",
            "queue": "platform-ops",
            "priority": "normal",
        }
    if tool_name == "update_vendor_record":
        return {
            "vendor_record_id": payload.get("record_id", "VENDOR-001"),
            "update_status": "applied",
        }
    return {"detail": "unsupported tool"}


def execute_mock_tool(
    *,
    db: Session,
    run_id: int,
    agent: Agent,
    tool: AgentTool | None,
    policy: Policy | None,
    tool_name: str,
    payload: dict[str, Any],
    risk_tier: str,
    approval_required: bool,
    approval_status: str | None,
) -> MockToolResult:
    started = perf_counter()

    if tool is None or not tool.allowed:
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        response = {
            "tool": tool_name,
            "allowed": False,
            "executed": False,
            "reason": f"Tool '{tool_name}' is not permitted for agent '{agent.name}'.",
            "execution_time_ms": elapsed_ms,
            "simulated_cost_usd": 0.0,
        }
        return MockToolResult(
            allowed=False,
            executed=False,
            requires_approval=bool(tool.requires_approval) if tool else False,
            approval_satisfied=False,
            tool_name=tool_name,
            event_type="tool_policy_violation",
            level=LogLevel.ERROR,
            message=response["reason"],
            response=response,
        )

    if policy and tool_name not in policy.allowed_tools:
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        response = {
            "tool": tool_name,
            "allowed": False,
            "executed": False,
            "reason": f"Tool '{tool_name}' is blocked by policy '{policy.name}' for risk tier '{risk_tier}'.",
            "execution_time_ms": elapsed_ms,
            "simulated_cost_usd": 0.0,
        }
        return MockToolResult(
            allowed=False,
            executed=False,
            requires_approval=policy.requires_human_approval,
            approval_satisfied=False,
            tool_name=tool_name,
            event_type="tool_policy_violation",
            level=LogLevel.ERROR,
            message=response["reason"],
            response=response,
        )

    requires_approval = bool(tool.requires_approval or (policy and policy.requires_human_approval) or approval_required)
    approval_satisfied = approval_status == ApprovalStatus.APPROVED.value
    if requires_approval and not approval_satisfied:
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        response = {
            "tool": tool_name,
            "allowed": True,
            "executed": False,
            "reason": f"Tool '{tool_name}' requires approval before execution.",
            "execution_time_ms": elapsed_ms,
            "simulated_cost_usd": 0.0,
        }
        return MockToolResult(
            allowed=True,
            executed=False,
            requires_approval=True,
            approval_satisfied=False,
            tool_name=tool_name,
            event_type="tool_approval_blocked",
            level=LogLevel.WARNING,
            message=response["reason"],
            response=response,
        )

    details = _build_success_payload(tool_name, payload, run_id)
    elapsed_ms = round((perf_counter() - started) * 1000, 2)
    response = {
        "tool": tool_name,
        "allowed": True,
        "executed": True,
        "requires_approval": requires_approval,
        "approval_satisfied": approval_satisfied,
        "execution_time_ms": elapsed_ms,
        "simulated_cost_usd": TOOL_COSTS_USD.get(tool_name, 0.01),
        "risk_tier": risk_tier,
        "details": details,
    }

    db.add(
        RunEvent(
            run_id=run_id,
            event_type="tool_call_audit",
            level=LogLevel.INFO,
            message=f"Tool '{tool_name}' executed under governance controls.",
            event_payload=response,
        )
    )
    db.commit()

    return MockToolResult(
        allowed=True,
        executed=True,
        requires_approval=requires_approval,
        approval_satisfied=approval_satisfied,
        tool_name=tool_name,
        event_type="tool_executed",
        level=LogLevel.INFO,
        message=f"Tool '{tool_name}' executed in demo mode.",
        response=response,
    )
