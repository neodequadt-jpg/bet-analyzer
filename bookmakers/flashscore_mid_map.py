"""
Flashscore MID mapping.

Maps (home, away) team pair -> Flashscore match id (mid).

Purpose:
  runner.py оперирует event_id / именами команд.
  injuries lookup требует Flashscore mid.
  mid_map — явный, кэшируемый артефакт, обновляемый из /fixtures/ HTML.
"""
from __future__ import annotations

import json
from pathlib import Path

from bookmakers.flashscore_parser import parse_fixtures_html
from bookmakers.normalizer import normalize_team


DEFAULT_PATH = Path("data/mid_map.json")


def build_mid_map_from_html(html: str) -> list[dict]:
    """Parse fixtures HTML -> list of records with normalized keys."""
    if not html:
        return []
    records: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for row in parse_fixtures_html(html):
        home = (row.get("home") or "").strip()
        away = (row.get("away") or "").strip()
        mid = row.get("mid")
        if not home or not away or not mid:
            continue
        home_norm = normalize_team(home)
        away_norm = normalize_team(away)
        key = (home_norm, away_norm)
        if key in seen:
            continue
        seen.add(key)
        records.append({
            "mid": mid,
            "home": home,
            "away": away,
            "home_norm": home_norm,
            "away_norm": away_norm,
            "kickoff": row.get("kickoff_text") or "",
            "match_url": row.get("match_url") or "",
        })
    return records


def save_mid_map(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_mid_map(path: Path = DEFAULT_PATH) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def find_mid(records: list[dict], home: str, away: str) -> str | None:
    """Lookup mid by normalized team pair. Returns None if not found."""
    if not records or not home or not away:
        return None
    h = normalize_team(home)
    a = normalize_team(away)
    for r in records:
        if r.get("home_norm") == h and r.get("away_norm") == a:
            return r.get("mid")
    return None
