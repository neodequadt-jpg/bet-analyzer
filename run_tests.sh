#!/usr/bin/env bash
# Run BET-ANALYZER tests using project .venv
set -euo pipefail
cd "$(dirname "$0")"

VENV_PY=".venv/bin/python"

if [ ! -x "$VENV_PY" ] || ! "$VENV_PY" -m pytest --version >/dev/null 2>&1; then
    echo "[run_tests] $VENV_PY has no pytest; falling back to AVITO venv"
    VENV_PY="$HOME/AVITO-PRINTER-V2/.venv/bin/python"
fi

if [ ! -x "$VENV_PY" ]; then
    echo "[run_tests] no python with pytest; using unittest"
    python3 tests/test_tg_chat.py
    exit 0
fi

echo "[run_tests] using $VENV_PY"
PYTHONPATH=. "$VENV_PY" -m pytest tests/ -v
