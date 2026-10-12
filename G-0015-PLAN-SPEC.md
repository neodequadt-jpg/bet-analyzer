# G-0015 SPEC: plan_builder — one-tap matched betting plan

## Files
- scoring/plan_builder.py (rewrite existing)
- tests/test_plan_builder.py (new)

## Purpose
Build ONE plan for ONE bonus + ONE signal + user-provided lay_odds.
Output: formatted Telegram HTML block "БОНУС / BACK / LAY / РЕЗУЛЬТАТ".

## Imports
from scoring.bonus_tracker import Bonus, list_active
from scoring.matched_betting import calc_lay, LayResult

## Bonus fields
bookmaker: str, type: str, amount: int, min_odds: float, max_odds: float,
expiry: str, status: str

## LayResult fields
lay_stake: float, liability: float, profit_if_back: float,
profit_if_lay: float, guaranteed: float

## Signal format (dict from data/backtest/signals/*.json)
{"event": "Ростов vs Акрон", "outcome": "away", "odds": 4.81,
 "bookmaker": "PARI", "league": "RPL", "kickoff": "09.10 19:30",
 "ev": 0.0818, "kelly": 0.0215}

## Public API

SIGNALS_DIR = Path("data/backtest/signals")

@dataclass
class Plan:
    bonus_bookmaker: str
    bonus_amount: float
    bonus_type: str
    bonus_expiry: str
    bonus_min_odds: float
    bonus_max_odds: float
    event: str
    outcome: str
    back_odds: float
    back_bookmaker: str
    league: str
    kickoff: str
    ev: float
    lay_odds: float
    lay_commission: float
    calc: LayResult
    # property: roi_pct = calc.guaranteed / bonus_amount * 100

def list_candidates(bonus: Bonus, signals: list[dict] | None = None,
                    limit: int = 5) -> list[dict]:
    """Signals with odds in [bonus.min_odds, bonus.max_odds], sorted by ev desc.
    If signals=None: load all from SIGNALS_DIR, dedup by (event, outcome, kickoff),
    keep max ev."""

def build_plan(bonus: Bonus, signal: dict, lay_odds: float,
               commission: float = 0.02) -> Plan:
    """Calc via calc_lay(bonus.amount, signal['odds'], lay_odds, commission)."""

def format_plan(plan: Plan) -> str:
    """Telegram HTML block, sections БОНУС/BACK/LAY/РЕЗУЛЬТАТ.
    Outcome labels: home->'П1 (победа хозяев)', draw->'X (ничья)',
    away->'П2 (победа гостей)'."""

def format_candidates(bonus: Bonus, cands: list[dict]) -> str:
    """Numbered HTML list. If empty: 'нет событий в диапазоне'."""

def format_lay_prompt(bonus: Bonus, signal: dict, idx: int) -> str:
    """Prompt asking user to enter /plan_go <bk> <idx> <lay_odds>."""

## NO
- Не делать build_plan() для всех бонусов сразу.
- Не изобретать back_odds_override / lay_odds_override.
- Не использовать find_optimal — только calc_lay.
- Не возвращать plain text — только Telegram HTML.

## Tests (tests/test_plan_builder.py, unittest, no network)
- test_list_candidates_filters_by_odds_range
- test_list_candidates_sorts_by_ev_desc
- test_list_candidates_empty_when_nothing_in_range
- test_build_plan_fields_match_inputs
- test_build_plan_roi_pct
- test_format_plan_contains_БОНУС_BACK_LAY_РЕЗУЛЬТАТ
- test_format_candidates_empty_message
- test_format_candidates_numbered
- test_format_lay_prompt_contains_command
