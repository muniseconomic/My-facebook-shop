"""Seed the database with reference data and a realistic demo dataset.

Run with:  python -m aml_platform.db.seed
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select

from ..core.enums import Direction, TransactionType
from .database import SessionLocal, init_db
from .models import (
    Alert,
    Case,
    CaseEvent,
    Customer,
    TransactionRecord,
    WatchlistRecord,
)

WATCHLIST_FILE = Path(__file__).resolve().parent.parent / "data" / "watchlist_sample.json"


def load_watchlist(db) -> int:
    data = json.loads(WATCHLIST_FILE.read_text())
    db.execute(delete(WatchlistRecord))
    for e in data:
        db.add(WatchlistRecord(
            entry_id=e["entry_id"], name=e["name"], list_type=e["list_type"],
            source=e.get("source", "INTERNAL"), aliases=e.get("aliases", []),
            date_of_birth=e.get("date_of_birth"), nationality=e.get("nationality"),
            program=e.get("program"), remarks=e.get("remarks"),
        ))
    db.commit()
    return len(data)


def _clear_transactional(db) -> None:
    db.execute(delete(CaseEvent))
    db.execute(delete(Alert))
    db.execute(delete(Case))
    db.execute(delete(TransactionRecord))
    db.execute(delete(Customer))
    db.commit()


def seed_customers(db) -> list[Customer]:
    customers = [
        Customer(
            customer_ref="CUST-1001", full_name="Alice Johnson",
            customer_type="INDIVIDUAL", date_of_birth="1985-03-14",
            nationality="GB", residence_country="GB", occupation="salaried_employee",
            onboarding_channel="BRANCH", products=["current_account", "savings_account"],
            expected_monthly_turnover=8000,
        ),
        Customer(
            customer_ref="CUST-1002", full_name="Global Horizon Trading LLC",
            customer_type="CORPORATE", incorporation_country="AE",
            residence_country="AE", industry="import_export",
            onboarding_channel="INTRODUCED",
            products=["trade_finance", "current_account"],
            countries_of_operation=["AE", "IR", "CN"],
            beneficial_owners=["Hassan Al Maktoum"], expected_monthly_turnover=250000,
        ),
        Customer(
            customer_ref="CUST-1003", full_name="Maria Fernanda Oliveira Santos",
            customer_type="INDIVIDUAL", date_of_birth="1972-06-18",
            nationality="BR", residence_country="BR", occupation="politician",
            onboarding_channel="BRANCH", is_pep=True,
            products=["private_banking", "current_account"],
            expected_monthly_turnover=40000,
        ),
        Customer(
            customer_ref="CUST-1004", full_name="Viktor Petrov",
            customer_type="INDIVIDUAL", date_of_birth="1968-04-12",
            nationality="RU", residence_country="RU", occupation="crypto_exchange",
            onboarding_channel="ONLINE", products=["crypto_custody"],
            expected_monthly_turnover=60000,
        ),
        Customer(
            customer_ref="CUST-1005", full_name="Sunrise Cash & Carry",
            customer_type="SOLE_PROPRIETOR", residence_country="US",
            incorporation_country="US", industry="cash_intensive_retail",
            onboarding_channel="BRANCH", products=["current_account"],
            expected_monthly_turnover=30000,
        ),
    ]
    db.add_all(customers)
    db.commit()
    for c in customers:
        db.refresh(c)
    return customers


def seed_transactions(db, customers: dict[str, Customer]) -> None:
    base = datetime(2026, 5, 1, 9, 0, 0)
    txns: list[TransactionRecord] = []

    def add(ref, cust, day, amount, **kw):
        txns.append(TransactionRecord(
            txn_ref=ref, customer_id=customers[cust].id,
            timestamp=base + timedelta(days=day, hours=kw.pop("hour", 0)),
            amount=amount, currency=kw.pop("currency", "USD"),
            direction=kw.pop("direction", Direction.DEBIT.value),
            txn_type=kw.pop("txn_type", TransactionType.TRANSFER.value),
            is_cash=kw.pop("is_cash", False),
            is_cross_border=kw.pop("is_cross_border", False),
            counterparty_name=kw.pop("counterparty_name", None),
            counterparty_country=kw.pop("counterparty_country", None),
            narrative=kw.pop("narrative", None),
        ))

    # CUST-1001: benign salary + spending
    add("TX-0001", "CUST-1001", 0, 6500, direction="CREDIT",
        txn_type="WIRE_IN", narrative="Salary")
    add("TX-0002", "CUST-1001", 2, 1200, narrative="Rent")
    add("TX-0003", "CUST-1001", 10, 300, narrative="Groceries")

    # CUST-1005: classic structuring - several sub-$10k cash deposits in a week
    for i in range(4):
        add(f"TX-010{i}", "CUST-1005", i, 9200 + i * 50, hour=i,
            direction="CREDIT", txn_type="CASH_DEPOSIT", is_cash=True,
            narrative="Cash deposit")

    # CUST-1002: high-risk geography + large cash + velocity
    add("TX-0201", "CUST-1002", 1, 480000, direction="CREDIT", txn_type="WIRE_IN",
        is_cross_border=True, counterparty_country="IR",
        counterparty_name="Persian Gulf Imports", narrative="Trade settlement")
    add("TX-0202", "CUST-1002", 2, 15000, direction="CREDIT",
        txn_type="CASH_DEPOSIT", is_cash=True, narrative="Cash takings")
    add("TX-0203", "CUST-1002", 3, 460000, direction="DEBIT", txn_type="WIRE_OUT",
        is_cross_border=True, counterparty_country="CN",
        counterparty_name="Shenzhen Electronics", narrative="Supplier payment")

    # CUST-1004: rapid movement / pass-through
    add("TX-0301", "CUST-1004", 0, 50000, hour=0, direction="CREDIT",
        txn_type="WIRE_IN", is_cross_border=True, counterparty_country="RU")
    add("TX-0302", "CUST-1004", 0, 24000, hour=6, direction="DEBIT",
        txn_type="WIRE_OUT", is_cross_border=True, counterparty_country="AE")
    add("TX-0303", "CUST-1004", 0, 23000, hour=12, direction="DEBIT",
        txn_type="WIRE_OUT", is_cross_border=True, counterparty_country="KP",
        counterparty_name="Unknown")

    db.add_all(txns)
    db.commit()


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        _clear_transactional(db)
        n = load_watchlist(db)
        print(f"Loaded {n} watchlist entries.")

        customers = seed_customers(db)
        by_ref = {c.customer_ref: c for c in customers}
        seed_transactions(db, by_ref)
        print(f"Seeded {len(customers)} customers and demo transactions.")

        # Run CRR + screening + monitoring so the demo DB is fully populated.
        from ..services import monitoring_service, onboarding

        for c in customers:
            onboarding.assess_customer(db, c)
            onboarding.screen_customer(db, c)
        result = monitoring_service.run_monitoring_all(db)

        print(f"CRR + screening complete. Monitoring created "
              f"{result['total_alerts_created']} alerts across "
              f"{result['customers_evaluated']} customers.")
        alerts = db.execute(select(Alert)).scalars().all()
        print(f"Total alerts in system: {len(alerts)}")
        print("Seed complete. Start the API with: "
              "uvicorn aml_platform.api.main:app --reload")
    finally:
        db.close()


if __name__ == "__main__":
    main()
