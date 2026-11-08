"""RU -> EN team aliases for top-5 leagues (cross-provider matching).

Fonbet names: Russian (Атлетико Мадрид)
Pinnacle names: English (Atletico Madrid)
This dict maps RU -> EN, applied in normalize_team BEFORE TEAM_ALIASES.

Source of truth (probed 2026-11-08):
- RU: Fonbet listBase, kind=1 level=1, top-5 segment ids (EVR-0053)
- EN: Pinnacle via TheOddsAPI, soccer_epl/spain_la_liga/italy_serie_a/
  germany_bundesliga/france_ligue_one (EVR-0055 probe)
- Values are lowercase, WITHOUT diacritics (normalize_team strips them
  via _strip_diacritics, so 'Atletico Madrid' and 'Atlético Madrid' both
  become 'atletico madrid').
"""

RU_TO_EN = {
    # === EPL (20) ===
    "арсенал": "arsenal",
    "астон вилла": "aston villa",
    "борнмут": "bournemouth",
    "брайтон": "brighton and hove albion",
    "брентфорд": "brentford",
    "ипсвич таун": "ipswich town",
    "ковентри сити": "coventry city",
    "кристал пэлас": "crystal palace",
    "ливерпуль": "liverpool",
    "лидс": "leeds united",
    "манчестер сити": "manchester city",
    "манчестер юнайтед": "manchester united",
    "ноттингем форест": "nottingham forest",
    "ньюкасл": "newcastle united",
    "сандерленд": "sunderland",
    "тоттенхэм": "tottenham hotspur",
    "фулхэм": "fulham",
    "халл сити": "hull city",
    "челси": "chelsea",
    "эвертон": "everton",

    # === La Liga (20) ===
    "алавес": "alaves",
    "атлетик бильбао": "athletic bilbao",
    "атлетико мадрид": "atletico madrid",
    "барселона": "barcelona",
    "бетис": "real betis",
    "валенсия": "valencia",
    "вильярреал": "villarreal",
    "депортиво ла-корунья": "deportivo la coruna",
    "леванте": "levante",
    "малага": "malaga",
    "осасуна": "ca osasuna",
    "райо вальекано": "rayo vallecano",
    "расинг сантандер": "real racing club de santander",
    "реал мадрид": "real madrid",
    "реал сосьедад": "real sociedad",
    "севилья": "sevilla",
    "сельта": "celta vigo",
    "хетафе": "getafe",
    "эльче": "elche cf",
    "эспаньол": "espanyol",

    # === Serie A (20) ===
    "аталанта": "atalanta bc",
    "болонья": "bologna",
    "венеция": "venezia",
    "дженоа": "genoa",
    "интер милан": "inter milan",
    "кальяри": "cagliari",
    "комо": "como",
    "лацио": "lazio",
    "лечче": "lecce",
    "милан": "ac milan",
    "монца": "monza",
    "наполи": "napoli",
    "парма": "parma",
    "рома": "as roma",
    "сассуоло": "sassuolo",
    "торино": "torino",
    "удинезе": "udinese",
    "фиорентина": "fiorentina",
    "фрозиноне": "frosinone",
    "ювентус": "juventus",

    # === Bundesliga (18) ===
    "айнтрахт франкфурт": "eintracht frankfurt",
    "аугсбург": "augsburg",
    "бавария": "bayern munich",
    "байер леверкузен": "bayer leverkusen",
    "боруссия дортмунд": "borussia dortmund",
    "боруссия менхенгладбах": "borussia monchengladbach",
    "вердер": "werder bremen",
    "гамбург": "hamburger sv",
    "кельн": "1. fc koln",
    "лейпциг": "rb leipzig",
    "майнц": "fsv mainz 05",
    "падерборн": "sc paderborn",
    "унион берлин": "union berlin",
    "фрайбург": "sc freiburg",
    "хоффенхайм": "tsg hoffenheim",
    "шальке 04": "fc schalke 04",
    "штутгарт": "vfb stuttgart",
    "эльверсберг": "elversberg",

    # === Ligue 1 (18) ===
    "анже": "angers",
    "брест": "brest",
    "гавр": "le havre",
    "ланс": "rc lens",
    "ле ман": "le mans fc",
    "лилль": "lille",
    "лион": "lyon",
    "лорьян": "lorient",
    "марсель": "marseille",
    "монако": "as monaco",
    "ницца": "nice",
    "осер": "auxerre",
    "псж": "paris saint germain",
    "париж": "paris fc",
    "ренн": "rennes",
    "страсбур": "strasbourg",
    "труа": "troyes",
    "тулуза": "toulouse",
}
