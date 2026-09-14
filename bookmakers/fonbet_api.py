"""
Fonbet API client.
Публичный JSON API легального ЦУПИС-БК Fonbet.
Endpoint: https://line-lb54-w.bk6bba-resources.com/ma/events/listBase
"""
import gzip
import json
import urllib.request
from pathlib import Path
from typing import Optional

from bookmakers.parser import OddsEvent

FONBET_BASE = "https://line-lb54-w.bk6bba-resources.com"
LIST_BASE_URL = f"{FONBET_BASE}/ma/events/listBase?lang=ru&scopeMarket=1600"
CACHE_PATH = Path("data/cache/fonbet/listBase.json")

# Sport ID РПЛ у Fonbet
SPORT_ID_RPL = 11935

# Кодировка факторов Fonbet (стандартная)
F_HOME = 921   # П1
F_DRAW = 922   # X
F_AWAY = 923   # П2
F_TOTAL_OVER_25 = 930   # ТБ 2.5
F_TOTAL_UNDER_25 = 931  # ТМ 2.5
F_HANDICAP1_P1 = 927    # Ф1 (+1)
F_HANDICAP2_M1 = 928    # Ф2 (-1)

BOOKMAKER_NAME = "Фонбет"


def fetch_list_base(force: bool = False) -> dict:
    """Скачивает listBase (кэширует в data/cache/fonbet/listBase.json)."""
    if not force and CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))

    req = urllib.request.Request(
        LIST_BASE_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
        if body[:1] == b"\x1f":  # gzip magic
            body = gzip.decompress(body)
    data = json.loads(body)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def _top_events_by_sport(data: dict, sport_id: int) -> list[dict]:
    """Возвращает top-level матчи (level=1, kind=1) для указанного sportId."""
    return [
        e for e in data.get("events", [])
        if e.get("level") == 1
        and e.get("kind") == 1
        and e.get("sportId") == sport_id
    ]


def _cf_map(data: dict) -> dict[int, dict]:
    return {c["e"]: c for c in data.get("customFactors", []) if "e" in c}


def parse_rpl_events(data: dict) -> list[OddsEvent]:
    """Парсит РПЛ матчи + 1X2 odds в OddsEvent[]."""
    events = _top_events_by_sport(data, SPORT_ID_RPL)
    cf_map = _cf_map(data)

    out: list[OddsEvent] = []
    for ev in events:
        cf = cf_map.get(ev["id"])
        if not cf:
            continue
        factors = {f["f"]: f["v"] for f in cf.get("factors", [])}

        odds_home = factors.get(F_HOME)
        odds_draw = factors.get(F_DRAW)
        odds_away = factors.get(F_AWAY)
        if not (odds_home and odds_draw and odds_away):
            continue

        out.append(OddsEvent(
            event_id=f"fonbet_{ev['id']}",
            sport="football",
            league="RPL",
            home=str(ev.get("team1", "")).strip(),
            away=str(ev.get("team2", "")).strip(),
            kickoff_iso=str(ev.get("startTime", "")),
            bookmaker=BOOKMAKER_NAME,
            odds_home=float(odds_home),
            odds_draw=float(odds_draw),
            odds_away=float(odds_away),
            odds_total_over=factors.get(F_TOTAL_OVER_25),
            odds_total_under=factors.get(F_TOTAL_UNDER_25),
            total_line=2.5,
        ))
    return out


def fetch_rpl_odds(force: bool = False) -> list[OddsEvent]:
    """High-level: скачать + распарсить РПЛ."""
    data = fetch_list_base(force=force)
    return parse_rpl_events(data)


if __name__ == "__main__":
    events = fetch_rpl_odds(force=False)
    print(f"РПЛ events: {len(events)}")
    for e in events[:5]:
        print(f"  {e.home:22} vs {e.away:22} | "
              f"1={e.odds_home} X={e.odds_draw} 2={e.odds_away}")
