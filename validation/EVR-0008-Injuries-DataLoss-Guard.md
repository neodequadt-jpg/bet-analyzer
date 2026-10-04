# EVR-0008: Flashscore Injuries Data-Loss Guard

Status: CLOSED
Date: 2026-10-04

## Object
`scripts/fetch_injuries.py` — sync runner for Flashscore missing players.

## Context
EVR-0007 showed that Flashscore exposes the "Missing Players" block only
inside a narrow timing window around kickoff. Earlier observation:
one match appeared in the block during match-day, then disappeared from
the live DOM a few hours later.

Verification today:

| File | len | testid present |
|---|---|---|
| match_zenit_baltika.html (match-day) | 1043005 | YES |
| match_bZoWLHvJ_fresh.html (refetched ~6h later) | 1050509 | NO |

Same mid, same session, same proxy. HTML size grew, "Missing Players"
still present as a JSON translation key, but the DOM block is gone.

## Problem
Naive `save_injuries()` unconditionally overwrites the cache.
Running `--force` outside the timing window would silently erase
previously captured evidence (4 players -> 0).

## Decision
Introduce a data-loss guard:

    if new_total == 0 and existing_total > 0 and not force_overwrite:
        preserve existing cache

Override flag `--force-overwrite` exists for explicit intent.

## Verified behaviour

| Invocation | Result |
|---|---|
| `--mid bZoWLHvJ --force` | parse=0, cache=4 - preserved |
| `--mid bZoWLHvJ --force --force-overwrite` | network timeout, cache unchanged |

Restored original 4-player cache from git after test.

## Semantics
Empty parse means "data not available right now" (EVR-0007),
not "no players are missing".
Cache is evidence; guards prevent accidental evidence destruction.

## Artifacts
- `scripts/fetch_injuries.py` (data-loss guard)
- `data/injuries/bZoWLHvJ.json` (preserved evidence)

## Related
- EVR-0007: Flashscore Missing Players Timing Window
