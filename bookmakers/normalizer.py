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
    Дедуп: для одного матча не больше 1 OddsEvent на (bookmaker).
    Приоритет: первый источник (передавайте Fonbet первым → он победит).
    """
    all_events: list[OddsEvent] = []
    for src in sources:
        all_events.extend(src)

    groups = group_by_match(all_events)

    deduped_groups: list[list[OddsEvent]] = []
    for key, events in groups.items():
        seen_bk: set[str] = set()
        unique: list[OddsEvent] = []
        for ev in events:
            bk_key = ev.bookmaker.strip().lower()
            if bk_key in seen_bk:
                continue
            seen_bk.add(bk_key)
            unique.append(ev)
        deduped_groups.append(unique)
    return deduped_groups


def group_label(group: list[OddsEvent]) -> str:
    """Читаемое имя группы по первому событию."""
    if not group:
        return "?"
    e = group[0]
    return f"{e.home} vs {e.away} ({len(group)} BK)"
