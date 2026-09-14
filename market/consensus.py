"""
Consensus odds: на основе коэффициентов нескольких БК
строим оценку истинной вероятности события.

Метод:
1. Для каждой БК убираем маржу (normalized implied prob).
2. Медиана по БК — consensus.
3. Confidence = сколько БК согласны + насколько разброс.
"""

from dataclasses import dataclass
from statistics import median, stdev
from typing import Optional

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


def build_consensus(events: list[OddsEvent]) -> dict[str, ConsensusOutcome]:
    home_odds: dict[str, float] = {}
    draw_odds: dict[str, float] = {}
    away_odds: dict[str, float] = {}
    over_odds: dict[str, float] = {}
    under_odds: dict[str, float] = {}

    for ev in events:
        if ev.odds_home:
            home_odds[ev.bookmaker] = ev.odds_home
        if ev.odds_draw:
            draw_odds[ev.bookmaker] = ev.odds_draw
        if ev.odds_away:
            away_odds[ev.bookmaker] = ev.odds_away
        if ev.odds_total_over:
            over_odds[ev.bookmaker] = ev.odds_total_over
        if ev.odds_total_under:
            under_odds[ev.bookmaker] = ev.odds_total_under

    result: dict[str, ConsensusOutcome] = {}

    for outcome, odds_map in (
        ("home", home_odds),
        ("draw", draw_odds),
        ("away", away_odds),
    ):
        if not odds_map:
            continue

        bk_probs: dict[str, float] = {}
        for bk_name in odds_map:
            h = home_odds.get(bk_name)
            d = draw_odds.get(bk_name)
            a = away_odds.get(bk_name)
            if not (h and d and a):
                continue
            raw = [_implied_prob(h), _implied_prob(d), _implied_prob(a)]
            normalized = _remove_margin(raw)
            idx = {"home": 0, "draw": 1, "away": 2}[outcome]
            bk_probs[bk_name] = normalized[idx]

        if not bk_probs:
            continue

        probs = list(bk_probs.values())
        consensus_prob = median(probs)
        consensus_odds = round(1 / consensus_prob, 2) if consensus_prob > 0 else 0.0

        sources = len(probs)
        spread = stdev(probs) if sources >= 2 else 0.0
        source_score = min(sources / 6.0, 1.0)
        spread_score = max(0.0, 1.0 - spread / 0.05)
        confidence = round(0.6 * source_score + 0.4 * spread_score, 2)

        result[outcome] = ConsensusOutcome(
            outcome=outcome,
            consensus_prob=round(consensus_prob, 4),
            consensus_odds=consensus_odds,
            confidence=confidence,
            sources=sources,
            bookmaker_odds=odds_map,
        )

    if over_odds and under_odds:
        bk_probs_over: dict[str, float] = {}
        for bk_name in set(over_odds) & set(under_odds):
            raw = [
                _implied_prob(over_odds[bk_name]),
                _implied_prob(under_odds[bk_name]),
            ]
            normalized = _remove_margin(raw)
            bk_probs_over[bk_name] = normalized[0]

        if bk_probs_over:
            probs = list(bk_probs_over.values())
            consensus_prob = median(probs)
            sources = len(probs)
            spread = stdev(probs) if sources >= 2 else 0.0
            source_score = min(sources / 6.0, 1.0)
            spread_score = max(0.0, 1.0 - spread / 0.05)
            confidence = round(0.6 * source_score + 0.4 * spread_score, 2)

            result["over"] = ConsensusOutcome(
                outcome="over",
                consensus_prob=round(consensus_prob, 4),
                consensus_odds=round(1 / consensus_prob, 2) if consensus_prob else 0.0,
                confidence=confidence,
                sources=sources,
                bookmaker_odds=over_odds,
            )

    return result


def evaluate_event(events: list[OddsEvent]) -> dict:
    if not events:
        return {"status": "no_data"}

    consensus = build_consensus(events)

    best_odds: dict[str, dict] = {}
    for outcome in consensus:
        odds_map = consensus[outcome].bookmaker_odds
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
        "consensus": {k: v.__dict__ for k, v in consensus.items()},
        "best_odds": best_odds,
    }
