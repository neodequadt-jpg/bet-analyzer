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


def load_verifications_summary(run_dir: str) -> dict | None:
    path = Path(run_dir) / "verifications.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    total = len(data)
    ok = sum(1 for item in data if item.get("ok", False))
    failed = total - ok
    failed_cmds = [item.get("cmd") for item in data if not item.get("ok", False)]
    
    return {
        "total": total,
        "ok": ok,
        "failed": failed,
        "failed_cmds": failed_cmds,
    }


def write(run_dir: str, status: str, reason: str, ctx: dict = None):
    d = Path(run_dir)
    d.mkdir(parents=True, exist_ok=True)
    ctx = ctx or {}
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    summary = load_verifications_summary(run_dir)

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
    
    if summary:
        lines.extend([
            "",
            "## Verifications",
            f"- Total: {summary['total']}",
            f"- OK: {summary['ok']}",
            f"- Failed: {summary['failed']}",
            f"- Failed Commands: {', '.join(summary['failed_cmds'])}",
        ])

    (d / "EVR.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    payload = {
        "run_id": d.name,
        "status": status,
        "reason": reason,
        "timestamp": ts,
        **ctx,
    }
    if summary:
        payload["verifications_summary"] = summary
        
    (d / "run.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    run_dir = sys.argv[1]
    status = sys.argv[2]
    reason = sys.argv[3]
    write(run_dir, status, reason)
