"""OpenLigaDB (Bundesliga, no API key)."""
from typing import List
from datetime import datetime, timezone
from .base import SportEvent, get_http_session
import time


BASE = "https://api.openligadb.de"
LEAGUES = ["bl1", "bl2"]  # Bundesliga 1/2


def fetch_events(hours: int = 168) -> List[SportEvent]:
    events: List[SportEvent] = []
    session = get_http_session()
    now = time.time()
    cutoff_lo = now - 2 * 3600
    cutoff_hi = now + hours * 3600
    year = datetime.now().year

    for lg in LEAGUES:
        try:
            url = f"{BASE}/getmatchdata/{lg}/{year}"
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json() or []
        except Exception as e:
            print(f"[openligadb] fetch failed {lg}: {e}")
            continue

        for m in data:
            dt_raw = m.get("matchDateTimeUTC") or m.get("matchDateTime")
            if not dt_raw:
                continue
            try:
                ts = int(datetime.fromisoformat(
                    dt_raw.replace("Z", "+00:00")).timestamp())
            except Exception:
                continue
            if not (cutoff_lo <= ts <= cutoff_hi):
                continue
            t1 = (m.get("team1") or {}).get("teamName")
            t2 = (m.get("team2") or {}).get("teamName")
            if not t1 or not t2:
                continue
            events.append(SportEvent(
                id=f"oldb_{m.get('matchID', '')}",
                sport="football",
                league=m.get("leagueName") or lg,
                home=t1,
                away=t2,
                start_ts=ts,
                source="openligadb",
            ))
    return events
