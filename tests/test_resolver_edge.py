"""Edge-case tests for scoring/resolver.py.

Covers boundary conditions NOT covered in tests/test_resolver.py.
No network. Pure logic functions only.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scoring.resolver import (
    _normalize,
    _parse_kickoff,
    _determine_result,
    _find_match,
)


class TestNormalizeEdge(unittest.TestCase):
    def test_empty_and_none(self):
        self.assertEqual(_normalize(""), "")
        self.assertEqual(_normalize("   "), "")
        self.assertEqual(_normalize(None), "")

    def test_whitespace_around_known_country(self):
        self.assertEqual(_normalize("  Россия  "), "russia")

    def test_unknown_country_lowercased(self):
        self.assertEqual(_normalize("Казахстан"), "казахстан")

    def test_alias_bosnia(self):
        # короткая форма мапится в полное название
        self.assertEqual(_normalize("босния"), "bosnia and herzegovina")


class TestParseKickoffEdge(unittest.TestCase):
    def test_extremes(self):
        ts1 = _parse_kickoff("01.01 00:00")
        ts2 = _parse_kickoff("31.12 23:59")
        self.assertIsNotNone(ts1)
        self.assertIsNotNone(ts2)
        self.assertLess(ts1, ts2)

    def test_invalid_date(self):
        self.assertIsNone(_parse_kickoff("32.13 25:61"))

    def test_missing_space(self):
        self.assertIsNone(_parse_kickoff("26.0921:45"))

    def test_empty(self):
        self.assertIsNone(_parse_kickoff(""))
        self.assertIsNone(_parse_kickoff(None))

    def test_double_space_is_ok(self):
        # ВАЖНО: код использует .strip().split() — нормализует
        self.assertIsNotNone(_parse_kickoff("26.09  21:45"))

    def test_trailing_space_is_ok(self):
        self.assertIsNotNone(_parse_kickoff("26.09 21:45 "))


class TestDetermineResultEdge(unittest.TestCase):
    def test_int_values(self):
        self.assertEqual(_determine_result({"intHomeScore": 2, "intAwayScore": 1}), "home")
        self.assertEqual(_determine_result({"intHomeScore": 0, "intAwayScore": 0}), "draw")
        self.assertEqual(_determine_result({"intHomeScore": 1, "intAwayScore": 3}), "away")

    def test_string_values(self):
        self.assertEqual(_determine_result({"intHomeScore": "2", "intAwayScore": "1"}), "home")

    def test_missing_keys(self):
        self.assertIsNone(_determine_result({}))
        self.assertIsNone(_determine_result({"intHomeScore": 1}))

    def test_non_numeric(self):
        self.assertIsNone(_determine_result({"intHomeScore": "abc", "intAwayScore": "2"}))

    def test_empty_strings(self):
        self.assertIsNone(_determine_result({"intHomeScore": "", "intAwayScore": ""}))


class TestFindMatchEdge(unittest.TestCase):
    def test_exact_russian_to_english(self):
        events = [{"strHomeTeam": "Slovakia", "strAwayTeam": "Moldova"}]
        m = _find_match(events, "Словакия", "Молдова")
        self.assertIsNotNone(m)
        self.assertEqual(m["strHomeTeam"], "Slovakia")

    def test_returns_first_match(self):
        events = [
            {"strHomeTeam": "Germany", "strAwayTeam": "Greece", "id": "first"},
            {"strHomeTeam": "Germany", "strAwayTeam": "Greece", "id": "second"},
        ]
        m = _find_match(events, "Германия", "Греция")
        self.assertEqual(m["id"], "first")

    def test_case_insensitive(self):
        events = [{"strHomeTeam": "SLOVAKIA", "strAwayTeam": "MOLDOVA"}]
        self.assertIsNotNone(_find_match(events, "Словакия", "Молдова"))

    def test_whitespace_tolerant(self):
        events = [{"strHomeTeam": "  Slovakia  ", "strAwayTeam": "Moldova"}]
        self.assertIsNotNone(_find_match(events, "Словакия", "Молдова"))

    def test_no_match_returns_none(self):
        events = [{"strHomeTeam": "Germany", "strAwayTeam": "Greece"}]
        self.assertIsNone(_find_match(events, "Россия", "Украина"))


if __name__ == "__main__":
    unittest.main()
