"""
Парсер коэффициентов. Mock-источник.
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import requests


CACHE_DIR = Path("data/cache/odds")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_SECONDS = 300


@dataclass
class OddsEvent:
    event_id: str
    sport: str
    league: str
    home: str
    away: str
    kickoff_iso: str
    bookmaker: str
    odds_home: Optional[float]
    odds_draw: Optional[float]
    odds_away: Optional[float]
    odds_total_over: Optional[float]
    odds_total_under: Optional[float]
    total_line: Optional[float]

    def to_dict(self):
        return asdict(self)


MOCK_DATA = {
    "rpl_zenit_spartak_2026_09_15": {
        "event_id": "rpl_zenit_spartak_2026_09_15",
        "sport": "football", "league": "RPL",
        "home": "Зенит", "away": "Спартак",
        "kickoff_iso": "2026-09-15T19:00:00+03:00",
        "bookmakers": [
            {"name": "Винлайн",     "home": 1.85, "draw": 3.60, "away": 4.20, "over": 1.90, "under": 1.90, "line": 2.5},
            {"name": "Фонбет",      "home": 1.80, "draw": 3.70, "away": 4.30, "over": 1.95, "under": 1.85, "line": 2.5},
            {"name": "Лига Ставок", "home": 1.90, "draw": 3.50, "away": 4.10, "over": 1.88, "under": 1.92, "line": 2.5},
            {"name": "Бет Бум",     "home": 1.83, "draw": 3.65, "away": 4.25, "over": 1.92, "under": 1.88, "line": 2.5},
            {"name": "PARI",        "home": 1.87, "draw": 3.55, "away": 4.15, "over": 1.89, "under": 1.91, "line": 2.5},
            {"name": "Марафон",     "home": 2.15, "draw": 3.90, "away": 3.60, "over": 2.10, "under": 1.78, "line": 2.5},
        ],
    },
    "rpl_cska_lokomotiv_2026_09_15": {
        "event_id": "rpl_cska_lokomotiv_2026_09_15",
        "sport": "football", "league": "RPL",
        "home": "ЦСКА", "away": "Локомотив",
        "kickoff_iso": "2026-09-15T21:30:00+03:00",
        "bookmakers": [
            {"name": "Винлайн",     "home": 2.10, "draw": 3.40, "away": 3.60, "over": 1.95, "under": 1.85, "line": 2.5},
            {"name": "Фонбет",      "home": 2.05, "draw": 3.45, "away": 3.70, "over": 1.90, "under": 1.90, "line": 2.5},
            {"name": "Лига Ставок", "home": 2.15, "draw": 3.35, "away": 3.55, "over": 1.93, "under": 1.87, "line": 2.5},
            {"name": "PARI",        "home": 2.08, "draw": 3.42, "away": 3.65, "over": 1.92, "under": 1.88, "line": 2.5},
            {"name": "Бетсити",     "home": 2.12, "draw": 3.38, "away": 3.58, "over": 1.91, "under": 1.89, "line": 2.5},
            {"name": "Марафон",     "home": 2.50, "draw": 3.50, "away": 3.10, "over": 2.15, "under": 1.72, "line": 2.5},
        ],
    },
    "khl_ska_dynamo_2026_09_15": {
        "event_id": "khl_ska_dynamo_2026_09_15",
        "sport": "hockey", "league": "KHL",
        "home": "СКА", "away": "Динамо М",
        "kickoff_iso": "2026-09-15T19:30:00+03:00",
        "bookmakers": [
            {"name": "Винлайн",     "home": 1.75, "draw": None, "away": 4.20, "over": 1.85, "under": 1.95, "line": 4.5},
            {"name": "Фонбет",      "home": 1.80, "draw": None, "away": 4.00, "over": 1.90, "under": 1.90, "line": 4.5},
            {"name": "Лига Ставок", "home": 1.78, "draw": None, "away": 4.15, "over": 1.88, "under": 1.92, "line": 4.5},
            {"name": "PARI",        "home": 1.82, "draw": None, "away": 3.95, "over": 1.87, "under": 1.93, "line": 4.5},
            {"name": "Марафон",     "home": 1.65, "draw": None, "away": 5.00, "over": 2.20, "under": 1.70, "line": 4.5},
        ],
    },
}


class OddsParser:
    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.trust_env = False

    def fetch_raw(self, event_id: str) -> dict:
        mock = MOCK_DATA.get(event_id)
        if mock is None:
            raise ValueError(f"Unknown event_id: {event_id}")
        return mock

    def parse(self, event_id: str) -> list[OddsEvent]:
        raw = self.fetch_raw(event_id)
        events = []
        for bk in raw["bookmakers"]:
            events.append(OddsEvent(
                event_id=raw["event_id"],
                sport=raw["sport"],
                league=raw["league"],
                home=raw["home"],
                away=raw["away"],
                kickoff_iso=raw["kickoff_iso"],
                bookmaker=bk["name"],
                odds_home=bk["home"],
                odds_draw=bk["draw"],
                odds_away=bk["away"],
                odds_total_over=bk["over"],
                odds_total_under=bk["under"],
                total_line=bk["line"],
            ))
        return events
