"""Shared pytest fixtures: make the project root importable (tg_bot lives there).

Also provides an autouse session-scoped fixture that replaces live
Fonbet calls with a local snapshot, so tests are deterministic.

Rationale (EVR-0010):
  build_pipeline() calls fetch_rpl_odds(force=True) on every invocation.
  Running many tests in one session triggered Fonbet rate limits,
  producing flaky failures in TestPipelineNoFutureFilter and TestSignals.
  Pinning a snapshot makes tests deterministic and offline-safe.
"""
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


FONBET_SNAPSHOT = Path(__file__).resolve().parent / "fixtures" / "fonbet_listBase.json"


@pytest.fixture(scope="session", autouse=True)
def _mock_fonbet():
    """Patch bookmakers.fonbet_api.fetch_list_base to read a snapshot.

    Falls back gracefully if the snapshot is missing (skip patch).
    """
    if not FONBET_SNAPSHOT.exists():
        yield
        return

    data = json.loads(FONBET_SNAPSHOT.read_text(encoding="utf-8"))

    import bookmakers.fonbet_api as fa

    original = fa.fetch_list_base

    def _mock(force: bool = False) -> dict:
        return data

    fa.fetch_list_base = _mock
    # Any module that already imported the symbol also needs patching
    try:
        import bookmakers.fonbet_extended as fx
        fx.fetch_list_base = _mock
    except Exception:
        pass

    yield

    fa.fetch_list_base = original
