"""Extract shell commands from a spec's ## Verification block.

Supports two formats:
  1. ```bash code fence``` — берём все непустые строки как отдельные команды
  2. Numbered list "1. cmd → expected" — обрезаем хвост →, склеиваем
     multi-line items (пока не встретим следующий "N.")

Output: JSON list of {"cmd": str} on stdout.
"""
import json
import re
import sys
from pathlib import Path


def _split_numbered(body: str):
    """Split into numbered items, keeping multi-line continuity."""
    # Ищем "N. " в начале строки
    pattern = re.compile(r"^\s*\d+\.\s+", re.MULTILINE)
    matches = list(pattern.finditer(body))
    if not matches:
        return []
    items = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        items.append(body[start:end])
    return items


def _strip_trailing_comment(first_line: str) -> str:
    """Remove ' → ...' or ' — ...' expected-output suffix."""
    # Split at first "→" or "—" with optional surrounding whitespace
    parts = re.split(r"\s*[→—]\s*", first_line, maxsplit=1)
    return parts[0].strip()


def extract(spec_path: str):
    text = Path(spec_path).read_text(encoding="utf-8")
    m = re.search(r"^## Verification\s*\n(.*?)(?=^## |\Z)",
                  text, re.MULTILINE | re.DOTALL)
    if not m:
        return []
    body = m.group(1)

    # Format 1: bash code fence
    fence = re.search(r"```(?:bash|sh)?\s*\n(.*?)```", body, re.DOTALL)
    if fence:
        cmds = []
        for line in fence.group(1).splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                cmds.append({"cmd": line})
        return cmds

    # Format 2: numbered list
    items = _split_numbered(body)
    cmds = []
    for item in items:
        lines = item.splitlines()
        if not lines:
            continue
        first = _strip_trailing_comment(lines[0])
        cmd_lines = [first]
        # Multi-line continuation until empty line or bullet
        for cont in lines[1:]:
            s = cont.rstrip()
            if not s.strip():
                continue
            # Bullet = конец команды
            if s.lstrip().startswith(("-", "•", "*")):
                break
            cmd_lines.append(s.strip())
        cmd = "\n".join(cmd_lines).strip()
        # Strip outer backticks
        if cmd.startswith("`") and cmd.endswith("`"):
            cmd = cmd[1:-1].strip()
        if cmd:
            cmds.append({"cmd": cmd})
    return cmds


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps([]))
        sys.exit(0)
    print(json.dumps(extract(sys.argv[1]), ensure_ascii=False, indent=2))
