# BET-ANALYZER

Value-bet detection for legal Russian bookmakers (ЦУПИС).

## Pipeline

sources (multi-BK) -> consensus (leave-one-out) -> scoring (EV, Kelly) -> value_bets

## Sources

| Mode | File | Data |
|---|---|---|
| mock | bookmakers/parser.py | 3 static events |
| manual | bookmakers/manual_source.py | JSON in data/manual/ |
| fonbet | bookmakers/fonbet_api.py | real RPL odds from Fonbet public API |
| hybrid | bookmakers/normalizer.py | merge fonbet + manual (dedup by BK) |

## Quick start

    python3 runner.py mock
    python3 runner.py fonbet
    python3 runner.py hybrid

## Setup

    export OMNI_KEY='oma_...'
    ~/AVITO-PRINTER-V2/.venv/bin/python runner.py hybrid

## Components

- bookmakers/registry.py - 11 legal RU BK (ЦУПИС)
- bookmakers/fonbet_api.py - Fonbet client (gzip JSON, factors 921/922/923)
- bookmakers/normalizer.py - multi-source merge + BK dedup
- market/consensus.py - leave-one-out consensus + margin removal
- scoring/ev.py - EV, Kelly, deal_score, per-sport cap
- ai/client.py - OmniRoute client
- runner.py - entry point (mock / manual / fonbet / hybrid)

## Output

- data/runs/YYYY-MM-DD-HH-MM-SS.json - run history
- data/cache/ - cache (fonbet, flashscore)
- validation/EVR-*.md - Engineering Validation Reports

## Known limitations

- Fonbet gives 1 BK per match; needs 2nd source for consensus
- Marathonbet API partial (top-markets works, list-events hidden by WS)
- Winline/BetBoom - SPA/WS, no REST events
- Flashscore - offshore only (no legal RU BK)

## Architecture decisions

- EVR-0001: KHL 2-way margin anomaly -> per-sport EV cap
- EVR-0002: API-Football Free tier without odds
- EVR-0003: SofaScore API 403
- EVR-0004: Flashscore does not carry RU BK
- EVR-0005: RU BK API landscape - only Fonbet
- EVR-0006: Marathonbet API partial

## Legal

Research only. Publishing predictions and accepting bets is a regulated activity (FNS license + ЦУПИС).
