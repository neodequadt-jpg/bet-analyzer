"""Smarkets exchange provider (public, no API key)."""
from __future__ import annotations
import os
import time
from typing import List, Dict
from datetime import datetime
import requests

BASE = "https://api.smarkets.com/v3"


def get_http_session():
    s = requests.Session()
    proxy = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
    return s


def _get(session, url, timeout=20, retries=3):
    """GET with retry on 502/503/timeout (opera-proxy flaky)."""
    last = None
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code in (502, 503, 504):
                last = f"HTTP {r.status_code}"
                time.sleep(1.5 * (2 ** attempt))
                continue
            return r
        except Exception as e:
            last = e
            time.sleep(1.5 * (2 ** attempt))
    print(f"[smarkets] give up {url}: {last}")
    return None


def _bp_to_odds(bp):
    return round(10000 / bp, 3) if bp else 0.0


def _extract_league(slug):
    parts = (slug or "").split("/")
    try:
        idx = parts.index("football")
        if idx + 1 < len(parts):
            return parts[idx + 1].replace("-", " ").title()
    except (ValueError, IndexError):
        pass
    return "Smarkets"


import json
from pathlib import Path as _Path

CACHE_PATH = _Path("data/cache/smarkets/events.json")
CACHE_TTL = 300  # 5 minutes


def _cache_load():
    try:
        if CACHE_PATH.exists():
            data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            if time.time() - data.get("ts", 0) < CACHE_TTL:
                return data.get("events", [])
    except Exception:
        pass
    return None


def _cache_save(events):
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(
            json.dumps({"ts": time.time(), "events": events}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def fetch_events(hours=72, max_events=30, deadline_sec=25):
    # Cache hit?
    cached = _cache_load()
    if cached is not None:
        now = time.time()
        lo = now - 3600
        hi = now + hours * 3600
        return [e for e in cached if lo <= e["start_ts"] <= hi][:max_events]

    session = get_http_session()
    now = time.time()
    lo = now - 3600
    hi = now + hours * 3600
    deadline = time.monotonic() + deadline_sec

    r = _get(session, f"{BASE}/events/?type=football_match&state=upcoming&limit=50",
             timeout=10, retries=2)
    if r is None or r.status_code != 200:
        print(f"[smarkets] events fail: {r.status_code if r else 'None'}")
        return []
    data = r.json() or {}

    out = []
    for ev in (data.get("events") or []):
        if len(out) >= max_events:
            break
        if time.monotonic() > deadline:
            print(f"[smarkets] deadline hit ({deadline_sec}s), collected {len(out)}")
            break
        start_dt = ev.get("start_datetime")
        if not start_dt:
            continue
        try:
            dt = datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
            ts = int(dt.timestamp())
        except Exception:
            continue
        if not (lo <= ts <= hi):
            continue
        ev_id = ev.get("id")
        name = ev.get("name", "")
        if " vs " not in name:
            continue
        home, _, away = name.partition(" vs ")

        r2 = _get(session, f"{BASE}/events/{ev_id}/markets/", timeout=15, retries=3)
        if time.monotonic() > deadline:
            break
        markets = (r2.json() if r2 else {}).get("markets", []) if r2 else []
        market_id = None
        for m in markets:
            mt = m.get("market_type") or {}
            if mt.get("name") == "WINNER_3_WAY" and m.get("state") == "open":
                market_id = m.get("id")
                break
        if not market_id:
            continue

        r3 = _get(session, f"{BASE}/markets/{market_id}/contracts/", timeout=15, retries=3)
        if time.monotonic() > deadline:
            break
        contracts = (r3.json() if r3 else {}).get("contracts", []) if r3 else []
        cid_by_side = {}
        for c in contracts:
            ct = (c.get("contract_type") or {}).get("name")
            if ct:
                cid_by_side[ct] = c.get("id")
        if not all(k in cid_by_side for k in ("HOME", "DRAW", "AWAY")):
            continue

        r4 = _get(session, f"{BASE}/markets/{market_id}/quotes/", timeout=15, retries=3)
        quotes = (r4.json() if r4 else {}) or {}

        def best_back(cid):
            q = quotes.get(str(cid)) or quotes.get(cid)
            if not q: return None
            bids = q.get("bids") or []
            if not bids: return None
            return _bp_to_odds(bids[0]["price"])

        oh = best_back(cid_by_side["HOME"])
        od = best_back(cid_by_side["DRAW"])
        oa = best_back(cid_by_side["AWAY"])
        if not (oh and od and oa):
            continue

        out.append({
            "id": f"sm_{ev_id}",
            "sport": "football",
            "league": _extract_league(ev.get("full_slug", "")),
            "home": home.strip(),
            "away": away.strip(),
            "start_ts": ts,
            "odds_home": oh,
            "odds_draw": od,
            "odds_away": oa,
            "bookmaker": "Smarkets",
            "source": "smarkets",
        })
    out.sort(key=lambda x: x["start_ts"])
    _cache_save(out)
    return out


if __name__ == "__main__":
    evs = fetch_events(hours=72)
    print(f"Smarkets events: {len(evs)}")
    for e in evs[:10]:
        dt = datetime.fromtimestamp(e["start_ts"])
        print(f"  {dt:%d.%m %H:%M}  {e['home'][:20]:20} vs {e['away'][:20]:20} @ {e['odds_home']}/{e['odds_draw']}/{e['odds_away']}")
