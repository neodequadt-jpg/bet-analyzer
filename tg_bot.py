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
from datetime import datetime, timedelta, timezone

import requests
import logging
# urllib3/requests must never log full request URLs (they contain BOT_TOKEN)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

# Fix: project packages (bookmakers.*, market.*, scoring.*, ai.*) must be
# importable without PYTHONPATH.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bookmakers.fonbet_api import fetch_rpl_odds
from bookmakers.fonbet_extended import fetch_events_by_sport, resolve_sport
from bookmakers.manual_source import list_manual_events, parse_manual
from bookmakers.normalizer import merge
from market.consensus import evaluate_event
from scoring.ev import evaluate_value
from ai.express_builder import ExpressBuilder
from ai.analyst import ValueBetAnalyst
from pathlib import Path

import re
_BOT_TOKEN_RE = re.compile(r"bot\d+:[A-Za-z0-9_-]+")
def _sanitize_error(text) -> str:
    """Redact Telegram bot token from error strings."""
    return _BOT_TOKEN_RE.sub("bot<REDACTED>", str(text))

# ---------------------------------------------------------------------------
# 1. Config
# ---------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
API_BASE = "https://api.telegram.org/bot" + BOT_TOKEN

def _parse_admin_ids(raw: str) -> set:
    """Parse a comma-separated TG_ADMIN_ID into a set of chat_ids."""
    out = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            pass
    return out


TG_ADMIN_IDS = _parse_admin_ids(os.environ.get("TG_ADMIN_ID", ""))
# backward-compat alias for any external references
TG_ADMIN_ID = next(iter(TG_ADMIN_IDS)) if len(TG_ADMIN_IDS) == 1 else None

START_TIME = time.time()
HTTP_TIMEOUT = 8
MAX_MESSAGE_LEN = 4000

# Resilience: long-poll getUpdates(timeout=25) dies on a flapping proxy,
# so we short-poll (timeout=1), warm the tunnel up front, and back off
# exponentially (3s -> 60s) on repeated failures.
BACKOFF_INITIAL = 3
BACKOFF_MAX = 60

# --- AI chat (universal sports-betting prompt) ---
_PROMPT_PATH = Path(__file__).parent / "prompts" / "sports_betting_ru.txt"
CHAT_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8") if _PROMPT_PATH.exists() else ""
OMNI_CHAT_URL = "http://127.0.0.1:20128/v1/chat/completions"
OMNI_CHAT_MODEL = "oc/big-pickle"
CHAT_HISTORY = {}
CHAT_HISTORY_MAX = 12

# ---------------------------------------------------------------------------
# i18n (RU/EN): dict-based, no babel/gettext
# ---------------------------------------------------------------------------
_LANG = {}                      # chat_id -> "ru" | "en"
DEFAULT_LANG = "ru"

_I18N = {
    "ru": {
        "welcome_title": "<b>\U0001F9E0 BET-ANALYZER bot</b>\n",
        "welcome_sub": "Pipeline: Fonbet + manual \u2192 consensus \u2192 EV \u2192 value bets.\n\n",
        "welcome_cmds": "<b>Команды:</b>\n",
        "welcome_footer": "\n\u0418\u043b\u0438 \u043f\u0440\u043e\u0441\u0442\u043e "
                          "\u043d\u0430\u043f\u0438\u0448\u0438 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 "
                          "\u2014 AI-\u0430\u0441\u0441\u0438\u0441\u0442\u0435\u043d\u0442 "
                          "\u043e\u0442\u0432\u0435\u0442\u0438\u0442.\n",
        "kb_value": "\U0001F4CA Value",
        "kb_express": "\u26A1 \u042d\u043a\u0441\u043f\u0440\u0435\u0441\u0441",
        "kb_report": "\U0001F4C4 \u041e\u0442\u0447\u0451\u0442",
        "kb_status": "\u2139\uFE0F \u0421\u0442\u0430\u0442\u0443\u0441",
        "kb_live": "\U0001F3BE Live TT",
        "kb_lang": "\U0001F310 EN",
        "live_header": "\u26A1 /live {sport} \u2014 \u0431\u043b\u0438\u0436\u0430\u0439\u0448\u0438\u0435 {hours} \u0447",
        "live_empty": "\u041c\u0430\u0442\u0447\u0435\u0439 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e \u0432 \u0431\u043b\u0438\u0436\u0430\u0439\u0448\u0438\u0435 {hours} \u0447.",
        "live_usage": "\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0438\u0435: /live &lt;sport&gt; &lt;hours&gt;\nsport: tt | football | hockey | tennis | esports\nhours: 1..4",
        "live_total": "\u0412\u0441\u0435\u0433\u043e: {n} \u043c\u0430\u0442\u0447\u0435\u0439.",
        "live_min_suffix": "\u043c\u0438\u043d",
        "live_msk": "\u041c\u0421\u041a",
        "live_in_min": "\u0447\u0435\u0440\u0435\u0437 {n} {unit}",
        "rate_limit": "\u23F3 \u0421\u043b\u0438\u0448\u043a\u043e\u043c \u043c\u043d\u043e\u0433\u043e \u0437\u0430\u043f\u0440\u043e\u0441\u043e\u0432. \u041f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u0435 \u0447\u0435\u0440\u0435\u0437 {n} \u0441.",
        "wl_reject": "\U0001F512 \u0411\u043e\u0442 \u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442 \u043f\u043e \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u044f\u043c.\n\u0412\u0430\u0448 chat_id: <code>{id}</code>\n\u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0435\u0433\u043e \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0443 \u0434\u043b\u044f \u0434\u043e\u0441\u0442\u0443\u043f\u0430.",
        "whoami_hint": "\u0412\u0430\u0448 chat_id: <code>{id}</code>\n\n\u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0435\u0433\u043e \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0443, \u0435\u0441\u043b\u0438 \u0431\u043e\u0442 \u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442 \u043f\u043e \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u044f\u043c.",
        "reset_ok": "\u2705 \u0418\u0441\u0442\u043e\u0440\u0438\u044f \u0434\u0438\u0430\u043b\u043e\u0433\u0430 \u0441 AI \u043e\u0447\u0438\u0449\u0435\u043d\u0430.",
        "lang_switched": "\U0001F310 \u042f\u0437\u044b\u043a \u043f\u0435\u0440\u0435\u043a\u043b\u044e\u0447\u0451\u043d \u043d\u0430: \u0420\u0443\u0441\u0441\u043a\u0438\u0439",
        "ai_directive": "\u041e\u0442\u0432\u0435\u0447\u0430\u0439 \u0422\u041e\u041b\u042c\u041a\u041e \u043d\u0430 \u0440\u0443\u0441\u0441\u043a\u043e\u043c \u044f\u0437\u044b\u043a\u0435.",
    },
    "en": {
        "welcome_title": "<b>\U0001F9E0 BET-ANALYZER bot</b>\n",
        "welcome_sub": "Pipeline: Fonbet + manual \u2192 consensus \u2192 EV \u2192 value bets.\n\n",
        "welcome_cmds": "<b>Commands:</b>\n",
        "welcome_footer": "\nOr just send a message \u2014 the AI assistant will reply.\n",
        "kb_value": "\U0001F4CA Value",
        "kb_express": "\u26A1 Express",
        "kb_report": "\U0001F4C4 Report",
        "kb_status": "\u2139\uFE0F Status",
        "kb_live": "\U0001F3BE Live TT",
        "kb_lang": "\U0001F310 RU",
        "live_header": "\u26A1 /live {sport} \u2014 next {hours} h",
        "live_empty": "No matches found in the next {hours} h.",
        "live_usage": "Usage: /live &lt;sport&gt; &lt;hours&gt;\nsport: tt | football | hockey | tennis | esports\nhours: 1..4",
        "live_total": "Total: {n} matches.",
        "live_min_suffix": "min",
        "live_msk": "MSK",
        "live_in_min": "in {n} {unit}",
        "rate_limit": "\u23F3 Too many requests. Retry in {n} s.",
        "wl_reject": "\U0001F512 Bot is invite-only.\nYour chat_id: <code>{id}</code>\nSend it to the admin for access.",
        "whoami_hint": "Your chat_id: <code>{id}</code>\n\nSend it to the admin if the bot is invite-only.",
        "reset_ok": "\u2705 AI chat history cleared.",
        "lang_switched": "\U0001F310 Language switched to: English",
        "ai_directive": "Reply ONLY in English.",
    },
}

def _get_lang(chat_id) -> str:
    return _LANG.get(chat_id, DEFAULT_LANG)

def _set_lang(chat_id, lang: str) -> str:
    lang = (lang or "").lower().strip()
    if lang in ("en", "eng", "english", "ang"):
        _LANG[chat_id] = "en"
    elif lang in ("ru", "rus", "russian"):
        _LANG[chat_id] = "ru"
    else:
        # toggle
        cur = _get_lang(chat_id)
        _LANG[chat_id] = "en" if cur == "ru" else "ru"
    return _LANG[chat_id]

def _t(chat_id, key, **fmt) -> str:
    lang = _get_lang(chat_id)
    text = _I18N.get(lang, {}).get(key) or _I18N[DEFAULT_LANG].get(key) or key
    return text.format(**fmt) if fmt else text

# argv for /live set by handle()/_handle_callback() before dispatch (see D4)
_LAST_LIVE_ARGV: list = []
_LAST_CHAT_ID = None

WELCOME_TEXT = (
    "<b>\U0001F9E0 BET-ANALYZER bot</b>\n"
    "Pipeline: Fonbet + manual \u2192 consensus \u2192 EV \u2192 value bets.\n\n"
    "<b>Commands:</b>\n"
    "/start \u2014 welcome\n"
    "/help \u2014 this help\n"
    "/value \u2014 run pipeline, show value bets\n"
    "/express \u2014 AI express from value bets\n"
    "/report \u2014 AI analyst report on the top bet\n"
    "/live &lt;sport&gt; &lt;hours&gt; \u2014 upcoming matches (tt/football/hockey/tennis/esports)\n"
    "/status \u2014 bot & pipeline status\n"
    "/whoami \u2014 print your chat_id\n"
    "/reset \u2014 clear AI chat history\n"
    "/prompt \u2014 show active system prompt\n"
    "\n"
    "\u0418\u043b\u0438 \u043f\u0440\u043e\u0441\u0442\u043e \u043d\u0430\u043f\u0438\u0448\u0438 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 \u2014 AI-\u0430\u0441\u0441\u0438\u0441\u0442\u0435\u043d\u0442 \u043e\u0442\u0432\u0435\u0442\u0438\u0442.\n"
)

_MAIN_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "\u26A1 \u042d\u043a\u0441\u043f\u0440\u0435\u0441\u0441", "callback_data": "/express"},
            {"text": "\U0001F3BE Live TT", "callback_data": "/live tt 1"},
        ],
        [
            {"text": "\U0001F4CA Value", "callback_data": "/value"},
            {"text": "\U0001F4C4 \u041e\u0442\u0447\u0451\u0442", "callback_data": "/report"},
        ],
        [
            {"text": "\u2139\uFE0F \u0421\u0442\u0430\u0442\u0443\u0441", "callback_data": "/status"},
            {"text": "\U0001F310 EN", "callback_data": "/lang"},
        ],
    ],
}

def get_main_keyboard(chat_id) -> dict:
    """Inline keyboard with per-chat language labels (3 grouped rows)."""
    return {
        "inline_keyboard": [
            [
                {"text": _t(chat_id, "kb_express"), "callback_data": "/express"},
                {"text": _t(chat_id, "kb_live"),    "callback_data": "/live tt 1"},
            ],
            [
                {"text": _t(chat_id, "kb_value"),  "callback_data": "/value"},
                {"text": _t(chat_id, "kb_report"), "callback_data": "/report"},
            ],
            [
                {"text": _t(chat_id, "kb_status"), "callback_data": "/status"},
                {"text": _t(chat_id, "kb_lang"),   "callback_data": "/lang"},
            ],
        ],
    }

def get_welcome_text(chat_id) -> str:
    """Welcome/help text localized for the chat's language."""
    lines = [
        _t(chat_id, "welcome_title"),
        _t(chat_id, "welcome_sub"),
        _t(chat_id, "welcome_cmds"),
        "/start \u2014 welcome\n",
        "/help \u2014 help\n",
        "/value \u2014 value bets\n",
        "/express \u2014 AI express\n",
        "/report \u2014 AI report\n",
        "/live &lt;sport&gt; &lt;hours&gt; \u2014 upcoming matches (tt/football/hockey/tennis/esports)\n",
        "/status \u2014 system status\n",
        "/whoami \u2014 my chat_id\n",
        "/reset \u2014 clear AI history\n",
        "/prompt \u2014 show system prompt\n",
        "/lang \u2014 switch language (RU/EN)\n",
        _t(chat_id, "welcome_footer"),
    ]
    return "".join(lines)

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


def get_updates(offset=None, timeout=1, retries=3, pause=0.3) -> list:
    """Short-poll with fast internal retries for a flaky proxy.

    opera-proxy randomly times out ~30% of requests (observed). Retry up to
    `retries` extra times with a short `pause` before letting the error through,
    so a single flake does not cost the caller a multi-second backoff.
    """
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    last_err = None
    for attempt in range(retries + 1):
        try:
            data = tg_get("getUpdates", params)
            return data.get("result") or []
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(pause)
    raise last_err


def chunk_text(text, max_len=MAX_MESSAGE_LEN) -> list:
    """Split long text into chunks on line boundaries; lossless for normal lines.

    When every line is no longer than max_len - 1, boundaries fall exactly at
    line ends and each non-final chunk keeps its trailing "\\n" separator, so
    "".join(chunks) == text. Lines longer than max_len - 1 are hard-split
    (losslessness is not guaranteed for those lines alone).
    """
    if len(text) <= max_len:
        return [text]
    chunks = []
    buf = []
    buf_len = 0
    for line in text.split("\n"):
        if len(line) > max_len - 1:
            # Hard split: flush any pending lines (keeping their separator),
            # then split the over-long line itself.
            if buf:
                chunks.append("\n".join(buf) + "\n")
                buf, buf_len = [], 0
            chunks.extend(line[i:i + max_len] for i in range(0, len(line), max_len))
            continue
        if not buf:
            buf, buf_len = [line], len(line)
            continue
        candidate_len = buf_len + 1 + len(line)
        if candidate_len > max_len - 1:
            # The next line would overflow: close this chunk at the current
            # line end and carry the "\n" separator over to the chunk's end.
            chunks.append("\n".join(buf) + "\n")
            buf, buf_len = [line], len(line)
        else:
            buf.append(line)
            buf_len = candidate_len
    if buf:
        chunks.append("\n".join(buf))
    return chunks


def send_message(chat_id, text, parse_mode="HTML", reply_markup=None, retries=3):
    """Send possibly-long message; long text is split into chunks.

    Each chunk is sent with up to `retries` attempts and growing pauses
    (1.5s, 3.0s, ...) so the bot survives a flapping proxy; the last
    error is re-raised. `reply_markup` is attached ONLY to the last chunk.
    """
    chunks = chunk_text(text)
    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": parse_mode,
        }
        if reply_markup is not None and i == len(chunks) - 1:
            payload["reply_markup"] = reply_markup
        for attempt in range(retries):
            try:
                tg_post("sendMessage", payload)
                break
            except Exception:
                if attempt == retries - 1:
                    raise
                time.sleep(1.5 * (2 ** attempt))


def _human_outcome(outcome, home, away) -> str:
    """Map a machine outcome key to a human-readable Russian phrase."""
    if outcome == "home":
        return f"победа {home}"
    if outcome == "draw":
        return "ничья"
    if outcome == "away":
        return f"победа {away}"
    if outcome == "over":
        return "тотал больше"
    if outcome == "under":
        return "тотал меньше"
    return str(outcome)


def _event_teams(event) -> tuple:
    """Split an event string "Home vs Away" into (home, away)."""
    parts = str(event).split(" vs ")
    if len(parts) >= 2:
        return parts[0], parts[1]
    return str(event), ""


SPORT_EMOJI = {
    "football": "⚽",
    "hockey": "🏒",
    "basketball": "🏀",
    "tennis": "🎾",
}


def _human_kickoff(raw) -> str:
    """Unix ts (digits) or ISO 8601 → 'DD.MM HH:MM' or '' if unparsable."""
    if raw is None or raw == "":
        return ""
    s = str(raw).strip()
    if s.isdigit():
        try:
            from datetime import datetime
            return datetime.fromtimestamp(int(s)).strftime("%d.%m %H:%M")
        except (ValueError, OSError):
            return s
    # ISO-like: '2026-09-15T19:00:00+03:00'
    if "T" in s:
        return s[:16].replace("T", " ")
    return s


def _sport_emoji(sport) -> str:
    return SPORT_EMOJI.get(str(sport or "").lower(), "")


def format_express(express: dict, events_meta: dict | None = None) -> str:
    """Render an ExpressBuilder result as plain human-readable HTML.

    events_meta is optional (backward compatible): when provided, each leg's
    sport emoji and kickoff time are looked up by the "Home vs Away" label.
    """
    legs = express.get("legs") or []
    if not legs and express.get("reason") is not None:
        return "\U0001F6AB Экспресс не собран: " + esc(express["reason"])
    if "error" in express:
        return "\u26A0\uFE0F Ошибка: " + esc(express["error"])

    # Map "Home vs Away" label -> meta dict, so AI legs (which carry the label
    # string, not an event_id) can be enriched with sport/kickoff.
    meta_by_label = {}
    for _eid, m in (events_meta or {}).items():
        label = (str(m.get("home", "")) + " vs " + str(m.get("away", ""))).strip()
        meta_by_label[label] = m

    parts = [
        f"\U0001F3AF <b>ЭКСПРЕСС</b> ({len(legs)} исходов)",
        "",
    ]
    for idx, leg in enumerate(legs, start=1):
        event_str = str(leg.get("event") or "")
        home, away = _event_teams(leg.get("event"))
        outcome = _human_outcome(leg.get("outcome"), home, away)
        meta = meta_by_label.get(event_str.strip())
        sport = _sport_emoji(meta.get("sport")) if meta else ""
        kickoff = _human_kickoff(meta.get("kickoff")) if meta else ""
        head = (sport + " " if sport else "") + "<b>" + esc(event_str) + "</b>"
        if kickoff:
            head += " (" + kickoff + ")"
        head += " \u2014 " + esc(outcome)
        parts.append(
            f"{idx}. {head}\n"
            f"   @ {esc(leg.get('bookmaker', '?'))}  <b>{esc(leg.get('odds', '?'))}</b>"
            f"  (deal {esc(leg.get('deal_score', '?'))})"
        )
        parts.append("")  # blank line between legs

    parts += [
        "\U0001F4CA <b>Итого:</b>",
        f"\u2022 Коэффициент: {express.get('total_odds', '?')}",
        f"\u2022 EV: {float(express.get('total_ev') or 0) * 100:.1f}% (рыночный консенсус)",
        f"\u2022 Размер ставки: {express.get('stake_pct', '?')}% банкролла",
        "",
        "\U0001F4AC <b>Обоснование:</b>",
        esc(express.get("rationale", "")),
        "",
        "\u26A0\uFE0F Это не value-ставка, а AI-выбор по рыночному консенсусу.",
    ]
    return "\n".join(parts)


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
def _format_odds(value) -> str:
    """Render an odds value compactly ('1.4', '2', '2.55')."""
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return str(value)


_SPORT_NAMES = {
    1: "\u0444\u0443\u0442\u0431\u043e\u043b",
    2: "\u0445\u043e\u043a\u043a\u0435\u0439",
    4: "\u0442\u0435\u043d\u043d\u0438\u0441",
    3088: "\u043d\u0430\u0441\u0442\u043e\u043b\u044c\u043d\u044b\u0439 \u0442\u0435\u043d\u043d\u0438\u0441",
    29086: "\u043a\u0438\u0431\u0435\u0440\u0441\u043f\u043e\u0440\u0442",
}


def cmd_live(argv: list[str], chat_id=None) -> str:
    """/live &lt;sport&gt; &lt;hours&gt; — upcoming Fonbet matches with П1/П2 odds.

    Defaults: sport=tt, hours=1. Hours are clamped to 1..4.
    """
    token = (argv[0] if argv and argv[0] else "tt").lower()
    hours_raw = argv[1] if len(argv) > 1 and argv[1] else "1"
    sport_id = resolve_sport(token)
    if sport_id is None:
        return _t(chat_id, "live_usage")
    try:
        hours = int(hours_raw)
    except ValueError:
        hours = 1
    hours = max(1, min(4, hours))

    try:
        events = fetch_events_by_sport(sport_id, hours=hours)
    except Exception as e:
        return "\u26A0\uFE0F error: " + esc(str(e))[:400]
    if not events:
        return _t(chat_id, "live_empty", hours=hours)

    tz_msk = timezone(timedelta(hours=3))
    now = time.time()
    name = _SPORT_NAMES.get(sport_id, token)
    lines = [
        f"<b>{_t(chat_id, 'live_header', sport=esc(name), hours=hours)}</b>",
        "",
    ]
    for ev in events:
        kickoff = datetime.fromtimestamp(ev["start_ts"], tz=tz_msk).strftime("%H:%M")
        delta_min = max(0, int((ev["start_ts"] - now) // 60))
        block = (
            f"\U0001F3AF <b>{kickoff} {_t(chat_id, 'live_msk')}</b> "
            f"({_t(chat_id, 'live_in_min', n=delta_min, unit=_t(chat_id, 'live_min_suffix'))})\n"
            f"   {esc(ev['home'])} vs {esc(ev['away'])}"
        )
        if ev.get("league"):
            block += f"\n   {esc(ev['league'])}"
        block += (
            f"\n   \u041f1: <code>{_format_odds(ev['odds_home'])}</code> | "
            f"\u041f2: <code>{_format_odds(ev['odds_away'])}</code>\n"
            f"   [place={ev.get('place', '')}]"
        )
        lines.append(block)
        lines.append("")
    lines.append(_t(chat_id, "live_total", n=len(events)))
    return "\n".join(lines)


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
    """Build express via AI. If value-bets < 2, fallback to market consensus picks."""
    results = build_pipeline()

    all_vbs = []
    events_meta = {}
    fallback = []

    for idx, item in enumerate(results, start=1):
        ev = item["event"]
        eid = f"match_{idx}"
        events_meta[eid] = {
            "home": ev["home"],
            "away": ev["away"],
            "league": ev["league"],
            "sport": ev.get("sport", ""),
            "kickoff": ev.get("kickoff", ""),
        }
        # value-bets (strict)
        for vb in item["value_bets"]:
            d = dict(vb)
            d["event_id"] = eid
            d["event"] = f"{ev['home']} vs {ev['away']}"
            all_vbs.append(d)

    # fallback: best-odds из consensus по всем матчам
    for idx, item in enumerate(results, start=1):
        ev = item["event"]
        eid = f"match_{idx}"
        for outcome, c in item["consensus"].items():
            best_odds = c.get("consensus_odds")
            if not best_odds:
                continue
            fallback.append({
                "event_id": eid,
                "outcome": outcome,
                "bookmaker": "consensus",
                "odds": best_odds,
                "ev": 0.0,
                "confidence": c.get("confidence", 0),
                "trust_score": 0.9,
                "deal_score": int(c.get("confidence", 0) * 100),
            })

    # sort fallback by deal_score desc
    fallback.sort(key=lambda x: x["deal_score"], reverse=True)

    express = ExpressBuilder().build(all_vbs, events_meta, fallback_candidates=fallback)
    return format_express(express, events_meta)

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


# --- Rate limit (token bucket, per chat_id) ---
_RATE_BUCKET: dict = {}   # chat_id -> [tokens, last_monotonic_ts]
_RATE_WARN: dict = {}     # chat_id -> last_warn_monotonic_ts
_RATE_CAPACITY: float = 20.0
_RATE_REFILL_PER_SEC: float = _RATE_CAPACITY / 60.0   # 1 token per 3 sec
_RATE_WARN_INTERVAL_SEC: float = 30.0

def _check_rate_limit(chat_id, cost: float = 1.0):
    """Token bucket. Returns (allowed: bool, retry_after_sec: float)."""
    now = time.monotonic()
    state = _RATE_BUCKET.get(chat_id)
    if state is None:
        state = [_RATE_CAPACITY, now]
        _RATE_BUCKET[chat_id] = state
    tokens, last = state
    elapsed = max(0.0, now - last)
    tokens = min(_RATE_CAPACITY, tokens + elapsed * _RATE_REFILL_PER_SEC)
    state[1] = now
    if tokens < cost:
        state[0] = tokens
        wait = (cost - tokens) / _RATE_REFILL_PER_SEC
        return False, wait
    state[0] = tokens - cost
    return True, 0.0

def _rate_check_and_warn(chat_id) -> bool:
    """Returns True if request allowed. Sends warning if blocked (once per interval)."""
    ok, wait = _check_rate_limit(chat_id)
    if ok:
        return True
    now = time.monotonic()
    last_warn = _RATE_WARN.get(chat_id, 0.0)
    if now - last_warn >= _RATE_WARN_INTERVAL_SEC:
        _RATE_WARN[chat_id] = now
        try:
            send_message(chat_id,
                _t(chat_id, "rate_limit", n=int(wait) + 1))
        except Exception:
            pass
    return False


def cmd_status() -> str:
    uptime_secs = int(time.time() - START_TIME)
    lines = ["<b>BOT STATUS</b>", f"uptime: {fmt_uptime(uptime_secs)}", ""]
    last_err = None
    for _attempt in range(3):
        try:
            data = tg_get("getMe")
            me = data.get("result") or {}
            first = me.get("first_name") or me.get("username") or "?"
            username = me.get("username", "?")
            lines.append(f"bot: <b>{esc(first)}</b> @{esc(username)}")
            lines.append(f"api ok: {bool(data.get('ok'))}")
            break
        except Exception as e:
            last_err = e
            if _attempt < 2:
                time.sleep(0.3)
    else:
        lines.append(f"bot info: unavailable \u2014 {esc(_sanitize_error(last_err)[:120])}")
    lines.append("")
    lines.append("<b>Pipeline availability:</b>")
    lines.append(pipeline_availability())
    return "\n".join(lines)


_LIVE_SPORT_RE = {
    3088: ("настольный", "настольн", "пинг", "пинг-понг", "tt", "тт",
           "table tennis", "tabletennis"),
    1:    ("футбол", "football", "фут"),
    2:    ("хоккей", "hockey", "хок"),
    4:    ("теннис", "tennis"),
    29086: ("киберспорт", "esports", "кибер"),
}
_EXPRESS_KEYWORDS = ("экспресс", "экспрес", "собери", "подбери", "предложи",
                     "прогноз", "сделай ставку", "поставь")

def _detect_live_query(text: str):
    """Return (sport_id, hours) if user wants live express, else None."""
    if not text:
        return None
    low = text.lower()
    if not any(k in low for k in _EXPRESS_KEYWORDS):
        return None
    sport_id = None
    for sid, keys in _LIVE_SPORT_RE.items():
        if any(k in low for k in keys):
            sport_id = sid
            break
    if sport_id is None:
        return None
    m = re.search(r"(\d+)\s*(?:час|ч\b|hour|h\b)", low)
    hours = int(m.group(1)) if m else 1
    hours = max(1, min(4, hours))
    return (sport_id, hours)

def _format_live_context(events, hours):
    """Format fetched events as a context block for the system prompt."""
    if not events:
        return ""
    lines = [
        f"АКТУАЛЬНЫЕ ДАННЫЕ (только что из Fonbet, ближайшие {hours} ч):",
        "",
    ]
    for i, e in enumerate(events[:8], 1):
        from datetime import datetime, timedelta, timezone
        ts_msk = datetime.fromtimestamp(e["start_ts"],
                                        tz=timezone(timedelta(hours=3)))
        hhmm = ts_msk.strftime("%H:%M")
        oh = e["odds_home"]
        oa = e["odds_away"]
        league = e.get("league") or ""
        lines.append(
            f"{i}. {hhmm} МСК — {e['home']} vs {e['away']} "
            f"({league})"
        )
        lines.append(f"   П1={oh}, П2={oa}")
    lines.append("")
    lines.append(
        "На основе этих данных собери 2-3 события для экспресса, если "
        "они подходят. Указывай коэффициенты, оценку и риски. Если "
        "данных недостаточно — скажи честно."
    )
    return "\n".join(lines)


def ai_chat(chat_id, user_text: str) -> str:
    """Free-text AI chat via OmniRoute with universal sports-betting prompt."""
    hist = CHAT_HISTORY.setdefault(chat_id, [])
    messages = []
    lang_directive = _t(chat_id, "ai_directive")
    system_text = lang_directive + "\n\n" + (CHAT_SYSTEM_PROMPT or "")
    try:
        detected = _detect_live_query(user_text)
        if detected:
            sport_id, hours = detected
            events = fetch_events_by_sport(sport_id, hours=hours, max_events=8)
            ctx = _format_live_context(events, hours)
            if ctx:
                system_text = (system_text + "\n\n" + ctx).strip()
    except Exception as _e:
        # silent fallback to plain chat on live fetch errors
        pass

    if system_text:
        messages.append({"role": "system", "content": system_text})
    messages.extend(hist[-CHAT_HISTORY_MAX:])
    messages.append({"role": "user", "content": user_text})
    payload = {
        "model": OMNI_CHAT_MODEL,
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 1200,
    }
    r = requests.post(OMNI_CHAT_URL, json=payload, timeout=90)
    r.raise_for_status()
    data = r.json()
    choices = data.get("choices") or []
    content = ""
    if choices:
        content = (choices[0].get("message") or {}).get("content") or ""
    content = content.strip() or "(пустой ответ)"
    hist.append({"role": "user", "content": user_text})
    hist.append({"role": "assistant", "content": content})
    del hist[:-CHAT_HISTORY_MAX]
    return content


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
    if command == "/live":
        # argv was stored in _LAST_LIVE_ARGV by handle()/_handle_callback();
        # empty list -> cmd_live falls back to defaults (tt, 1h)
        return cmd_live(_LAST_LIVE_ARGV, chat_id=_LAST_CHAT_ID)
    return "Unknown command. Use /help to see available commands."


def _handle_callback(cb):
    """Process inline keyboard callback_query."""
    cb_id = cb.get("id")
    data = (cb.get("data") or "").strip()
    msg = cb.get("message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    # Always ack to stop the spinner on the client
    try:
        tg_post("answerCallbackQuery", {"callback_query_id": cb_id})
    except Exception:
        pass
    if chat_id is None or not data:
        return
    if TG_ADMIN_IDS and chat_id not in TG_ADMIN_IDS:
        try:
            send_message(chat_id, _t(chat_id, "wl_reject", id=chat_id))
        except Exception:
            pass
        return
    if not _rate_check_and_warn(chat_id):
        return
    global _LAST_LIVE_ARGV, _LAST_CHAT_ID
    _LAST_CHAT_ID = chat_id
    if data == "/lang":
        _set_lang(chat_id, None)
        send_message(chat_id,
            _t(chat_id, "lang_switched"),
            reply_markup=get_main_keyboard(chat_id))
        return
    command = data.split()[0].split("@")[0].lower()
    if command == "/live":
        _LAST_LIVE_ARGV = data.split()[1:]
    try:
        reply = dispatch(command)
    except Exception as e:
        reply = "\u26A0\ufe0f error: " + esc(str(e))[:400]
    send_message(chat_id, reply, reply_markup=get_main_keyboard(chat_id))


# ---------------------------------------------------------------------------
# 5. Main loop
# ---------------------------------------------------------------------------
def handle(update):
    cb = update.get("callback_query")
    if cb:
        return _handle_callback(cb)
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return
    # /whoami always allowed — lets new users find their chat_id
    text_raw = (message.get("text") or "").strip()
    cmd = text_raw.split()[0].split("@")[0].lower() if text_raw else ""
    if cmd == "/whoami":
        send_message(chat_id, _t(chat_id, "whoami_hint", id=chat_id))
        return
    if TG_ADMIN_IDS and chat_id not in TG_ADMIN_IDS:
        send_message(chat_id, _t(chat_id, "wl_reject", id=chat_id))
        return
    if not _rate_check_and_warn(chat_id):
        return
    text = text_raw
    if not text:
        return
    command = text.split()[0].split("@")[0].lower()
    # --- AI chat extensions ---
    if command == "/reset":
        CHAT_HISTORY.pop(chat_id, None)
        send_message(chat_id, _t(chat_id, "reset_ok"))
        return
    if command == "/lang":
        argv = text.split()[1:]
        new_lang = _set_lang(chat_id, argv[0] if argv else None)
        send_message(chat_id,
            _t(chat_id, "lang_switched"),
            reply_markup=get_main_keyboard(chat_id))
        return
    if command == "/prompt":
        body = CHAT_SYSTEM_PROMPT[:4000] if CHAT_SYSTEM_PROMPT else "\u041f\u0440\u043e\u043c\u043f\u0442 \u043d\u0435 \u0437\u0430\u0433\u0440\u0443\u0436\u0435\u043d."
        send_message(chat_id, body)
        return
    if command in ("/start", "/help"):
        send_message(chat_id,
            get_welcome_text(chat_id),
            reply_markup=get_main_keyboard(chat_id))
        return
    if not text.startswith("/"):
        try:
            reply = ai_chat(chat_id, text)
        except Exception as e:
            reply = "\u26A0\uFE0F AI error: " + esc(str(e))[:400]
        send_message(chat_id, reply)
        return
    global _LAST_LIVE_ARGV, _LAST_CHAT_ID
    _LAST_CHAT_ID = chat_id
    if command == "/live":
        _LAST_LIVE_ARGV = text.split()[1:]
    try:
        reply = dispatch(command)
    except Exception as e:
        reply = "\u26A0\uFE0F error while running " + esc(command) + ": " + esc(str(e))[:400]
    send_message(chat_id, reply)


def warmup(max_pings=5, pause=1.0) -> int:
    """Probe Telegram with getMe until the flapping tunnel answers.

    Makes up to `max_pings` attempts with a `pause` second delay between
    them. Returns the ping number of the first success (1..max_pings), or
    max_pings if the tunnel never answered within the budget.
    """
    last_err = None
    for n in range(1, max_pings + 1):
        try:
            tg_get("getMe")
        except Exception as e:
            last_err = e
            if n < max_pings:
                time.sleep(pause)
            continue
        print(f"[tg_bot] tunnel warm after {n} pings")
        return n
    print(
        f"[tg_bot] tunnel NOT warm after {max_pings} pings ({_sanitize_error(last_err)}); "
        "continuing anyway",
        file=sys.stderr,
    )
    return max_pings


def next_backoff(current, max_backoff=BACKOFF_MAX) -> int:
    """Grow the retry delay exponentially, capped at 60s (3->6->12->24->48->60)."""
    return min(current * 2, max_backoff)


def main():
    if not BOT_TOKEN:
        print(
            "[tg_bot] BOT_TOKEN is not set. "
            "Export BOT_TOKEN=<telegram-bot-token> and run again.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("[tg_bot] starting, polling api.telegram.org ...")
    if TG_ADMIN_IDS:
        print(f"[tg_bot] chat whitelist: {sorted(TG_ADMIN_IDS)}")

    warmup()

    offset = None
    backoff = BACKOFF_INITIAL
    while True:
        try:
            updates = get_updates(offset)
        except Exception as e:
            print(f"[tg_bot] getUpdates failed: {_sanitize_error(e)}", file=sys.stderr)
            time.sleep(backoff)
            backoff = next_backoff(backoff)
            continue  # never crash the loop
        backoff = BACKOFF_INITIAL  # reset on success
        for update in updates:
            try:
                offset = update["update_id"] + 1
                handle(update)
            except Exception as e:
                print(f"[tg_bot] handle update failed: {_sanitize_error(e)}", file=sys.stderr)


if __name__ == "__main__":
    main()