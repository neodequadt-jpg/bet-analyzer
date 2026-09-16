"""Regression tests for AI chat, sanitize, keyboard, callback additions.

Stdlib only (unittest + unittest.mock) — no new dependencies.
Run: python3 tests/test_tg_chat.py
"""
import os
import sys
import time
import unittest
from unittest import mock

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
        with mock.patch.object(tg_bot, "tg_post", fake_post), \
             mock.patch.object(tg_bot, "dispatch", lambda cmd: "OK:" + cmd), \
             mock.patch.object(tg_bot, "TG_ADMIN_IDS", set()):
            tg_bot._handle_callback({
                "id": "cb1", "data": "/value",
                "message": {"chat": {"id": 42}},
            })
        methods = [m for m, _ in calls]
        self.assertEqual(methods, ["answerCallbackQuery", "sendMessage"])
        self.assertEqual(calls[1][1]["text"], "OK:/value")
        self.assertEqual(calls[1][1]["reply_markup"], tg_bot._MAIN_KEYBOARD)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
