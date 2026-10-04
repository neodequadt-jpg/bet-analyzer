"""Tests for Flashscore MID map."""
from pathlib import Path

import pytest

from bookmakers.flashscore_mid_map import (
    build_mid_map_from_html, find_mid,
)


CACHE = Path("data/cache/flashscore/rpl_fixtures.html")


def _load() -> str:
    if not CACHE.exists():
        pytest.skip(f"fixture missing: {CACHE}")
    return CACHE.read_text(encoding="utf-8")


def test_build_from_empty():
    assert build_mid_map_from_html("") == []


def test_build_from_cache_non_empty():
    records = build_mid_map_from_html(_load())
    assert len(records) > 10
    for r in records:
        assert r["mid"]
        assert r["home"]
        assert r["away"]
        assert r["home_norm"]
        assert r["away_norm"]


def test_find_mid_rostov_akron():
    records = build_mid_map_from_html(_load())
    assert find_mid(records, "FK Rostov", "Akron Togliatti") == "EotNuCVi"


def test_find_mid_orenburg_dm():
    records = build_mid_map_from_html(_load())
    assert find_mid(records, "Orenburg", "Dynamo Makhachkala") == "navVwj04"


def test_find_mid_missing():
    records = build_mid_map_from_html(_load())
    assert find_mid(records, "Foo", "Bar") is None


def test_find_mid_empty_records():
    assert find_mid([], "A", "B") is None
    assert find_mid([], "", "") is None
