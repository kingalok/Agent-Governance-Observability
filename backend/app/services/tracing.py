from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import langsmith as ls
from langsmith.run_helpers import get_current_run_tree

from app.config import Settings
from app.models import Agent


def configure_langsmith(settings: Settings) -> None:
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key

    tracing_enabled = settings.langsmith_tracing and bool(settings.langsmith_api_key)
    os.environ["LANGSMITH_TRACING"] = "true" if tracing_enabled else "false"


def build_trace_metadata(
    *,
    agent: Agent,
    run_id: int,
    approval_required: bool,
    risk_tier: str,
) -> dict[str, Any]:
    return {
        "agent_id": agent.id,
        "owner": agent.owner_name,
        "risk_tier": risk_tier,
        "approval_required": approval_required,
        "run_id": run_id,
    }


def update_current_trace(metadata: dict[str, Any] | None = None, outputs: dict[str, Any] | None = None) -> None:
    run_tree = get_current_run_tree()
    if run_tree is None:
        return

    if metadata:
        run_tree.metadata.update(metadata)
    if outputs:
        run_tree.outputs = {**(run_tree.outputs or {}), **outputs}


@ls.traceable(run_type="chain", name="governance-workflow-run")
def trace_graph_run(
    invoke: Callable[[dict[str, Any]], dict[str, Any]],
    state: dict[str, Any],
) -> dict[str, Any]:
    return invoke(state)


@ls.traceable(run_type="tool", name="mock-tool-execution")
def trace_tool_call(tool_name: str, payload: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    update_current_trace(outputs={"tool_name": tool_name, "tool_result": result})
    return result


@ls.traceable(run_type="chain", name="approval-decision")
def trace_approval_decision(decision_payload: dict[str, Any]) -> dict[str, Any]:
    update_current_trace(outputs={"approval_decision": decision_payload})
    return decision_payload


@ls.traceable(run_type="chain", name="workflow-final-output")
def trace_final_output(final_output: dict[str, Any]) -> dict[str, Any]:
    update_current_trace(outputs={"final_output": final_output})
    return final_output
