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
# Telegram via WireGuard wg0 (split-tunnel)
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
export no_proxy=127.0.0.1,localhost
export NO_PROXY=127.0.0.1,localhost
export TG_API_BASE=https://api.telegram.org

# Validate BOT_TOKEN
if [[ -z "${BOT_TOKEN:-}" ]]; then
  echo "ERROR: BOT_TOKEN not set. Create .env.bot with BOT_TOKEN=... or export BOT_TOKEN." >&2
  exit 1
fi

# Detect python
if [[ -n "${PYTHON:-}" ]]; then
  :
elif [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
  PYTHON="$SCRIPT_DIR/.venv/bin/python"
else
  PYTHON=python3
fi

echo "[bot.sh] starting telegram bot (python=$PYTHON)"
export PYTHONUNBUFFERED=1
exec "$PYTHON" tg_bot.py
