# G-0013 SPEC: Bonus Monitor + Tracker + Matched Betting

## Goal
Автоматически собирать бонусы БК, считать выгоду через matched betting,
мониторить надёжность букмекеров (легальных + офшорных).

## Branch
feat/g0013-bonus-tracker

## Verified source (2026-10-12)
- URL: https://metaratings.ru/bonuses/
- Method: requests.Session(trust_env=False).get() + regex __NEXT_DATA__
- Data path: __NEXT_DATA__.props.pageProps
    - bonuses: list[dict] (4 top)
    - bonusSliders: list[{title, bonuses: list[dict]}] (6 sliders, 54 total)
- Bookmaker field: item["promo"]["bookmaker"]["id"] + item["promo"]["analytics_data"]["bookmaker_name"]
- Fields per bonus:
    id, name, url, promo_code, bonus_text ("10 000 ₽"),
    start_date, end_date, expired, verified, exclusive,
    activations_count, likes, likes_percent, new
- Categories pages (/bonuses/freebety/, /bonuses/za-depozit/) return only 4 each — SKIP.

## Modules

### 1. scoring/bonus_monitor.py
- fetch_bonuses() -> list[dict]  (raw from metaratings)
- normalize(raw) -> Bonus (dataclass)
- snapshot_diff(current, prev) -> {"new": [...], "gone": [...], "changed": [...]}
- Save snapshot: data/bonuses_snapshot.json

Bonus dataclass:
  id: str
  bookmaker: str       # from promo.bookmaker.id or name
  title: str
  amount_rub: int|None # parse from bonus_text "10 000 ₽"
  promo_code: str|None
  url: str             # absolute (prefix https://metaratings.ru)
  verified: bool
  expired: bool
  end_date: str|None
  raw: dict            # keep original for audit

### 2. scoring/bonus_tracker.py
- load(path) -> dict  (data/bonuses.json, manual registry)
- validate(bonus) -> list[str]
- mark_used(name) -> None
- list_active() -> list[Bonus]

data/bonuses.json format (manual fill, наша «касса»):
{
  "Winline": {
    "type": "freebet_snr",
    "amount": 10000,
    "min_odds": 1.30,
    "max_odds": 2.50,
    "expiry": "2026-12-31",
    "status": "active"
  }
}

### 3. scoring/matched_betting.py
Formula SNR:
  lay_stake = (free_bet * (back_odds - 1)) / (lay_odds - commission)
  liability = lay_stake * (lay_odds - 1)
  profit_if_back = free_bet * (back_odds - 1) - liability
  profit_if_lay = lay_stake * (1 - commission)
  guaranteed = min(profit_if_back, profit_if_lay)

- calc_lay(free_bet, back_odds, lay_odds, commission=0.02) -> LayResult
- LayResult dataclass: lay_stake, liability, profit_back, profit_lay, guaranteed

### 4. scoring/bookmaker_monitor.py
- load(path) -> dict  (data/bookmakers.json)
- score(bk) -> int  (0-100 heuristic: license + payout_speed + issues)
- list_risky(threshold=50) -> list
- list_recommended(threshold=70) -> list

data/bookmakers.json — реестр, вручную.
Поля: license (UKGC|MGA|Curacao|Anjouan|RU|none), payout_days, issues[], notes
Офшоры: 1xBet, Melbet, Mostbet, Leon(bet), BetCity(offshore), Cosmobet, GGBet
Легальные РФ: Winline, PARI, Fonbet, Liga Stavok, BetBoom, Marathonbet, Zenit

### 5. tests/
- test_bonus_monitor.py  (mock requests, regex parse, diff)
- test_bonus_tracker.py  (load/validate/mark)
- test_matched_betting.py (formula correctness, edge cases)
- test_bookmaker_monitor.py (scoring, thresholds)

## Invariants
- requests.Session(trust_env=False), UA header
- No print() — logging
- Type hints + dataclasses
- EVR → workspace root: EVR-0021-G0013-*.md
- One module = one dshh call, verify py_compile between

## Out of scope
- Auto bet placement
- Auth on bookmakers
- Withdrawal
