"""Unit tests for tg_bot.py resilience features — no real network.

Covers: text chunking, short-poll getUpdates, send_message retries,
tunnel warmup, and exponential backoff. Uses monkeypatch + MagicMock only.
"""

from unittest.mock import MagicMock

import pytest

import tg_bot


def _no_sleep(monkeypatch):
    """Neutralize time.sleep so retry tests run instantly."""
    monkeypatch.setattr(tg_bot.time, "sleep", lambda _secs: None)


# ---------------------------------------------------------------------------
# chunk_text
# ---------------------------------------------------------------------------
def test_chunk_text_short():
    text = "short message \u2014 single chunk"
    chunks = tg_bot.chunk_text(text)
    assert chunks == [text]
    assert len(chunks) == 1


def test_chunk_text_long():
    lines = ["y" * 100 for _ in range(100)]
    text = "\n".join(lines)
    assert len(text) > tg_bot.MAX_MESSAGE_LEN
    chunks = tg_bot.chunk_text(text)
    assert len(chunks) > 1
    assert all(len(chunk) <= tg_bot.MAX_MESSAGE_LEN for chunk in chunks)
    assert "".join(chunks) == text  # nothing lost or duplicated


def test_chunk_text_no_split_lines():
    lines = ["line-%02d-%s" % (i, "y" * 100) for i in range(120)]
    text = "\n".join(lines)
    assert len(text) > tg_bot.MAX_MESSAGE_LEN
    chunks = tg_bot.chunk_text(text)
    assert len(chunks) > 1
    assert all(len(chunk) <= tg_bot.MAX_MESSAGE_LEN for chunk in chunks)
    # Lossless: "\n" separators are preserved at chunk ends.
    assert "".join(chunks) == text
    # Boundaries: every non-last chunk ends exactly at a line end (keeps the
    # trailing separator); no mid-line splits: each chunk is a run of whole
    # original lines.
    all_lines = text.split("\n")
    idx = 0
    for chunk in chunks[:-1]:
        assert chunk.endswith("\n")
        piece = chunk[:-1].split("\n")
        assert piece == all_lines[idx:idx + len(piece)]
        idx += len(piece)
    assert chunks[-1].split("\n") == all_lines[idx:]
    assert idx + len(chunks[-1].split("\n")) == len(all_lines)


def test_chunk_text_lossless():
    lines = [f"line-{i:03d}-" + "x" * 50 for i in range(200)]
    text = "\n".join(lines)
    assert all(len(line) <= tg_bot.MAX_MESSAGE_LEN - 1 for line in lines)
    chunks = tg_bot.chunk_text(text)
    assert "".join(chunks) == text
    assert all(len(chunk) <= tg_bot.MAX_MESSAGE_LEN for chunk in chunks)


# ---------------------------------------------------------------------------
# format_express
# ---------------------------------------------------------------------------
def test_format_express_human_readable():
    express = {
        "legs": [
            {"event": "Спартак vs Зенит", "outcome": "home",
             "bookmaker": "Fonbet", "odds": 2.10, "deal_score": 87},
            {"event": "Динамо vs ЦСКА", "outcome": "away",
             "bookmaker": "BetBoom", "odds": 3.40, "deal_score": 81},
        ],
        "total_odds": 7.14,
        "total_ev": 0.12,
        "stake_pct": 2.5,
        "rationale": "Обе команды в форме.",
    }
    result = tg_bot.format_express(express)
    assert "🎯" in result
    assert "ЭКСПРЕСС" in result
    assert "<pre>" not in result
    assert "Итого" in result
    assert "победа " in result


def test_format_express_empty():
    result = tg_bot.format_express({"legs": [], "reason": "insufficient value-bets"})
    assert "не собран" in result
    assert "insufficient value-bets" in result


def test_format_express_error():
    result = tg_bot.format_express({"error": "boom"})
    assert "Ошибка: boom" in result


# ---------------------------------------------------------------------------
# get_updates / send_message / warmup / backoff
# ---------------------------------------------------------------------------
def test_get_updates_short_poll(monkeypatch):
    mock_get = MagicMock(return_value={"ok": True, "result": []})
    monkeypatch.setattr(tg_bot, "tg_get", mock_get)

    updates = tg_bot.get_updates(offset=None)

    assert updates == []
    # timeout must be short (1s long-poll), not the old 25s.
    mock_get.assert_called_once_with("getUpdates", {"timeout": 1})


def test_send_message_retry(monkeypatch):
    _no_sleep(monkeypatch)
    calls = {"n": 0}

    def fake_post(method, json_data=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("502 Bad Gateway")
        return {"ok": True, "result": {}}

    monkeypatch.setattr(tg_bot, "tg_post", fake_post)

    tg_bot.send_message(chat_id=123, text="hello")

    assert calls["n"] == 3  # 2 failures + 1 success


def test_send_message_retry_fails(monkeypatch):
    _no_sleep(monkeypatch)
    calls = {"n": 0}

    def fake_post(method, json_data=None):
        calls["n"] += 1
        raise RuntimeError("502 Bad Gateway")

    monkeypatch.setattr(tg_bot, "tg_post", fake_post)

    with pytest.raises(RuntimeError, match="502"):
        tg_bot.send_message(chat_id=123, text="hello")

    assert calls["n"] == 3  # all 3 attempts made, last error raised


def test_warmup_breaks_on_success(monkeypatch):
    _no_sleep(monkeypatch)
    calls = {"n": 0}

    def fake_get(method, params=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("tunnel down")
        return {"ok": True, "result": {}}

    monkeypatch.setattr(tg_bot, "tg_get", fake_get)

    pings = tg_bot.warmup(max_pings=5, pause=1.0)

    assert calls["n"] == 3  # stops at first success, no extra pings
    assert pings == 3


def test_backoff_doubles():
    seq = [tg_bot.BACKOFF_INITIAL]
    for _ in range(5):
        seq.append(tg_bot.next_backoff(seq[-1]))
    assert seq == [3, 6, 12, 24, 48, 60]
    # capped at the max: does not grow past 60s
    assert tg_bot.next_backoff(tg_bot.BACKOFF_MAX) == tg_bot.BACKOFF_MAX

def test_get_updates_internal_retry(monkeypatch):
    """One flaky failure inside get_updates must not bubble up to caller."""
    monkeypatch.setattr(tg_bot.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    def fake_get(method, params=None):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("502 Bad Gateway")
        return {"ok": True, "result": [{"update_id": 1}]}

    monkeypatch.setattr(tg_bot, "tg_get", fake_get)
    updates = tg_bot.get_updates(offset=None, retries=3, pause=0.3)
    assert calls["n"] == 2
    assert updates == [{"update_id": 1}]


def test_get_updates_retries_exhausted(monkeypatch):
    """All internal retries failing -> error still raised for caller backoff."""
    monkeypatch.setattr(tg_bot.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    def fake_get(method, params=None):
        calls["n"] += 1
        raise RuntimeError("502 Bad Gateway")

    monkeypatch.setattr(tg_bot, "tg_get", fake_get)
    with pytest.raises(RuntimeError, match="502"):
        tg_bot.get_updates(offset=None, retries=3, pause=0.3)
    assert calls["n"] == 4  # 1 initial + 3 retries


def test_build_falls_back_when_value_single_match(monkeypatch):
    """2 value-bets in ONE match → fallback to consensus (not value mode)."""
    from ai.express_builder import ExpressBuilder

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["payload"] = json
        class R:
            status_code = 200
            def json(self):
                return {"choices": [{"message": {"content": "{\"legs\": [], \"reason\": \"test\"}"}}]}
        return R()

    monkeypatch.setattr("ai.express_builder.requests.post", fake_post)

    vb_same_match = [
        {"event_id": "match_1", "outcome": "away", "bookmaker": "X", "odds": 5.0,
         "ev": 0.05, "confidence": 0.8, "trust_score": 0.8, "deal_score": 60},
        {"event_id": "match_1", "outcome": "draw", "bookmaker": "Y", "odds": 4.0,
         "ev": 0.04, "confidence": 0.8, "trust_score": 0.8, "deal_score": 60},
    ]
    fallback = [
        {"event_id": "match_2", "outcome": "home", "bookmaker": "consensus",
         "odds": 2.0, "ev": 0.0, "confidence": 0.8, "trust_score": 0.9, "deal_score": 80},
        {"event_id": "match_3", "outcome": "away", "bookmaker": "consensus",
         "odds": 2.5, "ev": 0.0, "confidence": 0.8, "trust_score": 0.9, "deal_score": 80},
    ]
    b = ExpressBuilder()
    b.build(vb_same_match, {"match_2": {"home": "A", "away": "B", "league": "L"}},
            fallback_candidates=fallback)

    # Assert: fallback was used, payload's system prompt is the consensus one
    sys_content = captured["payload"]["messages"][0]["content"]
    assert "consensus" in sys_content.lower() or "рыночный" in sys_content.lower()


def test_build_handles_none_content(monkeypatch):
    """Provider flake: message.content is None → no crash, dict returned."""
    from ai.express_builder import ExpressBuilder

    def fake_post(url, headers=None, json=None, timeout=None):
        class R:
            status_code = 200
            def json(self):
                return {"choices": [{"message": {"content": None}}]}
        return R()

    monkeypatch.setattr("ai.express_builder.requests.post", fake_post)

    vb = [
        {"event_id": "match_1", "outcome": "away", "bookmaker": "X", "odds": 5.0,
         "ev": 0.05, "confidence": 0.8, "trust_score": 0.8, "deal_score": 60},
        {"event_id": "match_2", "outcome": "draw", "bookmaker": "Y", "odds": 4.0,
         "ev": 0.04, "confidence": 0.8, "trust_score": 0.8, "deal_score": 60},
    ]
    b = ExpressBuilder()
    result = b.build(vb, {"match_1": {"home": "A", "away": "B"}, "match_2": {"home": "C", "away": "D"}})

    assert isinstance(result, dict)
    assert "reason" in result or "legs" in result


def test_build_handles_non_json_content(monkeypatch):
    """Provider returned plain text → graceful dict with non-JSON reason."""
    from ai.express_builder import ExpressBuilder

    def fake_post(url, headers=None, json=None, timeout=None):
        class R:
            status_code = 200
            def json(self):
                return {"choices": [{"message": {"content": "Sorry, I can't help"}}]}
        return R()

    monkeypatch.setattr("ai.express_builder.requests.post", fake_post)

    vb = [
        {"event_id": "match_1", "outcome": "away", "bookmaker": "X", "odds": 5.0,
         "ev": 0.05, "confidence": 0.8, "trust_score": 0.8, "deal_score": 60},
        {"event_id": "match_2", "outcome": "draw", "bookmaker": "Y", "odds": 4.0,
         "ev": 0.04, "confidence": 0.8, "trust_score": 0.8, "deal_score": 60},
    ]
    b = ExpressBuilder()
    result = b.build(vb, {"match_1": {"home": "A", "away": "B"}, "match_2": {"home": "C", "away": "D"}})

    assert isinstance(result, dict)
    assert "non-JSON" in result.get("reason", "")
