#!/usr/bin/env python3
"""
Sync Flashscore 'missing players' for one or more matches into data/injuries/.

Reality (EVR-0007):
  Flashscore exposes missing players only ~24h around kickoff.
  Outside the window, cache is written as {"home": [], "away": []} — a valid result.

Usage:
    python scripts/fetch_injuries.py --mid bZoWLHvJ
    python scripts/fetch_injuries.py --mid bZoWLHvJ --force
    python scripts/fetch_injuries.py --all-from-midmap --window-hours 36
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bookmakers.flashscore_injuries import (  # noqa: E402
    load_injuries,
    parse_missing_players,
    save_injuries,
)
from bookmakers.flashscore_mid_map import load_mid_map  # noqa: E402
from bookmakers.flashscore_match_fetch import fetch_match_html  # noqa: E402


def sync_one(mid: str, *, force: bool = False, force_overwrite: bool = False, timeout_ms: int = 30000) -> dict:
    """Fetch + parse + save injuries for one mid.

    Returns the resulting injuries dict.
    """
    if not force:
        cached = load_injuries(mid)
        if cached is not None:
            print(f"[{mid}] cached, skip")
            return cached

    print(f"[{mid}] fetching…")
    html = fetch_match_html(mid, timeout_ms=timeout_ms)
    if not html:
        print(f"[{mid}] empty response — cache unchanged")
        return load_injuries(mid) or {"home": [], "away": []}

    data = parse_missing_players(html)
    total = len(data.get("home", [])) + len(data.get("away", []))

    # Data-loss guard (EVR-0007):
    # Outside the timing window Flashscore hides the lineup block.
    # Empty parse is "no data right now", not "no injuries".
    existing = load_injuries(mid) or {"home": [], "away": []}
    existing_total = len(existing.get("home", [])) + len(existing.get("away", []))
    if total == 0 and existing_total > 0 and not force_overwrite:
        print(f"[{mid}] parse=0, cache={existing_total} — preserving cache")
        return existing

    saved_path = save_injuries(mid, data)
    if saved_path is None:
        print(f"[{mid}] empty result, not persisted (no evidence)")
        return data
    print(f"[{mid}] saved {total} players -> {saved_path}")
    return data


def sync_all(force: bool, force_overwrite: bool, window_hours: int) -> None:
    """Sync all mids from mid_map (currently ignores window, hits only one page each)."""
    mid_map = load_mid_map()
    if not mid_map:
        print("mid_map empty — nothing to sync")
        return

    print(f"[sync] {len(mid_map)} mids in mid_map")
    for r in mid_map:
        mid = r.get("mid")
        if not mid:
            continue
        try:
            sync_one(mid, force=force, force_overwrite=force_overwrite)
        except Exception as e:
            print(f"[{mid}] FAIL: {e}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mid", help="Single Flashscore mid")
    p.add_argument("--all-from-midmap", action="store_true",
                   help="Sync every mid in data/mid_map.json")
    p.add_argument("--window-hours", type=int, default=36,
                   help="(reserved) sync only matches within N hours")
    p.add_argument("--force", action="store_true",
                   help="Ignore cache and refetch")
    p.add_argument("--force-overwrite", action="store_true",
                   help="Allow overwriting non-empty cache with empty parse")
    args = p.parse_args()

    if args.mid:
        sync_one(args.mid, force=args.force, force_overwrite=args.force_overwrite)
        return 0

    if args.all_from_midmap:
        sync_all(args.force, args.force_overwrite, args.window_hours)
        return 0

    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
