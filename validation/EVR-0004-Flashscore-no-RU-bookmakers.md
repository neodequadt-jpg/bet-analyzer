# EVR-0004: Flashscore не агрегирует легальные RU БК

Status: OPEN
Date: 2026-09-14

## Object
Flashscore как источник коэффициентов для value-detection на РПЛ.

## Environment
Playwright + opera-proxy (127.0.0.1:18080).
URL: /match/football/.../#/odds-comparison/1x2/full-time

## Expected
Список 5-10 БК, включая легальные РФ (Winline, Fonbet, Liga Stavok, BetBoom, Pari, Betcity, Leon, Olimp, Baltbet).

## Observed
- div.odds на странице: 2 (Lilibet, Betsmith)
- После клика "Show more": 0 (страница перерендерилась)
- В полном HTML: ни одного вхождения Winline/Fonbet/Liga Stavok/BetBoom/Pari/Betcity/Leon/Olimp/Baltbet
- Melbet — 12 упоминаний (offshore, не ЦУПИС-БК)

## Conclusion
Flashscore агрегирует offshore/зарубежные БК. Легальные РФ БК через ЦУПИС там отсутствуют.

Следствие: Flashscore не может быть источником odds для RU BK — он может быть только sharp reference (Pinnacle/Bet365/Betfair) для оценки true probability.

## Decision (proposed)
Гибридная архитектура:
- **Sharp reference (true prob)**: Flashscore → Pinnacle / Bet365
- **Target odds (value target)**: RU BK source (manual на текущем этапе, или отдельный парсер ЦУПИС-БК)

Конвейер: sharp reference → consensus → сравнение с RU BK odds → value bets.
