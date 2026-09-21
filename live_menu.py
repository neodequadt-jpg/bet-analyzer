"""Live submenu: sport -> time -> matches + express."""
from datetime import datetime, timedelta, timezone

MSK = timezone(timedelta(hours=3))

SPORTS_LIST = ["tt", "football", "hockey", "tennis", "basketball", "volleyball"]
SPORT_ALIASES = {
    "tt": "tt", "football": "football", "hockey": "hockey",
    "tennis": "tennis", "basketball": "basketball",
    "volleyball": "volleyball", "all": "all",
}


def sport_keyboard():
    return {"inline_keyboard": [
        [{"text": "\U0001F3D3 TT", "callback_data": "live_sport:tt"},
         {"text": "\u26bd \u0424\u0443\u0442\u0431\u043e\u043b",
          "callback_data": "live_sport:football"}],
        [{"text": "\U0001F3D2 \u0425\u043e\u043a\u043a\u0435\u0439",
          "callback_data": "live_sport:hockey"},
         {"text": "\U0001F3BE \u0422\u0435\u043d\u043d\u0438\u0441",
          "callback_data": "live_sport:tennis"}],
        [{"text": "\U0001F3C0 \u0411\u0430\u0441\u043a\u0435\u0442",
          "callback_data": "live_sport:basketball"},
         {"text": "\U0001F3D0 \u0412\u043e\u043b\u0435\u0439",
          "callback_data": "live_sport:volleyball"}],
        [{"text": "\U0001F30D \u0412\u0441\u0435 \u0441\u043f\u043e\u0440\u0442\u044b",
          "callback_data": "live_sport:all"}],
        [{"text": "\u2b05\ufe0f \u041d\u0430\u0437\u0430\u0434",
          "callback_data": "back:main"}],
    ]}


def time_keyboard(sport):
    return {"inline_keyboard": [
        [{"text": "\u26a1 1 \u0447\u0430\u0441", "callback_data": f"live_run:{sport}:1"},
         {"text": "\U0001F4C5 24 \u0447\u0430\u0441\u0430", "callback_data": f"live_run:{sport}:24"}],
        [{"text": "\U0001F4C6 72 \u0447\u0430\u0441\u0430", "callback_data": f"live_run:{sport}:72"},
         {"text": "\U0001F5D3 7 \u0434\u043d\u0435\u0439", "callback_data": f"live_run:{sport}:168"}],
        [{"text": "\U0001F4C5 30 \u0434\u043d\u0435\u0439", "callback_data": f"live_run:{sport}:720"}],
        [{"text": "\u2b05\ufe0f \u041d\u0430\u0437\u0430\u0434", "callback_data": "back:sports"}],
    ]}


def result_keyboard(sport, hours):
    return {"inline_keyboard": [
        [{"text": "\u26a1 \u0421\u043e\u0431\u0440\u0430\u0442\u044c \u044d\u043a\u0441\u043f\u0440\u0435\u0441\u0441",
          "callback_data": f"live_express:{sport}:{hours}"}],
        [{"text": "\u2b05\ufe0f \u041a \u0432\u0440\u0435\u043c\u0435\u043d\u0438",
          "callback_data": f"live_sport:{sport}"}],
    ]}


def fetch_matches(sport, hours):
    """Return list of dicts with home/away/league/start_ts/odds_home/odds_away."""
    if sport == "all":
        return _fetch_multi(hours)
    try:
        from bookmakers.fonbet_extended import fetch_events_by_sport, resolve_sport
        sid = resolve_sport(sport)
        if sid is None:
            return []
        # more events for larger windows
        max_ev = 500 if hours >= 168 else max(20, hours * 3)
        return fetch_events_by_sport(sid, hours=hours, max_events=max_ev)
    except Exception as e:
        print(f"[live_menu] fetch {sport} failed: {e}")
        return []


def _fetch_multi(hours):
    """3 per sport across 6 sports, deduped."""
    out = []
    for sp in SPORTS_LIST:
        try:
            evs = fetch_matches(sp, hours)
            for e in evs[:3]:
                d = dict(e)
                d["_sport"] = sp
                out.append(d)
        except Exception:
            continue
    return out


def format_matches(events, sport, hours):
    now = datetime.now(MSK)
    end = now + timedelta(hours=hours)
    label = "все спорты" if sport == "all" else sport
    header = (f"\U0001F534 <b>/live {label} \u2014 {hours} \u0447</b>\n"
              f"{now:%d.%m %H:%M} \u2192 {end:%d.%m %H:%M} \u041c\u0421\u041a\n\n")
    if not events:
        return header + "\u041c\u0430\u0442\u0447\u0435\u0439 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e."
    lines = [header]
    for i, e in enumerate(events, 1):
        ts = e.get("start_ts", 0)
        dt = datetime.fromtimestamp(ts, tz=MSK) if ts else None
        time_str = f"{dt:%H:%M}" if dt else "\u2014"
        oh = e.get("odds_home") or "\u2014"
        oa = e.get("odds_away") or "\u2014"
        sp_tag = f" [{e.get('_sport','')}]" if sport == "all" else ""
        lines.append(f"{i}. <b>{time_str}</b> {e.get('home','')} vs {e.get('away','')}{sp_tag}")
        if e.get("league"):
            lines.append(f"   {e['league'][:50]}")
        lines.append(f"   \u041f1: <code>{oh}</code> | \u041f2: <code>{oa}</code>")
    lines.append(f"\n\u0412\u0441\u0435\u0433\u043e: {min(len(events),15)}")
    return "\n".join(lines)


def build_express(events, sport, hours):
    scored = []
    for e in events:
        oh = e.get("odds_home")
        oa = e.get("odds_away")
        if not oh or not oa:
            continue
        try:
            implied = 1/float(oh) + 1/float(oa)
        except (ZeroDivisionError, TypeError, ValueError):
            continue
        scored.append((implied, e))
    if len(scored) < 2:
        return None
    scored.sort(key=lambda x: x[0])

    # Multi-sport: 1 per sport
    if sport == "all":
        seen = set()
        filtered = []
        for _, e in scored:
            sp = e.get("_sport", "?")
            if sp in seen:
                continue
            seen.add(sp)
            filtered.append((_, e))
            if len(filtered) >= 3:
                break
        scored = filtered

    legs = []
    for _, e in scored[:3]:
        oh = float(e["odds_home"])
        oa = float(e["odds_away"])
        if oh < oa:
            side = f"\u043f\u043e\u0431\u0435\u0434\u0430 {e['home']}"
            odds = oh
        else:
            side = f"\u043f\u043e\u0431\u0435\u0434\u0430 {e['away']}"
            odds = oa
        ts = e.get("start_ts", 0)
        dt = datetime.fromtimestamp(ts, tz=MSK) if ts else None
        time_str = f"{dt:%d.%m %H:%M}" if dt else "?"
        legs.append({
            "event": f"{e['home']} vs {e['away']}",
            "outcome": side,
            "odds": odds,
            "league": e.get("league", ""),
            "kickoff": time_str,
        })
    total = 1.0
    for leg in legs:
        total *= leg["odds"]
    label = "мульти-спорт" if sport == "all" else sport
    lines = [f"\U0001F3AF <b>\u042d\u041a\u0421\u041f\u0420\u0415\u0421\u0421 ({label}, {hours} \u0447)</b>\n"]
    for i, leg in enumerate(legs, 1):
        lines.append(f"{i}. <b>{leg['event']}</b> ({leg['kickoff']})")
        lines.append(f"   \u2014 {leg['outcome']}")
        lines.append(f"   @ <b>{leg['odds']}</b>")
        if leg["league"]:
            lines.append(f"   {leg['league'][:50]}")
        lines.append("")
    lines.append(f"\U0001F4CA \u0418\u0442\u043e\u0433\u043e: <b>{round(total, 2)}</b>")
    lines.append("\u26a0\ufe0f \u041d\u0435 value-\u0441\u0442\u0430\u0432\u043a\u0430, \u0430 \u0432\u044b\u0431\u043e\u0440 \u043f\u043e \u0440\u044b\u043d\u043e\u0447\u043d\u043e\u043c\u0443 \u043a\u043e\u043d\u0441\u0435\u043d\u0441\u0443\u0441\u0443.")
    return "\n".join(lines)
