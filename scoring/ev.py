"""
Value detection на leave-one-out consensus.
"""

from dataclasses import dataclass
from scoring.devig import shin_devig, multiplicative_devig
from bookmakers.registry import get_bookmaker

MIN_EV = 0.03
MIN_CONFIDENCE = 0.5
MIN_TRUST = 0.7

# Реалистичные потолки EV по видам спорта.
# 2-way рынки (KHL, теннис) имеют высокую маржу — consensus
# завышает EV. Ограничиваем разумными порогами.
MAX_EV_BY_SPORT = {
    "football": 0.25,
    "hockey":   0.15,
    "basketball": 0.15,
    "tennis":   0.15,
}


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
    p = max(0.0, min(1.0, true_prob))
    q = 1.0 - p
    f = (b * p - q) / b
    return max(0.0, min(1.0, f))


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

    consensus = event_data.get("consensus", {})
    if not consensus:
        return []

    outcomes = list(consensus.keys())
    SHARP_BOOKS = {"Pinnacle", "Betfair"}

    # 1. Sharp fair probabilities (devig, Shin preferred)
    sharp_bk = None
    for bk in SHARP_BOOKS:
        seq = []
        ok = True
        for oc in outcomes:
            o = (consensus[oc].get("bookmaker_odds") or {}).get(bk)
            if not o or o <= 1.0:
                ok = False
                break
            seq.append(o)
        if ok:
            sharp_bk = bk
            sharp_odds = seq
            break

    if sharp_bk:
        try:
            fair = shin_devig(sharp_odds)
        except ValueError:
            fair = multiplicative_devig(sharp_odds)
        fair_by_outcome = dict(zip(outcomes, fair))
        fair_source = f"Shin,{sharp_bk}"
    else:
        fair_by_outcome = {
            oc: consensus[oc].get("consensus_prob", 0) for oc in outcomes
        }
        fair_source = "consensus"

    # 2. Value = soft book where odds > fair_odds (sharp only for reference)
    value_bets = []
    sport = event_data.get("event", {}).get("sport", "football")
    max_ev = MAX_EV_BY_SPORT.get(sport, 0.15)

    for outcome in outcomes:
        true_prob = fair_by_outcome[outcome]
        if true_prob <= 0 or true_prob >= 1:
            continue
        fair_odds = 1.0 / true_prob
        bookmaker_odds = consensus[outcome].get("bookmaker_odds") or {}

        for bk, bk_odds in bookmaker_odds.items():
            if bk in SHARP_BOOKS:
                continue
            if not bk_odds or bk_odds <= fair_odds:
                continue
            ev = true_prob * bk_odds - 1.0
            if ev < MIN_EV or ev > max_ev:
                continue
            bk_info = get_bookmaker(bk)
            # Unknown bookmaker (not in registry, e.g. Fonbet): trust unknown,
            # not low — do not skip, but _deal_score is lowered (trust=0.5).
            if bk_info is not None:
                trust = bk_info.trust_score
                if trust < MIN_TRUST:
                    continue
            else:
                trust = 0.5
            confidence = consensus[outcome].get("confidence", 0.5)
            if confidence < MIN_CONFIDENCE:
                continue
            kelly = _kelly(true_prob, bk_odds)
            score = _deal_score(ev, confidence, trust)
            reasons = [
                f"EV {ev*100:.1f}%",
                f"true_prob {true_prob:.3f} ({fair_source})",
                f"кэф {bk_odds} @ {bk} vs fair {fair_odds:.2f}",
            ]
            value_bets.append(ValueBet(
                outcome=outcome, bookmaker=bk, odds=bk_odds,
                true_prob=round(true_prob, 4), ev=round(ev, 4),
                kelly=round(kelly, 4), confidence=round(confidence, 4),
                trust_score=trust, deal_score=score, reasons=reasons,
            ))

    value_bets.sort(key=lambda v: v.deal_score, reverse=True)
    return value_bets
