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
