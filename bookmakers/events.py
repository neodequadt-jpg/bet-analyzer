"""
Реестр событий для анализа.
На первом этапе — статический список.
Позже заменится на парсер с реального источника.
"""

from dataclasses import dataclass


@dataclass
class EventRef:
    event_id: str
    sport: str
    league: str
    home: str
    away: str
    kickoff_iso: str


EVENTS = [
    EventRef(
        event_id="rpl_zenit_spartak_2026_09_15",
        sport="football",
        league="RPL",
        home="Зенит",
        away="Спартак",
        kickoff_iso="2026-09-15T19:00:00+03:00",
    ),
    EventRef(
        event_id="rpl_cska_lokomotiv_2026_09_15",
        sport="football",
        league="RPL",
        home="ЦСКА",
        away="Локомотив",
        kickoff_iso="2026-09-15T21:30:00+03:00",
    ),
    EventRef(
        event_id="khl_ska_dynamo_2026_09_15",
        sport="hockey",
        league="KHL",
        home="СКА",
        away="Динамо М",
        kickoff_iso="2026-09-15T19:30:00+03:00",
    ),
]


def all_event_ids() -> list[str]:
    return [e.event_id for e in EVENTS]


def get_event(event_id: str) -> EventRef | None:
    for e in EVENTS:
        if e.event_id == event_id:
            return e
    return None
