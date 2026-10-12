"""Tests for providers.footbolno — unit tests, no real network."""
import io
import json
import os
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from providers.footbolno import (
    FootbolnoProvider,
    Match,
    _normalize_name,
    _safe_int,
)

CSV_HEADER = (
    "match_id,league_id,league,season,date_utc,date_msk,time_confirmed,round,"
    "home_id,home,away_id,away,home_goals,away_goals,home_pens,away_pens,"
    "status,venue,venue_ru,city,city_ru,attendance"
)

CSV_ROW_1 = (
    "1,235,РПЛ,2026/2027,2026-10-09T19:30:00Z,2026-10-09T22:30:00,1,10,"
    "espn:3852,Ростов,espn:22271,Акрон,1,0,,,finished,,,,,"
)
CSV_ROW_2 = (
    "2,235,РПЛ,2026/2027,2026-10-10T14:00:00Z,2026-10-10T17:00:00,1,11,"
    "espn:21539,Факел,espn:442,Локомотив,0,5,,,finished,,,,,"
)

CSV_BODY = "\n".join([CSV_HEADER, CSV_ROW_1, CSV_ROW_2]) + "\n"


def make_response(text: str, status_code: int = 200):
    """Build a mock requests.Response with correct UTF-8 encoding story."""
    r = mock.Mock()
    r.status_code = status_code
    r.content = text.encode("utf-8")
    r.text = text
    r.encoding = None  # сервер не отдаёт charset — код должен сам выставить utf-8
    return r


class TestNormalize(unittest.TestCase):
    def test_yo_to_ye(self):
        self.assertEqual(_normalize_name("Ёлка"), "елка")

    def test_strip_fk_prefix(self):
        self.assertEqual(_normalize_name("ФК Локомотив"), "локомотив")

    def test_hyphen_to_space(self):
        self.assertEqual(_normalize_name("Локомотив-Москва"), "локомотив москва")

    def test_collapse_whitespace(self):
        self.assertEqual(_normalize_name("  Спартак  "), "спартак")


class TestSafeInt(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(_safe_int("5"), 5)

    def test_empty(self):
        self.assertIsNone(_safe_int(""))

    def test_na(self):
        self.assertIsNone(_safe_int("NA"))

    def test_garbage(self):
        self.assertIsNone(_safe_int("x"))


if __name__ == "__main__":
    unittest.main()


class TestFetchParsing(unittest.TestCase):
    def setUp(self):
        self.tmp = mock.MagicMock()
        self.tmp.name = os.path.join("/tmp", f"fb-test-{os.getpid()}-{int(time.time()*1000)}")
        os.makedirs(self.tmp.name, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp.name, ignore_errors=True)

    def test_parses_two_matches(self):
        with mock.patch("requests.Session.get", return_value=make_response(CSV_BODY)) as g:
            p = FootbolnoProvider(cache_dir=self.tmp.name, ttl=9999)
            matches = p.fetch_league(235)
        self.assertEqual(len(matches), 2)
        m = matches[0]
        self.assertEqual(m.date_iso, "2026-10-09")
        self.assertEqual(m.home_id, "espn:3852")
        self.assertEqual(m.away_id, "espn:22271")
        self.assertEqual(m.home_goals, 1)
        self.assertEqual(m.away_goals, 0)
        self.assertEqual(m.status, "finished")

    def test_utf8_encoding_set(self):
        captured = {}

        def fake_get(url, **kw):
            r = make_response(CSV_BODY)
            captured["resp"] = r
            return r

        with mock.patch("requests.Session.get", side_effect=fake_get):
            p = FootbolnoProvider(cache_dir=self.tmp.name, ttl=9999)
            matches = p.fetch_league(235)
        self.assertEqual(captured["resp"].encoding, "utf-8")
        # если бы encoding не выставился — имена были бы mojibake
        self.assertEqual(matches[0].home_name, "Ростов")
        self.assertEqual(matches[1].away_name, "Локомотив")

    def test_session_trust_env_false(self):
        with mock.patch("requests.Session.get", return_value=make_response(CSV_BODY)):
            p = FootbolnoProvider(cache_dir=self.tmp.name, ttl=9999)
            p.fetch_league(235)
        self.assertFalse(p._session.trust_env)


class TestCache(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.join("/tmp", f"fb-cache-{os.getpid()}-{int(time.time()*1000)}")
        os.makedirs(self.dir, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_first_call_fetches_second_uses_cache(self):
        with mock.patch("requests.Session.get", return_value=make_response(CSV_BODY)) as g:
            p = FootbolnoProvider(cache_dir=self.dir, ttl=9999)
            p.fetch_league(235)
            p.fetch_league(235)
        self.assertEqual(g.call_count, 1)

    def test_refresh_forces_fetch(self):
        with mock.patch("requests.Session.get", return_value=make_response(CSV_BODY)) as g:
            p = FootbolnoProvider(cache_dir=self.dir, ttl=9999)
            p.fetch_league(235)
            p.fetch_league(235, refresh=True)
        self.assertEqual(g.call_count, 2)

    def test_ttl_expiry_refetches(self):
        with mock.patch("requests.Session.get", return_value=make_response(CSV_BODY)) as g:
            # первая сессия — наполнить кэш
            p1 = FootbolnoProvider(cache_dir=self.dir, ttl=10)
            p1.fetch_league(235)
            self.assertEqual(g.call_count, 1)

            # состарить meta.json (fetched_at в прошлом)
            meta_path = os.path.join(self.dir, "league-235.meta.json")
            self.assertTrue(os.path.exists(meta_path), f"no meta: {os.listdir(self.dir)}")
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            meta["fetched_at"] = time.time() - 1000
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f)

            # вторая сессия — свежий provider, in-memory пуст, disk cache истёк
            p2 = FootbolnoProvider(cache_dir=self.dir, ttl=10)
            p2.fetch_league(235)
        self.assertEqual(g.call_count, 2)


CSV_MULTI = "\n".join([
    CSV_HEADER,
    "1,235,РПЛ,2026/2027,2026-10-09T19:30:00Z,2026-10-09T22:30:00,1,,"
    "espn:3852,Ростов,espn:22271,Акрон,1,0,,,finished,,,,,",
    "2,235,РПЛ,2026/2027,2026-10-10T14:00:00Z,2026-10-10T17:00:00,1,,"
    "espn:21539,Факел,espn:442,Локомотив,0,5,,,finished,,,,,",
    "3,235,РПЛ,2026/2027,2026-10-01T18:00:00Z,2026-10-01T21:00:00,1,,"
    "espn:596,Динамо Москва,espn:1000,Краснодар,2,1,,,finished,,,,,",
    "4,235,РПЛ,2026/2027,2026-10-01T19:00:00Z,2026-10-01T22:00:00,1,,"
    "espn:22300,Динамо Махачкала,espn:1000,Краснодар,0,0,,,finished,,,,,",
]) + "\n"


class TestFindMatch(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.join("/tmp", f"fb-fm-{os.getpid()}-{int(time.time()*1000)}")
        os.makedirs(self.dir, exist_ok=True)
        self.patcher = mock.patch("requests.Session.get", return_value=make_response(CSV_MULTI))
        self.patcher.start()
        self.p = FootbolnoProvider(cache_dir=self.dir, ttl=9999)
        self.p.fetch_league(235)

    def tearDown(self):
        self.patcher.stop()
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_exact(self):
        m = self.p.find_match("Ростов", "Акрон", "2026-10-09", 235)
        self.assertIsNotNone(m)
        self.assertEqual(m.home_goals, 1)
        self.assertEqual(m.away_goals, 0)

    def test_case_insensitive(self):
        m = self.p.find_match("ростов", "акрон", "2026-10-09", 235)
        self.assertIsNotNone(m)
        self.assertEqual(m.home_id, "espn:3852")

    def test_normalized_fk_prefix(self):
        m = self.p.find_match("ФК Ростов", "Акрон", "2026-10-09", 235)
        self.assertIsNotNone(m)

    def test_fuzzy_city_suffix(self):
        # 'Локомотив Москва' в сигнале, 'Локомотив' в footbolno
        m = self.p.find_match("Факел", "Локомотив Москва", "2026-10-10", 235)
        self.assertIsNotNone(m)
        self.assertEqual(m.away_id, "espn:442")
        self.assertEqual(m.away_name, "Локомотив")

    def test_ambiguous_dinamo_returns_none(self):
        # 'Динамо' без города — два кандидата, должен вернуть None
        m = self.p.find_match("Динамо", "Краснодар", "2026-10-01", 235)
        self.assertIsNone(m)

    def test_dinamo_full_name_still_works(self):
        # полное имя — exact match, не должен ломаться
        m = self.p.find_match("Динамо Махачкала", "Краснодар", "2026-10-01", 235)
        self.assertIsNotNone(m)
        self.assertEqual(m.home_id, "espn:22300")

    def test_not_found(self):
        m = self.p.find_match("Барселона", "Реал", "2026-10-01", 235)
        self.assertIsNone(m)

    def test_date_mismatch(self):
        m = self.p.find_match("Ростов", "Акрон", "2025-01-01", 235)
        self.assertIsNone(m)


if __name__ == "__main__":
    unittest.main()
