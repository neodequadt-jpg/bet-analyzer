"""Tests for tg_bot.cmd_stats — 7d backtest results aggregation."""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tg_bot import cmd_stats


RESULTS_REL = Path("data/backtest/results")


def _write(dirpath: Path, name: str, *, won: bool, odds: float, kelly: float,
           resolved_at=None, extra: dict = None):
    rec = {
        "_won": won,
        "odds": odds,
        "kelly": kelly,
        "_resolved_at": (resolved_at or datetime.now(timezone.utc)).isoformat(),
    }
    if extra:
        rec.update(extra)
    (dirpath / f"{name}.json").write_text(
        json.dumps(rec, ensure_ascii=False), encoding="utf-8"
    )


def _prep(tmp_path: Path) -> Path:
    rdir = tmp_path / RESULTS_REL
    rdir.mkdir(parents=True)
    return rdir


def test_empty_results_dir(tmp_path, monkeypatch):
    _prep(tmp_path)
    monkeypatch.chdir(tmp_path)
    out = cmd_stats(0)
    assert "Нет результатов" in out


def test_missing_results_dir(tmp_path, monkeypatch):
    # не создаём results/
    monkeypatch.chdir(tmp_path)
    out = cmd_stats(0)
    assert "Нет результатов" in out


def test_single_win(tmp_path, monkeypatch):
    rdir = _prep(tmp_path)
    # stake = 10000 * 0.01 * 0.5 = 50 ; profit = 50 * (2.0 - 1) = 50 ; ROI = +100%
    _write(rdir, "win", won=True, odds=2.0, kelly=0.01)
    monkeypatch.chdir(tmp_path)
    out = cmd_stats(0)
    assert "1 resolved" in out
    assert "Выиграло: 1 / Проиграло: 0" in out
    assert "Winrate: <b>100.0%</b>" in out
    assert "ROI: <b>+100.00%</b>" in out


def test_single_loss(tmp_path, monkeypatch):
    rdir = _prep(tmp_path)
    _write(rdir, "loss", won=False, odds=2.0, kelly=0.01)
    monkeypatch.chdir(tmp_path)
    out = cmd_stats(0)
    assert "1 resolved" in out
    assert "Выиграло: 0 / Проиграло: 1" in out
    assert "Winrate: <b>0.0%</b>" in out
    assert "ROI: <b>-100.00%</b>" in out


def test_mixed(tmp_path, monkeypatch):
    rdir = _prep(tmp_path)
    _write(rdir, "w1", won=True, odds=3.0, kelly=0.01)
    _write(rdir, "l1", won=False, odds=2.0, kelly=0.01)
    monkeypatch.chdir(tmp_path)
    out = cmd_stats(0)
    assert "2 resolved" in out
    assert "Выиграло: 1 / Проиграло: 1" in out
    assert "Winrate: <b>50.0%</b>" in out


def test_old_excluded(tmp_path, monkeypatch):
    rdir = _prep(tmp_path)
    old = datetime.now(timezone.utc) - timedelta(days=30)
    _write(rdir, "old", won=True, odds=2.0, kelly=0.01, resolved_at=old)
    monkeypatch.chdir(tmp_path)
    out = cmd_stats(0)
    assert "Нет результатов" in out


def test_naive_datetime_treated_as_utc(tmp_path, monkeypatch):
    rdir = _prep(tmp_path)
    # наивный iso — свежий (сегодня), код должен трактовать как UTC и включить
    naive = datetime.now(timezone.utc).replace(tzinfo=None)
    _write(rdir, "naive", won=True, odds=2.0, kelly=0.01, resolved_at=naive)
    monkeypatch.chdir(tmp_path)
    out = cmd_stats(0)
    assert "1 resolved" in out


def test_malformed_json_skipped(tmp_path, monkeypatch):
    rdir = _prep(tmp_path)
    (rdir / "broken.json").write_text("{not json", encoding="utf-8")
    _write(rdir, "good", won=True, odds=2.0, kelly=0.01)
    monkeypatch.chdir(tmp_path)
    out = cmd_stats(0)
    assert "1 resolved" in out


def test_zero_stake_no_div_by_zero(tmp_path, monkeypatch):
    rdir = _prep(tmp_path)
    _write(rdir, "zero", won=True, odds=2.0, kelly=0.0)
    monkeypatch.chdir(tmp_path)
    out = cmd_stats(0)  # не должно упасть
    assert "ROI: <b>+0.00%</b>" in out
