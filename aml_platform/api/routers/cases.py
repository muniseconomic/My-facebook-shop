"""Case management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.database import get_session
from ...db.models import Case, CaseEvent
from ...services import case_management as cm
from ..schemas import (
    CaseEventRequest,
    CaseOut,
    CloseCaseRequest,
    EscalateRequest,
    FileSARRequest,
)

router = APIRouter(prefix="/cases", tags=["Case Management"])


@router.post("", response_model=CaseOut, summary="Escalate alerts into a case")
def create_case(req: EscalateRequest, db: Session = Depends(get_session)) -> Case:
    try:
        return cm.escalate_to_case(
            db, req.alert_ids, title=req.title, actor=req.actor,
            priority=req.priority, summary=req.summary,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("", response_model=list[CaseOut], summary="List cases")
def list_cases(db: Session = Depends(get_session)) -> list[Case]:
    return db.execute(select(Case).order_by(Case.created_at.desc())).scalars().all()


@router.get("/{case_id}", summary="Get a case with its audit trail")
def get_case(case_id: int, db: Session = Depends(get_session)) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "Case not found")
    events = db.execute(
        select(CaseEvent).where(CaseEvent.case_id == case_id).order_by(CaseEvent.created_at)
    ).scalars().all()
    return {
        "id": case.id,
        "case_ref": case.case_ref,
        "customer_id": case.customer_id,
        "title": case.title,
        "status": case.status,
        "priority": case.priority,
        "assigned_to": case.assigned_to,
        "summary": case.summary,
        "sar_reference": case.sar_reference,
        "alert_ids": [a.id for a in case.alerts],
        "audit_trail": [
            {
                "actor": e.actor,
                "action": e.action,
                "note": e.note,
                "at": e.created_at.isoformat(),
            }
            for e in events
        ],
    }


@router.post("/{case_id}/events", summary="Append an audit-trail event")
def add_event(case_id: int, req: CaseEventRequest, db: Session = Depends(get_session)) -> dict:
    try:
        event = cm.add_case_event(db, case_id, actor=req.actor, action=req.action, note=req.note)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"id": event.id, "action": event.action, "at": event.created_at.isoformat()}


@router.post("/{case_id}/file-sar", response_model=CaseOut, summary="File a SAR/STR")
def file_sar(case_id: int, req: FileSARRequest, db: Session = Depends(get_session)) -> Case:
    try:
        return cm.file_sar(
            db, case_id, actor=req.actor, sar_reference=req.sar_reference, note=req.note
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/{case_id}/close", response_model=CaseOut, summary="Close a case (no action)")
def close_case(case_id: int, req: CloseCaseRequest, db: Session = Depends(get_session)) -> Case:
    try:
        return cm.close_case(db, case_id, actor=req.actor, note=req.note)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
