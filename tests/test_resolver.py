import unittest
from scoring.resolver import COUNTRY_MAP, _normalize, _determine_result, _find_match

class TestResolver(unittest.TestCase):
    def test_country_map_has_key_teams(self):
        # TEAM_ALIASES keys are lowercase
        self.assertIn("грузия", COUNTRY_MAP)
        self.assertIn("германия", COUNTRY_MAP)
        
    def test_normalize_team(self):
        self.assertEqual(_normalize("Германия"), "germany")
        self.assertEqual(_normalize("Unknown Team"), "unknown team")
        
    def test_determine_result_home_win(self):
        self.assertEqual(_determine_result({"intHomeScore":"2","intAwayScore":"1"}), "home")
        self.assertEqual(_determine_result({"intHomeScore":"1","intAwayScore":"1"}), "draw")
        self.assertEqual(_determine_result({"intHomeScore":"0","intAwayScore":"2"}), "away")
        self.assertIsNone(_determine_result({"intHomeScore":"?","intAwayScore":"?"}))
        
    def test_find_match_exact(self):
        events = [{"strHomeTeam":"Germany","strAwayTeam":"Greece","intHomeScore":"2","intAwayScore":"1"}]
        m = _find_match(events, "Германия", "Греция")
        self.assertIsNotNone(m)
