from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ApprovalStatus
from app.schemas import (
    WorkflowResumeRequest,
    WorkflowRunDetailResponse,
    WorkflowRunRequest,
    WorkflowRunResponse,
)
from app.services.registry import get_agent
from app.services.workflow import (
    get_run_approval_checkpoint,
    get_sample_payloads,
    get_workflow_run,
    resume_workflow,
    run_workflow,
)


router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("/demo/run", response_model=WorkflowRunResponse)
def trigger_demo_workflow(
    agent_id: int, request: WorkflowRunRequest, db: Session = Depends(get_db)
) -> WorkflowRunResponse:
    agent = get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    result = run_workflow(db, agent, request.model_dump())
    db.refresh(result)
    state = result.state_payload
    return WorkflowRunResponse(
        run_id=result.id,
        workflow_name=result.workflow_name,
        agent_name=agent.name,
        status=result.status,
        current_node=result.current_node,
        state=result.status.value,
        risk_tier=state.get("effective_risk_tier", agent.risk_tier.value),
        requested_tool=result.requested_tool,
        approval_required=bool(state.get("approval_required", False)),
        message=state.get("final_message", "Workflow processed."),
    )


@router.post("/demo/runs/{run_id}/resume", response_model=WorkflowRunResponse)
def resume_demo_workflow(
    run_id: int, request: WorkflowResumeRequest, db: Session = Depends(get_db)
) -> WorkflowRunResponse:
    if request.decision not in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
        raise HTTPException(status_code=400, detail="Decision must be approved or rejected")

    run = get_workflow_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    approval = get_run_approval_checkpoint(db, run_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval checkpoint not found")

    try:
        updated_run = resume_workflow(db, run, approval, request.decision, request.decided_by)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    state = updated_run.state_payload
    agent = get_agent(db, updated_run.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    return WorkflowRunResponse(
        run_id=updated_run.id,
        workflow_name=updated_run.workflow_name,
        agent_name=agent.name,
        status=updated_run.status,
        current_node=updated_run.current_node,
        state=updated_run.status.value,
        risk_tier=state.get("effective_risk_tier", agent.risk_tier.value),
        requested_tool=updated_run.requested_tool,
        approval_required=bool(state.get("approval_required", False)),
        message=state.get("final_message", "Workflow resumed."),
    )


@router.get("/demo/runs/{run_id}", response_model=WorkflowRunDetailResponse)
def read_workflow_run(run_id: int, db: Session = Depends(get_db)) -> WorkflowRunDetailResponse:
    run = get_workflow_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return run


@router.get("/demo/sample-payloads")
def read_sample_payloads() -> dict[str, dict]:
    return get_sample_payloads()
