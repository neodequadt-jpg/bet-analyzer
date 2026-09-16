# DEMO-0006: Express fallback + robust AI parsing

Status: VERIFIED
Date: 2026-09-16

## Bug 1: single-match value-bets → no fallback
Observed: /express returns "insufficient value-bets" even when 2 value-bets
exist (both from same match Спартак-Факел). AI correctly refuses due to
correlation ban, but fallback never triggered because len(candidates) >= 2.

Fix: count unique event_ids, not raw candidate count.
  value_event_ids = {vb["event_id"] for vb in value_candidates}
  if len(value_candidates) >= 2 and len(value_event_ids) >= 2: mode = "value"
  elif fallback:                                              mode = "consensus"

## Bug 2: None content crash
Observed: "/express: 'NoneType' object has no attribute 'strip'"
Provider flake returned message.content = None.

Fix: robust parsing — None → reasoning_content fallback → dict passthrough
→ JSON parse → regex extract → graceful reason message.

## Verified
- py_compile: exit 0
- pytest: 17 passed (14 + 3 new: fallback, None, non-JSON)
- tg_bot.py unchanged (mtime 18:24:39)

## Files
- ai/express_builder.py (+32/-4)
- tests/test_tg_resilience.py (+89)
