# EVR-0002: API-Football Free tier не даёт odds

Status: CLOSED
Date: 2026-09-14

## Object
API-Football Free tier как источник коэффициентов.

## Environment
API key Free, season 2023, league 235 (RPL), 39 (EPL),
140 (La Liga), 135 (Serie A), 78 (Bundesliga).

## Expected
`/odds?fixture=<id>` возвращает bookmakers + коэффициенты.

## Observed
- `/odds?fixture=1042016` → results: 0, errors: []
- `/leagues?id=235` season 2023 → coverage.odds = false
- Все топ-лиги: coverage.odds = true только для season 2026
- Season 2026 → Free plan "do not have access to this season"

## Conclusion
Free tier API-Football:
- Даёт fixtures для 2022–2024
- НЕ даёт odds ни для одного доступного сезона
- Даёт odds для 2026, но 2026 недоступен на Free

Парадокс непреодолим в рамках Free tier.

## Decision
Переключаемся на альтернативный источник:
- SofaScore (unofficial API, JSON) — кандидат #1
- Flashscore + Playwright — кандидат #2
