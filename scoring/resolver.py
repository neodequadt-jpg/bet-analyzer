import os
import json
import requests
from datetime import datetime
import re
from bookmakers.normalizer import TEAM_ALIASES

COUNTRY_MAP = TEAM_ALIASES

def _normalize(name: str) -> str:
    return COUNTRY_MAP.get(name.lower().strip(), name.lower().strip())

def _determine_result(event: dict) -> str | None:
    try:
        home_score = int(event.get("intHomeScore", 0))
        away_score = int(event.get("intAwayScore", 0))
        if home_score > away_score:
            return "home"
        elif home_score < away_score:
            return "away"
        else:
            return "draw"
    except (ValueError, TypeError):
        return None

def _find_match(events: list[dict], home: str, away: str):
    norm_home = _normalize(home)
    norm_away = _normalize(away)
    
    for e in events:
        if _normalize(e.get("strHomeTeam", "")) == norm_home and \
           _normalize(e.get("strAwayTeam", "")) == norm_away:
            return e
    return None

def resolve_all():
    results_dir = "data/backtest/results"
    os.makedirs(results_dir, exist_ok=True)
    signals_dir = "data/backtest/signals"
    
    stats = {"checked": 0, "resolved": 0, "won": 0, "lost": 0, "pending": 0, "skipped": 0}
    
    cache = {}
    session = requests.Session()
    # Assuming proxy is in env
    
    for f in os.listdir(signals_dir):
        if not f.endswith(".json"): continue
        stats["checked"] += 1
        
        path = os.path.join(signals_dir, f)
        with open(path, "r") as f_in:
            signal = json.load(f_in)
            
        kickoff_str = signal.get("kickoff")
        try:
            # 26.09 17:00 -> 2026-09-26 17:00
            dt = datetime.strptime(f"2026.{kickoff_str}", "%Y.%d.%m %H:%M")
        except:
            stats["skipped"] += 1
            continue
            
        if (datetime.now() - dt).total_seconds() < 3 * 3600:
            stats["pending"] += 1
            continue
            
        date_str = dt.strftime("%Y-%m-%d")
        if date_str not in cache:
            try:
                resp = session.get(f"https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d={date_str}&s=Soccer", timeout=10)
                cache[date_str] = resp.json().get("events", []) or []
            except:
                cache[date_str] = []
        
        events = cache[date_str]
        match = _find_match(events, signal["event"].split(" - ")[0], signal["event"].split(" - ")[1])
        
        if match:
            res = _determine_result(match)
            if res:
                stats["resolved"] += 1
                if signal["outcome"] == res:
                    stats["won"] += 1
                else:
                    stats["lost"] += 1
                
                # Save result
                out_path = os.path.join(results_dir, f"{f}_{res}.json")
                with open(out_path, "w") as f_out:
                    json.dump({"signal": signal, "match": match, "result": res}, f_out)
            else:
                stats["skipped"] += 1
        else:
            stats["skipped"] += 1
            
    return stats
