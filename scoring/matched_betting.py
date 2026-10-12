"""Matched betting calculator — SNR (Stake Not Returned) free bet layout."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LayResult:
    """Result of a lay calculation for an SNR free bet."""

    lay_stake: float
    liability: float
    profit_if_back: float
    profit_if_lay: float
    guaranteed: float


def _validate_common(free_bet: float, back_odds: float, lay_odds: float, commission: float) -> None:
    """Raise ValueError if any input is out of domain."""
    if free_bet <= 0:
        raise ValueError(f"free_bet must be > 0, got {free_bet}")
    if back_odds <= 1:
        raise ValueError(f"back_odds must be > 1, got {back_odds}")
    if lay_odds <= 1:
        raise ValueError(f"lay_odds must be > 1, got {lay_odds}")
    if not (0 <= commission < 1):
        raise ValueError(f"commission must be in [0, 1), got {commission}")


def calc_lay(
    free_bet: float,
    back_odds: float,
    lay_odds: float,
    commission: float = 0.02,
) -> LayResult:
    """Calculate lay stake and guaranteed profit for an SNR free bet.

    Formula (Stake Not Returned):
        lay_stake      = free_bet * (back_odds - 1) / (lay_odds - commission)
        liability      = lay_stake * (lay_odds - 1)
        profit_if_back = free_bet * (back_odds - 1) - liability
        profit_if_lay  = lay_stake * (1 - commission)
        guaranteed     = min(profit_if_back, profit_if_lay)
    """
    _validate_common(free_bet, back_odds, lay_odds, commission)

    lay_stake = free_bet * (back_odds - 1) / (lay_odds - commission)
    liability = lay_stake * (lay_odds - 1)
    profit_if_back = free_bet * (back_odds - 1) - liability
    profit_if_lay = lay_stake * (1 - commission)
    guaranteed = min(profit_if_back, profit_if_lay)

    logger.debug(
        "calc_lay: free_bet=%.2f back_odds=%.2f lay_odds=%.2f comm=%.4f "
        "→ lay_stake=%.4f liability=%.4f profit_back=%.4f profit_lay=%.4f guaranteed=%.4f",
        free_bet, back_odds, lay_odds, commission,
        lay_stake, liability, profit_if_back, profit_if_lay, guaranteed,
    )

    return LayResult(
        lay_stake=lay_stake,
        liability=liability,
        profit_if_back=profit_if_back,
        profit_if_lay=profit_if_lay,
        guaranteed=guaranteed,
    )


def find_optimal(
    free_bet: float,
    back_odds: float,
    lay_odds_range: tuple[float, float],
    commission: float = 0.02,
) -> LayResult:
    """Find lay_odds within *lay_odds_range* that maximises guaranteed profit.

    Scans the range with a step of 0.01 and returns the LayResult for the
    best lay_odds found.  The returned LayResult corresponds to the optimal
    lay_odds; callers can inspect it to recover the odds used.
    """
    lo, hi = lay_odds_range
    if lo > hi:
        raise ValueError(f"lay_odds_range lower bound {lo} exceeds upper bound {hi}")

    # Validate with the boundary odds so we get early errors for free_bet / back_odds / commission.
    _validate_common(free_bet, back_odds, lo, commission)

    best_result: LayResult | None = None
    best_guaranteed = -math.inf
    best_odds = lo

    steps = round((hi - lo) / 0.01)
    for i in range(steps + 1):
        lay_odds = round(lo + i * 0.01, 10)  # avoid float drift
        if lay_odds > hi:
            break
        if lay_odds <= 1:
            continue
        result = calc_lay(free_bet, back_odds, lay_odds, commission)
        if result.guaranteed > best_guaranteed:
            best_guaranteed = result.guaranteed
            best_result = result
            best_odds = lay_odds

    if best_result is None:
        raise ValueError("no valid lay_odds found in the given range")

    logger.info(
        "find_optimal: free_bet=%.2f back_odds=%.2f range=[%.2f, %.2f] comm=%.4f "
        "→ best_lay_odds=%.2f guaranteed=%.4f",
        free_bet, back_odds, lo, hi, commission,
        best_odds, best_guaranteed,
    )

    return best_result
