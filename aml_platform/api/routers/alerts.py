"""Alert management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.database import get_session
from ...db.models import Alert
from ...services import case_management as cm
from ..schemas import AlertOut, AssignRequest, CloseAlertRequest

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=list[AlertOut], summary="List / filter alerts")
def list_alerts(
    status: str | None = Query(None),
    alert_type: str | None = Query(None),
    db: Session = Depends(get_session),
) -> list[Alert]:
    stmt = select(Alert).order_by(Alert.created_at.desc())
    if status:
        stmt = stmt.where(Alert.status == status)
    if alert_type:
        stmt = stmt.where(Alert.alert_type == alert_type)
    return db.execute(stmt).scalars().all()


@router.get("/{alert_id}", response_model=AlertOut, summary="Get an alert")
def get_alert(alert_id: int, db: Session = Depends(get_session)) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(404, "Alert not found")
    return alert


@router.post("/{alert_id}/assign", response_model=AlertOut, summary="Assign to analyst")
def assign(alert_id: int, req: AssignRequest, db: Session = Depends(get_session)) -> Alert:
    try:
        return cm.assign_alert(db, alert_id, req.analyst)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/{alert_id}/close", response_model=AlertOut, summary="Disposition an alert")
def close(alert_id: int, req: CloseAlertRequest, db: Session = Depends(get_session)) -> Alert:
    try:
        return cm.close_alert(
            db, alert_id, true_positive=req.true_positive, note=req.note, actor=req.actor
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
