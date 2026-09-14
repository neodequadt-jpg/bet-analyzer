# EVR-0001: KHL 2-way margin anomaly

Status: OPEN
Date: 2026-09-14

## Object
Value detector on 2-way markets (KHL: СКА — Динамо М).

## Environment
Mock data, 5 БК + Марафон sharp.
Consensus: leave-one-out, margin removed.

## Expected
Value detection works on both 3-way (football) and 2-way (hockey) markets.

## Observed
- 3-way (RPL): 2 value-bets, EV 10-14% — реалистично.
- 2-way (KHL): 2 value-bets, EV 27-52% — аномально высоко.

## Analysis
2-way рынки КХЛ имеют маржу 15-20%. После remove_margin
"fair odds" становятся ниже, чем у любого БК → все БК выглядят
как value, даже без реального edge.

## Conclusion
Detector fires, но для 2-way рынков нужно:
1. Использовать sharp reference (Pinnacle/Betfair) вместо consensus из тех же БК.
2. Или добавить проверку на максимально допустимый EV (cap по видам спорта).
3. Или отказаться от value-detection на 2-way до подключения реальных sharp-источников.

## Next Action
Реализовать cap по видам спорта:
- football: max EV 20%
- hockey: max EV 10%
- tennis: max EV 10%
