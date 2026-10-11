"""Unit tests for build_consensus / evaluate_event with mocked OddsEvent.

No network, no live data. Uses OddsEvent from bookmakers.parser.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bookmakers.parser import OddsEvent
from market.consensus import build_consensus, evaluate_event


def make_event(bk, h, d, a, home="Зенит", away="Спартак"):
    return OddsEvent(
        event_id="test_event",
        sport="football",
        league="RPL",
        home=home,
        away=away,
        kickoff_iso="2026-09-15T19:00:00+03:00",
        bookmaker=bk,
        odds_home=h,
        odds_draw=d,
        odds_away=a,
        odds_total_over=None,
        odds_total_under=None,
        total_line=None,
    )


class TestBuildConsensus(unittest.TestCase):
    def test_empty_events(self):
        self.assertEqual(build_consensus([]), {})

    def test_three_way_consensus(self):
        events = [
            make_event("Фонбет", 2.0, 4.0, 4.0),
            make_event("Винлайн", 2.0, 4.0, 4.0),
        ]
        result = build_consensus(events)
        self.assertIn("home", result)
        self.assertIn("draw", result)
        self.assertIn("away", result)
        self.assertEqual(result["home"].sources, 2)
        self.assertAlmostEqual(result["home"].consensus_prob, 0.5, places=4)
        self.assertAlmostEqual(result["home"].consensus_odds, 2.0, places=2)

    def test_two_way_no_draw(self):
        events = [
            make_event("Фонбет", 2.0, None, 2.0),
            make_event("Винлайн", 2.0, None, 2.0),
        ]
        result = build_consensus(events)
        self.assertIn("home", result)
        self.assertIn("away", result)
        self.assertNotIn("draw", result)

    def test_odds_map_populated(self):
        events = [
            make_event("Фонбет", 2.0, 4.0, 4.0),
            make_event("Винлайн", 2.0, 4.0, 4.0),
        ]
        result = build_consensus(events)
        home_map = result["home"].bookmaker_odds
        self.assertEqual(home_map.get("Фонбет"), 2.0)
        self.assertEqual(home_map.get("Винлайн"), 2.0)


class TestEvaluateEvent(unittest.TestCase):
    def test_no_data(self):
        self.assertEqual(evaluate_event([]), {"status": "no_data"})

    def test_status_ok_shape(self):
        events = [
            make_event("Фонбет", 2.0, 4.0, 4.0),
            make_event("Винлайн", 2.0, 4.0, 4.0),
        ]
        out = evaluate_event(events)
        self.assertEqual(out["status"], "ok")
        self.assertIn("event", out)
        self.assertIn("consensus", out)
        self.assertIn("best_odds", out)
        self.assertEqual(out["event"]["home"], "Зенит")
        self.assertEqual(out["event"]["away"], "Спартак")

    def test_exchange_excluded_from_best_odds(self):
        events = [
            make_event("Фонбет", 2.0, 4.0, 4.0),
            make_event("Smarkets", 2.1, 4.1, 4.1),  # биржа — исключается
        ]
        out = evaluate_event(events)
        self.assertEqual(out["status"], "ok")
        # best_odds должен использовать Фонбет (легальный), не Smarkets
        for outcome, info in out["best_odds"].items():
            self.assertNotEqual(
                info["bookmaker"], "Smarkets",
                f"exchange leaked into best_odds[{outcome}]",
            )


if __name__ == "__main__":
    unittest.main()
