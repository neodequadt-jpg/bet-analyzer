"""Tests for scoring.bonus_tracker – uses tmp_path, no network."""

from __future__ import annotations

import json
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from scoring.bonus_tracker import (
    Bonus,
    EXAMPLE_REGISTRY,
    load,
    validate,
    mark_used,
    list_active,
)


# ── helpers ──────────────────────────────────────────────────────────

def _write_registry(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _valid_entry(**overrides) -> dict:
    entry = {
        "type": "freebet_snr",
        "amount": 5000,
        "min_odds": 1.30,
        "max_odds": 2.50,
        "expiry": "2026-12-31",
        "status": "active",
    }
    entry.update(overrides)
    return entry


# ── load ─────────────────────────────────────────────────────────────

class TestLoadCreatesExampleIfMissing:
    def test_creates_file(self, tmp_path: Path):
        p = tmp_path / "bonuses.json"
        assert not p.exists()
        registry = load(p)
        assert p.exists()
        assert "Winline" in registry
        assert "PARI" in registry

    def test_existing_file_not_overwritten(self, tmp_path: Path):
        p = tmp_path / "bonuses.json"
        custom = {"Custom": _valid_entry()}
        _write_registry(p, custom)
        registry = load(p)
        assert "Custom" in registry
        assert "Winline" not in registry


# ── validate ─────────────────────────────────────────────────────────

class TestValidateOk:
    def test_valid_entry(self):
        assert validate(_valid_entry()) == []

    def test_example_entries_valid(self):
        for name, entry in EXAMPLE_REGISTRY.items():
            assert validate(entry) == [], f"{name} invalid"


class TestValidateMissingKey:
    def test_missing_amount(self):
        entry = _valid_entry()
        del entry["amount"]
        errors = validate(entry)
        assert any("missing key: amount" in e for e in errors)

    def test_missing_type(self):
        entry = _valid_entry()
        del entry["type"]
        errors = validate(entry)
        assert any("missing key: type" in e for e in errors)


class TestValidateBadAmount:
    def test_zero_amount(self):
        errors = validate(_valid_entry(amount=0))
        assert any("amount must be > 0" in e for e in errors)

    def test_negative_amount(self):
        errors = validate(_valid_entry(amount=-100))
        assert any("amount must be > 0" in e for e in errors)

    def test_string_amount(self):
        errors = validate(_valid_entry(amount="big"))
        assert any("amount must be numeric" in e for e in errors)


class TestValidateMinGtMax:
    def test_min_greater_than_max(self):
        errors = validate(_valid_entry(min_odds=3.0, max_odds=1.5))
        assert any("min_odds must be <= max_odds" in e for e in errors)

    def test_min_equal_max_ok(self):
        errors = validate(_valid_entry(min_odds=2.0, max_odds=2.0))
        assert not any("min_odds must be <= max_odds" in e for e in errors)


# ── list_active ──────────────────────────────────────────────────────

class TestListActiveFiltersStatus:
    def test_only_active_returned(self, tmp_path: Path):
        p = tmp_path / "bonuses.json"
        data = {
            "Active1": _valid_entry(status="active"),
            "Used1": _valid_entry(status="used"),
            "Skipped1": _valid_entry(status="skipped"),
        }
        _write_registry(p, data)
        active = list_active(p)
        names = [b.bookmaker for b in active]
        assert "Active1" in names
        assert "Used1" not in names
        assert "Skipped1" not in names


class TestListActiveFiltersExpired:
    def test_past_expiry_excluded(self, tmp_path: Path):
        p = tmp_path / "bonuses.json"
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        data = {
            "ExpiredBonus": _valid_entry(status="active", expiry=yesterday),
        }
        _write_registry(p, data)
        active = list_active(p)
        assert all(b.bookmaker != "ExpiredBonus" for b in active)

    def test_future_expiry_included(self, tmp_path: Path):
        p = tmp_path / "bonuses.json"
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        data = {
            "FreshBonus": _valid_entry(status="active", expiry=tomorrow),
        }
        _write_registry(p, data)
        active = list_active(p)
        assert any(b.bookmaker == "FreshBonus" for b in active)


# ── mark_used ────────────────────────────────────────────────────────

class TestMarkUsedChangesStatus:
    def test_status_becomes_used(self, tmp_path: Path):
        p = tmp_path / "bonuses.json"
        data = {"TestBK": _valid_entry(status="active")}
        _write_registry(p, data)
        mark_used("TestBK", p)
        registry = load(p)
        assert registry["TestBK"]["status"] == "used"

    def test_nonexistent_name_no_error(self, tmp_path: Path):
        p = tmp_path / "bonuses.json"
        data = {"Existing": _valid_entry(status="active")}
        _write_registry(p, data)
        mark_used("Ghost", p)  # should not raise
        registry = load(p)
        assert registry["Existing"]["status"] == "active"


# ── bookmaker field ──────────────────────────────────────────────────

class TestBookmakerFieldPresent:
    def test_bookmaker_is_key_name(self, tmp_path: Path):
        p = tmp_path / "bonuses.json"
        data = {"MyBookie": _valid_entry(status="active")}
        _write_registry(p, data)
        active = list_active(p)
        assert len(active) == 1
        assert active[0].bookmaker == "MyBookie"

    def test_bonus_dataclass_has_bookmaker(self, tmp_path: Path):
        p = tmp_path / "bonuses.json"
        data = {"Another": _valid_entry(status="active")}
        _write_registry(p, data)
        active = list_active(p)
        b = active[0]
        assert hasattr(b, "bookmaker")
        assert isinstance(b.bookmaker, str)
