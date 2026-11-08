"""
fonbet_extended.py — multi-sport events with П1/П2 odds from Fonbet listBase.

Reuses fetch_list_base() from bookmakers.fonbet_api. Sports are identified by
sport id (1=Football, 2=Hockey, 4=Tennis, 3088=TableTennis, 29086=Esports);
a sport owns segment ids via sports[].parentId, and top-level events
(level=1, kind=1) carry one of those segment ids in sportId.

Factors: f=921 (П1) and f=923 (П2) are shared between football and TT, so the
same constants from fonbet_api apply to every sport here.

Stdlib only — no new dependencies.
"""
import time

from bookmakers.fonbet_api import F_AWAY, F_DRAW, F_HOME, fetch_list_base

# Sport aliases (lowercase, RU+EN) -> Fonbet sport id
SPORT_ALIASES: dict[str, int] = {
    "football": 1,
    "\u0444\u0443\u0442\u0431\u043e\u043b": 1,          # футбол
    "hockey": 2,
    "\u0445\u043e\u043a\u043a\u0435\u0439": 2,          # хоккей
    "tennis": 4,
    "\u0442\u0435\u043d\u043d\u0438\u0441": 4,          # теннис
    "tt": 3088,
    "tabletennis": 3088,
    "\u043d\u0430\u0441\u0442\u043e\u043b\u044c\u043d\u044b\u0439": 3088,  # настольный
    "\u043f\u0438\u043d\u0433-\u043f\u043e\u043d\u0433": 3088,          # пинг-понг
    "esports": 29086,
    "\u043a\u0438\u0431\u0435\u0440\u0441\u043f\u043e\u0440\u0442": 29086,  # киберспорт
    "basketball": 3,
    "\u0431\u0430\u0441\u043a\u0435\u0442\u0431\u043e\u043b": 3,
    "volleyball": 9,
    "\u0432\u043e\u043b\u0435\u0439\u0431\u043e\u043b": 9,
}

# Events starting up to 5 minutes in the past are still "upcoming" (tolerance).
PAST_TOLERANCE_SEC = 300


def resolve_sport(token: str) -> int | None:
    """Map a sport alias (RU/EN, case-insensitive) to a Fonbet sport id."""
    if not token:
        return None
    return SPORT_ALIASES.get(str(token).strip().lower())


def _is_esports_segment(name: str) -> bool:
    """True if segment is esports (FC 26, кибер) - not a real sport."""
    if not name:
        return False
    low = name.lower()
    return any(x in low for x in (
        'fc 26', 'fc26', 'fc 25', 'fc25', 'esports', 'кибер',
        'fifa', 'efootball', 'nba 2k', 'cyber', 'esportsbattle',
    ))


def fetch_events_by_sport(sport_id: int, hours: int = 1,
                          max_events: int = 10) -> list[dict]:
    """Top-level events of `sport_id` within the next `hours` hours.

    Returns up to `max_events` dicts sorted by startTime ascending:
        {"id": int, "home": str, "away": str, "start_ts": int,
         "place": str, "odds_home": float, "odds_away": float,
         "league": str | None}   # league = segment name via id->name map
    Events without both f=921 and f=923 factors are skipped.
    """
    data = fetch_list_base()
    sports = data.get("sports") or []

    # segment name map (id -> name) for the league label
    name_map = {s["id"]: s.get("name") for s in sports if "id" in s}
    # segment ids owned by this sport
    segment_ids = {
        s["id"] for s in sports
        if s.get("kind") == "segment" and s.get("parentId") == sport_id
    }
    if not segment_ids:
        return []

    now = time.time()
    lo = now - PAST_TOLERANCE_SEC
    hi = now + hours * 3600

    # customFactors are keyed by event id (cf['e'])
    cf_map = {c["e"]: c for c in data.get("customFactors", []) if "e" in c}

    out: list[dict] = []
    for e in data.get("events", []):
        if e.get("kind") != 1 or e.get("level") != 1:
            continue
        # Skip esports (FC 26, кибер)
        _seg_name = name_map.get(e.get("sportId"), "")
        if _is_esports_segment(_seg_name):
            continue
        if e.get("sportId") not in segment_ids:
            continue
        if not e.get("team1") or not e.get("team2"):
            continue
        start_ts = e.get("startTime")
        if not isinstance(start_ts, (int, float)):
            continue
        if not (lo <= start_ts <= hi):
            continue

        cf = cf_map.get(e.get("id"))
        if not cf:
            continue
        factors = {f["f"]: f["v"] for f in cf.get("factors", [])}
        if F_HOME not in factors or F_AWAY not in factors:
            continue

        out.append({
            "id": e["id"],
            "home": str(e.get("team1", "")).strip(),
            "away": str(e.get("team2", "")).strip(),
            "start_ts": int(start_ts),
            "place": e.get("place", ""),
            "odds_home": float(factors[F_HOME]),
            "odds_away": float(factors[F_AWAY]),
            "league": name_map.get(e.get("sportId")),
        })

    out.sort(key=lambda d: d["start_ts"])
    return out[:max_events]



def fetch_real_today(sports=None, hours=24, max_per_sport=10):
    """Return today's real (non-esports) events with odds across sports."""
    if sports is None:
        sports = {1: 'football', 2: 'hockey', 3088: 'tt'}
    data = fetch_list_base()
    sports_meta = {s['id']: s.get('name', '') for s in data.get('sports', [])}
    events = data.get('events', [])
    custom = {c['e']: c for c in data.get('customFactors', [])}
    now = time.time()
    cutoff = now + hours * 3600

    def _is_esports(name):
        if not name: return False
        low = name.lower()
        return any(x in low for x in ('fc 26', 'fc26', 'esports', 'кибер', 'fifa', 'efootball'))

    # Build segment -> sport_id map
    seg_to_sport = {}
    for s in data.get('sports', []):
        if s.get('kind') == 'segment' and s.get('parentId') in sports:
            seg_to_sport[s['id']] = s['parentId']

    result = []
    by_sport = {}
    for e in events:
        seg_id = e.get('sportId')
        sport_id = seg_to_sport.get(seg_id)
        if sport_id is None: continue
        if e.get('kind') != 1 or e.get('level') != 1: continue
        seg_name = sports_meta.get(seg_id, '')
        if _is_esports(seg_name): continue
        ts = e.get('startTime')
        if not ts: continue
        try: tsi = int(ts)
        except: continue
        if not (now <= tsi <= cutoff): continue
        # odds from customFactors (f=921 home, 923 away)
        cf = custom.get(e['id'])
        if not cf: continue
        odds = {f.get('f'): f.get('v') for f in cf.get('factors', [])}
        home_o = odds.get(F_HOME)
        away_o = odds.get(F_AWAY)
        if not home_o or not away_o: continue
        key = sport_id
        by_sport.setdefault(key, 0)
        if by_sport[key] >= max_per_sport: continue
        by_sport[key] += 1
        result.append({
            'id': e['id'],
            'sport': sports.get(sport_id, 'sport'),
            'league': seg_name,
            'home': e.get('team1', ''),
            'away': e.get('team2', ''),
            'start_ts': tsi,
            'odds_home': home_o,
            'odds_draw': odds.get(F_DRAW),
            'odds_away': away_o,
        })
    result.sort(key=lambda x: x['start_ts'])
    return result


if __name__ == "__main__":
    events = fetch_events_by_sport(3088, hours=2)
    print(f"TT events: {len(events)}")
    for e in events[:10]:
        print(f"  {e['start_ts']} {e['home']} vs {e['away']} "
              f"{e['odds_home']} {e['odds_away']} [{e['place']}]")


def fetch_european_cups(hours: int = 48) -> list:
    """Fetch Fonbet odds for Europa League + Conference League as OddsEvent list.

    These overlap with Pinnacle on TheOddsAPI, enabling cross-BK consensus.
    """
    from bookmakers.parser import OddsEvent
    from bookmakers.fonbet_api import F_DRAW

    raw = fetch_list_base(force=False)
    if not raw:
        return []

    sports_data = raw.get("sports", [])
    football_segments = set()
    for sp in sports_data:
        if sp.get("id") != 1:  # 1 = football
            continue
        for seg in sp.get("segments", []):
            football_segments.add(seg.get("id"))

    now = time.time()
    events: list[OddsEvent] = []

    for ev in raw.get("events", []):
        if ev.get("level") != 1 or ev.get("kind") != 1:
            continue
        if ev.get("sportId") not in football_segments:
            continue

        name = (ev.get("name") or "").lower()
        if "лига европ" not in name and "лига конференц" not in name:
            continue

        start_ts = ev.get("startTime", 0)
        if start_ts < now - 300 or start_ts > now + hours * 3600:
            continue

        home = ev.get("nameRu", "").split(" — ")[0].strip() if "—" in (ev.get("nameRu") or "") else ""
        away = ev.get("nameRu", "").split(" — ")[1].strip() if "—" in (ev.get("nameRu") or "") else ""
        if not home or not away:
            continue

        factors = {f.get("f"): f for f in ev.get("factors", [])}
        odds_h = _factor_to_odds(factors.get(F_HOME, {}))
        odds_d = _factor_to_odds(factors.get(F_DRAW, {}))
        odds_a = _factor_to_odds(factors.get(F_AWAY, {}))

        if not odds_h or not odds_a:
            continue

        league_name = ev.get("leagueNameRu") or ev.get("leagueName") or "UEL"
        events.append(OddsEvent(
            event_id=f"fonbet_{ev.get('id', '')}",
            sport="football",
            league=league_name,
            home=home,
            away=away,
            kickoff_iso="",
            bookmaker="Фонбет",
            odds_home=odds_h,
            odds_draw=odds_d,
            odds_away=odds_a,
            odds_total_over=None,
            odds_total_under=None,
            total_line=None,
        ))

    return events


def _factor_to_odds(factor: dict) -> float | None:
    """Convert Fonbet factor dict to decimal odds."""
    if not factor:
        return None
    v = factor.get("v")
    if v is None:
        return None
    try:
        return round(float(v) / 10000, 3) if float(v) > 0 else None
    except (TypeError, ValueError):
        return None
