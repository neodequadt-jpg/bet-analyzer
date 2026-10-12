"""Tests for scoring.bonus_monitor – no network, unittest + unittest.mock."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scoring.bonus_monitor import (
    Bonus,
    fetch_bonuses,
    normalize,
    snapshot_diff,
    save_snapshot,
    load_snapshot,
)


class TestNormalizeExtractsAmount(unittest.TestCase):
    def test_rubles_with_spaces(self):
        raw = {"id": "1", "name": "Welcome", "bonus_text": "10 000 ₽"}
        b = normalize(raw)
        self.assertEqual(b.amount_rub, 10000)

    def test_rubles_no_spaces(self):
        raw = {"id": "2", "name": "Small", "bonus_text": "500₽"}
        b = normalize(raw)
        self.assertEqual(b.amount_rub, 500)

    def test_no_amount(self):
        raw = {"id": "3", "name": "NoAmt", "bonus_text": "Free spin"}
        b = normalize(raw)
        self.assertIsNone(b.amount_rub)


class TestNormalizeHandlesNonePromo(unittest.TestCase):
    def test_promo_is_none(self):
        raw = {"id": "10", "name": "X", "promo": None}
        b = normalize(raw)
        self.assertEqual(b.bookmaker, "unknown")

    def test_promo_missing(self):
        raw = {"id": "11", "name": "Y"}
        b = normalize(raw)
        self.assertEqual(b.bookmaker, "unknown")

    def test_promo_empty_dict(self):
        raw = {"id": "12", "name": "Z", "promo": {}}
        b = normalize(raw)
        self.assertEqual(b.bookmaker, "unknown")


class TestNormalizeBookmakerFromAnalyticsName(unittest.TestCase):
    def test_analytics_name_takes_precedence(self):
        raw = {
            "id": "20",
            "name": "Bonus",
            "promo": {
                "bookmaker": {"id": "fallback-bk"},
                "analytics_data": {"bookmaker_name": "Fonbet"},
            },
        }
        b = normalize(raw)
        self.assertEqual(b.bookmaker, "Fonbet")

    def test_fallback_to_bookmaker_id(self):
        raw = {
            "id": "21",
            "name": "Bonus",
            "promo": {
                "bookmaker": {"id": "League"},
                "analytics_data": {},
            },
        }
        b = normalize(raw)
        self.assertEqual(b.bookmaker, "League")


class TestSnapshotDiffNew(unittest.TestCase):
    def test_new_bonus(self):
        cur = [Bonus(id="1", bookmaker="A", title="T", amount_rub=100,
                     promo_code=None, url="http://x", verified=False,
                     expired=False, end_date=None)]
        prev: list[Bonus] = []
        diff = snapshot_diff(cur, prev)
        self.assertEqual(len(diff["new"]), 1)
        self.assertEqual(diff["new"][0]["id"], "1")
        self.assertEqual(len(diff["gone"]), 0)
        self.assertEqual(len(diff["changed"]), 0)


class TestSnapshotDiffGone(unittest.TestCase):
    def test_gone_bonus(self):
        cur: list[Bonus] = []
        prev = [Bonus(id="2", bookmaker="B", title="T", amount_rub=200,
                      promo_code=None, url="http://y", verified=False,
                      expired=False, end_date=None)]
        diff = snapshot_diff(cur, prev)
        self.assertEqual(len(diff["gone"]), 1)
        self.assertEqual(diff["gone"][0]["id"], "2")
        self.assertEqual(len(diff["new"]), 0)
        self.assertEqual(len(diff["changed"]), 0)


class TestSnapshotDiffChanged(unittest.TestCase):
    def test_amount_changed(self):
        cur = [Bonus(id="3", bookmaker="C", title="T", amount_rub=999,
                     promo_code=None, url="http://z", verified=False,
                     expired=False, end_date=None)]
        prev = [Bonus(id="3", bookmaker="C", title="T", amount_rub=500,
                      promo_code=None, url="http://z", verified=False,
                      expired=False, end_date=None)]
        diff = snapshot_diff(cur, prev)
        self.assertEqual(len(diff["changed"]), 1)
        self.assertEqual(diff["changed"][0]["id"], "3")
        self.assertEqual(diff["changed"][0]["fields"]["amount_rub"]["prev"], 500)
        self.assertEqual(diff["changed"][0]["fields"]["amount_rub"]["cur"], 999)

    def test_no_change(self):
        b = Bonus(id="4", bookmaker="D", title="T", amount_rub=100,
                  promo_code=None, url="http://w", verified=False,
                  expired=False, end_date=None)
        diff = snapshot_diff([b], [b])
        self.assertEqual(len(diff["changed"]), 0)


class TestDedupById(unittest.TestCase):
    """fetch_bonuses deduplicates by id — verify via mock."""

    @patch("scoring.bonus_monitor._session")
    def test_dedup_removes_duplicates(self, mock_session_cls: MagicMock):
        # Build fake HTML with __NEXT_DATA__ containing duplicate ids
        raw_items = [
            {"id": 100, "name": "A"},
            {"id": 100, "name": "A-dup"},
            {"id": 200, "name": "B"},
        ]
        next_data = {
            "props": {
                "pageProps": {
                    "bonuses": raw_items,
                    "bonusSliders": [],
                }
            }
        }
        html = (
            '<html><script id="__NEXT_DATA__">'
            + json.dumps(next_data)
            + '</script></html>'
        )
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        mock_sess = MagicMock()
        mock_sess.get.return_value = mock_resp
        mock_session_cls.return_value = mock_sess

        result = fetch_bonuses()
        ids = [item["id"] for item in result]
        self.assertEqual(ids, [100, 200])
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
