"""Customer behaviour / anomaly detection.

Two complementary, explainable statistical techniques:

  * **Self-baseline deviation** - compares current-period activity against the
    customer's own historical baseline using a z-score. This catches a customer
    who suddenly starts behaving unlike their established pattern.

  * **Peer-group comparison** - compares a customer against the distribution of
    a peer group (e.g. same segment / product). This catches a customer who is
    an outlier relative to similar customers, even if internally consistent.

These are deliberately transparent (no opaque ML black box) so that alerts are
defensible to investigators and regulators. They complement, and feed, the
rule-based transaction-monitoring scenarios.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime

from .enums import Severity
from .models import CustomerBaseline, Transaction


@dataclass
class BehaviourSignal:
    signal: str
    severity: Severity
    customer_id: str
    description: str
    z_score: float | None = None
    score: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "signal": self.signal,
            "severity": self.severity.value,
            "customer_id": self.customer_id,
            "description": self.description,
            "z_score": round(self.z_score, 2) if self.z_score is not None else None,
            "score": round(self.score, 2),
            "metadata": self.metadata,
        }


def _severity_from_z(z: float) -> Severity:
    az = abs(z)
    if az >= 4:
        return Severity.CRITICAL
    if az >= 3:
        return Severity.HIGH
    if az >= 2:
        return Severity.MEDIUM
    return Severity.LOW


def build_baseline(
    customer_id: str, historical: list[Transaction], months: int
) -> CustomerBaseline:
    """Construct a behavioural baseline from a customer's historical transactions."""
    if not historical or months <= 0:
        return CustomerBaseline(customer_id=customer_id)

    by_month: dict[str, list[float]] = {}
    countries: dict[str, int] = {}
    for t in historical:
        by_month.setdefault(t.timestamp.strftime("%Y-%m"), []).append(t.amount)
        if t.counterparty_country:
            cc = t.counterparty_country.upper()
            countries[cc] = countries.get(cc, 0) + 1

    monthly_volumes = [sum(v) for v in by_month.values()]
    monthly_counts = [len(v) for v in by_month.values()]
    all_amounts = [t.amount for t in historical]

    typical = sorted(countries, key=countries.get, reverse=True)[:10]
    return CustomerBaseline(
        customer_id=customer_id,
        avg_monthly_volume=statistics.fmean(monthly_volumes) if monthly_volumes else 0.0,
        std_monthly_volume=statistics.pstdev(monthly_volumes) if len(monthly_volumes) > 1 else 0.0,
        avg_txn_amount=statistics.fmean(all_amounts) if all_amounts else 0.0,
        std_txn_amount=statistics.pstdev(all_amounts) if len(all_amounts) > 1 else 0.0,
        avg_monthly_count=statistics.fmean(monthly_counts) if monthly_counts else 0.0,
        typical_countries=typical,
        sample_months=len(by_month),
    )


class BehaviourEngine:
    """Detects behavioural anomalies for a customer."""

    def __init__(self, z_threshold: float = 2.5) -> None:
        self.z_threshold = z_threshold

    def assess_self_baseline(
        self,
        baseline: CustomerBaseline,
        current_period_txns: list[Transaction],
    ) -> list[BehaviourSignal]:
        cid = baseline.customer_id
        signals: list[BehaviourSignal] = []
        if not current_period_txns:
            return signals

        current_volume = sum(t.amount for t in current_period_txns)
        current_count = len(current_period_txns)

        # Volume deviation
        if baseline.std_monthly_volume > 0:
            z = (current_volume - baseline.avg_monthly_volume) / baseline.std_monthly_volume
            if abs(z) >= self.z_threshold:
                signals.append(BehaviourSignal(
                    signal="VOLUME_DEVIATION",
                    severity=_severity_from_z(z),
                    customer_id=cid,
                    description=(
                        f"Current-period volume {current_volume:,.0f} deviates "
                        f"{z:+.1f}σ from the customer baseline mean "
                        f"{baseline.avg_monthly_volume:,.0f}."
                    ),
                    z_score=z,
                    score=min(100.0, abs(z) * 20),
                    metadata={"current_volume": current_volume,
                              "baseline_mean": baseline.avg_monthly_volume},
                ))
        elif baseline.avg_monthly_volume > 0 and current_volume >= 3 * baseline.avg_monthly_volume:
            signals.append(BehaviourSignal(
                signal="VOLUME_DEVIATION",
                severity=Severity.MEDIUM,
                customer_id=cid,
                description=(
                    f"Current-period volume {current_volume:,.0f} is "
                    f"{current_volume / baseline.avg_monthly_volume:.1f}x the "
                    f"baseline average."
                ),
                score=55.0,
                metadata={"current_volume": current_volume},
            ))

        # Count / frequency deviation
        if baseline.avg_monthly_count > 0 and current_count >= 3 * baseline.avg_monthly_count:
            signals.append(BehaviourSignal(
                signal="FREQUENCY_DEVIATION",
                severity=Severity.MEDIUM,
                customer_id=cid,
                description=(
                    f"{current_count} transactions this period vs a baseline "
                    f"average of {baseline.avg_monthly_count:.0f}."
                ),
                score=50.0,
                metadata={"current_count": current_count,
                          "baseline_count": baseline.avg_monthly_count},
            ))

        # New / atypical counterparty geography
        new_countries = sorted({
            t.counterparty_country.upper()
            for t in current_period_txns
            if t.counterparty_country
            and t.counterparty_country.upper() not in baseline.typical_countries
        })
        if new_countries and baseline.sample_months >= 1:
            signals.append(BehaviourSignal(
                signal="NEW_GEOGRAPHY",
                severity=Severity.MEDIUM,
                customer_id=cid,
                description=(
                    "Activity with previously-unseen counterparty countries: "
                    + ", ".join(new_countries)
                ),
                score=45.0,
                metadata={"new_countries": new_countries,
                          "typical_countries": baseline.typical_countries},
            ))
        return signals

    def assess_peer_group(
        self,
        customer_id: str,
        customer_value: float,
        peer_values: list[float],
        *,
        metric: str = "monthly_volume",
    ) -> list[BehaviourSignal]:
        """Flag a customer that is a statistical outlier within its peer group."""
        peers = [v for v in peer_values if v is not None]
        if len(peers) < 5:
            return []  # peer group too small to be meaningful
        mean = statistics.fmean(peers)
        std = statistics.pstdev(peers)
        if std <= 0:
            return []
        z = (customer_value - mean) / std
        if z < self.z_threshold:
            return []
        return [BehaviourSignal(
            signal="PEER_GROUP_OUTLIER",
            severity=_severity_from_z(z),
            customer_id=customer_id,
            description=(
                f"{metric} of {customer_value:,.0f} is {z:+.1f}σ above the "
                f"peer-group mean of {mean:,.0f} (n={len(peers)})."
            ),
            z_score=z,
            score=min(100.0, abs(z) * 20),
            metadata={"metric": metric, "peer_mean": mean, "peer_count": len(peers)},
        )]
