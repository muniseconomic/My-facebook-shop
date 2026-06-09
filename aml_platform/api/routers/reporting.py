"""Regulatory & management reporting endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db.database import get_session
from ...services import reporting

router = APIRouter(prefix="/reporting", tags=["Reporting / MIS"])


@router.get("/dashboard", summary="Consolidated compliance MIS dashboard")
def dashboard(db: Session = Depends(get_session)) -> dict:
    return reporting.dashboard(db)


@router.get("/ctr", summary="Currency Transaction Report feed")
def ctr(db: Session = Depends(get_session)) -> dict:
    return reporting.ctr_report(db)


@router.get("/risk-distribution", summary="Portfolio risk distribution")
def risk_distribution(db: Session = Depends(get_session)) -> dict:
    return reporting.risk_distribution(db)


@router.get("/sar-draft/{case_id}", summary="Generate a SAR/STR draft for a case")
def sar_draft(case_id: int, db: Session = Depends(get_session)) -> dict:
    try:
        return reporting.sar_draft(db, case_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
