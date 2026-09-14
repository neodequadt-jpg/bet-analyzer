#!/usr/bin/env python3
"""tg_bot.py — Telegram long-polling bot for BET-ANALYZER.

Pipeline: Fonbet + manual -> consensus -> EV -> value bets -> AI express/report.
Uses ONLY requests + stdlib (no aiogram / telebot / asyncio / threading).

- BOT_TOKEN from env (empty -> message + exit(1) in main()).
- Optional chat whitelist via TG_ADMIN_ID.
- Telegram API calls use requests default behavior (system env proxies are
  respected, nothing is bypassed); local OmniRoute goes via no_proxy.
"""

import html
import json
import os
import sys
import time

import requests

# Fix: project packages (bookmakers.*, market.*, scoring.*, ai.*) must be
# importable without PYTHONPATH.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bookmakers.fonbet_api import fetch_rpl_odds
from bookmakers.manual_source import list_manual_events, parse_manual
from bookmakers.normalizer import merge
from market.consensus import evaluate_event
from scoring.ev import evaluate_value
from ai.express_builder import ExpressBuilder
from ai.analyst import ValueBetAnalyst

# ---------------------------------------------------------------------------
# 1. Config
# ---------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
API_BASE = "https://api.telegram.org/bot" + BOT_TOKEN

TG_ADMIN_ID = None
try:
    _admin = os.environ.get("TG_ADMIN_ID", "").strip()
    if _admin:
        TG_ADMIN_ID = int(_admin)
except ValueError:
    print("[tg_bot] invalid TG_ADMIN_ID, whitelist disabled", file=sys.stderr)
    TG_ADMIN_ID = None

START_TIME = time.time()
HTTP_TIMEOUT = 30
MAX_MESSAGE_LEN = 4000

WELCOME_TEXT = (
    "<b>\U0001F9E0 BET-ANALYZER bot</b>\n"
    "Pipeline: Fonbet + manual \u2192 consensus \u2192 EV \u2192 value bets.\n\n"
    "<b>Commands:</b>\n"
    "/start \u2014 welcome\n"
    "/help \u2014 this help\n"
    "/value \u2014 run pipeline, show value bets\n"
    "/express \u2014 AI express from value bets\n"
    "/report \u2014 AI analyst report on the top bet\n"
    "/status \u2014 bot & pipeline status"
)

OUTCOME_LABELS = {"home": "home", "draw": "draw", "away": "away"}


# ---------------------------------------------------------------------------
# 2. Low-level helpers (requests only, timeout=30)
# ---------------------------------------------------------------------------
def esc(text) -> str:
    """Escape text for Telegram HTML parse mode."""
    return html.escape(str(text))


def tg_get(method, params=None) -> dict:
    url = API_BASE + "/" + method
    r = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError("Telegram API error: " + str(data.get("description")))
    return data


def tg_post(method, json_data=None) -> dict:
    url = API_BASE + "/" + method
    r = requests.post(url, json=json_data or {}, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError("Telegram API error: " + str(data.get("description")))
    return data


def get_updates(offset=None, timeout=25) -> list:
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    data = tg_get("getUpdates", params)
    return data.get("result") or []


def chunk_text(text, max_len=MAX_MESSAGE_LEN) -> list:
    """Split long text (>4000 chars) into chunks on line boundaries."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    buf = ""
    for line in text.split("\n"):
        if len(line) > max_len:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.extend(line[i:i + max_len] for i in range(0, len(line), max_len))
            continue
        candidate = line if not buf else buf + "\n" + line
        if len(candidate) > max_len:
            chunks.append(buf)
            buf = line
        else:
            buf = candidate
    if buf:
        chunks.append(buf)
    return chunks


def send_message(chat_id, text, parse_mode="HTML"):
    """Send possibly-long message; long text is split into chunks."""
    for chunk in chunk_text(text):
        tg_post("sendMessage", {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": parse_mode,
        })


# ---------------------------------------------------------------------------
# 4. Pipeline helper (shared by /value, /express, /report)
# ---------------------------------------------------------------------------
def build_pipeline():
    fonbet = fetch_rpl_odds(force=True)
    manual = []
    for eid in list_manual_events():
        manual.extend(parse_manual(eid))
    groups = merge(fonbet, manual)
    result = []  # list of {event, consensus, value_bets}
    for g in groups:
        if len(g) < 3:
            continue
        market = evaluate_event(g)
        if market.get("status") != "ok":
            continue
        vbs = evaluate_value(market)
        result.append({
            "event": market["event"],
            "consensus": market["consensus"],
            "value_bets": [vb.__dict__ for vb in vbs],
        })
    return result


# ---------------------------------------------------------------------------
# 3. Commands
# ---------------------------------------------------------------------------
def cmd_value() -> str:
    t0 = time.time()
    results = build_pipeline()
    elapsed = time.time() - t0

    n_matches = len(results)
    n_bets = sum(len(item["value_bets"]) for item in results)

    lines = [
        f"<b>Value analysis</b> \u2014 {n_matches} matches, {n_bets} value bets "
        f"({elapsed:.1f}s)"
    ]
    for item in results:
        if not item["value_bets"]:
            continue
        ev = item["event"]
        lines.append("")
        lines.append(
            f"\U0001F3C6 <b>{esc(ev['home'])}</b> vs <b>{esc(ev['away'])}</b> "
            f"({esc(ev['league'])})"
        )
        for vb in item["value_bets"]:
            lines.append(
                f"\u2022 {OUTCOME_LABELS.get(vb['outcome'], vb['outcome'])} @ "
                f"{esc(vb['bookmaker'])} \u2014 odds {vb['odds']}"
                f" | EV <b>+{vb['ev'] * 100:.1f}%</b>"
                f" | Kelly {vb['kelly'] * 100:.1f}%"
                f" | score {vb['deal_score']}"
            )
            if vb.get("reasons"):
                lines.append("    " + esc("; ".join(vb["reasons"])))
    if n_bets == 0:
        lines.append("")
        lines.append("No value bets found \u2014 market is efficient.")
    return "\n".join(lines)


def cmd_express() -> str:
    results = build_pipeline()
    all_vbs = []
    events_meta = {}
    for idx, item in enumerate(results, start=1):
        ev = item["event"]
        eid = f"match_{idx}"
        events_meta[eid] = {
            "home": ev["home"],
            "away": ev["away"],
            "league": ev["league"],
        }
        for vb in item["value_bets"]:
            d = dict(vb)
            d["event_id"] = eid
            d["event"] = f"{ev['home']} vs {ev['away']}"
            all_vbs.append(d)

    express = ExpressBuilder().build(all_vbs, events_meta)
    pretty = json.dumps(express, ensure_ascii=False, indent=2)
    escaped = html.escape(pretty)
    if len(escaped) <= MAX_MESSAGE_LEN:
        return "<pre>" + escaped + "</pre>"
    return escaped


def cmd_report() -> str:
    results = build_pipeline()
    item = next((r for r in results if r["value_bets"]), None)
    if item is None:
        return "No value-bets found \u2014 nothing to analyze."
    ev = item["event"]
    report = ValueBetAnalyst().analyze(
        event=ev,
        consensus=item["consensus"],
        value_bets=item["value_bets"],
    )
    header = (
        f"<b>{esc(ev['home'])} vs {esc(ev['away'])}</b> "
        f"({esc(ev['league'])}) \u2014 AI analyst\n"
    )
    return header + html.escape(report)


def pipeline_availability() -> str:
    lines = []
    cache = os.path.join("data", "cache", "fonbet", "listBase.json")
    lines.append(f"\u2022 fonbet cache: {'yes' if os.path.exists(cache) else 'no'}")
    manual_dir = os.path.join("data", "manual")
    if os.path.isdir(manual_dir):
        try:
            n = len([f for f in os.listdir(manual_dir) if f.endswith(".json")])
        except OSError:
            n = 0
        lines.append(f"\u2022 manual json files: {n}")
    else:
        lines.append("\u2022 manual dir: missing")
    try:
        # Any HTTP status (e.g. 405 on GET) proves the OmniRoute server is up;
        # only a connection error means the pipeline AI is unreachable.
        requests.get("http://127.0.0.1:20128/v1/chat/completions", timeout=2)
        lines.append("\u2022 OmniRoute: reachable")
    except Exception as e:
        lines.append(f"\u2022 OmniRoute: unreachable ({esc(str(e)[:60])})")
    return "\n".join(lines)


def fmt_uptime(total_secs) -> str:
    days, rem = divmod(total_secs, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    return f"{days}d {hours:02d}:{mins:02d}:{secs:02d}"


def cmd_status() -> str:
    uptime_secs = int(time.time() - START_TIME)
    lines = ["<b>BOT STATUS</b>", f"uptime: {fmt_uptime(uptime_secs)}", ""]
    try:
        data = tg_get("getMe")
        me = data.get("result") or {}
        first = me.get("first_name") or me.get("username") or "?"
        username = me.get("username", "?")
        lines.append(f"bot: <b>{esc(first)}</b> @{esc(username)}")
        lines.append(f"api ok: {bool(data.get('ok'))}")
    except Exception as e:
        lines.append(f"bot info: unavailable \u2014 {esc(str(e)[:120])}")
    lines.append("")
    lines.append("<b>Pipeline availability:</b>")
    lines.append(pipeline_availability())
    return "\n".join(lines)


def dispatch(command: str) -> str:
    if command in ("/start", "/help"):
        return WELCOME_TEXT
    if command == "/value":
        return cmd_value()
    if command == "/express":
        return cmd_express()
    if command == "/report":
        return cmd_report()
    if command == "/status":
        return cmd_status()
    return "Unknown command. Use /help to see available commands."


# ---------------------------------------------------------------------------
# 5. Main loop
# ---------------------------------------------------------------------------
def handle(update):
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return
    if TG_ADMIN_ID is not None and chat_id != TG_ADMIN_ID:
        return
    text = (message.get("text") or "").strip()
    if not text:
        return
    command = text.split()[0].split("@")[0].lower()
    try:
        reply = dispatch(command)
    except Exception as e:
        reply = "\u26A0\uFE0F error while running " + esc(command) + ": " + esc(str(e))[:400]
    send_message(chat_id, reply)


def main():
    if not BOT_TOKEN:
        print(
            "[tg_bot] BOT_TOKEN is not set. "
            "Export BOT_TOKEN=<telegram-bot-token> and run again.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("[tg_bot] starting, polling api.telegram.org ...")
    if TG_ADMIN_ID is not None:
        print(f"[tg_bot] chat whitelist: {TG_ADMIN_ID}")

    offset = None
    while True:
        try:
            updates = get_updates(offset)
        except Exception as e:
            print(f"[tg_bot] getUpdates failed: {e}", file=sys.stderr)
            time.sleep(5)
            continue  # never crash the loop
        for update in updates:
            try:
                offset = update["update_id"] + 1
                handle(update)
            except Exception as e:
                print(f"[tg_bot] handle update failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()