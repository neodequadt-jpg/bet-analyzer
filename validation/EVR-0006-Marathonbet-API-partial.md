# EVR-0006: Marathonbet new API — partial discovery

Status: PARTIAL / PAUSED
Date: 2026-09-14

## Object
Marathonbet (ЦУПИС) как 2-й источник odds для консенсуса.

## Discovered
- Base: `https://new.marathonbet.ru/eag/event-line/api/v1/`
- Required headers: `X-Pan-Source: web`, `Accept-Language: ru-RU,ru;q=0.9`
- Работает: `GET /top-markets/{treeId}` → возвращает типы рынков
- НЕ найдены: endpoints для events-list и odds (все 404)
- Playwright XHR не ловит event-line запросы на `/su/betting/football` — вероятно, линия грузится через WS или требует интерактива

## Conclusion
Marathonbet API рабочий, но events endpoint скрыт. Для 2-го БК требуется:
- либо WS-перехват (`page.on("websocket")`)
- либо headful-клик по линии для триггера XHR

Это отдельная задача, не блокер.

## Decision
Переключаемся на **гибридную архитектуру**:
- **Fonbet (RU, target)**: реальные odds для value-detection
- **Manual (multi-BK)**: оператор вводит 2-4 БК вручную (manual source)
- **Flashscore (sharp)**: Pinnacle/Bet365 как true probability reference (если найдём в geo)
- Для РПЛ консенсус из Fonbet+manual — приемлемо
