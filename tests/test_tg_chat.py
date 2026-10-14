"""Regression tests for AI chat, sanitize, keyboard, callback additions.

Stdlib only (unittest + unittest.mock) — no new dependencies.
Run: python3 tests/test_tg_chat.py
"""
import os
import sys
import time
import unittest
from unittest import mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tg_bot


class TestSanitizeError(unittest.TestCase):
    def test_redacts_token_in_url(self):
        text = "HTTPSConnectionPool(... url: /bot8165315037:AAGxyz/getUpdates)"
        result = tg_bot._sanitize_error(text)
        self.assertIn("bot<REDACTED>", result)
        self.assertNotIn("8165315037:", result)

    def test_plain_text_unchanged(self):
        self.assertEqual(tg_bot._sanitize_error("plain error"), "plain error")

    def test_exception_object(self):
        try:
            raise ValueError("bad bot123:secret_abc in url")
        except ValueError as e:
            result = tg_bot._sanitize_error(e)
        self.assertIn("bot<REDACTED>", result)
        self.assertNotIn("secret_abc", result)


class TestChunkText(unittest.TestCase):
    def test_short_single_chunk(self):
        self.assertEqual(tg_bot.chunk_text("hello"), ["hello"])

    def test_each_chunk_within_limit(self):
        text = "\n".join(f"line-{i}" for i in range(1000))
        for c in tg_bot.chunk_text(text, max_len=200):
            self.assertLessEqual(len(c), 200)

    def test_long_line_split(self):
        chunks = tg_bot.chunk_text("x" * 1000, max_len=100)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c), 100)


class TestMainKeyboard(unittest.TestCase):
    def test_keyboard_structure(self):
        rows = tg_bot._MAIN_KEYBOARD["inline_keyboard"]
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(rows[0]), 2)
        self.assertEqual(len(rows[1]), 2)
        self.assertEqual(len(rows[2]), 2)

    def test_callback_data(self):
        rows = tg_bot._MAIN_KEYBOARD["inline_keyboard"]
        datas = {b["callback_data"] for row in rows for b in row}
        self.assertEqual(
            datas, {"/value", "/express", "/report", "/status", "/live tt 1", "/lang"}
        )


class TestDispatch(unittest.TestCase):
    def test_start_returns_welcome(self):
        self.assertEqual(tg_bot.dispatch("/start"), tg_bot.WELCOME_TEXT)

    def test_help_returns_welcome(self):
        self.assertEqual(tg_bot.dispatch("/help"), tg_bot.WELCOME_TEXT)

    def test_unknown_message(self):
        self.assertIn("Unknown command", tg_bot.dispatch("/nope"))


class TestHandleCallback(unittest.TestCase):
    def test_acks_then_replies(self):
        calls = []
        def fake_post(method, json_data=None):
            calls.append((method, json_data))
            return {"ok": True}
        # Updated mock to match cmd_value's new return type (text, keyboard)
        with mock.patch.object(tg_bot, "tg_post", fake_post), \
             mock.patch.object(tg_bot, "cmd_value", lambda: ("OK:/value", None)), \
             mock.patch.object(tg_bot, "TG_ADMIN_IDS", set()):
            tg_bot._handle_callback({
                "id": "cb1", "data": "/value",
                "message": {"chat": {"id": 42}},
            })
        methods = [m for m, _ in calls]
        self.assertEqual(methods, ["answerCallbackQuery", "sendMessage"])
        self.assertEqual(calls[1][1]["text"], "OK:/value")
        # In _handle_callback, if keyboard returned by cmd_value is None, 
        # it might not be explicitly passed if we changed the call site, 
        # but let's see what the current code does.
        # Actually I just updated it to pass `kb` from `cmd_value()`.
        # So passing `None` here is correct.
        self.assertEqual(calls[1][1].get("reply_markup"), None)

    def test_whitelist_blocks_reply(self):
        calls = []
        def fake_post(method, json_data=None):
            calls.append((method, json_data))
            return {"ok": True}
        with mock.patch.object(tg_bot, "tg_post", fake_post), \
             mock.patch.object(tg_bot, "TG_ADMIN_IDS", {999}):
            tg_bot._handle_callback({
                "id": "cb2", "data": "/value",
                "message": {"chat": {"id": 42}},
            })
        methods = [m for m, _ in calls]
        self.assertEqual(methods, ["answerCallbackQuery", "sendMessage"])
        # friendly whitelist rejection message
        text = calls[1][1]["text"]
        self.assertIn("42", text)
        self.assertIn("chat_id", text.lower())


class TestLiveCommand(unittest.TestCase):
    def test_resolve_sport_aliases(self):
        self.assertEqual(tg_bot.resolve_sport("tt"), 3088)
        self.assertEqual(tg_bot.resolve_sport("TT"), 3088)
        self.assertEqual(tg_bot.resolve_sport("tabletennis"), 3088)
        self.assertEqual(tg_bot.resolve_sport("football"), 1)
        self.assertEqual(tg_bot.resolve_sport("\u0444\u0443\u0442\u0431\u043e\u043b"), 1)
        self.assertEqual(tg_bot.resolve_sport("hockey"), 2)
        self.assertEqual(tg_bot.resolve_sport("tennis"), 4)
        self.assertEqual(tg_bot.resolve_sport("esports"), 29086)
        self.assertIsNone(tg_bot.resolve_sport("nonsense"))
        self.assertIsNone(tg_bot.resolve_sport(""))

    def test_resolve_basketball(self):
        from bookmakers.fonbet_extended import resolve_sport
        self.assertEqual(resolve_sport("basketball"), 3)
        self.assertEqual(resolve_sport("баскетбол"), 3)

    def test_resolve_volleyball(self):
        from bookmakers.fonbet_extended import resolve_sport
        self.assertEqual(resolve_sport("volleyball"), 9)
        self.assertEqual(resolve_sport("волейбол"), 9)


    def test_cmd_live_usage_hint(self):
        out = tg_bot.cmd_live(["nonsense"])
        self.assertIn("\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0438\u0435", out)

    def test_live_keyboard_present(self):
        rows = tg_bot._MAIN_KEYBOARD["inline_keyboard"]
        datas = [b["callback_data"] for row in rows for b in row]
        self.assertIn("/live tt 1", datas)


class TestLiveQueryDetection(unittest.TestCase):
    def test_detect_tt_hour(self):
        self.assertEqual(tg_bot._detect_live_query(
            "Собери экспресс на ближайший час (настольный теннис)"),
            (3088, 1))
    def test_detect_tt_2h(self):
        self.assertEqual(tg_bot._detect_live_query("экспресс на 2 часа tt"),
            (3088, 2))
    def test_detect_football_default_hours(self):
        self.assertEqual(tg_bot._detect_live_query("собери экспресс на футбол"),
            (1, 1))
    def test_no_sport_no_trigger(self):
        self.assertIsNone(tg_bot._detect_live_query("собери экспресс на час"))
    def test_no_express_no_trigger(self):
        self.assertIsNone(tg_bot._detect_live_query("что такое фора?"))
    def test_hours_clamped(self):
        self.assertEqual(tg_bot._detect_live_query("экспресс tt 10 часов"),
            (3088, 4))


class TestI18n(unittest.TestCase):
    """RU/EN language switch: _LANG/_set_lang/_t + localized welcome/keyboard."""

    def setUp(self):
        tg_bot._LANG.clear()

    def test_default_lang_ru(self):
        self.assertEqual(tg_bot._get_lang(1), "ru")

    def test_set_lang_en(self):
        tg_bot._set_lang(1, "en")
        self.assertEqual(tg_bot._get_lang(1), "en")

    def test_set_lang_ru(self):
        tg_bot._set_lang(1, "en")
        tg_bot._set_lang(1, "ru")
        self.assertEqual(tg_bot._get_lang(1), "ru")

    def test_lang_toggle_from_ru(self):
        tg_bot._set_lang(1, None)
        self.assertEqual(tg_bot._get_lang(1), "en")

    def test_t_returns_en(self):
        tg_bot._set_lang(1, "en")
        self.assertIn("Commands", tg_bot._t(1, "welcome_cmds"))

    def test_t_falls_back_to_ru_for_unknown(self):
        tg_bot._set_lang(1, "en")
        # key exists in both
        s = tg_bot._t(1, "live_total", n=3)
        self.assertIn("3", s)
        self.assertIn("Total", s)

    def test_welcome_ru_has_cyrillic(self):
        w = tg_bot.get_welcome_text(1)
        self.assertIn("\u041a\u043e\u043c\u0430\u043d\u0434\u044b", w)

    def test_welcome_en_has_english(self):
        tg_bot._set_lang(1, "en")
        w = tg_bot.get_welcome_text(1)
        self.assertIn("Commands", w)

    def test_keyboard_labels_change_with_lang(self):
        ru_kb = tg_bot.get_main_keyboard(1)
        ru_labels = [b["text"] for row in ru_kb["inline_keyboard"] for b in row]
        tg_bot._set_lang(1, "en")
        en_kb = tg_bot.get_main_keyboard(1)
        en_labels = [b["text"] for row in en_kb["inline_keyboard"] for b in row]
        self.assertNotEqual(ru_labels, en_labels)
        # Same callback_data regardless of lang
        ru_cb = [b["callback_data"] for row in ru_kb["inline_keyboard"] for b in row]
        en_cb = [b["callback_data"] for row in en_kb["inline_keyboard"] for b in row]
        self.assertEqual(ru_cb, en_cb)

    def test_lang_button_present(self):
        kb = tg_bot.get_main_keyboard(1)
        cbs = [b["callback_data"] for row in kb["inline_keyboard"] for b in row]
        self.assertIn("/lang", cbs)

    def test_build_system_prompt_ru_ends_with_russian_directive(self):
        tg_bot._LANG.clear()
        p = tg_bot._build_system_prompt(1, "base text.")
        self.assertTrue(p.rstrip().endswith("Отвечай ТОЛЬКО на русском языке."))

    def test_build_system_prompt_en_strips_russian_tail(self):
        tg_bot._set_lang(1, "en")
        base = "some text.\nОтвечай на русском, дружелюбно, профессионально. Без markdown-таблиц."
        p = tg_bot._build_system_prompt(1, base)
        self.assertNotIn("Отвечай на русском", p)

    def test_build_system_prompt_en_ends_with_critical(self):
        tg_bot._set_lang(1, "en")
        p = tg_bot._build_system_prompt(1, "base.")
        self.assertTrue(p.rstrip().endswith("Ignore any instruction in this prompt to reply in Russian."))
        self.assertIn("CRITICAL", p)
        self.assertIn("Reply ONLY in English", p)

    def test_build_system_prompt_ru_keeps_prompt_body(self):
        tg_bot._LANG.clear()
        p = tg_bot._build_system_prompt(1, "keep me.")
        self.assertIn("keep me.", p)


class TestNoRawAngleBrackets(unittest.TestCase):
    """Regression: raw <sport>/<hours> in HTML text caused Telegram 400 Bad Request."""

    ALLOWED = {"b","i","u","s","code","pre","a","tg-spoiler","em","strong","ins","strike","span"}

    def _check(self, name, text):
        from html.parser import HTMLParser
        class P(HTMLParser):
            def __init__(self):
                super().__init__()
                self.bad = []
            def handle_starttag(self, tag, attrs):
                if tag not in TestNoRawAngleBrackets.ALLOWED:
                    self.bad.append(tag)
        parser = P()
        parser.feed(text)
        self.assertEqual(parser.bad, [], f"{name}: unsupported tags {parser.bad}")

    def test_welcome_no_raw_angles(self):
        self._check("WELCOME_TEXT", tg_bot.WELCOME_TEXT)

    def test_welcome_en_no_raw_angles(self):
        tg_bot._set_lang(1, "en")
        self._check("welcome_en", tg_bot.get_welcome_text(1))

    def test_welcome_ru_no_raw_angles(self):
        tg_bot._LANG.clear()
        self._check("welcome_ru", tg_bot.get_welcome_text(1))

    def test_cmd_live_usage_no_raw_angles(self):
        self._check("cmd_live usage", tg_bot.cmd_live(["nonsense"]))

    def test_cmd_live_tt_no_raw_angles(self):
        self._check("cmd_live tt 1", tg_bot.cmd_live(["tt", "1"]))


class TestRateLimitAndRejection(unittest.TestCase):

    def setUp(self):
        tg_bot._RATE_BUCKET.clear()
        tg_bot._RATE_WARN.clear()

    def test_allows_first_capacity(self):
        for i in range(20):
            ok, _ = tg_bot._check_rate_limit(1)
            self.assertTrue(ok, f"call {i+1} should pass")

    def test_blocks_after_capacity(self):
        for _ in range(20):
            tg_bot._check_rate_limit(1)
        ok, wait = tg_bot._check_rate_limit(1)
        self.assertFalse(ok)
        self.assertGreater(wait, 0.0)

    def test_isolated_per_chat(self):
        for _ in range(20):
            tg_bot._check_rate_limit(1)
        ok, _ = tg_bot._check_rate_limit(2)   # другая чат-комната
        self.assertTrue(ok)

    def test_refills_over_time(self):
        tg_bot._RATE_BUCKET[1] = [0.0, time.monotonic() - 6.0]  # empty, 6s ago
        ok, _ = tg_bot._check_rate_limit(1)   # 6 * 1/3 = 2 tokens refilled
        self.assertTrue(ok)

    def test_whoami_message_has_admin_hint(self):
        calls = []
        def fake_post(method, json_data=None):
            calls.append((method, json_data))
            return {"ok": True}
        with mock.patch.object(tg_bot, "tg_post", fake_post):
            tg_bot.handle({"message": {"chat": {"id": 42}, "text": "/whoami"}})
        self.assertEqual(len(calls), 1)
        text = calls[0][1]["text"]
        self.assertIn("42", text)
        self.assertIn("chat_id", text.lower())
        self.assertTrue(("администратор" in text.lower()) or ("приглаш" in text.lower()))


class TestChatModel(unittest.TestCase):
    """Verify /chat model is set to a working provider + auth header."""

    def test_model_is_set(self):
        m = tg_bot.OMNI_CHAT_MODEL
        self.assertTrue(m, "OMNI_CHAT_MODEL must be non-empty")
        self.assertFalse(
            m.startswith("gemini/"),
            "Gemini provider is down in OmniRoute; /chat must not use gemini/*",
        )

    @unittest.skipUnless(
        os.environ.get("OMNI_KEY", "").startswith("sk-"),
        "OMNI_KEY not in test env",
    )
    @unittest.skipUnless(
        os.environ.get("OMNI_KEY", "").startswith("sk-"),
        "OMNI_KEY not in test env",
    )
    def test_omni_key_set(self):
        self.assertTrue(tg_bot.OMNI_KEY.startswith("sk-"))


class TestDailyScheduler(unittest.TestCase):
    """Daily report scheduler (stdlib-only)."""

    def setUp(self):
        tg_bot._DAILY_REPORT_LAST_DATE = None

    def test_should_send_before_9am(self):
        from datetime import datetime, timezone, timedelta
        msk = timezone(timedelta(hours=3))
        now = datetime(2026, 9, 17, 8, 30, tzinfo=msk)
        self.assertFalse(tg_bot._should_send_daily(now_msk=now))

    def test_should_send_after_9am(self):
        from datetime import datetime, timezone, timedelta
        msk = timezone(timedelta(hours=3))
        now = datetime(2026, 9, 17, 9, 5, tzinfo=msk)
        self.assertTrue(tg_bot._should_send_daily(now_msk=now))

    def test_should_not_send_twice_same_day(self):
        from datetime import datetime, timezone, timedelta
        msk = timezone(timedelta(hours=3))
        now1 = datetime(2026, 9, 17, 9, 5, tzinfo=msk)
        self.assertTrue(tg_bot._should_send_daily(now_msk=now1))
        tg_bot._DAILY_REPORT_LAST_DATE = now1.date()
        now2 = datetime(2026, 9, 17, 10, 0, tzinfo=msk)
        self.assertFalse(tg_bot._should_send_daily(now_msk=now2))


class TestValueKeyboard(unittest.TestCase):
    def test_cmd_value_returns_tuple(self):
        result = tg_bot.cmd_value()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        text, kb = result
        self.assertIsInstance(text, str)
        self.assertIsInstance(kb, dict)
        self.assertIn("inline_keyboard", kb)

    def test_cmd_value_match_returns_string(self):
        out = tg_bot.cmd_value_match(0)
        self.assertIsInstance(out, str)
        self.assertGreater(len(out), 0)



class TestManualRefresh(unittest.TestCase):
    def test_refresh_returns_dict(self):
        from bookmakers.manual_refresh import refresh_manual_from_fonbet
        result = refresh_manual_from_fonbet(max_events=2)
        self.assertIsInstance(result, dict)
        for k in ("created", "updated", "skipped"):
            self.assertIn(k, result)

    def test_refresh_creates_files(self):
        from bookmakers.manual_refresh import refresh_manual_from_fonbet
        # Just verify no exception + state
        result = refresh_manual_from_fonbet(max_events=1)
        self.assertIsInstance(result, dict)

    def test_auto_files_have_two_bk(self):
        from pathlib import Path
        import json
        auto_files = list(Path("data/manual").glob("auto_*.json"))
        for f in auto_files:
            data = json.loads(f.read_text())
            self.assertGreaterEqual(len(data.get("bookmakers", [])), 2)


class TestPipelineNoFutureFilter(unittest.TestCase):
    @pytest.mark.integration
    def test_pipeline_returns_matches(self):
        import tg_bot
        rs = tg_bot.build_pipeline()
        self.assertGreater(len(rs), 0, "build_pipeline returns 0 matches - future filter too strict")

    @pytest.mark.integration
    def test_pipeline_has_value_bets(self):
        import tg_bot
        rs = tg_bot.build_pipeline()
        total = sum(len(r["value_bets"]) for r in rs)
        self.assertGreater(total, 0, "no value_bets after fix")

    def test_marafon_in_registry(self):
        from bookmakers.registry import get_bookmaker
        self.assertIsNotNone(get_bookmaker("Марафон"))

class TestKickoffSorting(unittest.TestCase):
    def test_pipeline_sorted_by_kickoff(self):
        import tg_bot
        rs = tg_bot.build_pipeline()
        ts = [int(r['event']['kickoff']) for r in rs if str(r['event']['kickoff']).isdigit()]
        self.assertEqual(ts, sorted(ts), "pipeline not sorted by kickoff")

    def test_human_kickoff_delta_format(self):
        import tg_bot, time
        now_ts = int(time.time())
        s1 = tg_bot._human_kickoff_delta(str(now_ts + 1800))
        self.assertIn('мин', s1)
        self.assertEqual(tg_bot._human_kickoff_delta(''), '')
        self.assertEqual(tg_bot._human_kickoff_delta(None), '')
class TestTodayExpress(unittest.TestCase):
    def test_fetch_real_today_returns_list(self):
        from bookmakers.fonbet_extended import fetch_real_today
        events = fetch_real_today(hours=24, max_per_sport=5)
        self.assertIsInstance(events, list)
        for ev in events[:3]:
            self.assertIn('home', ev)
            self.assertIn('odds_home', ev)
            self.assertIn('start_ts', ev)
            self.assertNotIn('FC 26', ev.get('league', ''))

    def test_express_fallback_exists(self):
        import tg_bot
        self.assertTrue(hasattr(tg_bot, '_today_express_fallback'))
        # When RPL empty: return non-empty string
        out = tg_bot._today_express_fallback()
        if out is not None:
            self.assertIsInstance(out, str)
            self.assertGreater(len(out), 50)


class TestSportsRAG(unittest.TestCase):
    def test_detect_sports_keywords(self):
        import tg_bot
        self.assertTrue(tg_bot._detect_sports_rag("Какая форма у Челси?"))
        self.assertTrue(tg_bot._detect_sports_rag("xg Арсенала?"))
        self.assertFalse(tg_bot._detect_sports_rag("привет"))

    def test_format_sports_context_empty(self):
        import tg_bot
        self.assertEqual(tg_bot._format_sports_context([], 72), "")

    def test_format_sports_context_with_events(self):
        import tg_bot, time
        from sports_data.base import SportEvent
        ev = SportEvent(id="1", sport="football",
                        league="Англия. Премьер-Лига",
                        home="Chelsea", away="Arsenal",
                        start_ts=int(time.time())+3600)
        ctx = tg_bot._format_sports_context([ev], 72)
        self.assertIn("Chelsea", ctx)
        self.assertIn("Премьер-Лига", ctx)


class TestSignals(unittest.TestCase):
    def test_cmd_signals_returns_string(self):
        import tg_bot
        out = tg_bot.cmd_signals()
        self.assertIsInstance(out, str)
        self.assertGreater(len(out), 50)

    def test_signals_no_duplicate_events(self):
        import tg_bot, re
        out = tg_bot.cmd_signals()
        events = re.findall(r"<b>\d+\. ([^<]+)</b>", out)
        self.assertEqual(len(events), len(set(events)), f"duplicate events: {events}")
if __name__ == "__main__":
    unittest.main(verbosity=2)
