"""Mapping between ORM rows and framework-free domain objects."""

from __future__ import annotations

from ..core.enums import (
    Channel,
    CustomerType,
    Direction,
    ScreeningListType,
    TransactionType,
)
from ..core.models import CustomerProfile, Transaction
from ..core.sanctions import WatchlistEntry
from ..db.models import Customer, TransactionRecord, WatchlistRecord


def _enum(enum_cls, value, default):
    if value is None:
        return default
    try:
        return enum_cls(value)
    except ValueError:
        return default


def customer_to_profile(c: Customer) -> CustomerProfile:
    return CustomerProfile(
        customer_id=c.customer_ref,
        full_name=c.full_name,
        customer_type=_enum(CustomerType, c.customer_type, CustomerType.INDIVIDUAL),
        date_of_birth=c.date_of_birth,
        nationality=c.nationality,
        residence_country=c.residence_country,
        occupation=c.occupation,
        industry=c.industry,
        products=list(c.products or []),
        onboarding_channel=_enum(Channel, c.onboarding_channel, None),
        is_pep=c.is_pep,
        pep_relationship=c.pep_relationship,
        adverse_media=c.adverse_media,
        expected_monthly_turnover=c.expected_monthly_turnover,
        incorporation_country=c.incorporation_country,
        beneficial_owners=list(c.beneficial_owners or []),
        countries_of_operation=list(c.countries_of_operation or []),
        aliases=list(c.aliases or []),
    )


def record_to_transaction(t: TransactionRecord, customer_ref: str) -> Transaction:
    return Transaction(
        transaction_id=t.txn_ref,
        customer_id=customer_ref,
        timestamp=t.timestamp,
        amount=t.amount,
        currency=t.currency,
        direction=_enum(Direction, t.direction, Direction.DEBIT),
        txn_type=_enum(TransactionType, t.txn_type, TransactionType.TRANSFER),
        is_cash=t.is_cash,
        is_cross_border=t.is_cross_border,
        counterparty_name=t.counterparty_name,
        counterparty_country=t.counterparty_country,
        counterparty_account=t.counterparty_account,
        channel=_enum(Channel, t.channel, None),
        narrative=t.narrative,
    )


def record_to_watchlist_entry(w: WatchlistRecord) -> WatchlistEntry:
    return WatchlistEntry(
        entry_id=w.entry_id,
        name=w.name,
        list_type=_enum(ScreeningListType, w.list_type, ScreeningListType.SANCTIONS),
        source=w.source,
        aliases=list(w.aliases or []),
        date_of_birth=w.date_of_birth,
        nationality=w.nationality,
        program=w.program,
        remarks=w.remarks,
    )
