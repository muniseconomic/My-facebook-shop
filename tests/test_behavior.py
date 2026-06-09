from datetime import datetime, timedelta

from aml_platform.core.behavior import BehaviourEngine, build_baseline
from aml_platform.core.enums import Direction
from aml_platform.core.models import Transaction

BASE = datetime(2026, 1, 1)


def _month_txns(month, count, amount):
    start = datetime(2026, month, 1)
    return [
        Transaction(transaction_id=f"T{month}-{i}", customer_id="C1",
                    timestamp=start + timedelta(days=i), amount=amount,
                    direction=Direction.DEBIT)
        for i in range(count)
    ]


def test_build_baseline_summarises_history():
    history = _month_txns(1, 5, 1000) + _month_txns(2, 5, 1000) + _month_txns(3, 5, 1000)
    baseline = build_baseline("C1", history, months=3)
    assert baseline.sample_months == 3
    assert baseline.avg_monthly_volume == 5000
    assert baseline.avg_monthly_count == 5


def test_volume_spike_flagged():
    history = _month_txns(1, 5, 1000) + _month_txns(2, 5, 1000) + _month_txns(3, 5, 1000)
    baseline = build_baseline("C1", history, months=3)
    current = _month_txns(4, 5, 20000)  # 100k vs 5k baseline
    signals = BehaviourEngine().assess_self_baseline(baseline, current)
    assert any(s.signal == "VOLUME_DEVIATION" for s in signals)


def test_stable_customer_not_flagged():
    history = _month_txns(1, 5, 1000) + _month_txns(2, 5, 1010) + _month_txns(3, 5, 990)
    baseline = build_baseline("C1", history, months=3)
    current = _month_txns(4, 5, 1000)
    signals = BehaviourEngine().assess_self_baseline(baseline, current)
    assert not any(s.signal == "VOLUME_DEVIATION" for s in signals)


def test_peer_group_outlier():
    peers = [10000, 11000, 9500, 10500, 9800, 10200]
    signals = BehaviourEngine().assess_peer_group("C1", 80000, peers)
    assert signals and signals[0].signal == "PEER_GROUP_OUTLIER"


def test_peer_group_too_small_is_ignored():
    assert BehaviourEngine().assess_peer_group("C1", 80000, [1, 2]) == []
