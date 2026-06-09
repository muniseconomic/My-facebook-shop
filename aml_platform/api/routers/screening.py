"""Ad-hoc sanctions / PEP / watchlist screening endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.database import get_session
from ...db.models import WatchlistRecord
from ...services import screening_service
from ..schemas import ScreeningRequest

router = APIRouter(prefix="/screening", tags=["Sanctions / Screening"])


@router.post("/name", summary="Screen a single name against all watchlists")
def screen_name(req: ScreeningRequest, db: Session = Depends(get_session)) -> dict:
    matches = screening_service.screen_name(db, req.name, date_of_birth=req.date_of_birth)
    engine = screening_service.build_engine(db)
    return {
        "subject": req.name,
        "risk_level": engine.screen_subject_risk(matches).value,
        "match_count": len(matches),
        "matches": [m.to_dict() for m in matches],
    }


@router.get("/watchlist", summary="List watchlist entries")
def list_watchlist(db: Session = Depends(get_session)) -> dict:
    rows = db.execute(select(WatchlistRecord)).scalars().all()
    return {
        "count": len(rows),
        "entries": [
            {
                "entry_id": r.entry_id,
                "name": r.name,
                "list_type": r.list_type,
                "source": r.source,
                "program": r.program,
            }
            for r in rows
        ],
    }
