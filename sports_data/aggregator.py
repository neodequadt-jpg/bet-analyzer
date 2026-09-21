"""Aggregate events from multiple sports data providers."""
from typing import List, Optional
import sys

from .base import SportEvent
from . import openfootball_provider
from . import thesportsdb_provider
from . import openligadb_provider
from . import sports_skills_provider


DEFAULT_SOURCES = [
    openfootball_provider,
    thesportsdb_provider,
    openligadb_provider,
    sports_skills_provider,
]


def fetch_all_events(hours: int = 24,
                     sources: Optional[List] = None) -> List[SportEvent]:
    """Fetch from all providers, dedup by (home, away, hour), sort by start."""
    if sources is None:
        sources = DEFAULT_SOURCES

    all_events: List[SportEvent] = []
    for src in sources:
        name = getattr(src, "__name__", str(src))
        try:
            evs = src.fetch_events(hours=hours)
            all_events.extend(evs)
        except Exception as e:
            print(f"[sports_data] {name} failed: {e}", file=sys.stderr)

    seen = set()
    unique: List[SportEvent] = []
    for ev in all_events:
        key = (ev.home.lower().strip(),
               ev.away.lower().strip(),
               ev.start_ts // 3600)
        if key in seen:
            continue
        seen.add(key)
        unique.append(ev)

    unique.sort(key=lambda x: x.start_ts)
    return unique
