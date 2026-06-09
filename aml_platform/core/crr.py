"""Customer Risk Rating (CRR) engine.

Implements a transparent, weighted, multi-factor risk-based assessment in line
with FATF Recommendation 1 (risk-based approach). Each risk *factor* produces a
0-100 sub-score; factors are combined using configurable weights into an overall
0-100 score that maps to a Low / Medium / High / Critical band.

The methodology is fully explainable: every assessment returns the contributing
factors, their scores, weights and rationale, which is what an examiner or an
internal model-validation function will ask for.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import reference_data as ref
from .enums import CustomerType, DueDiligenceLevel, RiskLevel
from .models import CustomerProfile

# Score assigned to each qualitative risk band.
_BAND_SCORE: dict[RiskLevel, float] = {
    RiskLevel.LOW: 15.0,
    RiskLevel.MEDIUM: 45.0,
    RiskLevel.HIGH: 75.0,
    RiskLevel.CRITICAL: 100.0,
}

# Inherent risk by customer/entity type.
_CUSTOMER_TYPE_RISK: dict[CustomerType, RiskLevel] = {
    CustomerType.INDIVIDUAL: RiskLevel.LOW,
    CustomerType.SOLE_PROPRIETOR: RiskLevel.MEDIUM,
    CustomerType.CORPORATE: RiskLevel.MEDIUM,
    CustomerType.GOVERNMENT: RiskLevel.LOW,
    CustomerType.FINANCIAL_INSTITUTION: RiskLevel.MEDIUM,
    CustomerType.TRUST: RiskLevel.HIGH,
    CustomerType.NPO: RiskLevel.HIGH,
}


@dataclass
class FactorScore:
    name: str
    score: float           # 0-100
    weight: float          # contribution weight (0-1)
    band: RiskLevel
    rationale: str

    @property
    def weighted(self) -> float:
        return self.score * self.weight


@dataclass
class CRRResult:
    customer_id: str
    overall_score: float
    risk_level: RiskLevel
    due_diligence: DueDiligenceLevel
    requires_edd: bool
    factors: list[FactorScore] = field(default_factory=list)
    overrides: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "customer_id": self.customer_id,
            "overall_score": round(self.overall_score, 2),
            "risk_level": self.risk_level.value,
            "due_diligence": self.due_diligence.value,
            "requires_edd": self.requires_edd,
            "factors": [
                {
                    "name": f.name,
                    "score": round(f.score, 2),
                    "weight": f.weight,
                    "band": f.band.value,
                    "weighted_score": round(f.weighted, 2),
                    "rationale": f.rationale,
                }
                for f in self.factors
            ],
            "overrides": self.overrides,
        }


# Default factor weights (must sum to ~1.0). Tunable per institution.
DEFAULT_WEIGHTS: dict[str, float] = {
    "customer_type": 0.15,
    "geography": 0.25,
    "occupation": 0.15,
    "product": 0.15,
    "channel": 0.10,
    "pep": 0.12,
    "adverse_media": 0.08,
}


class CRREngine:
    """Computes a customer's risk rating from its profile."""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self.weights = weights or dict(DEFAULT_WEIGHTS)

    # -- individual factor assessments ------------------------------------- #
    def _customer_type_factor(self, c: CustomerProfile) -> FactorScore:
        band = _CUSTOMER_TYPE_RISK.get(c.customer_type, RiskLevel.MEDIUM)
        return FactorScore(
            "customer_type", _BAND_SCORE[band], self.weights["customer_type"],
            band, f"{c.customer_type.value} inherent risk = {band.value}",
        )

    def _geography_factor(self, c: CustomerProfile) -> FactorScore:
        """Worst-case across nationality, residence, incorporation and operations."""
        candidates: list[tuple[RiskLevel, str]] = []
        for label, cc in (
            ("nationality", c.nationality),
            ("residence", c.residence_country),
            ("incorporation", c.incorporation_country),
        ):
            if cc:
                band, why = ref.country_risk(cc)
                candidates.append((band, f"{label} {cc.upper()}: {why}"))
        for cc in c.countries_of_operation:
            band, why = ref.country_risk(cc)
            candidates.append((band, f"operates in {cc.upper()}: {why}"))
        if not candidates:
            return FactorScore(
                "geography", _BAND_SCORE[RiskLevel.MEDIUM],
                self.weights["geography"], RiskLevel.MEDIUM,
                "No geography data provided",
            )
        worst = max(candidates, key=lambda x: x[0].rank)
        return FactorScore(
            "geography", _BAND_SCORE[worst[0]], self.weights["geography"],
            worst[0], worst[1],
        )

    def _occupation_factor(self, c: CustomerProfile) -> FactorScore:
        # For legal entities, use the industry as the activity descriptor.
        activity = c.occupation if c.customer_type == CustomerType.INDIVIDUAL else c.industry
        band, why = ref.occupation_risk(activity)
        return FactorScore(
            "occupation", _BAND_SCORE[band], self.weights["occupation"], band, why,
        )

    def _product_factor(self, c: CustomerProfile) -> FactorScore:
        if not c.products:
            return FactorScore(
                "product", _BAND_SCORE[RiskLevel.LOW], self.weights["product"],
                RiskLevel.LOW, "No products held",
            )
        worst_band = RiskLevel.LOW
        worst_why = ""
        for p in c.products:
            band, why = ref.product_risk(p)
            if band.rank >= worst_band.rank:
                worst_band, worst_why = band, why
        return FactorScore(
            "product", _BAND_SCORE[worst_band], self.weights["product"],
            worst_band, worst_why,
        )

    def _channel_factor(self, c: CustomerProfile) -> FactorScore:
        band, why = ref.channel_risk(c.onboarding_channel)
        return FactorScore(
            "channel", _BAND_SCORE[band], self.weights["channel"], band, why,
        )

    def _pep_factor(self, c: CustomerProfile) -> FactorScore:
        if c.is_pep:
            return FactorScore(
                "pep", _BAND_SCORE[RiskLevel.CRITICAL], self.weights["pep"],
                RiskLevel.CRITICAL, "Customer is a Politically Exposed Person",
            )
        if c.pep_relationship:
            return FactorScore(
                "pep", _BAND_SCORE[RiskLevel.HIGH], self.weights["pep"],
                RiskLevel.HIGH, "Family member / close associate of a PEP",
            )
        return FactorScore(
            "pep", _BAND_SCORE[RiskLevel.LOW], self.weights["pep"],
            RiskLevel.LOW, "No PEP exposure",
        )

    def _adverse_media_factor(self, c: CustomerProfile) -> FactorScore:
        band = RiskLevel.HIGH if c.adverse_media else RiskLevel.LOW
        why = "Adverse media identified" if c.adverse_media else "No adverse media"
        return FactorScore(
            "adverse_media", _BAND_SCORE[band], self.weights["adverse_media"],
            band, why,
        )

    # -- aggregation ------------------------------------------------------- #
    def assess(self, customer: CustomerProfile) -> CRRResult:
        factors = [
            self._customer_type_factor(customer),
            self._geography_factor(customer),
            self._occupation_factor(customer),
            self._product_factor(customer),
            self._channel_factor(customer),
            self._pep_factor(customer),
            self._adverse_media_factor(customer),
        ]
        total_weight = sum(f.weight for f in factors) or 1.0
        score = sum(f.weighted for f in factors) / total_weight

        overrides: list[str] = []
        # Mandatory escalations: certain factors force a floor on the rating
        # regardless of the weighted average (regulatory non-negotiables). A pure
        # weighted average can otherwise dilute a single extreme inherent risk.
        if customer.is_pep:
            score = max(score, _BAND_SCORE[RiskLevel.HIGH])
            overrides.append("PEP status forces minimum HIGH rating")
        geo = next(f for f in factors if f.name == "geography")
        if geo.band == RiskLevel.CRITICAL:
            score = max(score, _BAND_SCORE[RiskLevel.CRITICAL])
            overrides.append("Exposure to FATF call-for-action jurisdiction forces CRITICAL")
        if customer.adverse_media:
            score = max(score, _BAND_SCORE[RiskLevel.HIGH])
            overrides.append("Adverse media forces minimum HIGH rating")

        # Any single CRITICAL-band inherent factor warrants EDD.
        critical_factors = [f.name for f in factors if f.band == RiskLevel.CRITICAL]
        if critical_factors:
            score = max(score, _BAND_SCORE[RiskLevel.HIGH])
            overrides.append(
                "CRITICAL inherent factor(s) "
                f"({', '.join(critical_factors)}) force minimum HIGH rating"
            )
        # Multiple independent HIGH-or-above factors compound to HIGH.
        high_plus = [f.name for f in factors if f.band.rank >= RiskLevel.HIGH.rank]
        if len(high_plus) >= 2:
            score = max(score, _BAND_SCORE[RiskLevel.HIGH])
            overrides.append(
                f"{len(high_plus)} elevated risk factors "
                f"({', '.join(high_plus)}) force minimum HIGH rating"
            )

        level = RiskLevel.from_score(score)
        if level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            ddl = DueDiligenceLevel.ENHANCED
        elif level == RiskLevel.LOW:
            ddl = DueDiligenceLevel.SIMPLIFIED
        else:
            ddl = DueDiligenceLevel.STANDARD

        return CRRResult(
            customer_id=customer.customer_id,
            overall_score=score,
            risk_level=level,
            due_diligence=ddl,
            requires_edd=ddl == DueDiligenceLevel.ENHANCED,
            factors=factors,
            overrides=overrides,
        )
