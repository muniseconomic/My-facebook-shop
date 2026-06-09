"""Transaction Monitoring (TM) engine.

A configurable, scenario-based detection engine. Each scenario inspects a
customer's transactions (typically a rolling window) and yields zero or more
``Detection`` objects. Scenarios are intentionally small, independent and
parameterised so the MLRO can tune thresholds and switch scenarios on/off
without code changes.

Implemented scenarios (mapped to common typologies):

  * STRUCTURING            - multiple sub-threshold cash txns aggregating high
  * LARGE_CASH / CTR       - single cash txn over the reporting threshold
  * RAPID_MOVEMENT         - funds in then largely out within a short window
  * HIGH_RISK_GEOGRAPHY    - transfers to/from high-risk jurisdictions
  * VELOCITY               - sudden spike in count/value vs expected turnover
  * ROUND_AMOUNTS          - repeated suspiciously round-number transactions
  * DORMANT_REACTIVATION   - large activity after a long dormant period
  * RAPID_PASS_THROUGH     - high credit and debit turnover with low retained balance
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import reference_data as ref
from .enums import Direction, Severity, TransactionType
from .models import Transaction


@dataclass
class Detection:
    scenario: str
    severity: Severity
    customer_id: str
    description: str
    transaction_ids: list[str] = field(default_factory=list)
    score: float = 0.0  # 0-100 indicative risk score
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "severity": self.severity.value,
            "customer_id": self.customer_id,
            "description": self.description,
            "transaction_ids": self.transaction_ids,
            "score": round(self.score, 2),
            "metadata": self.metadata,
        }


@dataclass
class TMConfig:
    ctr_threshold: float = ref.CTR_THRESHOLD
    structuring_window_days: int = 7
    structuring_min_count: int = 3
    structuring_lower_band: float = 0.50   # only count txns >= 50% of threshold
    rapid_movement_window_hours: int = 72
    rapid_movement_passthrough_ratio: float = 0.80  # >=80% of inflow goes out
    velocity_multiplier: float = 3.0       # activity > 3x expected turnover
    round_amount_min_count: int = 3
    round_amount_modulo: float = 1000.0
    dormant_days: int = 180
    dormant_reactivation_amount: float = 5000.0
    passthrough_window_days: int = 30
    passthrough_min_turnover: float = 50000.0
    passthrough_retention_ratio: float = 0.10  # retains <10% of what flowed in


class TransactionMonitoringEngine:
    """Runs the configured detection scenarios over a set of transactions."""

    def __init__(self, config: TMConfig | None = None) -> None:
        self.config = config or TMConfig()

    def run(
        self,
        transactions: list[Transaction],
        *,
        expected_monthly_turnover: float | None = None,
    ) -> list[Detection]:
        """Run all scenarios for a single customer's transactions."""
        if not transactions:
            return []
        customer_id = transactions[0].customer_id
        txns = sorted(transactions, key=lambda t: t.timestamp)
        detections: list[Detection] = []
        detections += self._structuring(customer_id, txns)
        detections += self._large_cash(customer_id, txns)
        detections += self._rapid_movement(customer_id, txns)
        detections += self._high_risk_geography(customer_id, txns)
        detections += self._velocity(customer_id, txns, expected_monthly_turnover)
        detections += self._round_amounts(customer_id, txns)
        detections += self._dormant_reactivation(customer_id, txns)
        detections += self._pass_through(customer_id, txns)
        return detections

    # --------------------------------------------------------------------- #
    # Scenarios
    # --------------------------------------------------------------------- #
    def _structuring(self, cid: str, txns: list[Transaction]) -> list[Detection]:
        """Multiple cash transactions just under the CTR threshold that
        aggregate above it within a short rolling window (smurfing)."""
        cfg = self.config
        low = cfg.ctr_threshold * cfg.structuring_lower_band
        cash = [
            t for t in txns
            if t.is_cash and low <= t.amount < cfg.ctr_threshold
        ]
        results: list[Detection] = []
        window = timedelta(days=cfg.structuring_window_days)
        n = len(cash)
        for i in range(n):
            group = [cash[i]]
            for j in range(i + 1, n):
                if cash[j].timestamp - cash[i].timestamp <= window:
                    group.append(cash[j])
                else:
                    break
            total = sum(t.amount for t in group)
            if len(group) >= cfg.structuring_min_count and total >= cfg.ctr_threshold:
                results.append(Detection(
                    scenario="STRUCTURING",
                    severity=Severity.HIGH,
                    customer_id=cid,
                    description=(
                        f"{len(group)} cash transactions totalling "
                        f"{total:,.0f} within {cfg.structuring_window_days} days, "
                        f"each below the {cfg.ctr_threshold:,.0f} reporting threshold."
                    ),
                    transaction_ids=[t.transaction_id for t in group],
                    score=min(100.0, 60 + len(group) * 5),
                    metadata={"aggregate_amount": total, "count": len(group)},
                ))
                break  # report the first qualifying cluster only
        return results

    def _large_cash(self, cid: str, txns: list[Transaction]) -> list[Detection]:
        cfg = self.config
        results = []
        for t in txns:
            if t.is_cash and t.amount >= cfg.ctr_threshold:
                results.append(Detection(
                    scenario="LARGE_CASH_CTR",
                    severity=Severity.MEDIUM,
                    customer_id=cid,
                    description=(
                        f"Cash {t.txn_type.value} of {t.amount:,.0f} {t.currency} "
                        f"at/above CTR threshold {cfg.ctr_threshold:,.0f} - "
                        f"currency transaction report required."
                    ),
                    transaction_ids=[t.transaction_id],
                    score=55.0,
                    metadata={"amount": t.amount, "ctr_required": True},
                ))
        return results

    def _rapid_movement(self, cid: str, txns: list[Transaction]) -> list[Detection]:
        """Significant inflow rapidly followed by outflow of most of it."""
        cfg = self.config
        window = timedelta(hours=cfg.rapid_movement_window_hours)
        credits = [t for t in txns if t.direction == Direction.CREDIT]
        results = []
        for c in credits:
            out = sum(
                t.amount for t in txns
                if t.direction == Direction.DEBIT
                and 0 <= (t.timestamp - c.timestamp).total_seconds() <= window.total_seconds()
            )
            if c.amount > 0 and out >= c.amount * cfg.rapid_movement_passthrough_ratio:
                results.append(Detection(
                    scenario="RAPID_MOVEMENT",
                    severity=Severity.HIGH,
                    customer_id=cid,
                    description=(
                        f"Inflow of {c.amount:,.0f} followed by outflow of "
                        f"{out:,.0f} ({out / c.amount:.0%}) within "
                        f"{cfg.rapid_movement_window_hours}h - possible layering."
                    ),
                    transaction_ids=[c.transaction_id],
                    score=70.0,
                    metadata={"inflow": c.amount, "outflow_within_window": out},
                ))
        return results

    def _high_risk_geography(self, cid: str, txns: list[Transaction]) -> list[Detection]:
        from .enums import RiskLevel
        results = []
        for t in txns:
            if not t.counterparty_country:
                continue
            band, why = ref.country_risk(t.counterparty_country)
            if band.rank >= RiskLevel.HIGH.rank:
                sev = Severity.CRITICAL if band == RiskLevel.CRITICAL else Severity.HIGH
                results.append(Detection(
                    scenario="HIGH_RISK_GEOGRAPHY",
                    severity=sev,
                    customer_id=cid,
                    description=(
                        f"{t.direction.value} of {t.amount:,.0f} {t.currency} "
                        f"involving {t.counterparty_country.upper()} - {why}."
                    ),
                    transaction_ids=[t.transaction_id],
                    score=85.0 if band == RiskLevel.CRITICAL else 70.0,
                    metadata={"country": t.counterparty_country.upper(), "reason": why},
                ))
        return results

    def _velocity(
        self, cid: str, txns: list[Transaction],
        expected_monthly_turnover: float | None,
    ) -> list[Detection]:
        """Total monthly throughput far exceeding the customer's declared,
        expected turnover."""
        if not expected_monthly_turnover or expected_monthly_turnover <= 0:
            return []
        cfg = self.config
        by_month: dict[str, float] = defaultdict(float)
        ids_by_month: dict[str, list[str]] = defaultdict(list)
        for t in txns:
            key = t.timestamp.strftime("%Y-%m")
            by_month[key] += t.amount
            ids_by_month[key].append(t.transaction_id)
        results = []
        for month, total in by_month.items():
            if total >= expected_monthly_turnover * cfg.velocity_multiplier:
                results.append(Detection(
                    scenario="VELOCITY",
                    severity=Severity.HIGH,
                    customer_id=cid,
                    description=(
                        f"{month}: throughput {total:,.0f} is "
                        f"{total / expected_monthly_turnover:.1f}x the expected "
                        f"monthly turnover of {expected_monthly_turnover:,.0f}."
                    ),
                    transaction_ids=ids_by_month[month],
                    score=min(100.0, 50 + (total / expected_monthly_turnover) * 5),
                    metadata={"month": month, "throughput": total,
                              "expected": expected_monthly_turnover},
                ))
        return results

    def _round_amounts(self, cid: str, txns: list[Transaction]) -> list[Detection]:
        cfg = self.config
        round_txns = [
            t for t in txns
            if t.amount >= cfg.round_amount_modulo
            and t.amount % cfg.round_amount_modulo == 0
        ]
        if len(round_txns) >= cfg.round_amount_min_count:
            return [Detection(
                scenario="ROUND_AMOUNTS",
                severity=Severity.LOW,
                customer_id=cid,
                description=(
                    f"{len(round_txns)} round-number transactions (multiples of "
                    f"{cfg.round_amount_modulo:,.0f}) - atypical of genuine "
                    f"commercial activity."
                ),
                transaction_ids=[t.transaction_id for t in round_txns],
                score=35.0,
                metadata={"count": len(round_txns)},
            )]
        return []

    def _dormant_reactivation(self, cid: str, txns: list[Transaction]) -> list[Detection]:
        cfg = self.config
        results = []
        for i in range(1, len(txns)):
            gap = txns[i].timestamp - txns[i - 1].timestamp
            if (gap >= timedelta(days=cfg.dormant_days)
                    and txns[i].amount >= cfg.dormant_reactivation_amount):
                results.append(Detection(
                    scenario="DORMANT_REACTIVATION",
                    severity=Severity.MEDIUM,
                    customer_id=cid,
                    description=(
                        f"Account dormant for {gap.days} days then a transaction "
                        f"of {txns[i].amount:,.0f} {txns[i].currency}."
                    ),
                    transaction_ids=[txns[i].transaction_id],
                    score=50.0,
                    metadata={"dormant_days": gap.days, "amount": txns[i].amount},
                ))
        return results

    def _pass_through(self, cid: str, txns: list[Transaction]) -> list[Detection]:
        """High two-way turnover within a window while retaining little of it -
        characteristic of a funnel / mule / pass-through account."""
        cfg = self.config
        if not txns:
            return []
        end = txns[-1].timestamp
        start = end - timedelta(days=cfg.passthrough_window_days)
        window = [t for t in txns if t.timestamp >= start]
        inflow = sum(t.amount for t in window if t.direction == Direction.CREDIT)
        outflow = sum(t.amount for t in window if t.direction == Direction.DEBIT)
        turnover = inflow + outflow
        retained = abs(inflow - outflow)
        if (turnover >= cfg.passthrough_min_turnover and inflow > 0
                and retained <= inflow * cfg.passthrough_retention_ratio):
            return [Detection(
                scenario="RAPID_PASS_THROUGH",
                severity=Severity.HIGH,
                customer_id=cid,
                description=(
                    f"Over {cfg.passthrough_window_days} days: inflow "
                    f"{inflow:,.0f}, outflow {outflow:,.0f}, retaining only "
                    f"{retained:,.0f} - possible pass-through / mule account."
                ),
                transaction_ids=[t.transaction_id for t in window],
                score=72.0,
                metadata={"inflow": inflow, "outflow": outflow, "retained": retained},
            )]
        return []
