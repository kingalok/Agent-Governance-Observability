from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ApprovalCheckpoint, ApprovalStatus
from app.schemas import AgentControlRequest, AgentResponse, ApprovalDecisionRequest, ApprovalResponse
from app.services.registry import get_agent, list_agents, update_agent_status


router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentResponse], summary="List registered agents")
def read_agents(db: Session = Depends(get_db)) -> list[AgentResponse]:
    return list_agents(db)


@router.post("/{agent_id}/control", response_model=AgentResponse, summary="Pause, resume, or kill an agent")
def control_agent(agent_id: int, request: AgentControlRequest, db: Session = Depends(get_db)) -> AgentResponse:
    agent = get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        return update_agent_status(db, agent, request.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/approvals", response_model=list[ApprovalResponse])
def list_approvals(db: Session = Depends(get_db)) -> list[ApprovalResponse]:
    return db.query(ApprovalCheckpoint).order_by(ApprovalCheckpoint.created_at.desc()).all()


@router.post("/approvals/{approval_id}", response_model=ApprovalResponse)
def decide_approval(
    approval_id: int, request: ApprovalDecisionRequest, db: Session = Depends(get_db)
) -> ApprovalResponse:
    approval = db.get(ApprovalCheckpoint, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval checkpoint not found")

    if request.decision not in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
        raise HTTPException(status_code=400, detail="Decision must be approved or rejected")

    approval.status = request.decision
    approval.decided_by = request.decided_by
    approval.decided_at = datetime.utcnow()
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return approval
