"""Tests for scripts.bonus_cron – no network, unittest + unittest.mock."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# Make scripts importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scoring.bonus_monitor import Bonus

# Import after path setup
from scripts.bonus_cron import (
    main,
    format_alert,
    load_env,
    _parse_env_file,
    clear_proxy_env,
    PROXY_KEYS,
)


def _make_bonus(id="1", bookmaker="TestBK", title="Test Bonus", url="http://x"):
    """Helper to create a Bonus instance for testing."""
    return Bonus(
        id=id,
        bookmaker=bookmaker,
        title=title,
        amount_rub=100,
        promo_code=None,
        url=url,
        verified=False,
        expired=False,
        end_date=None,
    )


class TestAllNewSendsToAllAdmins(unittest.TestCase):
    """a) prev=[] → all new → send called for EACH TG_ADMIN_ID."""

    @patch("scripts.bonus_cron.send_message")
    @patch("scripts.bonus_cron.save_snapshot")
    @patch("scripts.bonus_cron.load_snapshot", return_value=[])
    @patch("scripts.bonus_cron.snapshot_diff")
    @patch("scripts.bonus_cron.normalize")
    @patch("scripts.bonus_cron.fetch_bonuses")
    @patch("scripts.bonus_cron._get_admin_ids", return_value={111, 222})
    @patch("scripts.bonus_cron.load_env")
    def test_all_new_sends_to_all(
        self, mock_load_env, mock_admin_ids, mock_fetch, mock_normalize,
        mock_diff, mock_load_snap, mock_save_snap, mock_send
    ):
        b = _make_bonus()
        mock_fetch.return_value = [{"id": "1"}]
        mock_normalize.return_value = b
        mock_diff.return_value = {
            "new": [{"id": "1", "bookmaker": "TestBK", "title": "Test Bonus", "url": "http://x"}],
            "gone": [],
            "changed": [],
        }

        with patch.object(sys, "argv", ["bonus_cron.py"]):
            rc = main()

        self.assertEqual(rc, 0)
        self.assertEqual(mock_send.call_count, 2)
        called_ids = {c.args[0] for c in mock_send.call_args_list}
        self.assertEqual(called_ids, {111, 222})


class TestNoChangesNoSend(unittest.TestCase):
    """b) No changes → send NOT called, save called."""

    @patch("scripts.bonus_cron.send_message")
    @patch("scripts.bonus_cron.save_snapshot")
    @patch("scripts.bonus_cron.load_snapshot", return_value=[])
    @patch("scripts.bonus_cron.snapshot_diff")
    @patch("scripts.bonus_cron.normalize")
    @patch("scripts.bonus_cron.fetch_bonuses")
    @patch("scripts.bonus_cron._get_admin_ids", return_value={111})
    @patch("scripts.bonus_cron.load_env")
    def test_no_changes(
        self, mock_load_env, mock_admin_ids, mock_fetch, mock_normalize,
        mock_diff, mock_load_snap, mock_save_snap, mock_send
    ):
        b = _make_bonus()
        mock_fetch.return_value = [{"id": "1"}]
        mock_normalize.return_value = b
        mock_diff.return_value = {"new": [], "gone": [], "changed": []}

        with patch.object(sys, "argv", ["bonus_cron.py"]):
            rc = main()

        self.assertEqual(rc, 0)
        mock_send.assert_not_called()
        mock_save_snap.assert_called_once()


class TestNewBonusSendsWithHTML(unittest.TestCase):
    """c) New bonus → send called with parse_mode='HTML'."""

    @patch("scripts.bonus_cron.send_message")
    @patch("scripts.bonus_cron.save_snapshot")
    @patch("scripts.bonus_cron.load_snapshot", return_value=[])
    @patch("scripts.bonus_cron.snapshot_diff")
    @patch("scripts.bonus_cron.normalize")
    @patch("scripts.bonus_cron.fetch_bonuses")
    @patch("scripts.bonus_cron._get_admin_ids", return_value={111})
    @patch("scripts.bonus_cron.load_env")
    def test_sends_with_html(
        self, mock_load_env, mock_admin_ids, mock_fetch, mock_normalize,
        mock_diff, mock_load_snap, mock_save_snap, mock_send
    ):
        b = _make_bonus()
        mock_fetch.return_value = [{"id": "1"}]
        mock_normalize.return_value = b
        mock_diff.return_value = {
            "new": [{"id": "1", "bookmaker": "TestBK", "title": "Test Bonus", "url": "http://x"}],
            "gone": [],
            "changed": [],
        }

        with patch.object(sys, "argv", ["bonus_cron.py"]):
            rc = main()

        self.assertEqual(rc, 0)
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        self.assertEqual(kwargs.get("parse_mode"), "HTML")


class TestDryRunNoSendNoSave(unittest.TestCase):
    """d) --dry-run → send NOT called, save NOT called."""

    @patch("scripts.bonus_cron.send_message")
    @patch("scripts.bonus_cron.save_snapshot")
    @patch("scripts.bonus_cron.load_snapshot", return_value=[])
    @patch("scripts.bonus_cron.snapshot_diff")
    @patch("scripts.bonus_cron.normalize")
    @patch("scripts.bonus_cron.fetch_bonuses")
    @patch("scripts.bonus_cron._get_admin_ids", return_value={111})
    @patch("scripts.bonus_cron.load_env")
    def test_dry_run(
        self, mock_load_env, mock_admin_ids, mock_fetch, mock_normalize,
        mock_diff, mock_load_snap, mock_save_snap, mock_send
    ):
        b = _make_bonus()
        mock_fetch.return_value = [{"id": "1"}]
        mock_normalize.return_value = b
        mock_diff.return_value = {
            "new": [{"id": "1", "bookmaker": "TestBK", "title": "Test Bonus", "url": "http://x"}],
            "gone": [],
            "changed": [],
        }

        with patch.object(sys, "argv", ["bonus_cron.py", "--dry-run"]):
            rc = main()

        self.assertEqual(rc, 0)
        mock_send.assert_not_called()
        mock_save_snap.assert_not_called()


class TestForceSendsOnEmptyDiff(unittest.TestCase):
    """e) --force → send called even with empty diff."""

    @patch("scripts.bonus_cron.send_message")
    @patch("scripts.bonus_cron.save_snapshot")
    @patch("scripts.bonus_cron.load_snapshot", return_value=[])
    @patch("scripts.bonus_cron.snapshot_diff")
    @patch("scripts.bonus_cron.normalize")
    @patch("scripts.bonus_cron.fetch_bonuses")
    @patch("scripts.bonus_cron._get_admin_ids", return_value={111})
    @patch("scripts.bonus_cron.load_env")
    def test_force_empty_diff(
        self, mock_load_env, mock_admin_ids, mock_fetch, mock_normalize,
        mock_diff, mock_load_snap, mock_save_snap, mock_send
    ):
        b = _make_bonus()
        mock_fetch.return_value = [{"id": "1"}]
        mock_normalize.return_value = b
        mock_diff.return_value = {"new": [], "gone": [], "changed": []}

        with patch.object(sys, "argv", ["bonus_cron.py", "--force"]):
            rc = main()

        self.assertEqual(rc, 0)
        mock_send.assert_called_once()


class TestFetchRaisesNonZero(unittest.TestCase):
    """f) fetch raises → main() != 0, send NOT called."""

    @patch("scripts.bonus_cron.send_message")
    @patch("scripts.bonus_cron.fetch_bonuses", side_effect=RuntimeError("network error"))
    @patch("scripts.bonus_cron._get_admin_ids", return_value={111})
    @patch("scripts.bonus_cron.load_env")
    def test_fetch_raises(
        self, mock_load_env, mock_admin_ids, mock_fetch, mock_send
    ):
        with patch.object(sys, "argv", ["bonus_cron.py"]):
            rc = main()

        self.assertNotEqual(rc, 0)
        mock_send.assert_not_called()


class TestProxyEnvClearedBeforeFetch(unittest.TestCase):
    """g) Proxy env cleared before fetch (side_effect verification)."""

    @patch("scripts.bonus_cron.send_message")
    @patch("scripts.bonus_cron.save_snapshot")
    @patch("scripts.bonus_cron.load_snapshot", return_value=[])
    @patch("scripts.bonus_cron.snapshot_diff")
    @patch("scripts.bonus_cron.normalize")
    @patch("scripts.bonus_cron.fetch_bonuses")
    @patch("scripts.bonus_cron._get_admin_ids", return_value={111})
    @patch("scripts.bonus_cron.load_env")
    def test_proxy_cleared(
        self, mock_load_env, mock_admin_ids, mock_fetch, mock_normalize,
        mock_diff, mock_load_snap, mock_save_snap, mock_send
    ):
        """Verify that by the time fetch_bonuses runs, proxy vars are gone."""
        proxy_state = {}

        def capture_proxy_state(*args, **kwargs):
            # Capture proxy env state at the moment fetch is called
            for k in PROXY_KEYS:
                proxy_state[k] = os.environ.get(k)
            return [{"id": "1"}]

        b = _make_bonus()
        mock_fetch.side_effect = capture_proxy_state
        mock_normalize.return_value = b
        mock_diff.return_value = {"new": [], "gone": [], "changed": []}

        # Set proxy env vars before main()
        for k in PROXY_KEYS:
            os.environ[k] = "http://proxy.test:3128"

        try:
            with patch.object(sys, "argv", ["bonus_cron.py"]):
                rc = main()
        finally:
            # Cleanup
            for k in PROXY_KEYS:
                os.environ.pop(k, None)

        # All proxy vars should be None at fetch time
        for k in PROXY_KEYS:
            self.assertIsNone(proxy_state[k], f"{k} should be None at fetch time")


class TestEnvParser(unittest.TestCase):
    """h) Env parser: tmp_path with 'export KEY=VALUE' and 'KEY=VALUE' → both picked up,
       already set NOT overwritten."""

    def test_export_prefix_stripped(self):
        """Lines with 'export KEY=VALUE' are parsed correctly."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            env_file = Path(td) / "test.env"
            env_file.write_text("export MY_TEST_KEY=hello\n", encoding="utf-8")
            # Make sure it's not already set
            os.environ.pop("MY_TEST_KEY", None)
            n = _parse_env_file(env_file)
            self.assertEqual(n, 1)
            self.assertEqual(os.environ["MY_TEST_KEY"], "hello")
            os.environ.pop("MY_TEST_KEY", None)

    def test_plain_key_value(self):
        """Lines with 'KEY=VALUE' (no export) are parsed correctly."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            env_file = Path(td) / "test.env"
            env_file.write_text("MY_PLAIN_KEY=world\n", encoding="utf-8")
            os.environ.pop("MY_PLAIN_KEY", None)
            n = _parse_env_file(env_file)
            self.assertEqual(n, 1)
            self.assertEqual(os.environ["MY_PLAIN_KEY"], "world")
            os.environ.pop("MY_PLAIN_KEY", None)

    def test_already_set_not_overwritten(self):
        """If key already in os.environ, it is NOT overwritten."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            env_file = Path(td) / "test.env"
            env_file.write_text("MY_EXISTING_KEY=newval\n", encoding="utf-8")
            os.environ["MY_EXISTING_KEY"] = "oldval"
            n = _parse_env_file(env_file)
            self.assertEqual(n, 0)
            self.assertEqual(os.environ["MY_EXISTING_KEY"], "oldval")
            os.environ.pop("MY_EXISTING_KEY", None)

    def test_quotes_stripped(self):
        """Surrounding single or double quotes are stripped."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            env_file = Path(td) / "test.env"
            env_file.write_text(
                'MY_QUOTED_KEY1="quoted_double"\n'
                "MY_QUOTED_KEY2='quoted_single'\n",
                encoding="utf-8",
            )
            os.environ.pop("MY_QUOTED_KEY1", None)
            os.environ.pop("MY_QUOTED_KEY2", None)
            n = _parse_env_file(env_file)
            self.assertEqual(n, 2)
            self.assertEqual(os.environ["MY_QUOTED_KEY1"], "quoted_double")
            self.assertEqual(os.environ["MY_QUOTED_KEY2"], "quoted_single")
            os.environ.pop("MY_QUOTED_KEY1", None)
            os.environ.pop("MY_QUOTED_KEY2", None)

    def test_comments_and_empty_lines_skipped(self):
        """Comments and empty lines are skipped."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            env_file = Path(td) / "test.env"
            env_file.write_text(
                "# this is a comment\n"
                "\n"
                "MY_COMMENT_KEY=val\n",
                encoding="utf-8",
            )
            os.environ.pop("MY_COMMENT_KEY", None)
            n = _parse_env_file(env_file)
            self.assertEqual(n, 1)
            self.assertEqual(os.environ["MY_COMMENT_KEY"], "val")
            os.environ.pop("MY_COMMENT_KEY", None)


class TestFormatAlert(unittest.TestCase):
    """Test format_alert output."""

    def test_format_with_new_items(self):
        diff = {
            "new": [
                {"bookmaker": "Fonbet", "title": "Welcome", "url": "https://x.ru"},
                {"bookmaker": "Liga", "title": "Freebet", "url": "https://y.ru"},
            ],
            "gone": [],
            "changed": [],
        }
        text = format_alert(diff)
        self.assertIn("🎁 <b>Bonus snapshot update</b>", text)
        self.assertIn("Новых: 2", text)
        self.assertIn("Пропало: 0", text)
        self.assertIn("Изменено: 0", text)

    def test_format_limits_to_five(self):
        new_items = [
            {"bookmaker": f"BK{i}", "title": f"T{i}", "url": f"http://u{i}"}
            for i in range(10)
        ]
        diff = {"new": new_items, "gone": [], "changed": []}
        text = format_alert(diff)
        # Should contain BK0..BK4 but not BK5
        self.assertIn("BK0", text)
        self.assertIn("BK4", text)
        self.assertNotIn("BK5", text)


class TestEmptyAdminIdReturns2(unittest.TestCase):
    """If TG_ADMIN_ID is empty after env load, main() returns 2."""

    @patch("scripts.bonus_cron._get_admin_ids", return_value=set())
    @patch("scripts.bonus_cron.load_env")
    def test_empty_admin_id(self, mock_load_env, mock_admin_ids):
        with patch.object(sys, "argv", ["bonus_cron.py"]):
            rc = main()
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
