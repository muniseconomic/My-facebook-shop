"""SQLAlchemy ORM models for the AML platform."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_ref: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    customer_type: Mapped[str] = mapped_column(String(32), default="INDIVIDUAL")
    date_of_birth: Mapped[str | None] = mapped_column(String(10), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(2), nullable=True)
    residence_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    incorporation_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(128), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    onboarding_channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    products: Mapped[list] = mapped_column(JSON, default=list)
    countries_of_operation: Mapped[list] = mapped_column(JSON, default=list)
    beneficial_owners: Mapped[list] = mapped_column(JSON, default=list)
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    is_pep: Mapped[bool] = mapped_column(Boolean, default=False)
    pep_relationship: Mapped[bool] = mapped_column(Boolean, default=False)
    adverse_media: Mapped[bool] = mapped_column(Boolean, default=False)
    expected_monthly_turnover: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Latest CRR snapshot
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    due_diligence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    crr_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    next_review_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    transactions: Mapped[list["TransactionRecord"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


class TransactionRecord(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    txn_ref: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    direction: Mapped[str] = mapped_column(String(8), default="DEBIT")
    txn_type: Mapped[str] = mapped_column(String(32), default="TRANSFER")
    is_cash: Mapped[bool] = mapped_column(Boolean, default=False)
    is_cross_border: Mapped[bool] = mapped_column(Boolean, default=False)
    counterparty_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    counterparty_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    counterparty_account: Mapped[str | None] = mapped_column(String(64), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="transactions")


class WatchlistRecord(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    list_type: Mapped[str] = mapped_column(String(32), default="SANCTIONS")
    source: Mapped[str] = mapped_column(String(32), default="INTERNAL")
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    date_of_birth: Mapped[str | None] = mapped_column(String(10), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(2), nullable=True)
    program: Mapped[str | None] = mapped_column(String(128), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    alert_type: Mapped[str] = mapped_column(String(32))  # TM / SCREENING / BEHAVIOUR
    scenario: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)
    description: Mapped[str] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(128), nullable=True)
    disposition_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    customer: Mapped["Customer"] = relationship(back_populates="alerts")
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), nullable=True)
    case: Mapped["Case | None"] = relationship(back_populates="alerts")


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_ref: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)
    priority: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    assigned_to: Mapped[str | None] = mapped_column(String(128), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sar_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    alerts: Mapped[list["Alert"]] = relationship(back_populates="case")
    events: Mapped[list["CaseEvent"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class CaseEvent(Base):
    """Immutable audit-trail entry for a case (who did what, when)."""

    __tablename__ = "case_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    actor: Mapped[str] = mapped_column(String(128), default="system")
    action: Mapped[str] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    case: Mapped["Case"] = relationship(back_populates="events")
