import pytest
from sports_data.base import SportEvent
from sports_data.aggregator import fetch_all_events

def test_base_sportevent_dataclass():
    ev = SportEvent(id="1", sport="f", league="l", home="A", away="B", start_ts=100)
    assert ev.home == "A"

def test_aggregator_dedup():
    ev1 = SportEvent(id="1", sport="f", league="l", home="A", away="B", start_ts=3600)
    ev2 = SportEvent(id="2", sport="f", league="l", home="A", away="B", start_ts=3650)
    ev3 = SportEvent(id="3", sport="f", league="l", home="C", away="D", start_ts=3600)
    
    # Mocking providers
    class MockProvider:
        def fetch_events(self, hours):
            return [ev1, ev2, ev3]
            
    res = fetch_all_events(hours=24, sources=[MockProvider()])
    # Should contain only ev1 and ev3 (ev2 is duplicate of ev1 because of 3600//3600 == 3650//3600)
    assert len(res) == 2

def test_import_sports_skills_no_crash():
    from sports_data import sports_skills_provider
    events = sports_skills_provider.fetch_events()
    assert isinstance(events, list)
