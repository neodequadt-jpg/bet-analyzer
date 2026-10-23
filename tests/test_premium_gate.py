"""Tests for premium subscription gating."""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch

from tg_bot import _premium_gate, is_premium, grant_premium


class TestPremiumGate:
    def test_free_commands_allowed(self):
        """Free commands always return None (no rejection)."""
        assert _premium_gate("/start", 123) is None
        assert _premium_gate("/help", 123) is None
        assert _premium_gate("/bonuses", 123) is None
        assert _premium_gate("/stats", 123) is None
        assert _premium_gate("/live", 123) is None
        assert _premium_gate("/backtest", 123) is None
        assert _premium_gate("/subscribe", 123) is None
        assert _premium_gate("/status", 123) is None
        assert _premium_gate("/bookmakers", 123) is None

    def test_premium_commands_blocked_for_free_user(self, tmp_path):
        """Premium commands return rejection message for non-premium users."""
        subs_path = tmp_path / "subscribers.json"
        subs_path.write_text("{}", encoding="utf-8")
        with patch("tg_bot._SUBSCRIBERS_FILE", subs_path):
            result = _premium_gate("/value", 999)
            assert result is not None
            assert "Premium" in result

            result = _premium_gate("/signals", 999)
            assert result is not None

            result = _premium_gate("/plan", 999)
            assert result is not None

    def test_premium_commands_allowed_for_premium_user(self, tmp_path):
        """Premium commands return None for premium users."""
        subs_path = tmp_path / "subscribers.json"
        subs_path.write_text("{}", encoding="utf-8")
        with patch("tg_bot._SUBSCRIBERS_FILE", subs_path):
            grant_premium(123, days=30)
            assert _premium_gate("/value", 123) is None
            assert _premium_gate("/signals", 123) is None
            assert _premium_gate("/plan", 123) is None
            assert _premium_gate("/express", 123) is None

    def test_expired_premium_blocked(self, tmp_path):
        """Expired premium user is treated as free."""
        subs_path = tmp_path / "subscribers.json"
        # Set expiry in the past
        expired_ts = time.time() - 100
        subs_path.write_text(json.dumps({"123": {"expiry_ts": expired_ts}}), encoding="utf-8")
        with patch("tg_bot._SUBSCRIBERS_FILE", subs_path):
            assert _premium_gate("/value", 123) is not None

    def test_plan_go_also_gated(self, tmp_path):
        """'/plan_go 1 2.15' should also be gated."""
        subs_path = tmp_path / "subscribers.json"
        subs_path.write_text("{}", encoding="utf-8")
        with patch("tg_bot._SUBSCRIBERS_FILE", subs_path):
            result = _premium_gate("/plan_go Winline 1 2.15", 999)
            assert result is not None
