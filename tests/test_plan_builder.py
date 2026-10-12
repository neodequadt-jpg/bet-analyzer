"""Tests for scoring/plan_builder — unittest + unittest.mock, no network."""
import unittest
from unittest.mock import patch

from scoring.bonus_tracker import Bonus
from scoring.matched_betting import LayResult
from scoring.plan_builder import (
    Plan,
    list_candidates,
    build_plan,
    format_plan,
    format_candidates,
    format_lay_prompt,
)


def _bonus(**kw):
    """Build a Bonus with sensible defaults, override as needed."""
    defaults = dict(
        bookmaker="PARI", type="SNR", amount=1000,
        min_odds=1.5, max_odds=5.0,
        expiry="31.12", status="active",
    )
    defaults.update(kw)
    return Bonus(**defaults)


def _signal(**kw):
    """Build a signal dict with sensible defaults."""
    defaults = dict(
        event="Rostov vs Akron", outcome="away", odds=4.81,
        bookmaker="PARI", league="RPL", kickoff="09.10 19:30",
        ev=0.0818, kelly=0.0215,
    )
    defaults.update(kw)
    return defaults


def _lay_result(**kw):
    defaults = dict(
        lay_stake=100.0, liability=200.0,
        profit_if_back=150.0, profit_if_lay=50.0,
        guaranteed=50.0,
    )
    defaults.update(kw)
    return LayResult(**defaults)


# ── list_candidates ──────────────────────────────────────────────

class TestListCandidatesFiltersByOddsRange(unittest.TestCase):
    """Only signals whose odds fall within [bonus.min_odds, bonus.max_odds]."""

    def test_filters_and_boundary_inclusive(self):
        b = _bonus(min_odds=2.0, max_odds=5.0)
        sigs = [
            _signal(odds=3.0),   # inside
            _signal(odds=1.5),   # below
            _signal(odds=5.5),   # above
            _signal(odds=2.0),   # boundary low
            _signal(odds=5.0),   # boundary high
        ]
        result = list_candidates(b, signals=sigs)
        odds = [s["odds"] for s in result]
        self.assertIn(3.0, odds)
        self.assertIn(2.0, odds)
        self.assertIn(5.0, odds)
        self.assertNotIn(1.5, odds)
        self.assertNotIn(5.5, odds)


class TestListCandidatesSortsByEvDesc(unittest.TestCase):
    """Signals sorted by ev descending."""

    def test_sort(self):
        b = _bonus(min_odds=1.0, max_odds=100.0)
        sigs = [_signal(ev=0.02), _signal(ev=0.10), _signal(ev=0.05)]
        result = list_candidates(b, signals=sigs)
        evs = [s["ev"] for s in result]
        self.assertEqual(evs, sorted(evs, reverse=True))


class TestListCandidatesEmptyWhenNothingInRange(unittest.TestCase):
    """Empty list when no signal fits the odds range."""

    def test_empty(self):
        b = _bonus(min_odds=10.0, max_odds=20.0)
        sigs = [_signal(odds=3.0), _signal(odds=5.0)]
        result = list_candidates(b, signals=sigs)
        self.assertEqual(result, [])


# ── build_plan ───────────────────────────────────────────────────

class TestBuildPlanFieldsMatchInputs(unittest.TestCase):
    """Plan fields mirror the bonus and signal passed in."""

    @patch("scoring.plan_builder.calc_lay")
    def test_fields(self, mock_calc):
        fake = _lay_result()
        mock_calc.return_value = fake
        b = _bonus()
        s = _signal()
        plan = build_plan(b, s, lay_odds=5.0, commission=0.03)

        self.assertEqual(plan.bonus_bookmaker, b.bookmaker)
        self.assertEqual(plan.bonus_amount, float(b.amount))
        self.assertEqual(plan.bonus_type, b.type)
        self.assertEqual(plan.bonus_expiry, b.expiry)
        self.assertEqual(plan.bonus_min_odds, float(b.min_odds))
        self.assertEqual(plan.bonus_max_odds, float(b.max_odds))
        self.assertEqual(plan.event, s["event"])
        self.assertEqual(plan.outcome, s["outcome"])
        self.assertAlmostEqual(plan.back_odds, s["odds"])
        self.assertEqual(plan.back_bookmaker, s["bookmaker"])
        self.assertEqual(plan.league, s["league"])
        self.assertEqual(plan.kickoff, s["kickoff"])
        self.assertAlmostEqual(plan.ev, s["ev"])
        self.assertAlmostEqual(plan.lay_odds, 5.0)
        self.assertAlmostEqual(plan.lay_commission, 0.03)
        self.assertIs(plan.calc, fake)
        mock_calc.assert_called_once_with(b.amount, s["odds"], 5.0, 0.03)


class TestBuildPlanRoiPct(unittest.TestCase):
    """roi_pct = calc.guaranteed / bonus_amount * 100."""

    @patch("scoring.plan_builder.calc_lay")
    def test_roi(self, mock_calc):
        fake = _lay_result(guaranteed=120.0)
        mock_calc.return_value = fake
        b = _bonus(amount=500)
        s = _signal()
        plan = build_plan(b, s, lay_odds=5.0)

        expected = 120.0 / 500.0 * 100
        self.assertAlmostEqual(plan.roi_pct, expected)


# ── format_plan ──────────────────────────────────────────────────

class TestFormatPlanContainsSections(unittest.TestCase):
    """Output contains БОНУС, BACK, LAY, РЕЗУЛЬТАТ section headers."""

    def test_sections(self):
        lr = _lay_result()
        plan = Plan(
            bonus_bookmaker="PARI", bonus_amount=1000, bonus_type="SNR",
            bonus_expiry="31.12", bonus_min_odds=1.5, bonus_max_odds=5.0,
            event="Rostov vs Akron", outcome="away", back_odds=4.81,
            back_bookmaker="PARI", league="RPL", kickoff="09.10 19:30",
            ev=0.0818, lay_odds=5.0, lay_commission=0.02, calc=lr,
        )
        text = format_plan(plan)
        self.assertIn("БОНУС", text)
        self.assertIn("BACK", text)
        self.assertIn("LAY", text)
        self.assertIn("РЕЗУЛЬТАТ", text)


# ── format_candidates ────────────────────────────────────────────

class TestFormatCandidatesEmptyMessage(unittest.TestCase):
    """When cands is empty, output mentions 'нет событий в диапазоне'."""

    def test_empty(self):
        b = _bonus()
        text = format_candidates(b, [])
        self.assertIn("нет событий в диапазоне", text)


class TestFormatCandidatesNumbered(unittest.TestCase):
    """Candidates are numbered 1., 2., …"""

    def test_numbered(self):
        b = _bonus()
        cands = [_signal(ev=0.10), _signal(ev=0.05)]
        text = format_candidates(b, cands)
        self.assertIn("<b>1.</b>", text)
        self.assertIn("<b>2.</b>", text)


# ── format_lay_prompt ────────────────────────────────────────────

class TestFormatLayPromptContainsCommand(unittest.TestCase):
    """Output contains /plan_go command template."""

    def test_command(self):
        b = _bonus()
        s = _signal()
        text = format_lay_prompt(b, s, idx=3)
        self.assertIn("/plan_go", text)
        self.assertIn("PARI", text)
        self.assertIn("3", text)


if __name__ == "__main__":
    unittest.main()
