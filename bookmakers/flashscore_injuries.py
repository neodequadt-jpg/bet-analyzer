"""
Flashscore missing players parser.

Extracts injured / suspended / questionable players from a Flashscore match page.

Source block:
    [data-testid="wcl-lineupsParticipantGeneral-{left|right}"]
Left  = home team missing players.
Right = away team missing players.

Known reason values:
    - "Knee Injury"
    - "Yellow Cards"
    - "Inactive"
    - "Questionable"
"""
from __future__ import annotations

from bs4 import BeautifulSoup


_SIDE_TO_KEY = (("left", "home"), ("right", "away"))


def parse_missing_players(html: str) -> dict:
    """
    Parse missing players from a Flashscore match page.

    Returns:
        {
          "home": [{"name": str, "reason": str}, ...],
          "away": [{"name": str, "reason": str}, ...],
        }
    """
    if not html:
        return {"home": [], "away": []}

    soup = BeautifulSoup(html, "html.parser")
    result: dict = {"home": [], "away": []}

    for side, key in _SIDE_TO_KEY:
        selector = f'[data-testid="wcl-lineupsParticipantGeneral-{side}"]'
        for div in soup.select(selector):
            name_el = div.select_one(".wcl-mainRow_IaUrm span")
            if not name_el:
                continue
            name = name_el.get_text(" ", strip=True)
            if not name:
                continue
            reason_el = div.select_one('[data-testid="wcl-scores-caption-05"]')
            reason = (
                reason_el.get_text(" ", strip=True)
                if reason_el else "unknown"
            )
            result[key].append({"name": name, "reason": reason})

    return result


# ---------------------------------------------------------------------------
# Cache lookup (read-only, no network)
# ---------------------------------------------------------------------------

import json
from pathlib import Path


INJURIES_CACHE_DIR = Path("data/injuries")


def injuries_cache_path(mid: str) -> Path:
    return INJURIES_CACHE_DIR / f"{mid}.json"


def save_injuries(mid: str, data: dict) -> Path:
    """Persist parsed injuries as a JSON cache file."""
    INJURIES_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = injuries_cache_path(mid)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def load_injuries(mid: str) -> dict | None:
    """Read cached injuries, or None if not cached."""
    if not mid:
        return None
    path = injuries_cache_path(mid)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return {
        "home": data.get("home") or [],
        "away": data.get("away") or [],
    }


def lookup_injuries_for_event(
    home: str,
    away: str,
    *,
    mid_map: list[dict] | None = None,
) -> dict:
    """
    Best-effort injuries lookup for a match by team names.

    Reads only cached injuries. No network calls.

    Returns {"home": [], "away": []} when:
      - mid not found in mid_map
      - cache entry missing
      - cache file malformed
    """
    empty = {"home": [], "away": []}
    if mid_map is None:
        from bookmakers.flashscore_mid_map import load_mid_map
        mid_map = load_mid_map()
    if not mid_map:
        return empty

    from bookmakers.flashscore_mid_map import find_mid
    mid = find_mid(mid_map, home, away)
    if not mid:
        return empty

    cached = load_injuries(mid)
    return cached if cached else empty
