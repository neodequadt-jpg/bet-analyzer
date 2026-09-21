"""Tests for sports_data module (no live API calls)."""
import unittest
from unittest import mock


class TestSportEventDataclass(unittest.TestCase):
    def test_defaults(self):
        from sports_data.base import SportEvent
        ev = SportEvent(id="x", sport="football", league="L",
                        home="A", away="B", start_ts=0)
        self.assertEqual(ev.extra, {})
        self.assertIsNone(ev.odds_home)
        self.assertEqual(ev.source, "")


class TestAggregatorDedup(unittest.TestCase):
    def test_identical_events_deduped(self):
        from sports_data.base import SportEvent
        from sports_data import aggregator
        e1 = SportEvent(id="1", sport="football", league="L",
                        home="A", away="B", start_ts=1000000, source="src1")
        e2 = SportEvent(id="2", sport="football", league="L",
                        home="A", away="B", start_ts=1000000 + 60, source="src2")
        fake = mock.Mock()
        fake.fetch_events = lambda hours=24: [e1, e2]
        evs = aggregator.fetch_all_events(hours=24, sources=[fake])
        self.assertEqual(len(evs), 1)

    def test_two_distinct_events_kept(self):
        from sports_data.base import SportEvent
        from sports_data import aggregator
        e1 = SportEvent(id="1", sport="football", league="L",
                        home="A", away="B", start_ts=1000000)
        e2 = SportEvent(id="2", sport="football", league="L",
                        home="C", away="D", start_ts=1000000)
        fake = mock.Mock()
        fake.fetch_events = lambda hours=24: [e1, e2]
        evs = aggregator.fetch_all_events(hours=24, sources=[fake])
        self.assertEqual(len(evs), 2)

    def test_failing_source_does_not_crash(self):
        from sports_data import aggregator
        from sports_data.base import SportEvent
        bad = mock.Mock()
        bad.fetch_events = lambda hours=24: (_ for _ in ()).throw(RuntimeError("boom"))
        good = mock.Mock()
        good.__name__ = "good"
        good.fetch_events = lambda hours=24: [
            SportEvent(id="1", sport="football", league="L",
                       home="A", away="B", start_ts=1000000)
        ]
        evs = aggregator.fetch_all_events(hours=24, sources=[bad, good])
        self.assertEqual(len(evs), 1)


class TestProvidersGraceful(unittest.TestCase):
    def test_openfootball_returns_list(self):
        from sports_data import openfootball_provider
        evs = openfootball_provider.fetch_events(hours=1)
        self.assertIsInstance(evs, list)

    def test_thesportsdb_returns_list(self):
        from sports_data import thesportsdb_provider
        evs = thesportsdb_provider.fetch_events(hours=1)
        self.assertIsInstance(evs, list)

    def test_openligadb_returns_list(self):
        from sports_data import openligadb_provider
        evs = openligadb_provider.fetch_events(hours=1)
        self.assertIsInstance(evs, list)


if __name__ == "__main__":
    unittest.main(verbosity=2)
