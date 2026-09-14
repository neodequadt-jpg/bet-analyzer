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

---

## Update 2026-09-14: гео-зависимость

Прокси 18080 выходит в Скандинавии (норвежские bonus-тексты в HTML).
Flashscore показывает скандинавские offshore БК: Lilibet (907), Betsmith (1259).

Bet365 упоминается 93 раза, 1xBet — 117 раз, но это баннеры/тексты, 
а не реальные odds-котировки. В DOM — только 2 div.odds.

Следствие: Flashscore показывает только те БК, у которых есть партнёрка в текущем гео.
Легальные RU БК (ЦУПИС) не появляются ни при каком гео — они не подключены к odds-feed Flashscore.

## Финальный вывод

Flashscore = sharp reference (offshore/зарубежные БК) для EPL/La Liga.
Для РПЛ / RU БК нужен отдельный источник:
- публичные API легальных БК (Winline, Fonbet, Liga Stavok) — гипотеза,
- или ручной ввод (manual source, уже работает),
- или парсинг ЦУПИС-сайтов.
