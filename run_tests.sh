#!/usr/bin/env bash
# Run all BET-ANALYZER tests.
# Prefers AVITO venv pytest (has pytest 9.x); falls back to system python3 + unittest.
set -euo pipefail
cd "$(dirname "$0")"

PYTEST_PY=""
for p in "$HOME/AVITO-PRINTER-V2/.venv/bin/python" python3; do
    if command -v "$p" >/dev/null 2>&1 && "$p" -m pytest --version >/dev/null 2>&1; then
        PYTEST_PY="$p"
        break
    fi
done

if [ -z "$PYTEST_PY" ]; then
    echo "[run_tests] pytest not found; running stdlib unittest only"
    python3 tests/test_tg_chat.py
    exit 0
fi

echo "[run_tests] using $PYTEST_PY"
PYTHONPATH=. "$PYTEST_PY" -m pytest tests/ -v
