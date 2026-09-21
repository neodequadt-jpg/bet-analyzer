import os
import requests
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class SportEvent:
    id: str
    sport: str
    league: str
    home: str
    away: str
    start_ts: int
    odds_home: Optional[float] = None
    odds_draw: Optional[float] = None
    odds_away: Optional[float] = None
    source: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

def get_http_session() -> requests.Session:
    session = requests.Session()
    proxy = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}
    return session
