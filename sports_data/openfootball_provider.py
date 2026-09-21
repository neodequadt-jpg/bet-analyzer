"""openfootball GitHub JSON fixtures (no API key)."""
from typing import List
from datetime import datetime, timedelta
from .base import SportEvent, get_http_session
import time


URLS = [
    "https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/en.1.json",
    "https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/es.1.json",
    "https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/it.1.json",
    "https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/de.1.json",
    "https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/fr.1.json",
]


def fetch_events(hours: int = 168) -> List[SportEvent]:
    events: List[SportEvent] = []
    session = get_http_session()
    now = time.time()
    cutoff_lo = now - 2 * 3600
    cutoff_hi = now + hours * 3600

    for url in URLS:
        try:
            resp = session.get(url, timeout=25)
            if resp.status_code != 200:
                continue
            data = resp.json()
        except Exception as e:
            print(f"[openfootball] fetch failed {url}: {e}")
            continue

        league = data.get("name", "Unknown")
        for m in data.get("matches", []):
            score = m.get("score")
            # openfootball format: score может быть dict {"ft": [...]} или list
            if isinstance(score, dict) and score.get("ft"):
                continue  # already played
            if isinstance(score, list) and len(score) >= 2:
                continue  # already played (list form)
            date_s = m.get("date")
            time_s = m.get("time") or "00:00"
            if not date_s:
                continue
            try:
                dt = datetime.strptime(f"{date_s} {time_s}", "%Y-%m-%d %H:%M")
                ts = int(dt.timestamp())
            except Exception:
                continue
            if not (cutoff_lo <= ts <= cutoff_hi):
                continue
            raw1 = m.get("team1")
            raw2 = m.get("team2")
            t1 = raw1.get("name") if isinstance(raw1, dict) else raw1
            t2 = raw2.get("name") if isinstance(raw2, dict) else raw2
            if not t1 or not t2:
                continue
            events.append(SportEvent(
                id=f"of_{t1}_{t2}_{date_s}",
                sport="football",
                league=league,
                home=t1,
                away=t2,
                start_ts=ts,
                source="openfootball",
            ))
    return events
