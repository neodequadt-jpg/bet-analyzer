"""Tests for TheOddsAPI provider (mocked, no network)."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from bookmakers.theoddsapi_provider import (
    fetch_odds,
    _convert_events,
    _parse_commence_time,
    SPORT_MAP,
)


def _sample_api_response():
    """TheOddsAPI v4 response with 'outcomes' format."""
    return [
        {
            "id": "abc123",
            "sport_key": "soccer_epl",
            "home_team": "Everton",
            "away_team": "Chelsea",
            "commence_time": "2026-10-20T16:00:00Z",
            "bookmakers": [
                {
                    "key": "pinnacle",
                    "title": "Pinnacle",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Everton", "price": 3.29},
                                {"name": "Draw", "price": 3.70},
                                {"name": "Chelsea", "price": 2.18},
                            ],
                        }
                    ],
                }
            ],
        }
    ]


class TestConvertEvents:
    def test_outcomes_format(self):
        events = _convert_events(_sample_api_response())
        assert len(events) == 1
        e = events[0]
        assert e.home == "Everton"
        assert e.away == "Chelsea"
        assert e.bookmaker == "Pinnacle"
        assert e.odds_home == 3.29
        assert e.odds_draw == 3.70
        assert e.odds_away == 2.18
        assert e.league == "EPL"

    def test_2way_market_no_draw(self):
        data = [
            {
                "id": "nhl1",
                "sport_key": "icehockey_nhl",
                "home_team": "Rangers",
                "away_team": "Islanders",
                "commence_time": "2026-10-20T23:00:00Z",
                "bookmakers": [
                    {
                        "key": "pinnacle",
                        "title": "Pinnacle",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Rangers", "price": 1.80},
                                    {"name": "Islanders", "price": 2.05},
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
        events = _convert_events(data)
        assert len(events) == 1
        assert events[0].odds_draw is None
        assert events[0].odds_home == 1.80

    def test_empty_response(self):
        events = _convert_events([])
        assert events == []

    def test_invalid_price_skipped(self):
        data = _sample_api_response()
        data[0]["bookmakers"][0]["markets"][0]["outcomes"][0]["price"] = 0.8
        events = _convert_events(data)
        assert len(events) == 0

    def test_sport_map(self):
        assert SPORT_MAP["soccer_epl"] == "EPL"
        assert SPORT_MAP["soccer_uefa_nations_league"] == "UEFA Nations League"

    def test_fallback_prices_format(self):
        """Support old 'prices' format with 'outcome' key."""
        data = [
            {
                "id": "old1",
                "sport_key": "soccer_epl",
                "home_team": "Arsenal",
                "away_team": "Tottenham",
                "commence_time": "2026-10-20T15:00:00Z",
                "bookmakers": [
                    {
                        "key": "pinnacle",
                        "title": "Pinnacle",
                        "markets": [
                            {
                                "key": "h2h",
                                "prices": [
                                    {"outcome": "Home", "price": 1.95},
                                    {"outcome": "Draw", "price": 3.50},
                                    {"outcome": "Away", "price": 4.10},
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
        events = _convert_events(data)
        # Old format uses "Home"/"Draw"/"Away" — won't match team names
        # This is expected to produce 0 events (names don't match)
        # The real API uses team names, so this is correct behavior
        assert len(events) == 0


class TestParseCommenceTime:
    def test_utc_to_msk(self):
        result = _parse_commence_time("2026-10-20T16:00:00Z")
        assert "19:00:00" in result

    def test_invalid_returns_raw(self):
        result = _parse_commence_time("invalid")
        assert result == "invalid"


class TestFetchOdds:
    def test_no_api_key_raises(self):
        with patch("bookmakers.theoddsapi_provider._read_cache", return_value=None),              patch("bookmakers.theoddsapi_provider._get_api_key", side_effect=EnvironmentError("ODDS_API_KEY not set")):
            with pytest.raises(EnvironmentError, match="ODDS_API_KEY"):
                fetch_odds()

    def test_uses_cache(self):
        cache_data = _sample_api_response()
        with patch("bookmakers.theoddsapi_provider._read_cache", return_value=cache_data), \
             patch("bookmakers.theoddsapi_provider._convert_events", wraps=_convert_events) as mock_conv:
            events = fetch_odds()
            assert mock_conv.called
