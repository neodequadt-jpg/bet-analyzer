from typing import List, Optional
from .base import SportEvent
from . import sports_skills_provider, understat_provider, openfootball_provider
import sys

def fetch_all_events(hours: int = 24, sources: Optional[List] = None) -> List[SportEvent]:
    """Merge events from all providers, deduplicate by (home, away, start_ts)."""
    if sources is None:
        sources = [sports_skills_provider, understat_provider, openfootball_provider]
    all_events = []
    for src in sources:
        try:
            all_events.extend(src.fetch_events(hours=hours))
        except Exception as e:
            print(f"[sports_data] {src.__name__} failed: {e}", file=sys.stderr)
    
    # dedup
    seen = set()
    unique = []
    for ev in all_events:
        # Round timestamp to nearest hour for key (start_ts // 3600)
        key = (ev.home.lower(), ev.away.lower(), ev.start_ts // 3600)
        if key not in seen:
            seen.add(key)
            unique.append(ev)
    unique.sort(key=lambda x: x.start_ts)
    return unique
