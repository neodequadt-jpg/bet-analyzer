"""
Реестр легальных букмекерских контор РФ.
Все БК обязаны быть подключены к ЦУПИС и иметь лицензию ФНС.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class BookmakerInfo:
    name: str
    cupis: str
    license_year: int
    site: str
    avg_margin_pct: float
    max_stake: int
    withdrawal_hours: float
    trust_score: float


BOOKMAKERS = [
    BookmakerInfo("Винлайн",     "Первый", 2016, "winline.ru",    4.0, 500_000,   1.5, 0.85),
    BookmakerInfo("Фонбет",      "Первый", 2009, "fonbet.ru",     5.0, 1_000_000, 3.0, 0.90),
    BookmakerInfo("Лига Ставок", "Первый", 2009, "ligastavok.ru", 5.5, 500_000,   4.0, 0.88),
    BookmakerInfo("Бет Бум",     "Второй", 2017, "betboom.ru",    4.8, 300_000,   2.0, 0.87),
    BookmakerInfo("PARI",        "Первый", 2021, "pari.ru",       4.5, 500_000,   3.5, 0.80),
    BookmakerInfo("Бетсити",     "Второй", 2016, "betcity.ru",    5.0, 300_000,   4.5, 0.86),
    BookmakerInfo("Леон",        "Второй", 2016, "leon.ru",       5.5, 200_000,   5.0, 0.83),
    BookmakerInfo("Олимп",       "Первый", 2012, "olimp.bet",     5.3, 300_000,   5.5, 0.82),
    BookmakerInfo("Мелбет",      "Второй", 2021, "melbet.ru",     5.0, 200_000,   6.0, 0.80),
    BookmakerInfo("Балтбет",     "Первый", 2009, "baltbet.ru",    5.5, 200_000,   6.5, 0.78),
    BookmakerInfo("Марафон",     "Первый", 2010, "marathonbet.ru", 3.0, 500_000,   4.0, 0.85),
]


def get_bookmaker(name: str) -> Optional[BookmakerInfo]:
    for bk in BOOKMAKERS:
        if bk.name.lower() == name.lower():
            return bk
    return None


def all_names() -> list[str]:
    return [bk.name for bk in BOOKMAKERS]


if __name__ == "__main__":
    print(f"Всего БК: {len(BOOKMAKERS)}")
    for bk in BOOKMAKERS:
        print(f"  {bk.name:14} | {bk.cupis:7} | trust={bk.trust_score}")
