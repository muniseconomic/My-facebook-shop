from datetime import datetime, timedelta

from aml_platform.core.enums import Direction, TransactionType
from aml_platform.core.models import Transaction
from aml_platform.core.transaction_monitoring import (
    TMConfig,
    TransactionMonitoringEngine,
)

BASE = datetime(2026, 5, 1, 9, 0, 0)


def _txn(tid, day, amount, **kw):
    return Transaction(
        transaction_id=tid, customer_id="C1",
        timestamp=BASE + timedelta(days=day, hours=kw.pop("hour", 0)),
        amount=amount, **kw,
    )


def _scenarios(detections):
    return {d.scenario for d in detections}


def test_structuring_detected():
    txns = [
        _txn(f"T{i}", i, 9300, direction=Direction.CREDIT,
             txn_type=TransactionType.CASH_DEPOSIT, is_cash=True)
        for i in range(4)
    ]
    dets = TransactionMonitoringEngine().run(txns)
    assert "STRUCTURING" in _scenarios(dets)


def test_large_cash_ctr():
    txns = [_txn("T1", 0, 15000, is_cash=True, direction=Direction.CREDIT,
                 txn_type=TransactionType.CASH_DEPOSIT)]
    dets = TransactionMonitoringEngine().run(txns)
    assert "LARGE_CASH_CTR" in _scenarios(dets)


def test_rapid_movement_passthrough():
    txns = [
        _txn("IN", 0, 50000, hour=0, direction=Direction.CREDIT,
             txn_type=TransactionType.WIRE_IN),
        _txn("OUT", 0, 45000, hour=10, direction=Direction.DEBIT,
             txn_type=TransactionType.WIRE_OUT),
    ]
    dets = TransactionMonitoringEngine().run(txns)
    assert "RAPID_MOVEMENT" in _scenarios(dets)


def test_high_risk_geography():
    txns = [_txn("T1", 0, 5000, direction=Direction.DEBIT,
                 counterparty_country="IR")]
    dets = TransactionMonitoringEngine().run(txns)
    geo = [d for d in dets if d.scenario == "HIGH_RISK_GEOGRAPHY"]
    assert geo and geo[0].severity.value == "CRITICAL"  # IR = call for action


def test_velocity_vs_expected_turnover():
    txns = [_txn(f"T{i}", i, 20000, direction=Direction.DEBIT) for i in range(10)]
    dets = TransactionMonitoringEngine().run(txns, expected_monthly_turnover=10000)
    assert "VELOCITY" in _scenarios(dets)


def test_clean_account_no_alerts():
    txns = [
        _txn("S", 0, 6500, direction=Direction.CREDIT, txn_type=TransactionType.WIRE_IN),
        _txn("R", 2, 1200, direction=Direction.DEBIT),
    ]
    dets = TransactionMonitoringEngine().run(txns, expected_monthly_turnover=8000)
    assert dets == []


def test_thresholds_are_configurable():
    cfg = TMConfig(ctr_threshold=5000)
    txns = [_txn("T1", 0, 6000, is_cash=True, direction=Direction.CREDIT,
                 txn_type=TransactionType.CASH_DEPOSIT)]
    dets = TransactionMonitoringEngine(cfg).run(txns)
    assert "LARGE_CASH_CTR" in _scenarios(dets)
