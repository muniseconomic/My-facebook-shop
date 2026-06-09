"""Framework-free domain dataclasses used by the core engines.

These are deliberately decoupled from the SQLAlchemy ORM so the engines can be
exercised in unit tests and batch jobs without a database. The service layer
maps ORM rows to/from these structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .enums import Channel, CustomerType, Direction, TransactionType


@dataclass
class CustomerProfile:
    """A customer/entity as seen by the risk and screening engines."""

    customer_id: str
    full_name: str
    customer_type: CustomerType = CustomerType.INDIVIDUAL
    date_of_birth: str | None = None
    nationality: str | None = None              # ISO alpha-2
    residence_country: str | None = None        # ISO alpha-2
    occupation: str | None = None
    industry: str | None = None
    products: list[str] = field(default_factory=list)
    onboarding_channel: Channel | None = None
    is_pep: bool = False
    pep_relationship: bool = False               # family / close associate of a PEP
    adverse_media: bool = False
    expected_monthly_turnover: float | None = None
    incorporation_country: str | None = None     # for legal entities
    beneficial_owners: list[str] = field(default_factory=list)
    countries_of_operation: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)

    def all_names(self) -> list[str]:
        return [self.full_name, *self.aliases]


@dataclass
class Transaction:
    """A single monetary transaction."""

    transaction_id: str
    customer_id: str
    timestamp: datetime
    amount: float                                # always positive
    currency: str = "USD"
    direction: Direction = Direction.DEBIT
    txn_type: TransactionType = TransactionType.TRANSFER
    is_cash: bool = False
    is_cross_border: bool = False
    counterparty_name: str | None = None
    counterparty_country: str | None = None      # ISO alpha-2
    counterparty_account: str | None = None
    channel: Channel | None = None
    narrative: str | None = None

    @property
    def signed_amount(self) -> float:
        return self.amount if self.direction == Direction.CREDIT else -self.amount


@dataclass
class CustomerBaseline:
    """Rolling behavioural baseline for a customer (used by behaviour analytics)."""

    customer_id: str
    avg_monthly_volume: float = 0.0      # average total $ moved per month
    std_monthly_volume: float = 0.0
    avg_txn_amount: float = 0.0
    std_txn_amount: float = 0.0
    avg_monthly_count: float = 0.0
    typical_countries: list[str] = field(default_factory=list)
    sample_months: int = 0
