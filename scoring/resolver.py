"""Auto-resolve signal results via TheSportsDB (public API key=3)."""
import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

SIGNALS_DIR = Path("data/backtest/signals")
RESULTS_DIR = Path("data/backtest/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

MSK = timezone(timedelta(hours=3))
THESPORTSDB = "https://www.thesportsdb.com/api/v1/json/3"


# RU→EN countries (only those that appear in signals)
COUNTRY_MAP = {
    "россия": "russia", "германия": "germany", "франция": "france",
    "англия": "england", "испания": "spain", "италия": "italy",
    "дания": "denmark", "уэльс": "wales", "сербия": "serbia",
    "нидерланды": "netherlands", "австрия": "austria", "косово": "kosovo",
    "греция": "greece", "грузия": "georgia", "украина": "ukraine",
    "исландия": "iceland", "эстония": "estonia", "словакия": "slovakia",
    "молдова": "moldova", "литва": "lithuania", "азербайджан": "azerbaijan",
    "турция": "turkey", "бельгия": "belgium", "чехия": "czech republic",
    "хорватия": "croatia", "польша": "poland",
    "босния и герцеговина": "bosnia and herzegovina",
    "босния": "bosnia and herzegovina",
    "шотландия": "scotland", "португалия": "portugal", "норвегия": "norway",
    "швеция": "sweden", "швейцария": "switzerland", "финляндия": "finland",
    "венгрия": "hungary", "северная ирландия": "northern ireland",
    "армения": "armenia", "латвия": "latvia", "сан-марино": "san marino",
    "болгария": "bulgaria", "люксембург": "luxembourg",
    "ирландия": "republic of ireland", "республика ирландия": "republic of ireland",
    "израиль": "israel",
}


def _normalize(name: str) -> str:
    n = (name or "").strip().lower()
    return COUNTRY_MAP.get(n, n)


def _get_session():
    s = requests.Session()
    # env may have a dead http_proxy (see ARTEM-PRETHEORY E1); ignore it.
    s.trust_env = False
    return s


def _parse_kickoff(kickoff_str: str) -> Optional[int]:
    """Parse '26.09 21:45' → unix ts (year 2026, MSK)."""
    if not kickoff_str:
        return None
    try:
        # "26.09 21:45"
        day_month, hm = kickoff_str.strip().split()
        dd, mm = day_month.split(".")
        hh, mi = hm.split(":")
        dt = datetime(2026, int(mm), int(dd), int(hh), int(mi), tzinfo=MSK)
        return int(dt.timestamp())
    except Exception:
        return None


def _determine_result(event: dict) -> Optional[str]:
    try:
        sh = event.get("intHomeScore")
        sa = event.get("intAwayScore")
        if sh is None or sa is None:
            return None
        sh, sa = int(sh), int(sa)
    except (TypeError, ValueError):
        return None
    if sh > sa:
        return "home"
    if sh < sa:
        return "away"
    return "draw"


FOOTBOLNO_LEAGUES = {
    "RPL": 235,
    "UEFA Nations League A": 5,
    "UEFA Nations League B": 5,
    "UEFA Nations League C": 5,
}

_footbolno_provider = None


def _get_footbolno():
    """Lazy singleton FootbolnoProvider (requests.Session trust_env=False inside)."""
    global _footbolno_provider
    if _footbolno_provider is None:
        from providers.footbolno import FootbolnoProvider
        _footbolno_provider = FootbolnoProvider(cache_dir="data/footbolno", ttl=6 * 3600)
    return _footbolno_provider


def _determine_result_from_match(m) -> Optional[str]:
    """Same semantics as _determine_result but for providers.footbolno.Match."""
    if m.home_goals is None or m.away_goals is None:
        return None
    if m.home_goals > m.away_goals:
        return "home"
    if m.home_goals < m.away_goals:
        return "away"
    return "draw"


def _find_match(events: list, home_ru: str, away_ru: str) -> Optional[dict]:
    h = _normalize(home_ru)
    a = _normalize(away_ru)
    for e in events:
        eh = _normalize(e.get("strHomeTeam", ""))
        ea = _normalize(e.get("strAwayTeam", ""))
        if (h == eh or h in eh or eh in h) and (a == ea or a in ea or ea in a):
            return e
    return None


def _fetch_events_for_date(session, date_str: str) -> list:
    try:
        r = session.get(f"{THESPORTSDB}/eventsday.php?d={date_str}&s=Soccer", timeout=20)
        if r.status_code != 200:
            return []
        return (r.json() or {}).get("events") or []
    except Exception as e:
        print(f"[resolver] fetch {date_str}: {e}")
        return []


def resolve_all() -> dict:
    """Read all signals, resolve via TheSportsDB, save results."""
    now = time.time()
    stats = {"checked": 0, "resolved": 0, "won": 0, "lost": 0,
             "pending": 0, "skipped": 0}

    # Collect all signals (flatten files)
    signals = []
    for sf in sorted(SIGNALS_DIR.glob("*.json")):
        try:
            d = json.loads(sf.read_text(encoding="utf-8"))
            for s in d.get("signals", []):
                s["_src"] = sf.name
                signals.append(s)
        except Exception as e:
            print(f"[resolver] read {sf.name}: {e}")

    session = _get_session()
    cache = {}

    for sig in signals:
        stats["checked"] += 1

        kick_ts = _parse_kickoff(sig.get("kickoff", ""))
        if kick_ts is None:
            stats["skipped"] += 1
            continue

        # Future or match in progress → pending
        if kick_ts > now - 3 * 3600:
            stats["pending"] += 1
            continue

        dt = datetime.fromtimestamp(kick_ts, tz=MSK)
        date_str = dt.strftime("%Y-%m-%d")

        ev_str = sig.get("event", "")
        if " vs " not in ev_str:
            stats["skipped"] += 1
            continue
        home_ru, away_ru = [x.strip() for x in ev_str.split(" vs ", 1)]

        league = sig.get("league", "")
        result = None
        score_str = None

        # Route: footbolno covers RPL + UEFA Nations League (EVR-0015/0017)
        if league in FOOTBOLNO_LEAGUES:
            fb = _get_footbolno()
            fb_match = fb.find_match(home_ru, away_ru, date_str, FOOTBOLNO_LEAGUES[league])
            if fb_match is None:
                stats["skipped"] += 1
                continue
            if fb_match.status != "finished":
                stats["pending"] += 1
                continue
            result = _determine_result_from_match(fb_match)
            if result is None:
                stats["pending"] += 1
                continue
            score_str = f"{fb_match.home_goals}-{fb_match.away_goals}"
        else:
            if date_str not in cache:
                cache[date_str] = _fetch_events_for_date(session, date_str)
                time.sleep(0.4)
            events = cache[date_str]
            match = _find_match(events, home_ru, away_ru)
            if not match:
                stats["skipped"] += 1
                continue
            result = _determine_result(match)
            if result is None:
                stats["pending"] += 1
                continue
            score_str = f"{match.get('intHomeScore')}-{match.get('intAwayScore')}"

        outcome = (sig.get("outcome") or "").lower()
        won = (outcome == result)
        stats["resolved"] += 1
        stats["won" if won else "lost"] += 1

        # Save result
        rid = f"{sig['_src'].replace('.json','')}__{home_ru}__{away_ru}__{outcome}"
        rid = rid.replace("/", "_").replace(" ", "_")
        out = {
            **sig,
            "_result": result,
            "_score": score_str,
            "_won": won,
            "_resolved_at": datetime.now(MSK).isoformat(),
        }
        (RESULTS_DIR / f"{rid}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return stats


if __name__ == "__main__":
    print(json.dumps(resolve_all(), ensure_ascii=False, indent=2))
