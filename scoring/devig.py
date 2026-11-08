"""Devig algorithms: fair probabilities from bookmaker odds.

Shin (1993): models favorite-longshot bias via "insider fraction" z.
Multiplicative: proportional normalization (fallback).
"""
from __future__ import annotations


def multiplicative_devig(odds: list[float]) -> list[float]:
    """Proportional devig. Returns probs summing to 1."""
    if len(odds) < 2 or any(o <= 1.0 for o in odds):
        raise ValueError(f"bad odds: {odds}")
    q = [1.0 / o for o in odds]
    Q = sum(q)
    if Q <= 0:
        raise ValueError("degenerate odds")
    return [qi / Q for qi in q]


def shin_devig(odds: list[float]) -> list[float]:
    """Shin (1993) devig. Returns probs summing to 1.

    Solves for z in (0,1) s.t. sum(pi_i(z)) == 1:
        pi_i(z) = (sqrt(z^2 + 4(1-z)*q_i^2/Q) - z) / (2(1-z))
    where q_i = 1/odds_i, Q = sum(q_i).

    Falls back to multiplicative if no vig or no solution.
    """
    if len(odds) < 2 or any(o <= 1.0 for o in odds):
        raise ValueError(f"bad odds: {odds}")

    q = [1.0 / o for o in odds]
    Q = sum(q)
    if Q <= 1.0:
        return [qi / Q for qi in q]

    def sum_pi(z: float) -> float:
        denom = 2.0 * (1.0 - z)
        total = 0.0
        for qi in q:
            disc = z * z + 4.0 * (1.0 - z) * qi * qi / Q
            if disc < 0:
                disc = 0.0
            total += (disc ** 0.5 - z) / denom
        return total

    lo, hi = 0.0, 1.0 - 1e-9
    if sum_pi(lo) <= 1.0:
        return [qi / Q for qi in q]
    if sum_pi(hi) >= 1.0:
        return multiplicative_devig(odds)

    for _ in range(80):
        mid = (lo + hi) / 2.0
        if sum_pi(mid) > 1.0:
            lo = mid
        else:
            hi = mid
    z = (lo + hi) / 2.0

    probs = []
    for qi in q:
        disc = z * z + 4.0 * (1.0 - z) * qi * qi / Q
        if disc < 0:
            disc = 0.0
        probs.append((disc ** 0.5 - z) / (2.0 * (1.0 - z)))

    total = sum(probs)
    if total <= 0:
        return multiplicative_devig(odds)
    return [p / total for p in probs]
