"""Tests for scoring/resolver.py."""
import unittest


class TestResolverHelpers(unittest.TestCase):
    def test_parse_kickoff_valid(self):
        from scoring.resolver import _parse_kickoff
        ts = _parse_kickoff("26.09 21:45")
        self.assertIsNotNone(ts)
        self.assertGreater(ts, 1700000000)

    def test_parse_kickoff_invalid(self):
        from scoring.resolver import _parse_kickoff
        self.assertIsNone(_parse_kickoff(""))
        self.assertIsNone(_parse_kickoff("garbage"))

    def test_determine_result(self):
        from scoring.resolver import _determine_result
        self.assertEqual(_determine_result({"intHomeScore": "2", "intAwayScore": "1"}), "home")
        self.assertEqual(_determine_result({"intHomeScore": "1", "intAwayScore": "1"}), "draw")
        self.assertEqual(_determine_result({"intHomeScore": "0", "intAwayScore": "2"}), "away")
        self.assertIsNone(_determine_result({"intHomeScore": None, "intAwayScore": None}))

    def test_normalize_team(self):
        from scoring.resolver import _normalize
        self.assertEqual(_normalize("Германия"), "germany")
        self.assertEqual(_normalize("Словакия"), "slovakia")
        self.assertEqual(_normalize("Unknown"), "unknown")

    def test_find_match_exact(self):
        from scoring.resolver import _find_match
        events = [{"strHomeTeam": "Germany", "strAwayTeam": "Greece",
                   "intHomeScore": "2", "intAwayScore": "1"}]
        m = _find_match(events, "Германия", "Греция")
        self.assertIsNotNone(m)

    def test_find_match_missing(self):
        from scoring.resolver import _find_match
        events = [{"strHomeTeam": "Germany", "strAwayTeam": "Greece"}]
        self.assertIsNone(_find_match(events, "Словакия", "Молдова"))

    def test_resolve_all_shape(self):
        import tempfile
        import pathlib
        from unittest.mock import patch
        import scoring.resolver as resolver_mod

        with tempfile.TemporaryDirectory() as td:
            empty_signals = pathlib.Path(td) / "signals"
            empty_results = pathlib.Path(td) / "results"
            empty_signals.mkdir()
            empty_results.mkdir()
            with patch.object(resolver_mod, "SIGNALS_DIR", empty_signals), \
                 patch.object(resolver_mod, "RESULTS_DIR", empty_results):
                r = resolver_mod.resolve_all()

        for k in ("checked", "resolved", "won", "lost", "pending", "skipped"):
            self.assertIn(k, r)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestResolvedStats(unittest.TestCase):
    def test_shape(self):
        from scoring.tracker import resolved_stats
        s = resolved_stats()
        for k in ("total", "pending", "resolved", "won", "lost",
                  "winrate", "roi", "profit", "staked"):
            self.assertIn(k, s)

    def test_empty_zero_roi(self):
        from scoring.tracker import resolved_stats
        s = resolved_stats()
        if s["resolved"] == 0:
            self.assertEqual(s["roi"], 0)
