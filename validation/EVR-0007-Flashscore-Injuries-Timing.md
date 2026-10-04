# EVR-0007: Flashscore Missing Players Timing Window

Status: CLOSED
Date: 2026-10-04

## Object
Flashscore "Missing Players" block as a source of injury data for BET-ANALYZER.

## Environment
- Playwright chromium_headless_shell-1234 via AVITO .venv
- Proxy http://127.0.0.1:18080
- User-Agent: Chrome 130 Linux
- Locale: ru-RU

## Expected
Block `[data-testid^="wcl-lineupsParticipantGeneral-"]` присутствует на любой
странице `/match/{mid}/`.

## Observed

| Match | Date | Offset | Block present |
|---|---|---|---|
| Baltika vs Zenit | 16.09 | 0 (match day) | YES |
| FK Rostov vs Akron | 09.10 | -6 days | NO |
| Orenburg vs Dynamo Mkh | 10.10 | -6 days | NO |
| Spartak vs FK Rostov | 13.09 | +21 days | NO |

Sample `match_zenit_baltika.html` — 2 missing players home, 2 away.

## Conclusion
Flashscore exposes missing-players block only in a narrow window around
match day (approx -24h .. +1h). It is NOT a general-purpose injuries source
for future matches or historical review.

## Decision
`parse_missing_players()` остаётся как **best-effort enricher**: применяется
только если блок присутствует. Для матчей вне окна — injuries пусты.

Параллельно рассматривается API-Football `/injuries` (Free tier) как
основной источник для будущих матчей.

## Artifacts
- `bookmakers/flashscore_injuries.py::parse_missing_players`
- `tests/test_flashscore_injuries.py`
