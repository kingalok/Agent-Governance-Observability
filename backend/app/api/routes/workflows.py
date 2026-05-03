from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ApprovalStatus
from app.schemas import (
    ApprovalActionRequest,
    ApprovalResponse,
    RuntimeLogResponse,
    WorkflowRunDetailResponse,
    WorkflowRunRequest,
    WorkflowRunResponse,
)
from app.services.registry import get_agent, get_run_events
from app.services.workflow import (
    build_run_response,
    get_run_approval_checkpoint,
    get_sample_payloads,
    get_workflow_run,
    kill_workflow_run,
    list_pending_approvals,
    list_workflow_runs,
    reject_workflow,
    resume_workflow,
    run_workflow,
)


router = APIRouter(tags=["workflow-runs"])


@router.post("/runs", response_model=WorkflowRunResponse, summary="Start a governance workflow run")
def create_run(request: WorkflowRunRequest, agent_id: int, db: Session = Depends(get_db)) -> WorkflowRunResponse:
    agent = get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    run = run_workflow(db, agent, request.model_dump())
    db.refresh(run)
    return WorkflowRunResponse(**build_run_response(run, agent))


@router.get("/runs", response_model=list[WorkflowRunResponse], summary="List workflow runs")
def read_runs(db: Session = Depends(get_db)) -> list[WorkflowRunResponse]:
    runs = list_workflow_runs(db)
    responses: list[WorkflowRunResponse] = []
    for run in runs:
        agent = get_agent(db, run.agent_id)
        if agent is None:
            continue
        responses.append(WorkflowRunResponse(**build_run_response(run, agent)))
    return responses


@router.get("/runs/{run_id}", response_model=WorkflowRunDetailResponse, summary="Get workflow run details")
def read_run(run_id: int, db: Session = Depends(get_db)) -> WorkflowRunDetailResponse:
    run = get_workflow_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    payload = WorkflowRunDetailResponse.model_validate(run)
    return payload.model_copy(update={"graph_state": run.state_payload})


@router.get("/runs/{run_id}/events", response_model=list[RuntimeLogResponse], summary="List persisted run events")
def read_run_events(run_id: int, db: Session = Depends(get_db)) -> list[RuntimeLogResponse]:
    run = get_workflow_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    return [RuntimeLogResponse.model_validate(event) for event in get_run_events(db, run_id)]


@router.get("/approvals/pending", response_model=list[ApprovalResponse], summary="List pending approvals")
def read_pending_approvals(db: Session = Depends(get_db)) -> list[ApprovalResponse]:
    return list_pending_approvals(db)


@router.post("/approvals/{run_id}/approve", response_model=WorkflowRunResponse, summary="Approve and resume a run")
def approve_run(run_id: int, request: ApprovalActionRequest, db: Session = Depends(get_db)) -> WorkflowRunResponse:
    run = get_workflow_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    approval = get_run_approval_checkpoint(db, run_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval checkpoint not found")

    try:
        updated_run = resume_workflow(db, run, approval, ApprovalStatus.APPROVED, request.reviewer_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    agent = get_agent(db, updated_run.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return WorkflowRunResponse(**build_run_response(updated_run, agent))


@router.post("/approvals/{run_id}/reject", response_model=WorkflowRunResponse, summary="Reject a run")
def reject_run(run_id: int, request: ApprovalActionRequest, db: Session = Depends(get_db)) -> WorkflowRunResponse:
    run = get_workflow_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    approval = get_run_approval_checkpoint(db, run_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval checkpoint not found")

    try:
        updated_run = reject_workflow(
            db,
            run,
            approval,
            reviewer_name=request.reviewer_name,
            rejection_reason=request.rejection_reason or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    agent = get_agent(db, updated_run.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return WorkflowRunResponse(**build_run_response(updated_run, agent))


@router.post("/runs/{run_id}/kill", response_model=WorkflowRunResponse, summary="Kill an active or paused run")
def kill_run(run_id: int, db: Session = Depends(get_db)) -> WorkflowRunResponse:
    run = get_workflow_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    try:
        updated_run = kill_workflow_run(db, run)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    agent = get_agent(db, updated_run.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return WorkflowRunResponse(**build_run_response(updated_run, agent))


@router.get("/workflows/demo/sample-payloads")
def read_sample_payloads() -> dict[str, dict]:
    return get_sample_payloads()
