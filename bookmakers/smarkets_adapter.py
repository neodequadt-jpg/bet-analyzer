"""Smarkets → OddsEvent adapter for merge()."""
from bookmakers.parser import OddsEvent
from bookmakers.smarkets_provider import fetch_events


def fetch_smarkets_events(hours: int = 720, max_events: int = 50) -> list[OddsEvent]:
    """Fetch Smarkets football matches and convert to OddsEvent list."""
    raw = fetch_events(hours=hours, max_events=max_events)
    out: list[OddsEvent] = []
    for e in raw:
        try:
            out.append(OddsEvent(
                event_id=e["id"],
                sport="football",
                league=e.get("league", "UEFA"),
                home=e["home"],
                away=e["away"],
                kickoff_iso=str(e["start_ts"]),
                bookmaker="Smarkets",
                odds_home=float(e["odds_home"]),
                odds_draw=float(e["odds_draw"]),
                odds_away=float(e["odds_away"]),
                odds_total_over=None,
                odds_total_under=None,
                total_line=None,
            ))
        except (KeyError, TypeError, ValueError) as ex:
            print(f"[smarkets_adapter] skip {e.get('id')}: {ex}")
    return out
