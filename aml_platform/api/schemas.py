"""Pydantic request/response schemas for the API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# Customers
# --------------------------------------------------------------------------- #
class CustomerCreate(BaseModel):
    customer_ref: str = Field(..., examples=["CUST-1001"])
    full_name: str
    customer_type: str = "INDIVIDUAL"
    date_of_birth: str | None = None
    nationality: str | None = None
    residence_country: str | None = None
    incorporation_country: str | None = None
    occupation: str | None = None
    industry: str | None = None
    onboarding_channel: str | None = None
    products: list[str] = Field(default_factory=list)
    countries_of_operation: list[str] = Field(default_factory=list)
    beneficial_owners: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    is_pep: bool = False
    pep_relationship: bool = False
    adverse_media: bool = False
    expected_monthly_turnover: float | None = None


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_ref: str
    full_name: str
    customer_type: str
    nationality: str | None
    residence_country: str | None
    is_pep: bool
    risk_score: float | None
    risk_level: str | None
    due_diligence: str | None
    next_review_date: datetime | None


# --------------------------------------------------------------------------- #
# Transactions
# --------------------------------------------------------------------------- #
class TransactionCreate(BaseModel):
    txn_ref: str
    customer_ref: str
    timestamp: datetime
    amount: float = Field(..., gt=0)
    currency: str = "USD"
    direction: str = "DEBIT"
    txn_type: str = "TRANSFER"
    is_cash: bool = False
    is_cross_border: bool = False
    counterparty_name: str | None = None
    counterparty_country: str | None = None
    counterparty_account: str | None = None
    channel: str | None = None
    narrative: str | None = None


# --------------------------------------------------------------------------- #
# Screening
# --------------------------------------------------------------------------- #
class ScreeningRequest(BaseModel):
    name: str = Field(..., examples=["Viktor Petrov"])
    date_of_birth: str | None = None


# --------------------------------------------------------------------------- #
# Alerts / cases
# --------------------------------------------------------------------------- #
class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    alert_type: str
    scenario: str
    severity: str
    score: float
    status: str
    description: str
    assigned_to: str | None
    case_id: int | None
    created_at: datetime


class AssignRequest(BaseModel):
    analyst: str


class CloseAlertRequest(BaseModel):
    true_positive: bool
    note: str
    actor: str = "analyst"


class EscalateRequest(BaseModel):
    alert_ids: list[int]
    title: str
    actor: str = "analyst"
    priority: str = "HIGH"
    summary: str | None = None


class CaseEventRequest(BaseModel):
    actor: str
    action: str
    note: str | None = None


class FileSARRequest(BaseModel):
    actor: str
    sar_reference: str
    note: str | None = None


class CloseCaseRequest(BaseModel):
    actor: str
    note: str


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_ref: str
    customer_id: int
    title: str
    status: str
    priority: str
    assigned_to: str | None
    sar_reference: str | None
    created_at: datetime
