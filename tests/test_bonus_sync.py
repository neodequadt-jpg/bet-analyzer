"""Tests for bonus_tracker.sync_from_monitor()."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scoring.bonus_tracker import sync_from_monitor, load, list_active


def _make_bonus_dc(bookmaker="winline", amount_rub=10000, end_date="2026-12-31"):
    """Minimal Bonus-like dict for normalize output."""
    from scoring.bonus_monitor import normalize, fetch_bonuses
    # Build a raw dict that normalize() can process
    return {
        "id": f"test-{bookmaker}",
        "bookmaker": bookmaker,
        "title": f"Freebet {amount_rub}",
        "amount_rub": amount_rub,
        "promo_code": None,
        "url": f"https://metaratings.ru/bonuses/{bookmaker}/",
        "verified": True,
        "expired": False,
        "end_date": end_date,
        "raw": {},
    }


class TestSyncFromMonitor:
    def test_adds_new_bonus(self, tmp_path):
        registry_path = tmp_path / "bonuses.json"
        registry_path.write_text("{}", encoding="utf-8")

        mock_bonus = MagicMock()
        mock_bonus.bookmaker = "winline"
        mock_bonus.amount_rub = 5000
        mock_bonus.end_date = "2026-12-31"
        mock_bonus.title = "Test bonus"

        with patch("scoring.bonus_monitor.fetch_bonuses", return_value=[{}]), \
             patch("scoring.bonus_monitor.normalize", return_value=mock_bonus), \
             patch("bookmakers.registry.get_bookmaker", return_value=MagicMock(name="Винлайн")):

            stats = sync_from_monitor(path=registry_path)

        assert stats["added"] >= 1
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        assert "Винлайн" in registry
        assert registry["Винлайн"]["amount"] == 5000

    def test_skips_existing(self, tmp_path):
        registry_path = tmp_path / "bonuses.json"
        existing = {"Винлайн": {"type": "freebet_snr", "amount": 10000,
                                "min_odds": 1.3, "max_odds": 2.5,
                                "expiry": "2026-12-31", "status": "active"}}
        registry_path.write_text(json.dumps(existing), encoding="utf-8")

        mock_bonus = MagicMock()
        mock_bonus.bookmaker = "winline"
        mock_bonus.amount_rub = 5000
        mock_bonus.end_date = "2026-12-31"

        with patch("scoring.bonus_monitor.fetch_bonuses", return_value=[{}]), \
             patch("scoring.bonus_monitor.normalize", return_value=mock_bonus), \
             patch("bookmakers.registry.get_bookmaker", return_value=MagicMock(name="Винлайн")):

            stats = sync_from_monitor(path=registry_path)

        assert stats["skipped_existing"] >= 1
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        assert registry["Винлайн"]["amount"] == 10000

    def test_skips_no_map(self, tmp_path):
        registry_path = tmp_path / "bonuses.json"
        registry_path.write_text("{}", encoding="utf-8")

        mock_bonus = MagicMock()
        mock_bonus.bookmaker = "unknown_bookmaker"
        mock_bonus.amount_rub = 5000
        mock_bonus.end_date = "2026-12-31"

        with patch("scoring.bonus_monitor.fetch_bonuses", return_value=[{}]), \
             patch("scoring.bonus_monitor.normalize", return_value=mock_bonus), \
             patch("bookmakers.registry.get_bookmaker", return_value=None):

            stats = sync_from_monitor(path=registry_path)

        assert stats["skipped_no_map"] >= 1

    def test_expiry_strips_time(self, tmp_path):
        registry_path = tmp_path / "bonuses.json"
        registry_path.write_text("{}", encoding="utf-8")

        mock_bonus = MagicMock()
        mock_bonus.bookmaker = "winline"
        mock_bonus.amount_rub = 5000
        mock_bonus.end_date = "2026-12-31T20:59:00+00:00"

        with patch("scoring.bonus_monitor.fetch_bonuses", return_value=[{}]), \
             patch("scoring.bonus_monitor.normalize", return_value=mock_bonus), \
             patch("bookmakers.registry.get_bookmaker", return_value=MagicMock(name="Винлайн")):

            sync_from_monitor(path=registry_path)

        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        expiry = registry["Винлайн"]["expiry"]
        assert "T" not in expiry
        assert expiry == "2026-12-31"
