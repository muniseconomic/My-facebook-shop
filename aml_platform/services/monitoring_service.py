"""Monitoring service: runs transaction-monitoring + behaviour analytics for a
customer and persists the resulting detections as alerts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.behavior import BehaviourEngine, build_baseline
from ..core.transaction_monitoring import TransactionMonitoringEngine
from ..db.models import Alert, Customer, TransactionRecord
from . import case_management as cm
from .mappers import record_to_transaction


def _load_transactions(db: Session, customer: Customer) -> list:
    rows = (
        db.execute(
            select(TransactionRecord)
            .where(TransactionRecord.customer_id == customer.id)
            .order_by(TransactionRecord.timestamp)
        )
        .scalars()
        .all()
    )
    return [record_to_transaction(r, customer.customer_ref) for r in rows]


def run_monitoring(
    db: Session,
    customer: Customer,
    *,
    persist: bool = True,
    baseline_split_days: int = 30,
) -> dict:
    """Run TM scenarios and behavioural analytics for one customer.

    Returns a dict of detections/signals and (optionally) the created alerts.
    The most recent ``baseline_split_days`` of activity is treated as the
    "current period" and the remainder as the behavioural baseline.
    """
    txns = _load_transactions(db, customer)
    tm = TransactionMonitoringEngine()
    detections = tm.run(txns, expected_monthly_turnover=customer.expected_monthly_turnover)

    behaviour_signals = []
    if txns:
        cutoff = txns[-1].timestamp - timedelta(days=baseline_split_days)
        history = [t for t in txns if t.timestamp < cutoff]
        current = [t for t in txns if t.timestamp >= cutoff]
        if history and current:
            baseline = build_baseline(customer.customer_ref, history, months=12)
            engine = BehaviourEngine()
            behaviour_signals = engine.assess_self_baseline(baseline, current)

    created_alerts: list[Alert] = []
    if persist:
        for d in detections:
            created_alerts.append(cm.create_alert(
                db, customer_id=customer.id, alert_type="TM",
                scenario=d.scenario, severity=d.severity.value,
                description=d.description, score=d.score,
                details={"transaction_ids": d.transaction_ids, **d.metadata},
            ))
        for s in behaviour_signals:
            created_alerts.append(cm.create_alert(
                db, customer_id=customer.id, alert_type="BEHAVIOUR",
                scenario=s.signal, severity=s.severity.value,
                description=s.description, score=s.score,
                details={"z_score": s.z_score, **s.metadata},
            ))

    return {
        "customer_ref": customer.customer_ref,
        "transactions_evaluated": len(txns),
        "detections": [d.to_dict() for d in detections],
        "behaviour_signals": [s.to_dict() for s in behaviour_signals],
        "alerts_created": [a.id for a in created_alerts],
    }


def run_monitoring_all(db: Session) -> dict:
    """Batch run monitoring across all customers (e.g. nightly job)."""
    customers = db.execute(select(Customer)).scalars().all()
    total_alerts = 0
    per_customer = []
    for c in customers:
        result = run_monitoring(db, c, persist=True)
        total_alerts += len(result["alerts_created"])
        per_customer.append(result)
    return {
        "customers_evaluated": len(customers),
        "total_alerts_created": total_alerts,
        "results": per_customer,
    }
