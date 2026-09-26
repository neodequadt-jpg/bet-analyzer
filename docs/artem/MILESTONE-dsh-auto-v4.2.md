# Milestone: dsh-auto v4.2

**Date:** 2026-09-26
**Status:** Validated (EVR-based, both PASS and FAIL paths)

## What
`~/.dsh/bin/dsh-auto.sh` v4.2 — ARTEM-strict wrapper (250 lines).

## Phases
1. Pre-flight: runtime whitelist + baseline tests + OmniRoute alive
2. Spec contract: 5 mandatory sections
3. Execute: model rotation (Groq 120b primary), exponential backoff
4. Verify: tests pass + commit created
4.5 Spec verification: extract `## Verification` → execute → rollback on fail
5. Evidence: EVR + run.json + verifications.json on any outcome

## Exit codes
0 PASS / 1 PRE_FLIGHT / 2 SPEC_INVALID / 3 EXEC_FAIL / 4 TESTS_FAIL / 5 NO_COMMIT / 6 VERIFY_FAIL

## Evidence
### FAIL path
- Run: `run-20260926-113348`
- verifications: 3 (2 ok, 1 fail `false`)
- rollback restored HEAD, run.json `status=FAIL reason=exit_6`

### PASS path
- Run: `run-20260926-114407`
- verifications: 2 (all ok)
- commit preserved `de7bb0c`, run.json `status=PASS model=groq/openai/gpt-oss-120b`

## ARTEM principles validated
- Repository Reality — Phase 1 whitelist
- Specification First — Phase 2 contract
- One Goal / One Commit — exit 5 catches no-commit
- Evidence Before Authority — Phase 4.5 не доверяет DSH
- Reproducibility — EVR per run
