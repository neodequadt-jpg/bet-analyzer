"""
BET-ANALYZER runner.
Поддерживает два источника:
- mock (встроенный в parser.py)
- manual (data/manual/*.json)

Конвейер: source → consensus → EV → value_bets → report.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from bookmakers.parser import OddsParser
from bookmakers.manual_source import list_manual_events, parse_manual
from market.consensus import evaluate_event
from scoring.ev import evaluate_value


RUNS_DIR = Path("data/runs")
RUNS_DIR.mkdir(parents=True, exist_ok=True)


def save_run(results: list[dict]) -> str:
    now = datetime.now()
    filename = now.strftime("%Y-%m-%d-%H-%M") + ".json"
    payload = {
        "timestamp": now.isoformat(timespec="seconds"),
        "count": len(results),
        "results": results,
    }
    path = RUNS_DIR / filename
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(path)


def process_event(event_id: str, events, source: str) -> dict | None:
    print(f"\n=== EVENT {event_id} ({source}) ===")
    print(f"Собрано кэфов от {len(events)} БК")

    market_data = evaluate_event(events)
    if market_data.get("status") != "ok":
        print(f"market: {market_data.get('status')}")
        return None

    ev = market_data["event"]
    print(f"{ev['home']} — {ev['away']} ({ev['league']})")
    print(f"kickoff: {ev['kickoff']}")

    for outcome, c in market_data["consensus"].items():
        print(
            f"  {outcome:6} prob={c['consensus_prob']:.3f} "
            f"odds={c['consensus_odds']} "
            f"conf={c['confidence']:.2f} "
            f"sources={c['sources']}"
        )

    value_bets = evaluate_value(market_data)
    print(f"\nVALUE BETS: {len(value_bets)}")

    for vb in value_bets:
        print(
            f"  [{vb.deal_score}/100] "
            f"{vb.outcome} @ {vb.bookmaker} {vb.odds} "
            f"EV={vb.ev*100:.1f}% "
            f"kelly={vb.kelly*100:.2f}%"
        )
        for reason in vb.reasons:
            print(f"      • {reason}")

    return {
        "event_id": event_id,
        "source": source,
        "event": ev,
        "consensus": market_data["consensus"],
        "value_bets": [vb.__dict__ for vb in value_bets],
    }


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "mock"
    parser = OddsParser()
    all_results = []
    total_value_bets = 0

    if mode == "manual":
        event_ids = list_manual_events()
        for event_id in event_ids:
            events = parse_manual(event_id)
            result = process_event(event_id, events, "manual")
            if result:
                all_results.append(result)
                total_value_bets += len(result["value_bets"])
    else:
        # mock — использует встроенные данные parser.py
        from bookmakers.parser import MOCK_DATA
        for event_id in MOCK_DATA:
            events = parser.parse(event_id)
            result = process_event(event_id, events, "mock")
            if result:
                all_results.append(result)
                total_value_bets += len(result["value_bets"])

    print(f"\n=== ИТОГО ({mode}) ===")
    print(f"Событий: {len(all_results)}")
    print(f"Value-bets: {total_value_bets}")

    if all_results:
        path = save_run(all_results)
        print(f"Сохранено: {path}")


if __name__ == "__main__":
    main()
