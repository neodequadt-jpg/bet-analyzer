#!/usr/bin/env bash
set -euo pipefail

# Resolve script directory and cd into it
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Load .env.bot if present (KEY=VALUE lines, ignore comments and blanks).
# An env var already set (even empty) takes precedence over .env.bot,
# so `BOT_TOKEN="" ./bot.sh` reliably triggers the error below.
if [[ -f .env.bot ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    # skip comments and empty lines
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "${line// /}" ]] && continue
    key="${line%%=*}"
    [[ -z "$key" ]] && continue
    [[ -v "$key" ]] && continue
    export "$line"
  done < .env.bot
fi

# Proxy settings
export http_proxy=http://127.0.0.1:18080
export https_proxy=http://127.0.0.1:18080
export no_proxy=127.0.0.1,localhost
export NO_PROXY=127.0.0.1,localhost

# Validate BOT_TOKEN
if [[ -z "${BOT_TOKEN:-}" ]]; then
  echo "ERROR: BOT_TOKEN not set. Create .env.bot with BOT_TOKEN=... or export BOT_TOKEN." >&2
  exit 1
fi

# Detect python
if [[ -n "${PYTHON:-}" ]]; then
  :
elif [[ -x /home/jail/AVITO-PRINTER-V2/.venv/bin/python ]]; then
  PYTHON=/home/jail/AVITO-PRINTER-V2/.venv/bin/python
else
  PYTHON=python3
fi

echo "[bot.sh] starting telegram bot (python=$PYTHON)"
exec "$PYTHON" tg_bot.py
