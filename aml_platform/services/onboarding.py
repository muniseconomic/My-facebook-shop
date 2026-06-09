"""Customer onboarding service: persists a customer, computes the CRR, and runs
sanctions/PEP screening as part of KYC/CDD."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..core.crr import CRREngine
from ..core.enums import RiskLevel
from ..db.models import Alert, Customer
from . import case_management as cm
from . import screening_service
from .mappers import customer_to_profile


def _review_days(level: str | None) -> int:
    return {
        RiskLevel.CRITICAL.value: settings.review_days_high,
        RiskLevel.HIGH.value: settings.review_days_high,
        RiskLevel.MEDIUM.value: settings.review_days_medium,
        RiskLevel.LOW.value: settings.review_days_low,
    }.get(level or "", settings.review_days_medium)


def assess_customer(db: Session, customer: Customer) -> dict:
    """Compute and persist the CRR for an existing customer."""
    profile = customer_to_profile(customer)
    result = CRREngine().assess(profile)

    customer.risk_score = result.overall_score
    customer.risk_level = result.risk_level.value
    customer.due_diligence = result.due_diligence.value
    customer.crr_factors = result.to_dict()["factors"]
    customer.next_review_date = datetime.now(timezone.utc) + timedelta(
        days=_review_days(result.risk_level.value)
    )
    db.commit()
    db.refresh(customer)
    return result.to_dict()


def screen_customer(db: Session, customer: Customer, *, persist: bool = True) -> dict:
    """Screen a customer (and aliases) against the watchlists."""
    engine = screening_service.build_engine(db)
    matches = []
    for name in [customer.full_name, *(customer.aliases or [])]:
        matches.extend(engine.screen_name(name, date_of_birth=customer.date_of_birth))
    # De-duplicate by watchlist entry, keeping the highest score.
    best: dict[str, object] = {}
    for m in matches:
        cur = best.get(m.entry.entry_id)
        if cur is None or m.score > cur.score:  # type: ignore[attr-defined]
            best[m.entry.entry_id] = m
    deduped = sorted(best.values(), key=lambda m: m.score, reverse=True)  # type: ignore

    created = []
    if persist:
        for m in deduped:
            if m.is_strong:  # type: ignore[attr-defined]
                sev = "CRITICAL" if m.entry.list_type.value == "SANCTIONS" else "HIGH"  # type: ignore
                alert = cm.create_alert(
                    db, customer_id=customer.id, alert_type="SCREENING",
                    scenario=f"{m.entry.list_type.value}_MATCH",  # type: ignore
                    severity=sev,
                    description=(
                        f"Potential {m.entry.list_type.value} match: subject "  # type: ignore
                        f"'{m.subject_name}' ~ '{m.matched_name}' "  # type: ignore
                        f"({m.score:.0f}% on {m.entry.source})"  # type: ignore
                    ),
                    score=m.score,  # type: ignore[attr-defined]
                    details=m.to_dict(),  # type: ignore[attr-defined]
                )
                created.append(alert.id)

    return {
        "customer_ref": customer.customer_ref,
        "matches": [m.to_dict() for m in deduped],  # type: ignore[attr-defined]
        "alerts_created": created,
    }


def onboard_customer(db: Session, customer: Customer) -> dict:
    """Full onboarding flow: persist, CRR, screening."""
    db.add(customer)
    db.commit()
    db.refresh(customer)
    crr = assess_customer(db, customer)
    screening = screen_customer(db, customer)
    return {"customer_ref": customer.customer_ref, "crr": crr, "screening": screening}
