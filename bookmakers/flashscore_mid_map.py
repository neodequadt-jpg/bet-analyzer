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


import re
from datetime import datetime, timezone, timedelta


_KICKOFF_RE = re.compile(r"^(\d{2})\.(\d{2})\.\s*(\d{2}):(\d{2})$")


def parse_kickoff(text: str, ref_year: int | None = None) -> int | None:
    """Parse 'DD.MM. HH:MM' -> unix ts (Moscow, UTC+3).

    Flashscore shows kickoff as '16.09. 18:30' (no year).
    Year inferred: if month < current month, assume next year.

    Returns unix seconds, or None if format is unknown.
    """
    if not text:
        return None
    m = _KICKOFF_RE.match(text.strip())
    if not m:
        return None
    dd, mm, hh, mi = (int(x) for x in m.groups())
    msk = timezone(timedelta(hours=3))
    now = datetime.now(tz=msk)

    if ref_year is not None:
        year = ref_year
    else:
        # Heuristic: choose the year that puts the kickoff closest to now
        # but within [-30d, +120d] window; otherwise assume current year.
        candidates = [now.year, now.year - 1, now.year + 1]
        best = None
        best_delta = None
        for y in candidates:
            try:
                dt = datetime(y, mm, dd, hh, mi, tzinfo=msk)
            except ValueError:
                continue
            delta = abs((dt - now).total_seconds())
            if best_delta is None or delta < best_delta:
                best = y
                best_delta = delta
        year = best if best is not None else now.year

    try:
        dt = datetime(year, mm, dd, hh, mi, tzinfo=msk)
    except ValueError:
        return None
    return int(dt.timestamp())


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
        kickoff_text = row.get("kickoff_text") or ""
        records.append({
            "mid": mid,
            "home": home,
            "away": away,
            "home_norm": home_norm,
            "away_norm": away_norm,
            "kickoff": kickoff_text,
            "kickoff_ts": parse_kickoff(kickoff_text),
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
