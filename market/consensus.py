"""
Leave-one-out consensus.
Для каждого БК consensus считается без него.
"""

from dataclasses import dataclass
from statistics import median, stdev

from bookmakers.parser import OddsEvent
from bookmakers.registry import get_bookmaker


@dataclass
class ConsensusOutcome:
    outcome: str
    consensus_prob: float
    consensus_odds: float
    confidence: float
    sources: int
    bookmaker_odds: dict


def _implied_prob(odds: float) -> float:
    if odds is None or odds <= 1.0:
        return 0.0
    return 1.0 / odds


def _remove_margin(probs: list[float]) -> list[float]:
    total = sum(probs)
    if total <= 0:
        return probs
    return [p / total for p in probs]


def _consensus_from_subset(subset, outcome):
    """
    Поддерживает:
    - 3-way рынок (football): home / draw / away
    - 2-way рынок (hockey, tennis): home / away
    """
    bk_probs = []
    for h, d, a in subset.values():
        if h is None or a is None:
            continue

        if d is None:
            # 2-way рынок
            if outcome == "draw":
                continue
            raw = [_implied_prob(h), _implied_prob(a)]
            normalized = _remove_margin(raw)
            idx = {"home": 0, "away": 1}[outcome]
        else:
            # 3-way рынок
            raw = [_implied_prob(h), _implied_prob(d), _implied_prob(a)]
            normalized = _remove_margin(raw)
            idx = {"home": 0, "draw": 1, "away": 2}[outcome]

        bk_probs.append(normalized[idx])

    if not bk_probs:
        return 0.0, 0.0, 0

    prob = median(bk_probs)
    sources = len(bk_probs)
    spread = stdev(bk_probs) if sources >= 2 else 0.0
    source_score = min(sources / 6.0, 1.0)
    spread_score = max(0.0, 1.0 - spread / 0.05)
    confidence = round(0.6 * source_score + 0.4 * spread_score, 2)
    return prob, confidence, sources


def build_consensus(events):
    raw_by_bk = {ev.bookmaker: (ev.odds_home, ev.odds_draw, ev.odds_away) for ev in events}
    result = {}
    for outcome in ("home", "draw", "away"):
        prob, conf, src = _consensus_from_subset(raw_by_bk, outcome)
        if src == 0:
            continue
        odds_map = {
            ev.bookmaker: getattr(ev, f"odds_{outcome}")
            for ev in events if getattr(ev, f"odds_{outcome}")
        }
        result[outcome] = ConsensusOutcome(
            outcome=outcome,
            consensus_prob=round(prob, 4),
            consensus_odds=round(1 / prob, 2) if prob else 0.0,
            confidence=conf,
            sources=src,
            bookmaker_odds=odds_map,
        )
    return result


def consensus_per_bookmaker(events):
    raw_by_bk = {ev.bookmaker: (ev.odds_home, ev.odds_draw, ev.odds_away) for ev in events}
    result = {}
    for bk_name in raw_by_bk:
        subset = {k: v for k, v in raw_by_bk.items() if k != bk_name}
        if not subset:
            continue
        bk_result = {}
        for outcome in ("home", "draw", "away"):
            prob, conf, src = _consensus_from_subset(subset, outcome)
            if src == 0:
                continue
            bk_result[outcome] = ConsensusOutcome(
                outcome=outcome,
                consensus_prob=round(prob, 4),
                consensus_odds=round(1 / prob, 2) if prob else 0.0,
                confidence=conf,
                sources=src,
                bookmaker_odds={
                    k: raw_by_bk[k][{"home": 0, "draw": 1, "away": 2}[outcome]]
                    for k in subset
                },
            )
        result[bk_name] = bk_result
    return result


def evaluate_event(events):
    if not events:
        return {"status": "no_data"}

    market_consensus = build_consensus(events)
    per_bk = consensus_per_bookmaker(events)

    best_odds = {}
    for outcome in market_consensus:
        odds_map = market_consensus[outcome].bookmaker_odds
        if not odds_map:
            continue
        best_bk = max(odds_map, key=odds_map.get)
        bk_info = get_bookmaker(best_bk)
        best_odds[outcome] = {
            "bookmaker": best_bk,
            "odds": odds_map[best_bk],
            "trust_score": bk_info.trust_score if bk_info else 0.5,
            "cupis": bk_info.cupis if bk_info else None,
        }

    return {
        "status": "ok",
        "event": {
            "sport": events[0].sport,
            "league": events[0].league,
            "home": events[0].home,
            "away": events[0].away,
            "kickoff": events[0].kickoff_iso,
        },
        "consensus": {k: v.__dict__ for k, v in market_consensus.items()},
        "consensus_per_bk": {
            bk: {out: c.__dict__ for out, c in outcomes.items()}
            for bk, outcomes in per_bk.items()
        },
        "best_odds": best_odds,
    }
