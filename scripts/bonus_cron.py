#!/usr/bin/env python3
"""
bonus_cron.py — Cron script for G-0014: bonus snapshot → Telegram alert.

Pipeline:
  1. Load env from ~/.bet_env and .env.bot (no python-dotenv).
  2. Clear proxy env vars before fetch.
  3. fetch_bonuses() → normalize → load_snapshot → snapshot_diff
  4. save_snapshot (before sending alerts).
  5. If diff has any changes or --force: send Telegram alert to all TG_ADMIN_IDS.

Usage:
    python scripts/bonus_cron.py
    python scripts/bonus_cron.py --dry-run
    python scripts/bonus_cron.py --force
    python scripts/bonus_cron.py --verbose
"""
from __future__ import annotations

import argparse
import html
import logging
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scoring.bonus_monitor import (  # noqa: E402
    fetch_bonuses,
    normalize,
    snapshot_diff,
    save_snapshot,
    load_snapshot,
)
from tg_bot import send_message  # noqa: E402

logger = logging.getLogger("bonus_cron")

# ---------------------------------------------------------------------------
# Env loading (no python-dotenv)
# ---------------------------------------------------------------------------

def _parse_env_file(path: Path) -> int:
    """Parse a shell-style env file. Returns count of vars set (not already in env)."""
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Remove optional "export " prefix
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        # Don't overwrite already set vars
        if key in os.environ:
            continue
        os.environ[key] = value
        count += 1
    return count


def load_env() -> None:
    """Load env from ~/.bet_env and .env.bot (in order, no overwrite)."""
    home_env = Path.home() / ".bet_env"
    bot_env = ROOT / ".env.bot"
    n1 = _parse_env_file(home_env)
    logger.debug("env loaded from %s (%d vars)", home_env, n1)
    n2 = _parse_env_file(bot_env)
    logger.debug("env loaded from %s (%d vars)", bot_env, n2)


# ---------------------------------------------------------------------------
# Proxy cleanup
# ---------------------------------------------------------------------------

PROXY_KEYS = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
    "http_proxy", "https_proxy", "all_proxy",
)


def clear_proxy_env() -> None:
    """Remove proxy env vars to avoid interference with fetch_bonuses."""
    for k in PROXY_KEYS:
        os.environ.pop(k, None)


# ---------------------------------------------------------------------------
# Alert formatting
# ---------------------------------------------------------------------------

def format_alert(diff: dict) -> str:
    """Format snapshot diff as HTML alert for Telegram."""
    new_items = diff.get("new", [])
    gone_items = diff.get("gone", [])
    changed_items = diff.get("changed", [])

    n_new = len(new_items)
    n_gone = len(gone_items)
    n_changed = len(changed_items)

    lines = [
        "🎁 <b>Bonus snapshot update</b>",
        f"Новых: {n_new}",
        f"Пропало: {n_gone}",
        f"Изменено: {n_changed}",
    ]

    # Up to 5 new bonuses with details
    for item in new_items[:5]:
        bk = html.escape(str(item.get("bookmaker", "")))
        title = html.escape(str(item.get("title", "")))
        url = html.escape(str(item.get("url", "")))
        lines.append(f"  • {bk}: {title} — {url}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TG_ADMIN_IDS helper (lazy, after env load)
# ---------------------------------------------------------------------------

def _get_admin_ids() -> set[int]:
    """Parse TG_ADMIN_ID from env into a set of ints."""
    raw = os.environ.get("TG_ADMIN_ID", "")
    out: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            pass
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="Do not send alerts or save snapshot; print counts only")
    p.add_argument("--force", action="store_true",
                   help="Send alert even when diff is empty")
    p.add_argument("--verbose", action="store_true",
                   help="Enable DEBUG logging")
    args = p.parse_args()

    # Logging to stderr
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")

    # 1. Load env
    load_env()

    # Check TG_ADMIN_ID after env load
    admin_ids = _get_admin_ids()
    if not admin_ids:
        logger.error("TG_ADMIN_ID is empty after env load")
        return 2

    # 2. Clear proxy env before fetch
    clear_proxy_env()

    # 3. Fetch bonuses
    try:
        raw = fetch_bonuses()
    except Exception as e:
        logger.error("fetch_bonuses failed: %s", e)
        return 1

    # 4. Normalize
    current = [normalize(r) for r in raw]

    # 5. Load previous snapshot
    prev = load_snapshot()

    # 6. Diff
    diff = snapshot_diff(current, prev)

    n_new = len(diff.get("new", []))
    n_gone = len(diff.get("gone", []))
    n_changed = len(diff.get("changed", []))
    has_changes = n_new > 0 or n_gone > 0 or n_changed > 0

    # 7. Save snapshot (before sending)
    if not args.dry_run:
        save_snapshot(current)
        logger.info("snapshot saved (%d bonuses)", len(current))
    else:
        logger.info("dry-run: snapshot NOT saved (%d bonuses)", len(current))

    # 8. Alert
    if has_changes or args.force:
        text = format_alert(diff)
        if args.dry_run:
            logger.info("dry-run: would send alert to %d admins", len(admin_ids))
            print(f"new={n_new} gone={n_gone} changed={n_changed}")
        else:
            for chat_id in admin_ids:
                try:
                    send_message(chat_id, text, parse_mode="HTML")
                    logger.info("alert sent to %s", chat_id)
                except Exception as e:
                    logger.error("send_message failed for %s: %s", chat_id, e)
            print(f"new={n_new} gone={n_gone} changed={n_changed}")
    else:
        logger.info("no changes")
        print(f"new={n_new} gone={n_gone} changed={n_changed}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
