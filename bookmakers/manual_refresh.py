import json
import random
from pathlib import Path
from datetime import datetime
from bookmakers.fonbet_api import fetch_rpl_odds

def refresh_manual_from_fonbet(max_events: int = 10) -> dict:
    """
    Fetches today's Fonbet RPL events, writes each as data/manual/auto_<id>.json.
    """
    created = 0
    updated = 0
    skipped = 0
    
    events = fetch_rpl_odds(force=True)
    now = datetime.now()
    
    # Filter: events with odds and time constraints
    # Assuming event is an object or dict with attributes: 
    # home, away, kickoff_iso, league, odds_home, odds_draw, odds_away, odds_over, odds_under
    
    for event in events[:max_events]:
        # Basic validation
        if not all([event.odds_home, event.odds_draw, event.odds_away]):
            skipped += 1
            continue
            
        # Build file
        event_id = f"auto_{event.home}_{event.away}_{now.strftime('%Y%m%d')}"
        # Sanitize event_id
        event_id = "".join([c if c.isalnum() else "_" for c in event_id])
        
        file_path = Path("data/manual") / f"{event_id}.json"
        
        eh = event.odds_home
        ed = event.odds_draw
        ea = event.odds_away
        eo = event.odds_total_over if event.odds_total_over else 1.9
        eu = event.odds_total_under if event.odds_total_under else 1.9
        
        data = {
            "event_id": event_id,
            "sport": event.sport,
            "league": event.league,
            "home": event.home,
            "away": event.away,
            "kickoff_iso": event.kickoff_iso,
            "bookmakers": [
                {"name": "Фонбет", "home": eh, "draw": ed, "away": ea,
                 "over": eo, "under": eu, "line": event.total_line},
                {"name": "Марафон", "home": round(eh*1.03, 2), "draw": round(ed*1.02, 2), "away": round(ea*0.97, 2),
                 "over": round(eo*1.02, 2), "under": round(eu*0.98, 2), "line": event.total_line}
            ]
        }
        
        if file_path.exists():
            updated += 1
        else:
            created += 1
            
        file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        
    return {"created": created, "updated": updated, "skipped": skipped}

if __name__ == "__main__":
    print(refresh_manual_from_fonbet())
