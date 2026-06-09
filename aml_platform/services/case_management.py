"""Alert and case management service.

Implements the investigative workflow used by the compliance unit:

    detection -> Alert (OPEN)
              -> analyst triage (IN_REVIEW)
              -> close as false positive, OR escalate to a Case
    Case      -> investigation -> MLRO decision -> SAR/STR filed or no action

Every state change on a case is recorded as an immutable ``CaseEvent`` to give
a complete, defensible audit trail.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.enums import AlertStatus, CaseStatus
from ..db.models import Alert, Case, CaseEvent, Customer


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_alert(
    db: Session,
    *,
    customer_id: int,
    alert_type: str,
    scenario: str,
    severity: str,
    description: str,
    score: float = 0.0,
    details: dict | None = None,
) -> Alert:
    alert = Alert(
        customer_id=customer_id,
        alert_type=alert_type,
        scenario=scenario,
        severity=severity,
        score=score,
        description=description,
        details=details or {},
        status=AlertStatus.OPEN.value,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def assign_alert(db: Session, alert_id: int, analyst: str) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise ValueError(f"Alert {alert_id} not found")
    alert.assigned_to = analyst
    alert.status = AlertStatus.IN_REVIEW.value
    db.commit()
    db.refresh(alert)
    return alert


def close_alert(
    db: Session, alert_id: int, *, true_positive: bool, note: str, actor: str = "analyst"
) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise ValueError(f"Alert {alert_id} not found")
    alert.status = (
        AlertStatus.CLOSED_TRUE_POSITIVE.value
        if true_positive
        else AlertStatus.CLOSED_FALSE_POSITIVE.value
    )
    alert.disposition_note = note
    alert.assigned_to = alert.assigned_to or actor
    db.commit()
    db.refresh(alert)
    return alert


def _next_case_ref(db: Session) -> str:
    count = db.execute(select(Case)).scalars().all()
    return f"CASE-{_utcnow():%Y}-{len(count) + 1:05d}"


def escalate_to_case(
    db: Session,
    alert_ids: list[int],
    *,
    title: str,
    actor: str = "analyst",
    priority: str = "HIGH",
    summary: str | None = None,
) -> Case:
    """Create an investigation case from one or more alerts."""
    alerts = [db.get(Alert, aid) for aid in alert_ids]
    alerts = [a for a in alerts if a is not None]
    if not alerts:
        raise ValueError("No valid alerts provided")
    customer_id = alerts[0].customer_id

    case = Case(
        case_ref=_next_case_ref(db),
        customer_id=customer_id,
        title=title,
        status=CaseStatus.UNDER_INVESTIGATION.value,
        priority=priority,
        assigned_to=actor,
        summary=summary,
    )
    db.add(case)
    db.flush()  # obtain case.id

    for a in alerts:
        a.case_id = case.id
        a.status = AlertStatus.ESCALATED.value
    db.add(CaseEvent(
        case_id=case.id, actor=actor, action="CASE_OPENED",
        note=f"Escalated from alerts {[a.id for a in alerts]}",
    ))
    db.commit()
    db.refresh(case)
    return case


def add_case_event(
    db: Session, case_id: int, *, actor: str, action: str, note: str | None = None
) -> CaseEvent:
    if db.get(Case, case_id) is None:
        raise ValueError(f"Case {case_id} not found")
    event = CaseEvent(case_id=case_id, actor=actor, action=action, note=note)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def file_sar(
    db: Session, case_id: int, *, actor: str, sar_reference: str, note: str | None = None
) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise ValueError(f"Case {case_id} not found")
    case.status = CaseStatus.SAR_FILED.value
    case.sar_reference = sar_reference
    db.add(CaseEvent(
        case_id=case.id, actor=actor, action="SAR_FILED",
        note=note or f"SAR/STR filed with reference {sar_reference}",
    ))
    db.commit()
    db.refresh(case)
    return case


def close_case(
    db: Session, case_id: int, *, actor: str, note: str
) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise ValueError(f"Case {case_id} not found")
    case.status = CaseStatus.CLOSED_NO_ACTION.value
    db.add(CaseEvent(case_id=case.id, actor=actor, action="CASE_CLOSED", note=note))
    db.commit()
    db.refresh(case)
    return case


def customer_by_ref(db: Session, customer_ref: str) -> Customer | None:
    return db.execute(
        select(Customer).where(Customer.customer_ref == customer_ref)
    ).scalar_one_or_none()
