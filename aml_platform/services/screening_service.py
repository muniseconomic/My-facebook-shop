"""Screening service: loads watchlists from the DB and screens names."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..core.sanctions import MatchResult, ScreeningEngine
from ..db.models import WatchlistRecord
from .mappers import record_to_watchlist_entry


def build_engine(db: Session) -> ScreeningEngine:
    """Construct a screening engine populated from the watchlist table."""
    rows = db.execute(select(WatchlistRecord)).scalars().all()
    entries = [record_to_watchlist_entry(r) for r in rows]
    return ScreeningEngine(entries, threshold=settings.screening_threshold)


def screen_name(
    db: Session, name: str, *, date_of_birth: str | None = None
) -> list[MatchResult]:
    engine = build_engine(db)
    return engine.screen_name(name, date_of_birth=date_of_birth)
