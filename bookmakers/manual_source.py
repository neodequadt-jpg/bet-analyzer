"""
Manual source: чтение коэффициентов из data/manual/*.json.
Event ID берётся из содержимого JSON, не из имени файла.
"""
import json
from pathlib import Path
from bookmakers.parser import OddsEvent

MANUAL_DIR = Path("data/manual")


def list_manual_events() -> list[str]:
    """Возвращает список event_id из содержимого JSON-файлов."""
    if not MANUAL_DIR.exists():
        return []
    event_ids = []
    for path in sorted(MANUAL_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            eid = data.get("event_id")
            if eid:
                event_ids.append(eid)
        except Exception as e:
            print(f"[manual] skip {path.name}: {e}")
    return event_ids


def load_manual(event_id: str) -> dict:
    """Ищет файл, содержащий указанный event_id."""
    if not MANUAL_DIR.exists():
        raise FileNotFoundError(f"manual dir not found: {MANUAL_DIR}")
    for path in sorted(MANUAL_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("event_id") == event_id:
                return data
        except Exception:
            continue
    raise FileNotFoundError(f"event_id not found in manual: {event_id}")


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
