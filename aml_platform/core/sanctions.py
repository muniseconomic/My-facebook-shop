"""Sanctions / PEP / watchlist screening engine.

Performs fuzzy name matching of a subject (customer, counterparty, or
transaction party) against one or more watchlists (OFAC SDN, UN consolidated,
EU, internal blacklist, PEP lists).

Matching strategy (combined, configurable):

  * Normalisation - case-folding, punctuation/diacritic stripping, removal of
    corporate and honorific noise words, whitespace collapsing.
  * Token-set ratio - order-independent token comparison (handles reordered
    name parts and middle names).
  * Jaro-Winkler / partial ratio - tolerant of typos and transliteration.
  * Alias expansion - every alias on a list entry is screened independently and
    the best score is kept.
  * Date-of-birth corroboration - boosts confidence when DoB matches.

The engine returns ranked candidate matches with a 0-100 confidence score and a
configurable auto-hit threshold. Whitelisting (previously cleared matches) is
supported to suppress known false positives.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from .enums import RiskLevel, ScreeningListType

# Noise tokens removed before comparison.
_CORP_NOISE = {
    "ltd", "limited", "llc", "inc", "incorporated", "co", "company", "corp",
    "corporation", "plc", "gmbh", "sa", "sas", "bv", "ag", "pte", "llp",
    "the", "and", "of", "for", "group", "holdings", "international",
}
_HONORIFICS = {"mr", "mrs", "ms", "miss", "dr", "prof", "sheikh", "hon", "sir"}
_NOISE = _CORP_NOISE | _HONORIFICS


@dataclass
class WatchlistEntry:
    entry_id: str
    name: str
    list_type: ScreeningListType
    source: str = "INTERNAL"               # e.g. OFAC, UN, EU
    aliases: list[str] = field(default_factory=list)
    date_of_birth: str | None = None
    nationality: str | None = None
    program: str | None = None             # sanctions program / designation
    remarks: str | None = None

    def all_names(self) -> list[str]:
        return [self.name, *self.aliases]


@dataclass
class MatchResult:
    subject_name: str
    entry: WatchlistEntry
    matched_name: str
    score: float                            # 0-100 confidence
    dob_match: bool = False

    @property
    def is_strong(self) -> bool:
        return self.score >= 90

    def to_dict(self) -> dict:
        return {
            "subject_name": self.subject_name,
            "matched_name": self.matched_name,
            "score": round(self.score, 1),
            "dob_match": self.dob_match,
            "entry": {
                "entry_id": self.entry.entry_id,
                "name": self.entry.name,
                "list_type": self.entry.list_type.value,
                "source": self.entry.source,
                "program": self.entry.program,
                "nationality": self.entry.nationality,
            },
        }


def normalise(name: str) -> str:
    """Lower-case, strip accents/punctuation and remove noise tokens."""
    if not name:
        return ""
    # Strip accents / diacritics.
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in decomposed if not unicodedata.combining(c))
    ascii_name = ascii_name.lower()
    ascii_name = re.sub(r"[^a-z0-9\s]", " ", ascii_name)
    tokens = [t for t in ascii_name.split() if t and t not in _NOISE]
    return " ".join(tokens)


class ScreeningEngine:
    """Screens subject names against a set of watchlist entries."""

    def __init__(
        self,
        entries: list[WatchlistEntry] | None = None,
        *,
        threshold: float = 82.0,
        whitelist: set[tuple[str, str]] | None = None,
    ) -> None:
        # whitelist holds (normalised_subject, entry_id) pairs previously cleared.
        self.entries: list[WatchlistEntry] = entries or []
        self.threshold = threshold
        self.whitelist = whitelist or set()

    def add_entries(self, entries: list[WatchlistEntry]) -> None:
        self.entries.extend(entries)

    def whitelist_match(self, subject_name: str, entry_id: str) -> None:
        self.whitelist.add((normalise(subject_name), entry_id))

    @staticmethod
    def _pair_score(a_norm: str, b_norm: str) -> float:
        if not a_norm or not b_norm:
            return 0.0
        # Combine complementary similarity measures and take the strongest.
        token_set = fuzz.token_set_ratio(a_norm, b_norm)
        token_sort = fuzz.token_sort_ratio(a_norm, b_norm)
        partial = fuzz.partial_ratio(a_norm, b_norm)
        return max(token_set, token_sort, partial * 0.95)

    def screen_name(
        self,
        subject_name: str,
        *,
        date_of_birth: str | None = None,
        list_types: list[ScreeningListType] | None = None,
    ) -> list[MatchResult]:
        """Return ranked matches above the configured threshold."""
        subj_norm = normalise(subject_name)
        if not subj_norm:
            return []
        results: list[MatchResult] = []
        for entry in self.entries:
            if list_types and entry.list_type not in list_types:
                continue
            if (subj_norm, entry.entry_id) in self.whitelist:
                continue  # previously cleared false positive
            best_score = 0.0
            best_name = entry.name
            for candidate in entry.all_names():
                score = self._pair_score(subj_norm, normalise(candidate))
                if score > best_score:
                    best_score, best_name = score, candidate

            dob_match = bool(
                date_of_birth and entry.date_of_birth
                and date_of_birth == entry.date_of_birth
            )
            if dob_match:
                best_score = min(100.0, best_score + 8)  # corroboration boost

            if best_score >= self.threshold:
                results.append(MatchResult(
                    subject_name=subject_name,
                    entry=entry,
                    matched_name=best_name,
                    score=best_score,
                    dob_match=dob_match,
                ))
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def screen_subject_risk(self, matches: list[MatchResult]) -> RiskLevel:
        """Translate a set of matches into an overall screening risk band."""
        if not matches:
            return RiskLevel.LOW
        top = matches[0]
        if top.entry.list_type == ScreeningListType.SANCTIONS and top.score >= 90:
            return RiskLevel.CRITICAL
        if top.score >= 90:
            return RiskLevel.HIGH
        if top.score >= self.threshold:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
