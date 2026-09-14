# EVR-0001: KHL 2-way margin anomaly

Status: RESOLVED
Date: 2026-09-14

## Object
Value detector on 2-way markets (KHL).

## Expected
Value detection works on both 3-way and 2-way markets.

## Observed
2-way markets КХЛ дают EV 27-52% — аномально высоко
из-за высокой маржи и leave-one-out consensus из тех же БК.

## Decision
Добавлен per-sport EV cap:
- football:  25%
- hockey:    15%
- basketball: 15%
- tennis:    15%

Value с EV > cap отбрасывается как false positive.

## Result
После фикса:
- RPL: 2 value-bets (EV 10-14%) — реалистично
- KHL: 0 value-bets — 2-way аномалия отсечена

## Conclusion
Cap по видам спорта работает как эвристика.
При подключении реальных sharp-источников (Pinnacle, Betfair)
cap можно снять или снизить.
