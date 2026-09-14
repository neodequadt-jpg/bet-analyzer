"""
Парсер коэффициентов.
На первом этапе — mock-источник для проверки конвейера.
Реальный источник подставляется через fetch_raw().
"""

import json
import time
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


class OddsParser:
    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 Chrome/130 Safari/537.36"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        })

    def _cache_path(self, key: str) -> Path:
        safe = "".join(c if c.isalnum() else "_" for c in key)
        return CACHE_DIR / f"{safe}.json"

    def _load_cache(self, key: str) -> Optional[dict]:
        path = self._cache_path(key)
        if not path.exists():
            return None
        if time.time() - path.stat().st_mtime > CACHE_TTL_SECONDS:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _save_cache(self, key: str, data: dict) -> None:
        self._cache_path(key).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def fetch_raw(self, event_id: str) -> dict:
        """
        Mock-источник. Заменить на Flashscore/Oddsportal.
        """
        cache_key = f"raw_{event_id}"
        cached = self._load_cache(cache_key)
        if cached:
            return cached

        mock = {
            "event_id": event_id,
            "sport": "football",
            "league": "RPL",
            "home": "Зенит",
            "away": "Спартак",
            "kickoff_iso": "2026-09-15T19:00:00+03:00",
            "bookmakers": [
                {"name": "Винлайн",     "home": 1.85, "draw": 3.60, "away": 4.20, "over": 1.90, "under": 1.90, "line": 2.5},
                {"name": "Фонбет",      "home": 1.80, "draw": 3.70, "away": 4.30, "over": 1.95, "under": 1.85, "line": 2.5},
                {"name": "Лига Ставок", "home": 1.90, "draw": 3.50, "away": 4.10, "over": 1.88, "under": 1.92, "line": 2.5},
                {"name": "Бет Бум",     "home": 1.83, "draw": 3.65, "away": 4.25, "over": 1.92, "under": 1.88, "line": 2.5},
                {"name": "PARI",        "home": 1.87, "draw": 3.55, "away": 4.15, "over": 1.89, "under": 1.91, "line": 2.5},
            ],
        }
        self._save_cache(cache_key, mock)
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
