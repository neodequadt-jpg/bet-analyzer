from typing import List
from .base import SportEvent, get_http_session
import json
from datetime import datetime, timedelta

def fetch_events(hours: int = 168) -> List[SportEvent]:
    events = []
    urls = [
        "https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/en.1.json",
        "https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/es.1.json",
        "https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/it.1.json",
        "https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/de.1.json"
    ]
    
    session = get_http_session()
    
    for url in urls:
        try:
            resp = session.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            
            data = resp.json()
            league = data.get("name", "Unknown")
            for match in data.get("matches", []):
                # Parse date and filter
                match_date_str = match.get("date")
                try:
                    match_dt = datetime.strptime(match_date_str, "%Y-%m-%d")
                    if match_dt > datetime.now() and match_dt < datetime.now() + timedelta(hours=hours):
                        events.append(SportEvent(
                            id=f"of_{match['team1']['name']}_{match['team2']['name']}_{match_date_str}",
                            sport="football",
                            league=league,
                            home=match['team1']['name'],
                            away=match['team2']['name'],
                            start_ts=int(match_dt.timestamp()),
                            source="openfootball"
                        ))
                except Exception:
                    continue
        except Exception:
            continue
            
    return events
