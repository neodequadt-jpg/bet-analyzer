"""Bookmaker reliability monitor — scoring, risky/recommended lists.

Reads data/bookmakers.json and assigns a 0-100 heuristic score
based on license, payout speed, and reported issues.

Spec: G-0013 §4
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# License weight table
# ---------------------------------------------------------------------------
_LICENSE_WEIGHT: dict[str, int] = {
    "UKGC": 40,
    "MGA": 40,
    "RU": 30,
    "Curacao": 15,
    "Anjouan": 5,
    "none": 0,
}

# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def load(path: str | Path = "data/bookmakers.json") -> dict[str, Any]:
    """Load the bookmaker registry from a JSON file.

    Returns a dict mapping bookmaker name → info dict.
    """
    p = Path(path)
    logger.info("Loading bookmaker registry from %s", p)
    with p.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    logger.debug("Loaded %d bookmakers", len(data))
    return data


def score(bk: dict[str, Any]) -> int:
    """Compute a 0-100 reliability score for a single bookmaker record.

    Heuristic breakdown (max 100):
      - license weight: UKGC/MGA=40, RU=30, Curacao=15, Anjouan=5, none=0
      - payout speed:   max(0, 30 - payout_days * 3)
      - issues penalty: max(0, 30 - len(issues) * 10)

    Result is clamped to [0, 100].
    """
    # License component
    lic: str = bk.get("license", "none")
    license_pts: int = _LICENSE_WEIGHT.get(lic, 0)

    # Payout speed component
    payout_days: int = bk.get("payout_days", 30)
    payout_pts: int = max(0, 30 - payout_days * 3)

    # Issues component
    issues: list[str] = bk.get("issues", [])
    issues_pts: int = max(0, 30 - len(issues) * 10)

    total: int = license_pts + payout_pts + issues_pts
    clamped: int = max(0, min(100, total))

    logger.debug(
        "score: license=%s→%d, payout_days=%d→%d, issues=%d→%d, total=%d→%d",
        lic, license_pts, payout_days, payout_pts,
        len(issues), issues_pts, total, clamped,
    )
    return clamped


# ---------------------------------------------------------------------------
# List helpers
# ---------------------------------------------------------------------------

def list_risky(
    threshold: int = 50,
    registry_path: str | Path = "data/bookmakers.json",
) -> list[tuple[str, int]]:
    """Return bookmakers scoring below *threshold*, sorted worst-first.

    Each entry is (name, score).
    """
    data = load(registry_path)
    results: list[tuple[str, int]] = []
    for name, bk in data.items():
        s = score(bk)
        if s < threshold:
            results.append((name, s))
    results.sort(key=lambda x: x[1])
    logger.info("list_risky(threshold=%d): %d bookmakers", threshold, len(results))
    return results


def list_recommended(
    threshold: int = 70,
    registry_path: str | Path = "data/bookmakers.json",
) -> list[tuple[str, int]]:
    """Return bookmakers scoring at or above *threshold*, sorted best-first.

    Each entry is (name, score).
    """
    data = load(registry_path)
    results: list[tuple[str, int]] = []
    for name, bk in data.items():
        s = score(bk)
        if s >= threshold:
            results.append((name, s))
    results.sort(key=lambda x: x[1], reverse=True)
    logger.info("list_recommended(threshold=%d): %d bookmakers", threshold, len(results))
    return results
