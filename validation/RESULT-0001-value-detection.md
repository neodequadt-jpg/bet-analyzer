# RESULT-0001: Value-detection на реальных данных РПЛ

Status: VERIFIED
Date: 2026-09-14

## Setup
- Fonbet API: 8 матчей РПЛ (real odds)
- Manual: 4 матча × 6 БК (Фонбет, Винлайн, Лига Ставок, PARI, BetBoom, Марафон)
- Consensus: leave-one-out + margin removal
- Порог: MIN_EV=0.03, MIN_CONFIDENCE=0.5, MIN_TRUST=0.7

## Result (real data)

| Матч | Best EV | BK | Passes threshold |
|---|---|---|---|
| Спартак - Факел (away) | +2.22% | Лига Ставок | НЕТ (порог 3%) |
| Локомотив - Крылья | -2.60% | Лига Ставок | НЕТ |
| Балтика - Зенит | -1.25% | Марафон | НЕТ |
| Оренбург - Краснодар | -1.94% | Марафон | НЕТ |

**Value-bets = 0** после 6-BK consensus.

## Lilibet (Flashscore offshore) — проверка как 2-й real-source
Для Балтика-Зенит:
- home 4.40 (fair 4.76, EV -7.6%)
- draw 3.40 (fair 3.95, EV -14.3%)
- away 1.80 (fair 1.87, EV -3.5%)

Все три отрицательные. Flashscore offshore НЕ даёт value.

## Conclusion
На текущем туре РПЛ рынок эффективен: 6 БК сходятся в оценках, spread 2-3%.
Value не появляется. Это корректный результат value-detection системы.

Система готова находить value когда:
- Рынок имеет реальный spread > 5%
- Появляется новость, которую БК ещё не отыграли
- Находится неточная линия у одного БК

## Verified pipeline (DEMO-0001, DEMO-0002)
- Fonbet API → consensus → EV → AI (analyst.py) — работает
- DSH → OmniRoute → express_builder.py — работает
- express_ai mode в runner — работает (корректно возвращает insufficient value-bets)

## Available modes
mock / manual / fonbet / hybrid / hybrid_ai / express_ai

## Files
- ai/analyst.py, ai/express_builder.py, ai/express_prompt.py
- bookmakers/fonbet_api.py
- market/consensus.py, scoring/ev.py, bookmakers/normalizer.py
- runner.py (6 modes)
