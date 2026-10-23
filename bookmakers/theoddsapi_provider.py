"""TheOddsAPI provider — Pinnacle + other international bookmakers.

Source: https://the-odds-api.com
Free tier: 500 requests/month, no credit card.
API key from env: ODDS_API_KEY

Provides odds from Pinnacle (sharpest book) and other non-ЦУПИС bookmakers.
Used as calibration source for consensus — NOT for placing bets
(российские пользователи не могут ставить в Pinnacle легально).
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests

from bookmakers.parser import OddsEvent

logger = logging.getLogger(__name__)

BASE_URL = "https://api.the-odds-api.com/v4"
CACHE_DIR = Path("data/cache/theoddsapi")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

SPORT_MAP = {
    "soccer_epl": "EPL",
    "soccer_germany_bundesliga": "Bundesliga",
    "soccer_spain_la_liga": "La Liga",
    "soccer_italy_serie_a": "Serie A",
    "soccer_france_ligue_one": "Ligue 1",
    "soccer_uefa_champs_league": "UCL",
    "soccer_uefa_europa_league": "UEL",
    "soccer_uefa_nations_league": "UEFA Nations League",
    "soccer_efl_champ": "Championship",
    "soccer_netherlands_eredivisie": "Eredivisie",
    "soccer_portugal_primeira_liga": "Primeira Liga",
    "soccer_turkey_super_league": "Turkey Super League",
    "icehockey_nhl": "NHL",
    "basketball_nba": "NBA",
}

# Nations League divisions to exclude (0/28 win rate)
NATIONS_EXCLUDE_TIERS = ["League C", "League D"]

DEFAULT_BOOKMAKERS = "pinnacle"
MSK = timezone(timedelta(hours=3))


def _get_api_key() -> str:
    key = os.environ.get("ODDS_API_KEY", "").strip()
    if not key:
        raise EnvironmentError("ODDS_API_KEY not set. Get free key at https://the-odds-api.com")
    return key


def _get_session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    return s


def _cache_path(sport_key: str) -> Path:
    return CACHE_DIR / f"{sport_key}_odds.json"


def _read_cache(sport_key: str, ttl: int = 300) -> Optional[list]:
    p = _cache_path(sport_key)
    if not p.exists():
        return None
    age = time.time() - p.stat().st_mtime
    if age > ttl:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_cache(sport_key: str, data: list) -> None:
    p = _cache_path(sport_key)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_commence_time(ct: str) -> str:
    try:
        dt = datetime.fromisoformat(ct.replace("Z", "+00:00"))
        return dt.astimezone(MSK).isoformat()
    except Exception:
        return ct


def _extract_outcome_price(outcomes: list, team_name: str, is_home: bool) -> Optional[float]:
    """Extract price from outcomes list. API uses 'outcomes' with 'name'/'price'."""
    for o in outcomes:
        name = o.get("name", "").lower()
        price = o.get("price")
        if price is None or price <= 1.0:
            continue
        # Match by team name or by position
        if is_home and name == team_name.lower():
            return price
        if not is_home and name == team_name.lower():
            return price
    return None


def fetch_odds(
    sport_key: str = "soccer_epl",
    bookmakers: str = DEFAULT_BOOKMAKERS,
    markets: str = "h2h",
    ttl: int = 300,
    group_exclude: list[str] | None = None,
) -> list[OddsEvent]:
    """Fetch odds from TheOddsAPI and convert to OddsEvent list.

    group_exclude: list of substrings; matches whose 'group' field contains
    any of these are excluded (e.g. ["League C", "League D"]).
    """
    cached = _read_cache(sport_key, ttl)
    if cached is not None:
        logger.debug("Using cached odds for %s", sport_key)
        return _convert_events(cached, group_exclude=group_exclude)

    api_key = _get_api_key()
    session = _get_session()

    url = f"{BASE_URL}/sports/{sport_key}/odds/"
    params = {
        "apiKey": api_key,
        "regions": "eu",
        "markets": markets,
        "bookmakers": bookmakers,
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }

    try:
        r = session.get(url, params=params, timeout=20)
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error("TheOddsAPI HTTP error: %s (status=%d)", e, r.status_code)
        return []
    except Exception as e:
        logger.error("TheOddsAPI request failed: %s", e)
        return []

    remaining = r.headers.get("x-requests-remaining")
    used = r.headers.get("x-requests-used")
    if remaining:
        logger.info("TheOddsAPI quota: %s remaining, %s used", remaining, used)

    data = r.json()
    _write_cache(sport_key, data)
    return _convert_events(data, group_exclude=group_exclude)


def _convert_events(data: list, group_exclude: list[str] | None = None) -> list[OddsEvent]:
    """Convert TheOddsAPI response to OddsEvent list.

    API returns 'outcomes' (not 'prices'): [{name: "Chelsea", price: 2.18}, ...]

    group_exclude: if set, skip matches whose 'group' field contains any substring.
    """
    events = []
    for match in data:
        # Exclude by group (e.g. Nations League C/D)
        if group_exclude:
            group = match.get("group", "")
            if any(ex in group for ex in group_exclude):
                continue
        match_id = match.get("id", "")
        sport_key = match.get("sport_key", "")
        league = SPORT_MAP.get(sport_key, sport_key)
        home = match.get("home_team", "")
        away = match.get("away_team", "")
        kickoff = _parse_commence_time(match.get("commence_time", ""))

        for bk_data in match.get("bookmakers", []):
            bk_key = bk_data.get("key", "")
            bk_title = bk_data.get("title", bk_key)

            for market in bk_data.get("markets", []):
                if market.get("key") != "h2h":
                    continue

                # API format: outcomes = [{name, price}, ...]
                outcomes = market.get("outcomes", [])
                if not outcomes:
                    # Fallback: старый формат prices = [{outcome, price}, ...]
                    outcomes = market.get("prices", [])
                    for o in outcomes:
                        if "name" not in o and "outcome" in o:
                            o["name"] = o["outcome"]

                if len(outcomes) < 2:
                    continue

                # Map outcomes by name matching
                home_odds = away_odds = draw_odds = None
                for o in outcomes:
                    name = o.get("name", "").lower()
                    price = o.get("price")
                    if price is None or price <= 1.0:
                        continue
                    if name == home.lower():
                        home_odds = price
                    elif name == away.lower():
                        away_odds = price
                    elif name == "draw":
                        draw_odds = price

                if home_odds is None or away_odds is None:
                    continue

                events.append(OddsEvent(
                    event_id=f"theoddsapi_{match_id}",
                    sport="football" if "soccer" in sport_key else "hockey" if "icehockey" in sport_key else "other",
                    league=league,
                    home=home,
                    away=away,
                    kickoff_iso=kickoff,
                    bookmaker=bk_title,
                    odds_home=home_odds,
                    odds_draw=draw_odds,
                    odds_away=away_odds,
                    odds_total_over=None,
                    odds_total_under=None,
                    total_line=None,
                ))
                break  # only first h2h market
    logger.info("TheOddsAPI: %d odds entries for %d matches", len(events), len(data))
    return events


def fetch_pinnacle_epl(ttl: int = 300) -> list[OddsEvent]:
    """Convenience: fetch Pinnacle odds for EPL."""
    return fetch_odds("soccer_epl", bookmakers="pinnacle", ttl=ttl)


def fetch_pinnacle_nations_league(ttl: int = 300) -> list[OddsEvent]:
    """Convenience: fetch Pinnacle odds for UEFA Nations League (excludes C/D)."""
    return fetch_odds("soccer_uefa_nations_league", bookmakers="pinnacle", ttl=ttl,
                       group_exclude=NATIONS_EXCLUDE_TIERS)


def fetch_pinnacle_bundesliga(ttl: int = 300) -> list[OddsEvent]:
    """Convenience: fetch Pinnacle odds for Bundesliga."""
    return fetch_odds("soccer_germany_bundesliga", bookmakers="pinnacle", ttl=ttl)


def fetch_pinnacle_liga(ttl: int = 300) -> list[OddsEvent]:
    """Convenience: fetch Pinnacle odds for La Liga."""
    return fetch_odds("soccer_spain_la_liga", bookmakers="pinnacle", ttl=ttl)


def fetch_pinnacle_serie_a(ttl: int = 300) -> list[OddsEvent]:
    """Convenience: fetch Pinnacle odds for Serie A."""
    return fetch_odds("soccer_italy_serie_a", bookmakers="pinnacle", ttl=ttl)
