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

## Telegram Bot

`tg_bot.py` — интерактивный бот с командами:

| Команда | Описание |
|---|---|
| `/value` | Pipeline по Fonbet+manual, показать value-bets |
| `/signals` | Топ-5 value-bets с Kelly-ставками |
| `/express` | AI-экспресс из value-bets |
| `/report` | AI-отчёт по топ-ставке |
| `/live <sport> <hours>` | Матчи Fonbet (tt/football/hockey/tennis/esports) |
| **`/mma`** | **Расписание единоборств с кэфами (UFC / ACA / Fight Nights)** |
| `/status` | Статус системы |
| `/lang` | RU/EN |
| `/reset`, `/prompt` | AI-чат |

Запуск: `./bot.sh` (использует `BOT_TOKEN` из `.env.bot` + `opera-proxy` на 18080).

### MMA submenu

`/mma` открывает меню турниров (`ACA 208`, `UFC 333`, `UFC Fight Night 290`).
Клик по турниру — список боёв с коэффициентами П1/П2 из Fonbet.
Источник: `bookmakers/fonbet_mma.py` (sport root `37145 Единоборства`).
Исключаются симуляторы (H2H LIGA) и грэпплинг.

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
- bookmakers/fonbet_mma.py - MMA schedule + odds (UFC/ACA/Fight Nights)
- bookmakers/flashscore_parser.py - Flashscore fixtures parser
- bookmakers/flashscore_match_fetch.py - Playwright match page fetcher
- bookmakers/flashscore_injuries.py - missing-players parser + cache
- bookmakers/flashscore_mid_map.py - (home, away) -> Flashscore mid
- scripts/fetch_injuries.py - CLI sync for injuries cache
- ai/client.py - OmniRoute client
- ai/analyst.py - AI value-bet analyst (with injuries enrichment)
- tg_bot.py - Telegram bot
- runner.py - entry point (mock / manual / fonbet / hybrid / hybrid_ai / express_ai)

## Output

- data/runs/YYYY-MM-DD-HH-MM-SS.json - run history
- data/cache/ - runtime cache (fonbet, flashscore)
- data/injuries/ - injuries evidence (mid -> missing players, non-empty only)
- data/mid_map.json - Flashscore mid mapping (home, away) -> mid
- validation/EVR-*.md - Engineering Validation Reports

## Testing

    .venv/bin/pytest tests/ -q

Tests use a pinned Fonbet snapshot (`tests/fixtures/fonbet_listBase.json`)
via an autouse fixture in `tests/conftest.py`, so they are deterministic
and offline-safe (EVR-0010).

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
- EVR-0007: Flashscore missing players timing window (~24h around kickoff)
- EVR-0008: Injuries data-loss guard + evidence-only persistence
- EVR-0009: Injuries sync validation deferred (RPL gap 04.10-09.10)
- EVR-0010: Flaky Fonbet tests fixed via snapshot fixture (tests/fixtures/)

## Legal

Research only. Publishing predictions and accepting bets is a regulated activity (FNS license + ЦУПИС).
