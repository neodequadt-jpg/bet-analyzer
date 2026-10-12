"""Bonus monitor – fetch, normalize, diff bonuses from metaratings.ru."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

URL = "https://metaratings.ru/bonuses/"
SNAPSHOT_PATH = Path("data/bonuses_snapshot.json")
_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)
_AMOUNT_RE = re.compile(r"(\d[\d\s]*)\s*₽")


@dataclass
class Bonus:
    id: str
    bookmaker: str
    title: str
    amount_rub: int | None
    promo_code: str | None
    url: str
    verified: bool
    expired: bool
    end_date: str | None
    raw: dict = field(default_factory=dict, repr=False)


def _session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    s.headers["User-Agent"] = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )
    return s


def fetch_bonuses() -> list[dict]:
    """Fetch raw bonus dicts from metaratings.ru main bonuses page."""
    logger.info("Fetching bonuses from %s", URL)
    resp = _session().get(URL, timeout=20)
    resp.raise_for_status()

    m = _NEXT_DATA_RE.search(resp.text)
    if not m:
        logger.error("__NEXT_DATA__ not found in response")
        raise ValueError("__NEXT_DATA__ not found in page HTML")

    next_data = json.loads(m.group(1))
    page_props: dict = next_data["props"]["pageProps"]

    raw_items: list[dict] = list(page_props.get("bonuses", []))
    for slider in page_props.get("bonusSliders", []):
        raw_items.extend(slider.get("bonuses", []))

    # dedup by id — top и sliders пересекаются
    seen: dict[str, dict] = {}
    for item in raw_items:
        bid = str(item.get("id") or "")
        if not bid:
            continue
        seen[bid] = item

    bonuses = list(seen.values())
    logger.info("Fetched %d raw bonuses (%d after dedup)", len(raw_items), len(bonuses))
    return bonuses


def _parse_amount(text: str | None) -> int | None:
    if not text:
        return None
    m = _AMOUNT_RE.search(text)
    if not m:
        return None
    return int(m.group(1).replace(" ", ""))


def normalize(raw: dict) -> Bonus:
    """Convert a raw bonus dict from metaratings into a Bonus dataclass."""
    promo = raw.get("promo") or {}
    bk = promo.get("bookmaker") or {}
    analytics = promo.get("analytics_data") or {}

    bookmaker = (
        analytics.get("bookmaker_name")
        or bk.get("id")
        or "unknown"
    )
    title = raw.get("name", "")
    bonus_text = raw.get("bonus_text")
    amount_rub = _parse_amount(bonus_text)

    promo_code = raw.get("promo_code") or None
    rel_url = raw.get("url", "")
    url = rel_url if rel_url.startswith("http") else f"https://metaratings.ru{rel_url}"

    verified = bool(raw.get("verified"))
    expired = bool(raw.get("expired"))
    end_date = raw.get("end_date") or None

    return Bonus(
        id=str(raw.get("id", "")),
        bookmaker=bookmaker,
        title=title,
        amount_rub=amount_rub,
        promo_code=promo_code,
        url=url,
        verified=verified,
        expired=expired,
        end_date=end_date,
        raw=raw,
    )


def snapshot_diff(
    current: list[Bonus],
    prev: list[Bonus],
) -> dict[str, list[dict]]:
    """Compare two snapshots; return {"new": [...], "gone": [...], "changed": [...]}."""
    cur_map = {b.id: b for b in current}
    prev_map = {b.id: b for b in prev}

    new_ids = cur_map.keys() - prev_map.keys()
    gone_ids = prev_map.keys() - cur_map.keys()
    common_ids = cur_map.keys() & prev_map.keys()

    changed: list[dict] = []
    for bid in common_ids:
        c = cur_map[bid]
        p = prev_map[bid]
        diffs: dict[str, Any] = {}
        for fld in (
            "bookmaker",
            "title",
            "amount_rub",
            "promo_code",
            "url",
            "verified",
            "expired",
            "end_date",
        ):
            cv = getattr(c, fld)
            pv = getattr(p, fld)
            if cv != pv:
                diffs[fld] = {"prev": pv, "cur": cv}
        if diffs:
            changed.append({"id": bid, "fields": diffs})

    result = {
        "new": [_bonus_to_dict(cur_map[i]) for i in new_ids],
        "gone": [_bonus_to_dict(prev_map[i]) for i in gone_ids],
        "changed": changed,
    }
    logger.info(
        "Snapshot diff: new=%d gone=%d changed=%d",
        len(result["new"]),
        len(result["gone"]),
        len(result["changed"]),
    )
    return result


def _bonus_to_dict(b: Bonus) -> dict:
    return {
        "id": b.id,
        "bookmaker": b.bookmaker,
        "title": b.title,
        "amount_rub": b.amount_rub,
        "promo_code": b.promo_code,
        "url": b.url,
        "verified": b.verified,
        "expired": b.expired,
        "end_date": b.end_date,
    }


def save_snapshot(bonuses: list[Bonus], path: Path = SNAPSHOT_PATH) -> None:
    """Persist current bonus list to JSON snapshot."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [_bonus_to_dict(b) for b in bonuses]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved %d bonuses to %s", len(data), path)


def load_snapshot(path: Path = SNAPSHOT_PATH) -> list[Bonus]:
    """Load a previously saved snapshot."""
    if not path.exists():
        logger.warning("Snapshot %s not found", path)
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        Bonus(
            id=d["id"],
            bookmaker=d["bookmaker"],
            title=d["title"],
            amount_rub=d["amount_rub"],
            promo_code=d["promo_code"],
            url=d["url"],
            verified=d["verified"],
            expired=d["expired"],
            end_date=d["end_date"],
        )
        for d in data
    ]
