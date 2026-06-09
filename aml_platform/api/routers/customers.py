"""Customer / KYC endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.database import get_session
from ...db.models import Customer
from ...services import onboarding
from ...services.case_management import customer_by_ref
from ..schemas import CustomerCreate, CustomerOut

router = APIRouter(prefix="/customers", tags=["Customers / KYC"])


def _to_model(payload: CustomerCreate) -> Customer:
    return Customer(
        customer_ref=payload.customer_ref,
        full_name=payload.full_name,
        customer_type=payload.customer_type,
        date_of_birth=payload.date_of_birth,
        nationality=payload.nationality,
        residence_country=payload.residence_country,
        incorporation_country=payload.incorporation_country,
        occupation=payload.occupation,
        industry=payload.industry,
        onboarding_channel=payload.onboarding_channel,
        products=payload.products,
        countries_of_operation=payload.countries_of_operation,
        beneficial_owners=payload.beneficial_owners,
        aliases=payload.aliases,
        is_pep=payload.is_pep,
        pep_relationship=payload.pep_relationship,
        adverse_media=payload.adverse_media,
        expected_monthly_turnover=payload.expected_monthly_turnover,
    )


@router.post("/onboard", summary="Onboard a customer (persist + CRR + screening)")
def onboard(payload: CustomerCreate, db: Session = Depends(get_session)) -> dict:
    if customer_by_ref(db, payload.customer_ref):
        raise HTTPException(409, f"Customer {payload.customer_ref} already exists")
    customer = _to_model(payload)
    return onboarding.onboard_customer(db, customer)


@router.get("", response_model=list[CustomerOut], summary="List customers")
def list_customers(db: Session = Depends(get_session)) -> list[Customer]:
    return db.execute(select(Customer)).scalars().all()


@router.get("/{customer_ref}", response_model=CustomerOut, summary="Get a customer")
def get_customer(customer_ref: str, db: Session = Depends(get_session)) -> Customer:
    c = customer_by_ref(db, customer_ref)
    if c is None:
        raise HTTPException(404, "Customer not found")
    return c


@router.post("/{customer_ref}/reassess", summary="Recompute the CRR")
def reassess(customer_ref: str, db: Session = Depends(get_session)) -> dict:
    c = customer_by_ref(db, customer_ref)
    if c is None:
        raise HTTPException(404, "Customer not found")
    return onboarding.assess_customer(db, c)


@router.post("/{customer_ref}/screen", summary="Re-screen the customer")
def screen(customer_ref: str, db: Session = Depends(get_session)) -> dict:
    c = customer_by_ref(db, customer_ref)
    if c is None:
        raise HTTPException(404, "Customer not found")
    return onboarding.screen_customer(db, c)
