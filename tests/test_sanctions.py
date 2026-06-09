from aml_platform.core.enums import ScreeningListType
from aml_platform.core.sanctions import (
    ScreeningEngine,
    WatchlistEntry,
    normalise,
)

ENTRIES = [
    WatchlistEntry(
        entry_id="S1", name="Viktor Anatolyevich Petrov",
        list_type=ScreeningListType.SANCTIONS, source="OFAC",
        aliases=["Viktor Petrov", "V. A. Petrov"], date_of_birth="1968-04-12",
    ),
    WatchlistEntry(
        entry_id="S2", name="Global Horizon Trading LLC",
        list_type=ScreeningListType.SANCTIONS, source="OFAC",
        aliases=["GH Trading"],
    ),
]


def test_normalise_removes_noise_and_accents():
    assert normalise("Mr. Víktor Petrov!") == "viktor petrov"
    assert normalise("Global Horizon Trading LLC") == "global horizon trading"


def test_exact_alias_match():
    engine = ScreeningEngine(ENTRIES)
    matches = engine.screen_name("Viktor Petrov")
    assert matches and matches[0].entry.entry_id == "S1"
    assert matches[0].score >= 90


def test_typo_tolerant_match():
    engine = ScreeningEngine(ENTRIES)
    matches = engine.screen_name("Viktor Petroff")  # transliteration variant
    assert matches and matches[0].entry.entry_id == "S1"


def test_reordered_tokens_match():
    engine = ScreeningEngine(ENTRIES)
    matches = engine.screen_name("Petrov Viktor Anatolyevich")
    assert matches and matches[0].entry.entry_id == "S1"


def test_corporate_noise_ignored():
    engine = ScreeningEngine(ENTRIES)
    matches = engine.screen_name("Global Horizon Trading")
    assert matches and matches[0].entry.entry_id == "S2"


def test_dob_boost():
    engine = ScreeningEngine(ENTRIES)
    with_dob = engine.screen_name("Viktor Petrov", date_of_birth="1968-04-12")
    assert with_dob[0].dob_match


def test_no_false_positive_for_unrelated_name():
    engine = ScreeningEngine(ENTRIES)
    assert engine.screen_name("Catherine Williams") == []


def test_whitelist_suppresses_match():
    engine = ScreeningEngine(ENTRIES)
    assert engine.screen_name("Viktor Petrov")  # matches before whitelisting
    engine.whitelist_match("Viktor Petrov", "S1")
    assert engine.screen_name("Viktor Petrov") == []
