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

from bookmakers.fonbet_api import F_AWAY, F_HOME, fetch_list_base

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
}

# Events starting up to 5 minutes in the past are still "upcoming" (tolerance).
PAST_TOLERANCE_SEC = 300


def resolve_sport(token: str) -> int | None:
    """Map a sport alias (RU/EN, case-insensitive) to a Fonbet sport id."""
    if not token:
        return None
    return SPORT_ALIASES.get(str(token).strip().lower())


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


if __name__ == "__main__":
    events = fetch_events_by_sport(3088, hours=2)
    print(f"TT events: {len(events)}")
    for e in events[:10]:
        print(f"  {e['start_ts']} {e['home']} vs {e['away']} "
              f"{e['odds_home']} {e['odds_away']} [{e['place']}]")