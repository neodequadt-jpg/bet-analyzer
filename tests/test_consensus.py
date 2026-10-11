"""Unit tests for market/consensus.py — pure logic, no network."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market.consensus import (
    _implied_prob,
    _remove_margin,
    _consensus_from_subset,
)


class TestImpliedProb(unittest.TestCase):
    def test_normal_odds(self):
        self.assertAlmostEqual(_implied_prob(2.0), 0.5, places=6)
        self.assertAlmostEqual(_implied_prob(4.0), 0.25, places=6)

    def test_invalid_odds(self):
        self.assertEqual(_implied_prob(None), 0.0)
        self.assertEqual(_implied_prob(0), 0.0)
        self.assertEqual(_implied_prob(1.0), 0.0)
        self.assertEqual(_implied_prob(0.5), 0.0)


class TestRemoveMargin(unittest.TestCase):
    def test_normalizes(self):
        out = _remove_margin([0.5, 0.5, 0.5])
        self.assertAlmostEqual(sum(out), 1.0, places=6)
        for p in out:
            self.assertAlmostEqual(p, 1.0 / 3.0, places=6)

    def test_zero_total_returns_unchanged(self):
        self.assertEqual(_remove_margin([0.0, 0.0, 0.0]), [0.0, 0.0, 0.0])

    def test_single_prob_normalized_to_one(self):
        self.assertEqual(_remove_margin([0.5]), [1.0])


class TestConsensusFromSubset(unittest.TestCase):
    def test_three_way_median(self):
        # 3 bookmakers, 3-way market, fair odds (no margin)
        # h=2.0 -> 0.5; d=4.0 -> 0.25; a=4.0 -> 0.25
        subset = {
            "bk1": (2.0, 4.0, 4.0),
            "bk2": (2.0, 4.0, 4.0),
            "bk3": (2.0, 4.0, 4.0),
        }
        prob, conf, sources = _consensus_from_subset(subset, "home")
        self.assertEqual(sources, 3)
        self.assertAlmostEqual(prob, 0.5, places=6)
        self.assertGreater(conf, 0.0)

    def test_three_way_skips_none_rows(self):
        subset = {
            "bk1": (2.0, 4.0, 4.0),
            "bk2": (None, None, None),
            "bk3": (2.0, 4.0, 4.0),
        }
        prob, conf, sources = _consensus_from_subset(subset, "home")
        self.assertEqual(sources, 2)

    def test_two_way_skips_draw_outcome(self):
        # 2-way market: draw=None, outcome=draw → skip
        subset = {
            "bk1": (2.0, None, 2.0),
            "bk2": (2.0, None, 2.0),
        }
        prob, conf, sources = _consensus_from_subset(subset, "draw")
        self.assertEqual(sources, 0)
        self.assertEqual(prob, 0.0)

    def test_empty_subset(self):
        prob, conf, sources = _consensus_from_subset({}, "home")
        self.assertEqual((prob, conf, sources), (0.0, 0.0, 0))


if __name__ == "__main__":
    unittest.main()
