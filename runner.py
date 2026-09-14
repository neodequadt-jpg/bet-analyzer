"""
BET-ANALYZER runner.
Источники:
  - mock:    MOCK_DATA в parser.py
  - manual:  data/manual/*.json
  - fonbet:  публичный API Fonbet (ЦУПИС)
Конвейер: source -> consensus -> EV -> value_bets -> report.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Fix: чтобы работал импорт bookmakers.* без PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bookmakers.parser import OddsParser, MOCK_DATA
from bookmakers.manual_source import list_manual_events, parse_manual
from bookmakers.fonbet_api import fetch_rpl_odds
from market.consensus import evaluate_event
from scoring.ev import evaluate_value

RUNS_DIR = Path("data/runs")
RUNS_DIR.mkdir(parents=True, exist_ok=True)


def save_run(results):
    now = datetime.now()
    filename = now.strftime("%Y-%m-%d-%H-%M-%S") + ".json"
    payload = {"timestamp": now.isoformat(timespec="seconds"), "count": len(results), "results": results}
    path = RUNS_DIR / filename
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def process_event(event_id, events, source):
    print(f"\n=== EVENT {event_id} ({source}) ===")
    print(f"Собрано кэфов от {len(events)} БК")
    if not events:
        return None
    market_data = evaluate_event(events)
    if market_data.get("status") != "ok":
        print(f"market: {market_data.get('status')}")
        return None
    ev = market_data["event"]
    print(f"{ev['home']} - {ev['away']} ({ev['league']})")
    print(f"kickoff: {ev['kickoff']}")
    for outcome, c in market_data["consensus"].items():
        print(f"  {outcome:6} prob={c['consensus_prob']:.3f} odds={c['consensus_odds']} conf={c['confidence']:.2f} sources={c['sources']}")
    value_bets = evaluate_value(market_data)
    print(f"\nVALUE BETS: {len(value_bets)}")
    for vb in value_bets:
        print(f"  [{vb.deal_score}/100] {vb.outcome} @ {vb.bookmaker} {vb.odds} EV={vb.ev*100:.1f}% kelly={vb.kelly*100:.2f}%")
        for reason in vb.reasons:
            print(f"      - {reason}")
    return {
        "event_id": event_id,
        "source": source,
        "event": ev,
        "consensus": market_data["consensus"],
        "value_bets": [vb.__dict__ for vb in value_bets],
    }


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "mock"
    print(f"[runner] mode={mode}")
    all_results = []
    total_value_bets = 0

    if mode == "manual":
        for event_id in list_manual_events():
            events = parse_manual(event_id)
            r = process_event(event_id, events, "manual")
            if r:
                all_results.append(r)
                total_value_bets += len(r["value_bets"])

    elif mode == "fonbet":
        events = fetch_rpl_odds(force=True)
        print(f"[fonbet] загружено {len(events)} матчей РПЛ")
        # Один БК = консенсус невозможен, но валидируем данные
        for e in events:
            r = process_event(e.event_id, [e], "fonbet")
            if r:
                all_results.append(r)
                total_value_bets += len(r["value_bets"])

    else:  # mock
        parser = OddsParser()
        for event_id in MOCK_DATA:
            events = parser.parse(event_id)
            r = process_event(event_id, events, "mock")
            if r:
                all_results.append(r)
                total_value_bets += len(r["value_bets"])

    print(f"\n=== ИТОГО ({mode}) ===")
    print(f"Событий: {len(all_results)}")
    print(f"Value-bets: {total_value_bets}")
    if all_results:
        path = save_run(all_results)
        print(f"Сохранено: {path}")


if __name__ == "__main__":
    main()
