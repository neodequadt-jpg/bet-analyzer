"""
Normalizer: объединяет OddsEvent[] из разных источников в единые матчи.
Маппинг по (normalized_home, normalized_away) — имена команд могут отличаться.
"""
import re
from dataclasses import dataclass
from typing import Iterable

from bookmakers.parser import OddsEvent


# Синонимы названий команд (Fonbet / Manual / Flashscore называют по-разному)
TEAM_ALIASES = {
    "зенит": "зенит",
    "зенит спб": "зенит",
    "зенит санкт-петербург": "зенит",
    "спартак": "спартак",
    "спартак москва": "спартак",
    "цска": "цска",
    "локомотив": "локомотив",
    "локомотив москва": "локомотив",
    "краснодар": "краснодар",
    "динамо": "динамо",
    "динамо москва": "динамо",
    "динамо махачкала": "динамо мх",
    "ростов": "ростов",
    "рубин": "рубин",
    "ахмат": "ахмат",
    "крылья советов": "крылья",
    "балтика": "балтика",
    "факел": "факел",
    "оренбург": "оренбург",
    "пари нн": "пари нн",
    "акрон": "акрон",
}


def normalize_team(name: str) -> str:
    n = (name or "").strip().lower()
    # Убираем пробелы в начале/конце, схлопываем множественные
    n = re.sub(r"\s+", " ", n)
    return TEAM_ALIASES.get(n, n)


def match_key(ev: OddsEvent) -> tuple[str, str]:
    return (normalize_team(ev.home), normalize_team(ev.away))


def group_by_match(events: Iterable[OddsEvent]) -> dict[tuple[str, str], list[OddsEvent]]:
    """Группирует события по паре команд. Возвращает {key: [OddsEvent...]}."""
    groups: dict[tuple[str, str], list[OddsEvent]] = {}
    for ev in events:
        key = match_key(ev)
        groups.setdefault(key, []).append(ev)
    return groups


def merge(*sources: list[OddsEvent]) -> list[list[OddsEvent]]:
    """
    Объединяет события из нескольких источников в группы по матчу.
    Возвращает список групп, каждая группа = один матч с несколькими БК.
    """
    all_events: list[OddsEvent] = []
    for src in sources:
        all_events.extend(src)
    groups = group_by_match(all_events)
    return list(groups.values())


def group_label(group: list[OddsEvent]) -> str:
    """Читаемое имя группы по первому событию."""
    if not group:
        return "?"
    e = group[0]
    return f"{e.home} vs {e.away} ({len(group)} BK)"
