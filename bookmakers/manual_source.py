"""
Manual source: чтение коэффициентов из data/manual/*.json.
Используется для верификации конвейера, пока внешние API недоступны.
"""

import json
from pathlib import Path

from bookmakers.parser import OddsEvent


MANUAL_DIR = Path("data/manual")


def list_manual_events() -> list[str]:
    if not MANUAL_DIR.exists():
        return []
    return sorted(p.stem for p in MANUAL_DIR.glob("*.json"))


def load_manual(event_id: str) -> dict:
    path = MANUAL_DIR / f"{event_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"manual file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def parse_manual(event_id: str) -> list[OddsEvent]:
    raw = load_manual(event_id)
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
