# EVR-0010: Flaky Fonbet Tests Fixed via Snapshot Fixture

Status: CLOSED
Date: 2026-10-04

## Object
Flaky failures in tests:
- tests/test_tg_chat.py::TestPipelineNoFutureFilter::test_pipeline_returns_matches
- tests/test_tg_chat.py::TestSignals::test_signals_no_duplicate_events

## Observed
Intermittent failures (~1 in N full runs):
  assertGreater(0, 0) - build_pipeline returned 0 matches

Isolated run: PASS
Full run (134 tests): occasionally FAIL
Re-run immediately after: PASS

## Root cause
build_pipeline() calls fetch_rpl_odds(force=True) on every invocation.
Full test run triggers many sequential Fonbet requests.
Under load, Fonbet returns 429 / timeout -> build_pipeline returns 0 matches
-> assertions fail.

This is not a code defect. The tests depend on a live external service.

## Fix
tests/conftest.py: session-scoped autouse fixture `_mock_fonbet`
  - reads snapshot tests/fixtures/fonbet_listBase.json
  - replaces bookmakers.fonbet_api.fetch_list_base and
    bookmakers.fonbet_extended.fetch_list_base with a stub
  - restores original on teardown

Snapshot: copy of data/cache/fonbet/listBase.json
  - events: 10793, customFactors: 10618, sports: 806

## Verified
Two full runs in a row: 134 passed, ~50s each.
Previous behavior: 70-120s with intermittent failures.

## Trade-offs
- Snapshot pinned to date of creation; Fonbet data drifts.
  Tests now measure code behavior, not live data.
- Snapshot 11 MB in git. Consider minifying later (drop metadata).

## Related
- EVR-0002: API-Football Free tier (Fonbet was chosen as primary odds source)
