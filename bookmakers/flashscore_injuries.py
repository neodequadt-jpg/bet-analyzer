"""
Flashscore missing players parser.

Extracts injured / suspended / questionable players from a Flashscore match page.

Source block:
    [data-testid="wcl-lineupsParticipantGeneral-{left|right}"]
Left  = home team missing players.
Right = away team missing players.

Known reason values:
    - "Knee Injury"
    - "Yellow Cards"
    - "Inactive"
    - "Questionable"
"""
from __future__ import annotations

from bs4 import BeautifulSoup


_SIDE_TO_KEY = (("left", "home"), ("right", "away"))


def parse_missing_players(html: str) -> dict:
    """
    Parse missing players from a Flashscore match page.

    Returns:
        {
          "home": [{"name": str, "reason": str}, ...],
          "away": [{"name": str, "reason": str}, ...],
        }
    """
    if not html:
        return {"home": [], "away": []}

    soup = BeautifulSoup(html, "html.parser")
    result: dict = {"home": [], "away": []}

    for side, key in _SIDE_TO_KEY:
        selector = f'[data-testid="wcl-lineupsParticipantGeneral-{side}"]'
        for div in soup.select(selector):
            name_el = div.select_one(".wcl-mainRow_IaUrm span")
            if not name_el:
                continue
            name = name_el.get_text(" ", strip=True)
            if not name:
                continue
            reason_el = div.select_one('[data-testid="wcl-scores-caption-05"]')
            reason = (
                reason_el.get_text(" ", strip=True)
                if reason_el else "unknown"
            )
            result[key].append({"name": name, "reason": reason})

    return result
