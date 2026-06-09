"""Regulatory & management reporting service.

Produces the outputs the compliance unit and its regulator expect:

  * **CTR feed** - cash transactions at/above the reporting threshold.
  * **SAR/STR draft** - a structured suspicious-activity report drawn from a case.
  * **MIS dashboard** - portfolio risk distribution, alert/case KPIs.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.enums import AlertStatus
from ..core.reference_data import CTR_THRESHOLD
from ..db.models import Alert, Case, Customer, TransactionRecord


def ctr_report(db: Session) -> dict:
    rows = (
        db.execute(
            select(TransactionRecord)
            .where(TransactionRecord.is_cash.is_(True))
            .where(TransactionRecord.amount >= CTR_THRESHOLD)
            .order_by(TransactionRecord.timestamp.desc())
        )
        .scalars()
        .all()
    )
    items = [
        {
            "txn_ref": r.txn_ref,
            "timestamp": r.timestamp.isoformat(),
            "amount": r.amount,
            "currency": r.currency,
            "type": r.txn_type,
            "direction": r.direction,
        }
        for r in rows
    ]
    return {"threshold": CTR_THRESHOLD, "count": len(items), "transactions": items}


def risk_distribution(db: Session) -> dict:
    rows = db.execute(select(Customer.risk_level)).scalars().all()
    dist = Counter(r or "UNRATED" for r in rows)
    return dict(dist)


def alert_kpis(db: Session) -> dict:
    statuses = db.execute(select(Alert.status)).scalars().all()
    by_status = Counter(statuses)
    types = db.execute(select(Alert.alert_type)).scalars().all()
    by_type = Counter(types)
    closed = (
        by_status.get(AlertStatus.CLOSED_FALSE_POSITIVE.value, 0)
        + by_status.get(AlertStatus.CLOSED_TRUE_POSITIVE.value, 0)
    )
    fp = by_status.get(AlertStatus.CLOSED_FALSE_POSITIVE.value, 0)
    fp_rate = (fp / closed) if closed else None
    return {
        "total": len(statuses),
        "by_status": dict(by_status),
        "by_type": dict(by_type),
        "false_positive_rate": round(fp_rate, 3) if fp_rate is not None else None,
    }


def dashboard(db: Session) -> dict:
    """Single consolidated MIS view for the compliance unit."""
    total_customers = db.execute(
        select(func.count()).select_from(Customer)
    ).scalar_one()
    open_alerts = db.execute(
        select(func.count()).select_from(Alert)
        .where(Alert.status == AlertStatus.OPEN.value)
    ).scalar_one()
    open_cases = db.execute(
        select(func.count()).select_from(Case)
        .where(Case.status != "CLOSED_NO_ACTION")
    ).scalar_one()
    sars = db.execute(
        select(func.count()).select_from(Case)
        .where(Case.sar_reference.isnot(None))
    ).scalar_one()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "customers": total_customers,
        "risk_distribution": risk_distribution(db),
        "open_alerts": open_alerts,
        "open_cases": open_cases,
        "sars_filed": sars,
        "alert_kpis": alert_kpis(db),
    }


def sar_draft(db: Session, case_id: int) -> dict:
    """Generate a structured SAR/STR draft from a case."""
    case = db.get(Case, case_id)
    if case is None:
        raise ValueError(f"Case {case_id} not found")
    customer = db.get(Customer, case.customer_id)
    alerts = case.alerts

    grounds = [
        f"- [{a.scenario}] {a.description} (severity {a.severity}, score {a.score:.0f})"
        for a in alerts
    ]
    return {
        "report_type": "SAR/STR (draft)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_ref": case.case_ref,
        "subject": {
            "name": customer.full_name if customer else None,
            "customer_ref": customer.customer_ref if customer else None,
            "date_of_birth": customer.date_of_birth if customer else None,
            "nationality": customer.nationality if customer else None,
            "risk_level": customer.risk_level if customer else None,
        },
        "summary": case.summary or case.title,
        "grounds_for_suspicion": grounds,
        "number_of_alerts": len(alerts),
        "status": case.status,
        "sar_reference": case.sar_reference,
        "note": (
            "This is a system-generated draft. The MLRO must review, complete "
            "and validate before filing with the FIU/regulator."
        ),
    }
