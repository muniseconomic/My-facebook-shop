"""Transaction ingestion + monitoring endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db.database import get_session
from ...db.models import TransactionRecord
from ...services import monitoring_service
from ...services.case_management import customer_by_ref
from ..schemas import TransactionCreate

router = APIRouter(prefix="/transactions", tags=["Transactions / Monitoring"])


@router.post("", summary="Ingest a transaction")
def ingest(payload: TransactionCreate, db: Session = Depends(get_session)) -> dict:
    customer = customer_by_ref(db, payload.customer_ref)
    if customer is None:
        raise HTTPException(404, f"Customer {payload.customer_ref} not found")
    record = TransactionRecord(
        txn_ref=payload.txn_ref,
        customer_id=customer.id,
        timestamp=payload.timestamp.replace(tzinfo=None),
        amount=payload.amount,
        currency=payload.currency,
        direction=payload.direction,
        txn_type=payload.txn_type,
        is_cash=payload.is_cash,
        is_cross_border=payload.is_cross_border,
        counterparty_name=payload.counterparty_name,
        counterparty_country=payload.counterparty_country,
        counterparty_account=payload.counterparty_account,
        channel=payload.channel,
        narrative=payload.narrative,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": record.id, "txn_ref": record.txn_ref}


@router.post("/monitor/{customer_ref}", summary="Run monitoring for one customer")
def monitor_customer(
    customer_ref: str, persist: bool = True, db: Session = Depends(get_session)
) -> dict:
    customer = customer_by_ref(db, customer_ref)
    if customer is None:
        raise HTTPException(404, "Customer not found")
    return monitoring_service.run_monitoring(db, customer, persist=persist)


@router.post("/monitor", summary="Run monitoring across the whole portfolio")
def monitor_all(db: Session = Depends(get_session)) -> dict:
    return monitoring_service.run_monitoring_all(db)
