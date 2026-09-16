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
    text = "x" * 8000
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
    # Boundaries: every non-last chunk must end exactly at a line end.
    pos = 0
    for chunk in chunks[:-1]:
        assert text[pos + len(chunk)] == "\n"
        pos += len(chunk) + 1
    assert pos + len(chunks[-1]) == len(text)
    # No mid-line splits: each chunk is a run of whole original lines.
    all_lines = text.split("\n")
    idx = 0
    for chunk in chunks:
        piece = chunk.split("\n")
        assert piece == all_lines[idx:idx + len(piece)]
        idx += len(piece)
    assert idx == len(all_lines)


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