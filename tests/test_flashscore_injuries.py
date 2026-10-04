"""Tests for Flashscore missing players parser."""
from pathlib import Path

import pytest

from bookmakers.flashscore_injuries import parse_missing_players


CACHE = Path("data/cache/flashscore/match_zenit_baltika.html")


def _load_html() -> str:
    if not CACHE.exists():
        pytest.skip(f"fixture missing: {CACHE}")
    return CACHE.read_text(encoding="utf-8")


def test_parse_returns_two_sides():
    data = parse_missing_players(_load_html())
    assert set(data.keys()) == {"home", "away"}


def test_home_players_have_names_and_reasons():
    data = parse_missing_players(_load_html())
    names = [p["name"] for p in data["home"]]
    assert "Anderson E." in names
    assert "Filin A." in names
    for p in data["home"]:
        assert p["name"]
        assert p["reason"]
        assert p["reason"] != "unknown"


def test_away_players_present():
    data = parse_missing_players(_load_html())
    names = [p["name"] for p in data["away"]]
    assert "Wendel" in names
    assert "Gustavo Mantuan" in names


def test_empty_html_returns_empty_lists():
    assert parse_missing_players("") == {"home": [], "away": []}


def test_no_missing_block_returns_empty_lists():
    assert parse_missing_players("<html><body>nothing</body></html>") == {
        "home": [],
        "away": [],
    }


# ---------------------------------------------------------------------------
# Cache lookup tests
# ---------------------------------------------------------------------------

from bookmakers.flashscore_injuries import (  # noqa: E402
    save_injuries, load_injuries,
    lookup_injuries_for_event,
    injuries_cache_path,
)


def test_save_and_load_injuries_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "bookmakers.flashscore_injuries.INJURIES_CACHE_DIR", tmp_path,
    )
    mid = "TEST_MID"
    payload = {
        "home": [{"name": "A", "reason": "Knee Injury"}],
        "away": [{"name": "B", "reason": "Inactive"}],
    }
    save_injuries(mid, payload)
    loaded = load_injuries(mid)
    assert loaded == payload


def test_load_injuries_missing_returns_none():
    assert load_injuries("NO_SUCH_MID_12345") is None


def test_lookup_returns_empty_when_mid_map_empty():
    assert lookup_injuries_for_event("A", "B", mid_map=[]) == {"home": [], "away": []}


def test_lookup_returns_empty_when_mid_not_found():
    mid_map = [{"home_norm": "x", "away_norm": "y", "mid": "12345"}]
    assert lookup_injuries_for_event("Foo", "Bar", mid_map=mid_map) == {
        "home": [], "away": [],
    }
