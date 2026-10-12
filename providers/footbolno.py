"""footbolno.ru data provider — adapter for footbolno.ru open data.

Source: https://footbolno.ru/data/
  index.json          — manifest (license CC BY 4.0)
  league/{id}.json    — league meta
  league/{id}-matches.csv — match CSV

CSV columns (verified):
  match_id, league_id, league, season, date_utc, date_msk, time_confirmed, round,
  home_id, home, away_id, away, home_goals, away_goals, home_pens, away_pens,
  status, venue, venue_ru, city, city_ru, attendance

Critical: server does NOT send charset=utf-8 for CSV.  We must force
r.encoding = 'utf-8' before parsing to avoid mojibake.

Critical: matching uses canonical IDs (home_id, away_id, date_utc[:10]),
NOT team names.  Names are used only for mapping signal team name → canonical id.
"""

import csv
import io
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://footbolno.ru/data"


@dataclass
class Match:
    """A single match from footbolno.ru."""
    date_iso: str          # YYYY-MM-DD (from date_utc[:10])
    home_id: str           # canonical team id, e.g. 'espn:1963'
    away_id: str           # canonical team id
    home_name: str         # display name from CSV
    away_name: str         # display name from CSV
    home_goals: Optional[int]
    away_goals: Optional[int]
    status: str            # e.g. 'completed', 'scheduled'
    league_id: str
    season: str            # e.g. '2016' or '2018/2019'
    source: str = "footbolno"


def _normalize_name(name: str) -> str:
    """Normalize a team name for fuzzy matching.

    Steps:
      - ё → е
      - lower
      - strip leading 'ФК ' / 'ФК'
      - collapse hyphens and extra spaces
    """
    s = name.replace("ё", "е").replace("Ё", "е")
    s = s.lower()
    # strip leading 'ФК ' or 'ФК'
    s = re.sub(r"^фк\s+", "", s)
    s = re.sub(r"^фк", "", s)
    # collapse hyphens to spaces
    s = s.replace("-", " ")
    # collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _safe_int(val: str) -> Optional[int]:
    """Parse int from CSV value, return None on failure."""
    if val is None or val == "" or val == "NA":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


class FootbolnoProvider:
    """Provider for footbolno.ru open football data.

    Args:
        cache_dir: directory for cached CSV and meta files.
        ttl: cache time-to-live in seconds (default 6 hours).
        session: optional pre-configured requests.Session.
    """

    def __init__(
        self,
        cache_dir: str = "data/footbolno",
        ttl: int = 6 * 3600,
        session: Optional[requests.Session] = None,
    ):
        self.cache_dir = cache_dir
        self.ttl = ttl
        if session is not None:
            self._session = session
        else:
            self._session = requests.Session()
            self._session.trust_env = False
        self._timeout = 15

        # Per-league caches: {league_id: list[Match]}
        self._matches: Dict[int, List[Match]] = {}
        # Per-league canonical name index: {league_id: {team_id: set(names)}}
        self._name_index: Dict[int, Dict[str, Set[str]]] = {}
        # Per-league reverse lookup maps (built lazily)
        self._exact_map: Dict[int, Dict[str, str]] = {}
        self._ci_map: Dict[int, Dict[str, str]] = {}
        self._norm_map: Dict[int, Dict[str, Set[str]]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_league(self, league_id: int, refresh: bool = False) -> List[Match]:
        """Fetch matches for a league (from cache or network).

        Args:
            league_id: footbolno league id (e.g. 235 for RPL).
            refresh: force re-download even if cache is fresh.

        Returns:
            List of Match objects.
        """
        if not refresh and league_id in self._matches:
            return self._matches[league_id]

        csv_text = self._get_csv(league_id, refresh=refresh)
        matches = self._parse_csv(csv_text, league_id)
        self._matches[league_id] = matches
        self._build_name_index(league_id, matches)
        return matches

    def find_match(
        self,
        home: str,
        away: str,
        date_iso: str,
        league_id: int,
    ) -> Optional[Match]:
        """Find a match by team names and date.

        Matching strategy:
          1. Resolve home/away names to canonical IDs via name index.
          2. Look up match by (home_id, away_id, date_iso[:10]).

        Args:
            home: home team name (signal name, may differ from CSV).
            away: away team name.
            date_iso: date in YYYY-MM-DD format.
            league_id: footbolno league id.

        Returns:
            Match if found, None otherwise.
        """
        # Ensure league data is loaded
        if league_id not in self._matches:
            self.fetch_league(league_id)

        home_id = self._resolve_name(league_id, home)
        away_id = self._resolve_name(league_id, away)

        if home_id is None or away_id is None:
            logger.debug(
                "Could not resolve names: home=%r → %r, away=%r → %r",
                home, home_id, away, away_id,
            )
            return None

        date_key = date_iso[:10]
        for m in self._matches.get(league_id, []):
            if m.home_id == home_id and m.away_id == away_id and m.date_iso == date_key:
                return m
        return None

    # ------------------------------------------------------------------
    # CSV fetching + caching
    # ------------------------------------------------------------------

    def _get_csv(self, league_id: int, refresh: bool = False) -> str:
        """Get CSV text for a league, using cache if fresh."""
        os.makedirs(self.cache_dir, exist_ok=True)
        csv_path = os.path.join(self.cache_dir, f"league-{league_id}.csv")
        meta_path = os.path.join(self.cache_dir, f"league-{league_id}.meta.json")

        if not refresh:
            cached = self._read_cache(csv_path, meta_path)
            if cached is not None:
                return cached

        # Fetch from network
        url = f"{BASE_URL}/league/{league_id}-matches.csv"
        logger.info("Fetching %s", url)
        r = self._session.get(url, timeout=self._timeout, allow_redirects=True)
        r.raise_for_status()

        # CRITICAL: server does not send charset=utf-8; force it
        r.encoding = "utf-8"
        text = r.text

        # Write cache
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write(text)

        meta = {
            "fetched_at": time.time(),
            "league_id": league_id,
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f)

        return text

    def _read_cache(self, csv_path: str, meta_path: str) -> Optional[str]:
        """Read cached CSV if meta exists and TTL not exceeded."""
        if not os.path.exists(csv_path) or not os.path.exists(meta_path):
            return None
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            fetched_at = meta.get("fetched_at", 0)
            if time.time() - fetched_at > self.ttl:
                logger.debug("Cache expired for %s", csv_path)
                return None
            with open(csv_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.warning("Cache read error: %s", e)
            return None

    # ------------------------------------------------------------------
    # CSV parsing
    # ------------------------------------------------------------------

    def _parse_csv(self, text: str, league_id: int) -> List[Match]:
        """Parse CSV text into Match objects."""
        matches: List[Match] = []
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            try:
                date_utc = row.get("date_utc", "")
                if not date_utc:
                    continue
                date_iso = date_utc[:10]
                home_id = row.get("home_id", "").strip()
                away_id = row.get("away_id", "").strip()
                if not home_id or not away_id:
                    continue

                m = Match(
                    date_iso=date_iso,
                    home_id=home_id,
                    away_id=away_id,
                    home_name=row.get("home", ""),
                    away_name=row.get("away", ""),
                    home_goals=_safe_int(row.get("home_goals", "")),
                    away_goals=_safe_int(row.get("away_goals", "")),
                    status=row.get("status", ""),
                    league_id=str(row.get("league_id", league_id)),
                    season=row.get("season", ""),
                )
                matches.append(m)
            except Exception as e:
                logger.warning("Parse error on row: %s", e)
                continue
        logger.info("Parsed %d matches for league %s", len(matches), league_id)
        return matches

    # ------------------------------------------------------------------
    # Name index + resolution
    # ------------------------------------------------------------------

    def _build_name_index(self, league_id: int, matches: List[Match]) -> None:
        """Build canonical name index: {team_id: set(all observed names)}."""
        idx: Dict[str, Set[str]] = {}
        for m in matches:
            for tid, tname in [(m.home_id, m.home_name), (m.away_id, m.away_name)]:
                if tid and tname:
                    idx.setdefault(tid, set()).add(tname)

        self._name_index[league_id] = idx

        # Build reverse lookup maps
        exact: Dict[str, str] = {}
        ci: Dict[str, str] = {}
        norm: Dict[str, Set[str]] = {}

        for tid, names in idx.items():
            for name in names:
                # exact
                exact[name] = tid
                # case-insensitive
                ci[name.lower()] = tid
                # normalized
                n = _normalize_name(name)
                norm.setdefault(n, set()).add(tid)

        self._exact_map[league_id] = exact
        self._ci_map[league_id] = ci
        self._norm_map[league_id] = norm

    def _resolve_name(self, league_id: int, name: str) -> Optional[str]:
        """Resolve team name -> canonical team id.

        Order:
          1. Exact
          2. Case-insensitive
          3. Normalized (unambiguous)
          4. Drop trailing token (city suffix), unambiguous only
        """
        exact = self._exact_map.get(league_id, {})
        ci = self._ci_map.get(league_id, {})
        norm = self._norm_map.get(league_id, {})

        if name in exact:
            return exact[name]
        lower = name.lower()
        if lower in ci:
            return ci[lower]

        n = _normalize_name(name)
        hit = self._lookup_unique(norm, n)
        if hit is not None:
            return hit

        parts = n.split()
        while len(parts) > 1:
            parts = parts[:-1]
            hit = self._lookup_unique(norm, " ".join(parts))
            if hit is not None:
                return hit
        return None

    @staticmethod
    def _lookup_unique(norm, key):
        cands = norm.get(key)
        if not cands:
            return None
        if len(cands) == 1:
            return next(iter(cands))
        logger.debug("Ambiguous normalized name %r -> %s", key, cands)
        return None

