"""
Value detection на leave-one-out consensus.
"""

from dataclasses import dataclass

MIN_EV = 0.03
MIN_CONFIDENCE = 0.5
MIN_TRUST = 0.7


@dataclass
class ValueBet:
    outcome: str
    bookmaker: str
    odds: float
    true_prob: float
    ev: float
    kelly: float
    confidence: float
    trust_score: float
    deal_score: int
    reasons: list


def _kelly(true_prob, odds):
    if odds <= 1.0:
        return 0.0
    b = odds - 1.0
    p = true_prob
    q = 1.0 - p
    f = (b * p - q) / b
    return max(0.0, f)


def _deal_score(ev, confidence, trust):
    if ev <= 0:
        return 0
    if ev >= 0.15:
        ev_score = 100
    elif ev >= 0.10:
        ev_score = 90
    elif ev >= 0.05:
        ev_score = 60
    elif ev >= 0.03:
        ev_score = 40
    else:
        ev_score = max(0, round(ev * 1000))
    raw = ev_score * (0.5 + 0.5 * confidence) * (0.5 + 0.5 * trust)
    return max(0, min(100, round(raw)))


def evaluate_value(event_data):
    if event_data.get("status") != "ok":
        return []

    per_bk = event_data.get("consensus_per_bk", {})
    best_odds = event_data.get("best_odds", {})
    value_bets = []

    for outcome, best in best_odds.items():
        bk_name = best["bookmaker"]
        bk_outcomes = per_bk.get(bk_name, {})
        if outcome not in bk_outcomes:
            continue

        c = bk_outcomes[outcome]
        if c["confidence"] < MIN_CONFIDENCE:
            continue

        odds = best["odds"]
        true_prob = c["consensus_prob"]
        confidence = c["confidence"]
        trust = best["trust_score"]

        if trust < MIN_TRUST:
            continue

        ev = true_prob * odds - 1.0
        if ev < MIN_EV:
            continue

        kelly = _kelly(true_prob, odds)
        score = _deal_score(ev, confidence, trust)

        reasons = [
            f"EV {ev*100:.1f}%",
            f"confidence {confidence:.2f} (без {bk_name})",
            f"trust {trust:.2f}",
            f"кэф {odds} vs честный {c['consensus_odds']}",
        ]

        value_bets.append(ValueBet(
            outcome=outcome,
            bookmaker=bk_name,
            odds=odds,
            true_prob=true_prob,
            ev=round(ev, 4),
            kelly=round(kelly, 4),
            confidence=confidence,
            trust_score=trust,
            deal_score=score,
            reasons=reasons,
        ))

    value_bets.sort(key=lambda v: v.deal_score, reverse=True)
    return value_bets
