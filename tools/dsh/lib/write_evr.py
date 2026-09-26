"""Write EVR.md + run.json (PASS or FAIL). Idempotent.

Usage:
  python3 write_evr.py <run_dir> <status> <reason>
    status = PASS | FAIL
    reason = short reason string
"""
import json
import sys
from datetime import datetime
from pathlib import Path


def write(run_dir: str, status: str, reason: str, ctx: dict = None):
    d = Path(run_dir)
    d.mkdir(parents=True, exist_ok=True)
    ctx = ctx or {}
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# EVR-{d.name}",
        "",
        f"- Status: **{status}**",
        f"- Timestamp: {ts}",
        f"- Reason: {reason}",
        "",
        "## Context",
    ]
    for k, v in ctx.items():
        lines.append(f"- {k}: {v}")

    (d / "EVR.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    payload = {
        "run_id": d.name,
        "status": status,
        "reason": reason,
        "timestamp": ts,
        **ctx,
    }
    (d / "run.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    run_dir = sys.argv[1]
    status = sys.argv[2]
    reason = sys.argv[3]
    write(run_dir, status, reason)
