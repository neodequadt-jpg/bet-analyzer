# EVR-0005: Landscape RU BK APIs

Status: RESEARCH DONE
Date: 2026-09-14

## Object
Исследование публичных JSON API легальных РФ БК для value-detection на РПЛ.

## Result

### Fonbet — WORKS ✅
- Endpoint: `https://line-lb54-w.bk6bba-resources.com/ma/events/listBase`
- Формат: gzip JSON
- Odds coding: 921=П1, 922=X, 923=П2, 930=ТБ2.5, 931=ТМ2.5
- РПЛ sportId: 11935
- Результат: 8 матчей текущего тура с 1X2 odds
- Реализовано: `bookmakers/fonbet_api.py`

### Marathonbet — PARTIAL
- Endpoint: `https://lu.marathonbet.ru/su/liveupdate/homepage/` (JSONP)
- Возвращает: menu events (без odds)
- Для odds нужен отдельный detail-endpoint по eventUid
- Playwright работает, но нужен второй шаг (event detail)

### Winline — BLOCKED
- Angular SPA, endpoints `/api/v2/*` требуют cookies/session
- JSON REST отдаёт только static-data, promo, loyalty
- Events — через WebSocket (не отдаёт REST)

### BetBoom — BLOCKED
- Использует SportHub (sportbook.sporthub.bet) с WS + protobuf
- REST `site_api/v1/*` — все 404
- Требует reverse WS-protobuf — большой инженерный шаг

### Flashscore — OFF-SHORE ONLY
- Не содержит легальные РФ БК (см. EVR-0004)
- Скандинавское geo: Lilibet, Betsmith
- Bet365/1xBet упоминаются, но не в div.odds (баннеры)

## Conclusion

На текущий момент **только Fonbet** даёт чистый публичный JSON API для РПЛ.

Для multi-BK консенсуса нужны:
- Marathonbet: событие detail endpoint (2-й шаг, реально)
- либо ручной merge (manual source + Fonbet)
- либо Flashscore offshore как sharp reference (Pinnacle/Bet365 как consensus) + Fonbet как value target

## Architecture decision

Гибридная модель:
- **Sharp reference (true prob):** Flashscore (Pinnacle/Bet365) — offshore БК, доступны через прокси
- **Target (value target):** Fonbet — RU BK, реальные ставки
- Pipeline: Flashscore → consensus → сравнение с Fonbet → value bets

Требуется: implement sharp fetcher (Flashscore odds для конкретного матча)
