"""Matched betting plan builder — bonus + signal + lay_odds -> Plan."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from scoring.bonus_tracker import Bonus, list_active
from scoring.matched_betting import calc_lay, LayResult

logger = logging.getLogger(__name__)

SIGNALS_DIR = Path("data/backtest/signals")
_OUTCOME_RU = {
    "home": "П1 (победа хозяев)",
    "draw": "X (ничья)",
    "away": "П2 (победа гостей)",
}


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

    @property
    def roi_pct(self) -> float:
        if self.bonus_amount <= 0:
            return 0.0
        return self.calc.guaranteed / self.bonus_amount * 100


def _load_all_signals() -> list[dict]:
    out: list[dict] = []
    if not SIGNALS_DIR.exists():
        return out
    for f in sorted(SIGNALS_DIR.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            for s in d.get("signals", []):
                s["_src"] = f.name
                out.append(s)
        except Exception as e:
            logger.warning("read %s: %s", f.name, e)
    return out


def _dedup_signals(signals: list[dict]) -> list[dict]:
    best: dict = {}
    for s in signals:
        key = (s.get("event"), s.get("outcome"), s.get("kickoff"))
        if key not in best or (s.get("ev") or 0) > (best[key].get("ev") or 0):
            best[key] = s
    return list(best.values())


def list_candidates(
    bonus: Bonus,
    signals: Optional[list[dict]] = None,
    limit: int = 5,
) -> list[dict]:
    if signals is None:
        signals = _dedup_signals(_load_all_signals())
    lo = float(bonus.min_odds or 1.0)
    hi = float(bonus.max_odds or 100.0)
    filtered: list[dict] = []
    for s in signals:
        odds = s.get("odds")
        if odds is None:
            continue
        try:
            odds = float(odds)
        except (TypeError, ValueError):
            continue
        if not (lo <= odds <= hi):
            continue
        filtered.append(s)
    filtered.sort(key=lambda x: (x.get("ev") or 0), reverse=True)
    return filtered[:limit]


def build_plan(
    bonus: Bonus,
    signal: dict,
    lay_odds: float,
    commission: float = 0.02,
) -> Plan:
    back_odds = float(signal["odds"])
    calc = calc_lay(bonus.amount, back_odds, lay_odds, commission)
    return Plan(
        bonus_bookmaker=bonus.bookmaker,
        bonus_amount=float(bonus.amount),
        bonus_type=bonus.type,
        bonus_expiry=bonus.expiry,
        bonus_min_odds=float(bonus.min_odds),
        bonus_max_odds=float(bonus.max_odds),
        event=signal.get("event", ""),
        outcome=signal.get("outcome", ""),
        back_odds=back_odds,
        back_bookmaker=signal.get("bookmaker", "?"),
        league=signal.get("league", ""),
        kickoff=signal.get("kickoff", ""),
        ev=float(signal.get("ev") or 0),
        lay_odds=lay_odds,
        lay_commission=commission,
        calc=calc,
    )


def format_plan(plan: Plan) -> str:
    lines = [
        "📋 <b>ПЛАН MATCHED BETTING</b>",
        "",
        "🎁 <b>БОНУС</b>",
        f"   Букмекер: <b>{plan.bonus_bookmaker}</b>",
        f"   Тип: {plan.bonus_type}",
        f"   Сумма: <b>{plan.bonus_amount:.0f}₽</b>",
        f"   Условие: кэф {plan.bonus_min_odds}–{plan.bonus_max_odds}",
        f"   До: {plan.bonus_expiry}",
        "",
        "📌 <b>BACK (ставка фрибетом)</b>",
        f"   Букмекер: {plan.back_bookmaker}",
        f"   Матч: {plan.event}",
        f"   Лига: {plan.league} • {plan.kickoff}",
        f"   Исход: <b>{_OUTCOME_RU.get(plan.outcome, plan.outcome)}</b>",
        f"   Кэф: <b>{plan.back_odds}</b>",
        f"   Ставка: {plan.bonus_amount:.0f}₽ (весь фрибет)",
        f"   EV сигнала: {plan.ev:+.3f}",
        "",
        "🔄 <b>LAY (противоположная)</b>",
        f"   Биржа: Smarkets",
        f"   Кэф: <b>{plan.lay_odds:.2f}</b>",
        f"   Lay stake: <b>{plan.calc.lay_stake:.2f}₽</b>",
        f"   Liability: <b>{plan.calc.liability:.2f}₽</b>",
        f"   Комиссия: {plan.lay_commission*100:.1f}%",
        "",
        "💰 <b>РЕЗУЛЬТАТ</b>",
        f"   Если back выиграет: <b>{plan.calc.profit_if_back:+.2f}₽</b>",
        f"   Если lay выиграет: <b>{plan.calc.profit_if_lay:+.2f}₽</b>",
        f"   <b>ГАРАНТИРОВАННЫЙ ПРОФИТ: {plan.calc.guaranteed:+.2f}₽</b>",
        f"   ROI на бонус: <b>{plan.roi_pct:+.1f}%</b>",
        "",
        "⚠️ Проверь кэфы на Smarkets перед ставкой — они меняются.",
    ]
    return "\n".join(lines)


def format_candidates(bonus: Bonus, cands: list[dict]) -> str:
    if not cands:
        return (
            f"📋 <b>{bonus.bookmaker}</b> — нет событий в диапазоне "
            f"кэф {bonus.min_odds}–{bonus.max_odds}.\n"
            f"Попробуй другой бонус или обнови сигналы."
        )
    lines = [f"📋 <b>{bonus.bookmaker}</b> — топ-{len(cands)} событий", ""]
    for i, s in enumerate(cands, 1):
        outcome = _OUTCOME_RU.get(s.get("outcome"), s.get("outcome"))
        lines.append(
            f"<b>{i}.</b> {s.get('event')} • {s.get('league')}\n"
            f"    {outcome} @ <b>{s.get('odds')}</b> "
            f"({s.get('bookmaker')}) EV {float(s.get('ev') or 0):+.3f}"
        )
    lines.append("")
    lines.append("Выбери событие: /plan_go "
                 f"{bonus.bookmaker} &lt;N&gt; &lt;lay_odds&gt;")
    return "\n".join(lines)


def format_lay_prompt(bonus: Bonus, signal: dict, idx: int) -> str:
    outcome = _OUTCOME_RU.get(signal.get("outcome"), signal.get("outcome"))
    return (
        f"📋 <b>{bonus.bookmaker}</b> #{idx}: {signal.get('event')}\n"
        f"Исход: {outcome}\n"
        f"Back-кэф: <b>{signal.get('odds')}</b> ({signal.get('bookmaker')})\n\n"
        f"Открой Smarkets, найди этот матч, посмотри <b>lay-кэф</b> "
        f"на тот же исход.\n\n"
        f"Отправь:\n"
        f"<code>/plan_go {bonus.bookmaker} {idx} &lt;lay_odds&gt;</code>\n"
        f"Пример: <code>/plan_go {bonus.bookmaker} {idx} 2.15</code>"
    )
