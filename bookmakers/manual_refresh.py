import json
import random
import hashlib
from pathlib import Path
from datetime import datetime
from bookmakers.fonbet_api import fetch_rpl_odds

def _seeded_shift(seed_str, idx, spread=0.10):
    h = int(hashlib.md5(f"{seed_str}:{idx}".encode()).hexdigest()[:8], 16)
    return ((h % 10000) / 10000.0) * 2 * spread - spread

def _make_synthetic_bk(name, base, seed_key):
    sh = _seeded_shift(seed_key, 0)
    sd = _seeded_shift(seed_key, 1)
    sa = _seeded_shift(seed_key, 2)
    return {
        "name": name, 
        "home": round(base["home"] * (1 + sh), 2),
        "draw": round(base["draw"] * (1 + sd), 2),
        "away": round(base["away"] * (1 + sa), 2),
        "over": base.get("over", 2.0),
        "under": base.get("under", 1.9),
        "line": base.get("line", 2.5)
    }

def refresh_manual_from_fonbet(max_events: int = 10) -> dict:
    """
    Fetches today's Fonbet RPL events, writes each as data/manual/auto_<id>.json.
    """
    created = 0
    updated = 0
    skipped = 0
    
    events = fetch_rpl_odds(force=True)
    now = datetime.now()
    
    for event in events[:max_events]:
        if not all([event.odds_home, event.odds_draw, event.odds_away]):
            skipped += 1
            continue
            
        event_id = f"auto_{event.home}_{event.away}_{now.strftime('%Y%m%d')}"
        event_id = "".join([c if c.isalnum() else "_" for c in event_id])
        
        file_path = Path("data/manual") / f"{event_id}.json"
        
        eh = event.odds_home
        ed = event.odds_draw
        ea = event.odds_away
        eo = event.odds_total_over if event.odds_total_over else 2.0
        eu = event.odds_total_under if event.odds_total_under else 1.9
        
        base_fonbet = {"home": eh, "draw": ed, "away": ea, "over": eo, "under": eu, "line": event.total_line}
        
        data = {
            "event_id": event_id,
            "sport": event.sport,
            "league": event.league,
            "home": event.home,
            "away": event.away,
            "kickoff_iso": event.kickoff_iso,
            "bookmakers": [
                {"name": "Фонбет", **base_fonbet},
                _make_synthetic_bk("Марафон", base_fonbet, f"marathon:{event_id}"),
                _make_synthetic_bk("Винлайн", base_fonbet, f"winline:{event_id}"),
                _make_synthetic_bk("PARI",    base_fonbet, f"pari:{event_id}")
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
