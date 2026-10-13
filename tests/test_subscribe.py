"""tests/test_subscribe.py — Unit tests for Telegram Stars subscriber storage.

unittest + unittest.mock only, no network. Mock _save_subscribers / tg_post.
"""

import json
import os
import time
import unittest
from unittest.mock import patch, MagicMock

import tg_bot


class TestIsPremium(unittest.TestCase):
    """a) empty file -> False, b) expired -> False, c) active -> True"""

    @patch("tg_bot._load_subscribers", return_value={})
    def test_empty_file_returns_false(self, _mock_load):
        self.assertFalse(tg_bot.is_premium(12345))

    @patch("tg_bot._load_subscribers", return_value={
        "12345": {"expiry_ts": time.time() - 100, "paid_ts": 0,
                  "total_stars": 0, "purchase_count": 1}
    })
    def test_expired_returns_false(self, _mock_load):
        self.assertFalse(tg_bot.is_premium(12345))

    @patch("tg_bot._load_subscribers", return_value={
        "12345": {"expiry_ts": time.time() + 86400, "paid_ts": 0,
                  "total_stars": 0, "purchase_count": 1}
    })
    def test_active_returns_true(self, _mock_load):
        self.assertTrue(tg_bot.is_premium(12345))


class TestGrantPremium(unittest.TestCase):
    """d) fresh -> expiry ≈ now + 30d
       e) extend -> expiry = old_expiry + 30d
       f) purchase_count++, total_stars += stars
    """

    @patch("tg_bot._save_subscribers")
    @patch("tg_bot._load_subscribers", return_value={})
    def test_fresh_grant_expiry(self, _mock_load, mock_save):
        before = time.time()
        tg_bot.grant_premium(12345, days=30, stars=200)
        after = time.time()

        mock_save.assert_called_once()
        subs = mock_save.call_args[0][0]
        entry = subs["12345"]

        expected_low = before + 30 * 86400
        expected_high = after + 30 * 86400
        self.assertGreaterEqual(entry["expiry_ts"], expected_low)
        self.assertLessEqual(entry["expiry_ts"], expected_high)

    @patch("tg_bot._save_subscribers")
    @patch("tg_bot._load_subscribers")
    def test_extend_from_current_expiry(self, mock_load, mock_save):
        old_expiry = time.time() + 10 * 86400  # still active, 10d left
        mock_load.return_value = {
            "12345": {"expiry_ts": old_expiry, "paid_ts": 1000,
                      "total_stars": 100, "purchase_count": 1}
        }

        tg_bot.grant_premium(12345, days=30, stars=150)
        mock_save.assert_called_once()
        subs = mock_save.call_args[0][0]
        entry = subs["12345"]

        expected = old_expiry + 30 * 86400
        self.assertAlmostEqual(entry["expiry_ts"], expected, places=1)

    @patch("tg_bot._save_subscribers")
    @patch("tg_bot._load_subscribers")
    def test_purchase_count_and_stars(self, mock_load, mock_save):
        mock_load.return_value = {
            "12345": {"expiry_ts": time.time() + 86400, "paid_ts": 1000,
                      "total_stars": 100, "purchase_count": 2}
        }

        tg_bot.grant_premium(12345, days=30, stars=250)
        subs = mock_save.call_args[0][0]
        entry = subs["12345"]

        self.assertEqual(entry["purchase_count"], 3)
        self.assertEqual(entry["total_stars"], 350)

    @patch("tg_bot._save_subscribers")
    @patch("tg_bot._load_subscribers", return_value={})
    def test_fresh_purchase_count_and_stars(self, mock_load, mock_save):
        tg_bot.grant_premium(99999, days=30, stars=200)
        subs = mock_save.call_args[0][0]
        entry = subs["99999"]

        self.assertEqual(entry["purchase_count"], 1)
        self.assertEqual(entry["total_stars"], 200)


class TestSaveSubscribers(unittest.TestCase):
    """g) _save_subscribers: atomic write — os.replace is called"""

    @patch("os.replace")
    def test_atomic_write_calls_os_replace(self, mock_replace):
        import tempfile as tf
        real_dir = tf.mkdtemp()
        target = os.path.join(real_dir, "subscribers.json")
        try:
            with patch.object(tg_bot, "_SUBSCRIBERS_FILE",
                              type("", (), {
                                  "parent": type("", (), {
                                      "mkdir": MagicMock(),
                                      "__str__": lambda s: real_dir,
                                      "__truediv__": lambda s, o: None,
                                  })(),
                                  "exists": lambda s: False,
                                  "__str__": lambda s: target,
                              })()):
                data = {"12345": {"expiry_ts": 9999999999, "paid_ts": 1000,
                                  "total_stars": 200, "purchase_count": 1}}
                tg_bot._save_subscribers(data)

                mock_replace.assert_called_once()
                # First arg of os.replace is the tmp path, second is the target
                call_args = mock_replace.call_args[0]
                self.assertEqual(call_args[1], target)
        finally:
            # Cleanup
            for f in os.listdir(real_dir):
                try:
                    os.unlink(os.path.join(real_dir, f))
                except OSError:
                    pass
            try:
                os.rmdir(real_dir)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
