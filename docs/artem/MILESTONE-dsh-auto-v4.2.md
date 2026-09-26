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

---

## Update 2: Dogfooding + EVR summary (2026-09-26)

### Self-modification loop closed
- Commit `e3a9e5e` — DSH через dsh-auto правил **свой же** `tools/dsh/lib/write_evr.py`
- Phase 4.5 выполнилась через **новую версию** write_evr.py (dogfooding)
- Git rollback защищает infra-lib после миграции в repo

### EVR summary enhancement
- `write_evr.py` v2 читает `verifications.json` и включает
  `verifications_summary: {total, ok, failed, failed_cmds}` в run.json
- EVR.md получил секцию `## Verifications`
- Validated на FAIL-path run-20260926-123929 (exit 6, rollback)

### Infra in git
- `tools/dsh/` — vendored: dsh-auto.sh, extract_verifications.py, write_evr.py, phase45.sh
- Symlinks из `~/.dsh/` → `~/BET-ANALYZER/tools/dsh/`
- Rollback через `git reset --hard` восстанавливает весь toolchain

### Evidence table
| Run | Path | Model | Result |
|---|---|---|---|
| run-20260926-113348 | FAIL (exit 6) | groq/openai/gpt-oss-120b | verif 3 (2 ok, 1 fail) |
| run-20260926-114407 | PASS | groq/openai/gpt-oss-120b | verif 2 (all ok) |
| run-20260926-115425 | PASS (live task G-AI-0001) | groq/openai/gpt-oss-120b | verif 3 (all ok) |
| run-20260926-122908 | PASS (dogfooding) | groq/openai/gpt-oss-120b | verif 3 (all ok) |
| run-20260926-123929 | FAIL (exit 6, EVR summary) | groq/openai/gpt-oss-120b | verif 2 (1 ok, 1 fail) |
