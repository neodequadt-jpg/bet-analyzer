"""
Fonbet MMA schedule fetcher.

Source: Fonbet listBase (public JSON, ЦУПИС).

Reality (2026-10-04):
  MMA events live under sport tree root 37145 ('Единоборства').
  Each UFC tournament has one or more segment ids (kind=segment,
  parentId=37145). Top-level fights have kind=1, level=1, carrying
  one of these segment ids in sportId.
  Factors f=921 (П1) and f=923 (П2) apply to MMA (no draw factor).

Excludes:
  - H2H LIGA (simulator, name contains 'H2H')
  - Грэпплинг (not MMA, name contains 'Грэпплинг')
"""
from __future__ import annotations

import time

from bookmakers.fonbet_api import F_AWAY, F_HOME, fetch_list_base


MMA_ROOT_SPORT_ID = 37145

# Names to skip (simulator / non-MMA)
_EXCLUDE_KEYWORDS = (
    "h2h liga",
    "грэпплинг",
    "grappling",
)


def _is_excluded(name: str) -> bool:
    if not name:
        return False
    low = name.lower()
    return any(k in low for k in _EXCLUDE_KEYWORDS)


def _mma_segment_ids(sports: list[dict]) -> set[int]:
    """Segment ids belonging to MMA root (37145)."""
    return {
        s["id"] for s in sports
        if s.get("kind") == "segment" and s.get("parentId") == MMA_ROOT_SPORT_ID
    }


def fetch_mma_events(*, hours: int = 24 * 60, max_events: int = 100) -> list[dict]:
    """
    Fetch MMA fights within `hours` from now.

    Returns list of dicts:
        {
          "event_id": int,
          "home": str,      # fighter 1
          "away": str,      # fighter 2
          "start_ts": int,
          "tournament": str,  # segment name (e.g. "MMA. UFC 333. ...")
          "place": str,
          "odds_home": float | None,
          "odds_away": float | None,
        }
    """
    data = fetch_list_base()
    sports = data.get("sports") or []
    segment_ids = _mma_segment_ids(sports)
    if not segment_ids:
        return []

    name_map = {s["id"]: (s.get("name") or "") for s in sports}
    cf_map = {c["e"]: c for c in data.get("customFactors", []) if "e" in c}

    now = time.time()
    hi = now + hours * 3600

    out: list[dict] = []
    for e in data.get("events", []):
        if e.get("kind") != 1 or e.get("level") != 1:
            continue
        if e.get("sportId") not in segment_ids:
            continue
        home = str(e.get("team1") or "").strip()
        away = str(e.get("team2") or "").strip()
        if not home or not away:
            continue
        start_ts = e.get("startTime")
        if not isinstance(start_ts, (int, float)):
            continue
        if start_ts < now - 3600 or start_ts > hi:
            continue

        tournament = name_map.get(e.get("sportId"), "")
        if _is_excluded(tournament):
            continue

        cf = cf_map.get(e.get("id"))
        odds_home = odds_away = None
        if cf:
            factors = {f["f"]: f["v"] for f in cf.get("factors", [])}
            if F_HOME in factors:
                odds_home = float(factors[F_HOME])
            if F_AWAY in factors:
                odds_away = float(factors[F_AWAY])

        out.append({
            "event_id": e["id"],
            "home": home,
            "away": away,
            "start_ts": int(start_ts),
            "tournament": tournament,
            "place": e.get("place") or "",
            "odds_home": odds_home,
            "odds_away": odds_away,
        })

    out.sort(key=lambda d: d["start_ts"])
    return out[:max_events]


import re as _re

# Patterns to extract base tournament name
_TOURNAMENT_PATTERNS = [
    # "MMA. UFC 333. ..." / "ММА. UFC Fight Night 290. Лас-Вегас. ..."
    _re.compile(r"(?:MMA|ММА)\s*\.\s*(UFC\s+(?:Fight\s+Night\s+)?\d+)", _re.IGNORECASE),
    # "MMA. ACA 208. Грозный"
    _re.compile(r"(?:MMA|ММА)\s*\.\s*(ACA\s+\d+)", _re.IGNORECASE),
    # "MMA. Fight Nights. Гран-при. ..."
    _re.compile(r"(?:MMA|ММА)\s*\.\s*(Fight\s+Nights)", _re.IGNORECASE),
]


def normalize_tournament(label: str) -> str:
    """Reduce segment name to base tournament name.

    Examples:
      'MMA. UFC 333. Остров Яс. ...' -> 'UFC 333'
      'ММА. UFC Fight Night 290. Лас-Вегас. ...' -> 'UFC Fight Night 290'
      'MMA. ACA 208. Грозный' -> 'ACA 208'
      'MMA. Fight Nights. Гран-при. ...' -> 'Fight Nights'
    """
    if not label:
        return "unknown"
    for pat in _TOURNAMENT_PATTERNS:
        m = pat.search(label)
        if m:
            return m.group(1)
    # Fallback: first 2 dot-separated tokens
    parts = [p.strip() for p in label.split(".") if p.strip()]
    return " · ".join(parts[:2]) if parts else label



def group_by_tournament(events: list[dict]) -> dict[str, list[dict]]:
    """Group fights by normalized tournament name.

    Multiple segments of the same tournament are merged
    (e.g. UFC 333 heavy + featherweight main events -> one 'UFC 333' group).
    """
    groups: dict[str, list[dict]] = {}
    for e in events:
        key = normalize_tournament(e.get("tournament", ""))
        groups.setdefault(key, []).append(e)
    return groups
