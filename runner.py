"""
BET-ANALYZER runner.
Конвейер: event_id → parser → consensus → EV → value-ставки.
"""

import json
from datetime import datetime
from pathlib import Path

from bookmakers.parser import OddsParser
from market.consensus import evaluate_event
from scoring.ev import evaluate_value


EVENTS = [
    "rpl_zenit_spartak_2026_09_15",
]

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


def main():
    parser = OddsParser()
    all_results = []

    for event_id in EVENTS:
        print(f"\n=== EVENT {event_id} ===")

        events = parser.parse(event_id)
        print(f"Собрано кэфов от {len(events)} БК")

        market_data = evaluate_event(events)
        if market_data.get("status") != "ok":
            print(f"market: {market_data.get('status')}")
            continue

        ev = market_data["event"]
        print(f"{ev['home']} — {ev['away']} ({ev['league']})")
        print(f"kickoff: {ev['kickoff']}")

        consensus = market_data["consensus"]
        for outcome, c in consensus.items():
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

        all_results.append({
            "event_id": event_id,
            "event": ev,
            "consensus": consensus,
            "value_bets": [vb.__dict__ for vb in value_bets],
        })

    if all_results:
        path = save_run(all_results)
        print(f"\nСохранено: {path}")


if __name__ == "__main__":
    main()
