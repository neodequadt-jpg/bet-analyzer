"""Unit tests for scoring.matched_betting — no network, pure math."""

import math
import unittest

from scoring.matched_betting import LayResult, calc_lay, find_optimal


class TestCalcLay(unittest.TestCase):
    """Tests for calc_lay (SNR free-bet calculator)."""

    # ------------------------------------------------------------------
    # Known example
    # ------------------------------------------------------------------
    def test_calc_lay_snr_known_example(self) -> None:
        """Hand-verified SNR example: free_bet=10000, back=2.0, lay=2.05, comm=0.02."""
        r = calc_lay(10000, 2.0, 2.05, 0.02)
        self.assertAlmostEqual(r.lay_stake, 4926.11, places=1)
        self.assertAlmostEqual(r.liability, 5172.41, places=1)
        self.assertAlmostEqual(r.guaranteed, 4827.59, places=1)

    # ------------------------------------------------------------------
    # Equilibrium property
    # ------------------------------------------------------------------
    def test_profit_back_equals_profit_lay_at_equilibrium(self) -> None:
        """At equilibrium lay_odds the two profit branches are equal."""
        free_bet = 5000
        back_odds = 3.0
        commission = 0.05
        # Equilibrium: lay_odds = (back_odds - 1 + commission) / (1 - commission)
        lay_odds_eq = (back_odds - 1 + commission) / (1 - commission)
        r = calc_lay(free_bet, back_odds, lay_odds_eq, commission)
        self.assertAlmostEqual(r.profit_if_back, r.profit_if_lay, places=6)

    # ------------------------------------------------------------------
    # Zero commission
    # ------------------------------------------------------------------
    def test_calc_lay_zero_commission(self) -> None:
        """With commission=0 the formulas simplify cleanly."""
        r = calc_lay(1000, 2.5, 2.6, 0.0)
        expected_lay_stake = 1000 * (2.5 - 1) / 2.6
        self.assertAlmostEqual(r.lay_stake, expected_lay_stake, places=6)
        expected_liability = expected_lay_stake * (2.6 - 1)
        self.assertAlmostEqual(r.liability, expected_liability, places=6)
        # With zero commission profit_if_lay == lay_stake
        self.assertAlmostEqual(r.profit_if_lay, expected_lay_stake, places=6)

    # ------------------------------------------------------------------
    # Custom commission (e.g. Betfair 5 %)
    # ------------------------------------------------------------------
    def test_calc_lay_custom_commission(self) -> None:
        """Betfair-style 5 % commission."""
        r = calc_lay(2000, 1.8, 1.85, 0.05)
        expected_lay_stake = 2000 * (1.8 - 1) / (1.85 - 0.05)
        self.assertAlmostEqual(r.lay_stake, expected_lay_stake, places=4)
        self.assertGreater(r.guaranteed, 0)

    # ------------------------------------------------------------------
    # Validation — back_odds
    # ------------------------------------------------------------------
    def test_invalid_back_odds_raises(self) -> None:
        """back_odds <= 1 must raise ValueError."""
        with self.assertRaises(ValueError):
            calc_lay(100, 1.0, 2.0)
        with self.assertRaises(ValueError):
            calc_lay(100, 0.5, 2.0)

    # ------------------------------------------------------------------
    # Validation — lay_odds
    # ------------------------------------------------------------------
    def test_invalid_lay_odds_raises(self) -> None:
        """lay_odds <= 1 must raise ValueError."""
        with self.assertRaises(ValueError):
            calc_lay(100, 2.0, 1.0)
        with self.assertRaises(ValueError):
            calc_lay(100, 2.0, 0.9)

    # ------------------------------------------------------------------
    # Validation — free_bet
    # ------------------------------------------------------------------
    def test_invalid_free_bet_raises(self) -> None:
        """free_bet <= 0 must raise ValueError."""
        with self.assertRaises(ValueError):
            calc_lay(0, 2.0, 2.1)
        with self.assertRaises(ValueError):
            calc_lay(-500, 2.0, 2.1)

    # ------------------------------------------------------------------
    # Validation — commission
    # ------------------------------------------------------------------
    def test_invalid_commission_raises(self) -> None:
        """commission >= 1 or < 0 must raise ValueError."""
        with self.assertRaises(ValueError):
            calc_lay(100, 2.0, 2.1, 1.0)
        with self.assertRaises(ValueError):
            calc_lay(100, 2.0, 2.1, -0.01)

    # ------------------------------------------------------------------
    # find_optimal — finds minimum-guaranteed-maximising lay_odds
    # ------------------------------------------------------------------
    def test_find_optimal_finds_min_in_range(self) -> None:
        """find_optimal must match a manual brute-force scan."""
        free_bet = 10000
        back_odds = 2.0
        commission = 0.02
        lo, hi = 1.90, 2.20

        # Manual scan
        best_g = -math.inf
        best_odds = lo
        step = 0.01
        steps = round((hi - lo) / step)
        for i in range(steps + 1):
            lay_odds = round(lo + i * step, 10)
            if lay_odds > hi or lay_odds <= 1:
                continue
            r = calc_lay(free_bet, back_odds, lay_odds, commission)
            if r.guaranteed > best_g:
                best_g = r.guaranteed
                best_odds = lay_odds

        optimal = find_optimal(free_bet, back_odds, (lo, hi), commission)
        self.assertAlmostEqual(optimal.guaranteed, best_g, places=4)

    # ------------------------------------------------------------------
    # find_optimal — empty / invalid range
    # ------------------------------------------------------------------
    def test_find_optimal_empty_range_raises_or_handles(self) -> None:
        """An inverted or empty range must raise ValueError."""
        with self.assertRaises(ValueError):
            find_optimal(1000, 2.0, (2.10, 2.05))  # lo > hi


if __name__ == "__main__":
    unittest.main()
