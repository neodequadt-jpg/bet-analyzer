"""Forward-test tracker: сохраняет /signals и результаты матчей."""
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

SIGNALS_DIR = Path("data/backtest/signals")
SIGNALS_DIR.mkdir(parents=True, exist_ok=True)


def log_signals(signals: list) -> Path:
    """Save top-N value-bets to timestamped file."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = SIGNALS_DIR / f"{ts}.json"
    payload = {
        "ts": time.time(),
        "iso": datetime.now(timezone.utc).isoformat(),
        "count": len(signals),
        "signals": signals,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_all_signals() -> list:
    """Load all logged signals for stats."""
    out = []
    for f in sorted(SIGNALS_DIR.glob("*.json")):
        try:
            d = json.loads(f.read_text())
            for s in d.get("signals", []):
                s["_logged_at"] = d.get("iso")
                s["_file"] = f.name
                out.append(s)
        except Exception:
            continue
    return out


def stats_summary() -> dict:
    """Summary: total signals, by EV, by bookmaker."""
    all_s = load_all_signals()
    total = len(all_s)
    if not total:
        return {"total": 0}

    by_bk = {}
    by_ev = {"low": 0, "mid": 0, "high": 0}
    total_ev = 0.0
    for s in all_s:
        bk = s.get("bookmaker", "?")
        by_bk[bk] = by_bk.get(bk, 0) + 1
        ev = s.get("ev", 0)
        total_ev += ev
        if ev < 0.05:
            by_ev["low"] += 1
        elif ev < 0.10:
            by_ev["mid"] += 1
        else:
            by_ev["high"] += 1
    return {
        "total": total,
        "avg_ev": total_ev / total,
        "by_bookmaker": by_bk,
        "by_ev_band": by_ev,
    }


def resolved_stats() -> dict:
    rdir = Path("data/backtest/results")
    signals = load_all_signals()
    total = len(signals)
    resolved_list = []
    if rdir.exists():
        for f in rdir.glob("*.json"):
            try:
                resolved_list.append(json.loads(f.read_text()))
            except Exception:
                continue
    won = sum(1 for r in resolved_list if r.get("_won"))
    lost = len(resolved_list) - won
    pending = total - len(resolved_list)
    bank = 10000
    kelly_frac = 0.5
    profit = 0.0
    staked = 0.0
    for r in resolved_list:
        odds = r.get("odds") or 0
        kelly = r.get("kelly") or 0
        stake = bank * kelly * kelly_frac
        staked += stake
        if r.get("_won"):
            profit += stake * (odds - 1)
        else:
            profit -= stake
    roi = (profit / staked * 100) if staked > 0 else 0.0
    winrate = (won / len(resolved_list) * 100) if resolved_list else 0.0
    return {
        "total": total,
        "pending": pending,
        "resolved": len(resolved_list),
        "won": won,
        "lost": lost,
        "winrate": round(winrate, 1),
        "roi": round(roi, 2),
        "profit": round(profit, 2),
        "staked": round(staked, 2),
    }


def resolved_stats() -> dict:
    """Read resolved results, compute ROI/winrate."""
    rdir = Path("data/backtest/results")
    signals = load_all_signals()
    total = len(signals)

    resolved_list = []
    if rdir.exists():
        for f in rdir.glob("*.json"):
            try:
                resolved_list.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                continue

    won = sum(1 for r in resolved_list if r.get("_won"))
    lost = len(resolved_list) - won
    pending = total - len(resolved_list)

    bank = 10000
    kelly_frac = 0.5
    profit = 0.0
    staked = 0.0
    for r in resolved_list:
        odds = r.get("odds") or 0
        kelly = r.get("kelly") or 0
        stake = bank * kelly * kelly_frac
        staked += stake
        if r.get("_won"):
            profit += stake * (odds - 1)
        else:
            profit -= stake

    roi = (profit / staked * 100) if staked > 0 else 0.0
    winrate = (won / len(resolved_list) * 100) if resolved_list else 0.0

    return {
        "total": total,
        "pending": pending,
        "resolved": len(resolved_list),
        "won": won,
        "lost": lost,
        "winrate": round(winrate, 1),
        "roi": round(roi, 2),
        "profit": round(profit, 2),
        "staked": round(staked, 2),
    }
