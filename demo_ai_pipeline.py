"""Demo: Python + OmniRoute + DeepSeek-style prompt."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bookmakers.fonbet_api import fetch_rpl_odds
from bookmakers.manual_source import list_manual_events, parse_manual
from bookmakers.normalizer import merge
from market.consensus import evaluate_event
from scoring.ev import evaluate_value
from ai.analyst import ValueBetAnalyst


def main():
    print("[1/4] Fetch Fonbet RPL odds...")
    fonbet_events = fetch_rpl_odds(force=True)
    print("      fonbet raw:", len(fonbet_events))

    print("[2/4] Load manual multi-BK data...")
    manual_events = []
    for eid in list_manual_events():
        manual_events.extend(parse_manual(eid))
    print("      manual raw:", len(manual_events))

    print("[3/4] Merge + consensus + EV...")
    groups = merge(fonbet_events, manual_events)
    print("      grouped:", len(groups))

    target_market = None
    target_group = None
    target_vbs = None
    for group in groups:
        if len(group) < 3:
            continue
        market = evaluate_event(group)
        if market.get("status") != "ok":
            continue
        vbs = evaluate_value(market)
        if vbs:
            target_market = market
            target_group = group
            target_vbs = vbs
            break

    if not target_vbs:
        print("      no value-bets -> skip AI")
        return

    ev = target_market["event"]
    print("      target:", ev["home"], "vs", ev["away"], "(", len(target_group), "BK )")
    print("      value-bets:", len(target_vbs))

    print("[4/4] AI analyst via OmniRoute...")
    ai = ValueBetAnalyst()
    print("      model:", ai.model, "| auth:", bool(ai.api_key))

    try:
        report = ai.analyze(
            event=ev,
            consensus=target_market["consensus"],
            value_bets=[vb.__dict__ for vb in target_vbs],
        )
    except Exception as e:
        print("      AI err:", e)
        return

    print()
    print("=" * 70)
    print("  AI REPORT:", ev["home"], "vs", ev["away"])
    print("=" * 70)
    print(report)
    print("=" * 70)

    out = Path("data/runs") / "demo_ai_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "event": ev,
        "consensus": target_market["consensus"],
        "value_bets": [vb.__dict__ for vb in target_vbs],
        "ai_report": report,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved:", out)


if __name__ == "__main__":
    main()
