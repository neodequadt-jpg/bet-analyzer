"""Manual bonus registry: load / validate / mark_used / list_active."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path("data/bonuses.json")

EXAMPLE_REGISTRY: dict[str, dict[str, Any]] = {
    "Winline": {
        "type": "freebet_snr",
        "amount": 10000,
        "min_odds": 1.30,
        "max_odds": 2.50,
        "expiry": "2026-12-31",
        "status": "active",
    },
    "PARI": {
        "type": "freebet_snr",
        "amount": 15000,
        "min_odds": 1.50,
        "max_odds": 3.00,
        "expiry": "2026-12-31",
        "status": "active",
    },
}


@dataclass
class Bonus:
    """Single bonus entry from the manual registry."""

    bookmaker: str
    type: str
    amount: int
    min_odds: float
    max_odds: float
    expiry: str
    status: str


def _ensure_file(path: Path) -> None:
    """Create *path* with EXAMPLE_REGISTRY if it does not exist."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(EXAMPLE_REGISTRY, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("Created example registry at %s", path)


def load(path: str | Path = DEFAULT_PATH) -> dict[str, dict[str, Any]]:
    """Load the manual bonus registry from *path*.

    If the file is missing, an example with Winline/PARI is created first.
    """
    p = Path(path)
    _ensure_file(p)
    with p.open(encoding="utf-8") as fh:
        data: dict[str, dict[str, Any]] = json.load(fh)
    logger.debug("Loaded %d bonus entries from %s", len(data), p)
    return data


def _save(registry: dict[str, dict[str, Any]], path: Path) -> None:
    """Atomically-ish write *registry* back to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(registry, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    logger.debug("Saved registry (%d entries) to %s", len(registry), path)


def validate(bonus: dict[str, Any]) -> list[str]:
    """Return a list of validation error strings for a single bonus entry.

    An empty list means the entry is valid.
    """
    errors: list[str] = []

    # required keys
    required = ("type", "amount", "min_odds", "max_odds", "expiry", "status")
    for key in required:
        if key not in bonus:
            errors.append(f"missing key: {key}")

    # type checks (only if key present)
    if "type" in bonus and not isinstance(bonus["type"], str):
        errors.append("type must be str")

    if "amount" in bonus:
        if not isinstance(bonus["amount"], (int, float)):
            errors.append("amount must be numeric")
        elif bonus["amount"] <= 0:
            errors.append("amount must be > 0")

    if "min_odds" in bonus:
        if not isinstance(bonus["min_odds"], (int, float)):
            errors.append("min_odds must be numeric")
        elif bonus["min_odds"] < 1.0:
            errors.append("min_odds must be >= 1.0")

    if "max_odds" in bonus:
        if not isinstance(bonus["max_odds"], (int, float)):
            errors.append("max_odds must be numeric")
        elif bonus["max_odds"] < 1.0:
            errors.append("max_odds must be >= 1.0")

    if "min_odds" in bonus and "max_odds" in bonus:
        if isinstance(bonus["min_odds"], (int, float)) and isinstance(bonus["max_odds"], (int, float)):
            if bonus["min_odds"] > bonus["max_odds"]:
                errors.append("min_odds must be <= max_odds")

    if "expiry" in bonus:
        try:
            datetime.strptime(str(bonus["expiry"]), "%Y-%m-%d")
        except ValueError:
            errors.append("expiry must be YYYY-MM-DD")

    if "status" in bonus:
        valid_statuses = {"active", "used", "expired", "skipped"}
        if bonus["status"] not in valid_statuses:
            errors.append(f"status must be one of {sorted(valid_statuses)}")

    return errors


def mark_used(name: str, path: str | Path = DEFAULT_PATH) -> None:
    """Set status='used' for bonus *name* and persist the registry."""
    p = Path(path)
    registry = load(p)
    if name not in registry:
        logger.warning("Bonus %r not found in registry — skipping", name)
        return
    registry[name]["status"] = "used"
    _save(registry, p)
    logger.info("Marked bonus %r as used", name)


def list_active(path: str | Path = DEFAULT_PATH) -> list[Bonus]:
    """Return all bonuses with status=='active' as Bonus dataclass instances."""
    registry = load(path)
    today = date.today()
    active: list[Bonus] = []
    for name, entry in registry.items():
        if entry.get("status") != "active":
            continue
        # auto-expire if past expiry date
        try:
            expiry_date = date.fromisoformat(entry["expiry"])
            if expiry_date < today:
                logger.info("Bonus %r expired (%s) — skipping", name, entry["expiry"])
                continue
        except (KeyError, ValueError):
            pass  # keep if expiry missing/malformed
        active.append(
            Bonus(
                bookmaker=name,
                type=entry.get("type", ""),
                amount=int(entry.get("amount", 0)),
                min_odds=float(entry.get("min_odds", 1.0)),
                max_odds=float(entry.get("max_odds", 1.0)),
                expiry=str(entry.get("expiry", "")),
                status=entry.get("status", "active"),
            )
        )
    logger.debug("Found %d active bonuses", len(active))
    return active
