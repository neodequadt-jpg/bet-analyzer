# EVR-0003: SofaScore API блокирует запросы

Status: CLOSED
Date: 2026-09-14

## Object
SofaScore API как источник коэффициентов.

## Environment
Direct request, no proxy, custom User-Agent.

## Expected
`/api/v1/sport/football/scheduled-events/<date>` возвращает JSON с events.

## Observed
HTTP 403 Forbidden
body: {"error": {"code": 403, "reason": "Forbidden" }}

## Conclusion
SofaScore блокирует request по fingerprint/геолокации.
Обход требует Cloudflare-bypass или residential proxy — выходит
за рамки текущей задачи.

## Decision
Переключаемся на manual source (ввод коэффициентов вручную)
для верификации конвейера на реальных данных.
После успешной верификации — вернуться к вопросу source
(Flashscore + Playwright как основной кандидат).
