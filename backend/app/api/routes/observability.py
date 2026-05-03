from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import DashboardSummaryResponse, RuntimeLogResponse, UsageSnapshotResponse
from app.services.registry import get_dashboard_summary, get_runtime_logs, get_usage_snapshots


router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/summary", response_model=DashboardSummaryResponse, summary="Get dashboard summary metrics")
def read_summary(db: Session = Depends(get_db)) -> DashboardSummaryResponse:
    return get_dashboard_summary(db)


@router.get("/logs", response_model=list[RuntimeLogResponse], summary="List recent runtime logs")
def read_logs(db: Session = Depends(get_db)) -> list[RuntimeLogResponse]:
    return get_runtime_logs(db)


@router.get("/usage", response_model=list[UsageSnapshotResponse], summary="List usage snapshots")
def read_usage(db: Session = Depends(get_db)) -> list[UsageSnapshotResponse]:
    return get_usage_snapshots(db)
