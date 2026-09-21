"""TheSportsDB free API (key="3", no signup)."""
from typing import List
from datetime import datetime, timedelta
from .base import SportEvent, get_http_session
import time


BASE = "https://www.thesportsdb.com/api/v1/json/3"
FREE_KEY = "3"


def _day_str(offset_days: int = 0) -> str:
    return (datetime.now() + timedelta(days=offset_days)).strftime("%Y-%m-%d")


def fetch_events(hours: int = 72) -> List[SportEvent]:
    events: List[SportEvent] = []
    session = get_http_session()
    now = time.time()
    cutoff_lo = now - 2 * 3600
    cutoff_hi = now + hours * 3600
    days = max(1, min(7, hours // 24 + 1))

    for off in range(days):
        d = _day_str(off)
        try:
            url = f"{BASE}/eventsday.php?d={d}&s=Soccer"
            resp = session.get(url, timeout=30)
            if resp.status_code != 200:
                continue
            data = resp.json() or {}
        except Exception as e:
            print(f"[thesportsdb] fetch failed {d}: {e}")
            continue

        for e in (data.get("events") or []):
            ts_raw = e.get("strTimestamp")
            if not ts_raw:
                continue
            try:
                ts = int(datetime.fromisoformat(
                    ts_raw.replace("Z", "+00:00")).timestamp())
            except Exception:
                continue
            if not (cutoff_lo <= ts <= cutoff_hi):
                continue
            events.append(SportEvent(
                id=f"tsdb_{e.get('idEvent', '')}",
                sport="football",
                league=e.get("strLeague") or "Unknown",
                home=e.get("strHomeTeam") or "",
                away=e.get("strAwayTeam") or "",
                start_ts=ts,
                source="thesportsdb",
                extra={"league_id": e.get("idLeague")},
            ))
    return events
