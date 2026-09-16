"""Regression tests for AI chat, sanitize, keyboard, callback additions.

Stdlib only (unittest + unittest.mock) — no new dependencies.
Run: python3 tests/test_tg_chat.py
"""
import os
import sys
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
        self.assertEqual(len(rows[2]), 1)

    def test_callback_data(self):
        rows = tg_bot._MAIN_KEYBOARD["inline_keyboard"]
        datas = {b["callback_data"] for row in rows for b in row}
        self.assertEqual(
            datas, {"/value", "/express", "/report", "/status", "/live tt 1"}
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
             mock.patch.object(tg_bot, "dispatch", lambda cmd: "OK:" + cmd):
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
        self.assertEqual(methods, ["answerCallbackQuery"])


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

    def test_cmd_live_usage_no_raw_angles(self):
        self._check("cmd_live usage", tg_bot.cmd_live(["nonsense"]))

    def test_cmd_live_tt_no_raw_angles(self):
        self._check("cmd_live tt 1", tg_bot.cmd_live(["tt", "1"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
