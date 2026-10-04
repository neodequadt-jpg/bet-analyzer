# EVR-0009: Injuries Sync Window Reality Check

Status: OPEN
Date: 2026-10-04
Review date: 2026-10-08 (before RPL match 09.10)

## Object
End-to-end validation of `scripts/fetch_injuries.py --window-hours N`.

## Context
EVR-0007: Flashscore missing-players block appears ~24h around kickoff.
EVR-0008: data-loss guard + evidence-only persistence implemented.

## Expected
With `--window-hours 36`, injuries sync should fetch and cache
injuries for RPL matches within [now-24h, now+36h].

## Observed (2026-10-04 ~17:00 MSK)
- Fresh fixtures fetch: 112 matches, OK
- mid_map rebuilt: 112 records
- Nearest RPL kickoff: 2026-10-09 19:30 MSK
- `in_window = 0` — no matches in `[-24h, +36h]`

## Conclusion
The `--window-hours` filter works correctly, but the current date
sits in a gap between RPL rounds. Injuries sync cannot be validated
end-to-end today.

## Decision
Postpone end-to-end validation until ~12-24h before the next RPL match
(2026-10-09 19:30 MSK).

## Deferred work
- CLI `--window-hours N` → actually uses kickoff_ts filter (pending)
- Cron / runner hook for auto-sync (pending)

## No further engineering until review date
Reason: feature depends on data that does not exist at this time.
Continuing would build blindly.

## Review checklist (2026-10-08)
1. Run `python scripts/fetch_injuries.py --window-hours 36`
2. Confirm injuries cached for match(es) on 09.10-10.10
3. Verify runner passes injuries into AI prompt
4. Compare AI report with and without injuries
5. Close EVR-0009 as PASS or FAIL

## Related
- EVR-0007: timing window
- EVR-0008: data-loss guard
