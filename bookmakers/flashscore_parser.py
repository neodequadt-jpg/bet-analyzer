"""
Flashscore parser via Playwright.
Цель: получить коэффициенты 1X2 и тоталы для матча РПЛ.
"""
import asyncio
import json
import logging
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PwTimeout

log = logging.getLogger("flashscore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

FLASHSCORE_BASE = "https://www.flashscore.com"
CACHE_DIR = Path("data/cache/flashscore")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class FlashscoreParser:
    def __init__(self, headless: bool = True, timeout: int = 30000,
                 proxy: str | None = "http://127.0.0.1:18080"):
        self.headless = headless
        self.timeout = timeout
        self.proxy = proxy  # default: AVITO opera-proxy

    async def _new_page(self, browser):
        return await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
        )

    async def probe_homepage(self) -> dict:
        """Проверка: открывается ли Flashscore вообще."""
        async with async_playwright() as pw:
            launch_kwargs = {"headless": self.headless}
            if self.proxy:
                launch_kwargs["proxy"] = {"server": self.proxy}
            browser = await pw.chromium.launch(**launch_kwargs)
            page = await self._new_page(browser)
            try:
                await page.goto(
                    FLASHSCORE_BASE,
                    timeout=self.timeout,
                    wait_until="domcontentloaded",
                )
                return {
                    "status": "ok",
                    "title": await page.title(),
                    "url": page.url,
                    "proxy": self.proxy,
                }
            except PwTimeout:
                return {"status": "timeout", "proxy": self.proxy}
            except Exception as e:
                return {"status": "error", "error": str(e), "proxy": self.proxy}
            finally:
                await browser.close()


def probe_sync(proxy: str | None = None) -> dict:
    return asyncio.run(FlashscoreParser(proxy=proxy).probe_homepage())


if __name__ == "__main__":
    import sys
    proxy = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(probe_sync(proxy=proxy), ensure_ascii=False, indent=2))


# --- Reality probe: dump league pages ---
RPL_BASE = "https://www.flashscore.com/football/russia/premier-league"
RPL_RESULTS = f"{RPL_BASE}/results/"
RPL_FIXTURES = f"{RPL_BASE}/fixtures/"


class FlashscoreLeagueProbe(FlashscoreParser):
    async def dump(self, url: str, out_path: str) -> dict:
        async with async_playwright() as pw:
            launch_kwargs = {"headless": self.headless}
            if self.proxy:
                launch_kwargs["proxy"] = {"server": self.proxy}
            browser = await pw.chromium.launch(**launch_kwargs)
            page = await self._new_page(browser)
            try:
                await page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")
                # Ждём пока JS-таблица матчей отрисуется.
                # Flashscore грузит матчи lazy — ждём появления селектора.
                try:
                    await page.wait_for_selector("[id^='g_1_']", timeout=15000)
                except PwTimeout:
                    pass
                await page.wait_for_timeout(3000)
                html = await page.content()
                Path(out_path).write_text(html, encoding="utf-8")
                match_count = html.count("event__match ")
                return {
                    "status": "ok",
                    "url": page.url,
                    "title": await page.title(),
                    "html_size": len(html),
                    "event_match_count": match_count,
                    "out_path": out_path,
                }
            except PwTimeout:
                return {"status": "timeout", "url": url}
            except Exception as e:
                return {"status": "error", "error": str(e), "url": url}
            finally:
                await browser.close()


def dump_results_sync() -> dict:
    import asyncio
    return asyncio.run(
        FlashscoreLeagueProbe().dump(RPL_RESULTS, "data/cache/flashscore/rpl_results.html")
    )


def dump_fixtures_sync() -> dict:
    import asyncio
    return asyncio.run(
        FlashscoreLeagueProbe().dump(RPL_FIXTURES, "data/cache/flashscore/rpl_fixtures.html")
    )


# --- Parsing: fixtures list from HTML ---
from typing import Optional


def parse_fixtures_html(html: str) -> list[dict]:
    """
    Извлекает список матчей из HTML страницы /fixtures/ или /results/.
    Возвращает: [{match_id, mid, match_url, home, away, kickoff_text}].
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("div.event__match[data-event-row='true']")

    out: list[dict] = []
    for row in rows:
        row_id = row.get("id", "")
        match_id = row_id.replace("g_1_", "", 1) if row_id.startswith("g_1_") else None

        link = row.select_one("a.eventRowLink")
        href = link.get("href") if link else None
        mid = None
        if href and "mid=" in href:
            mid = href.split("mid=", 1)[1].split("&", 1)[0]

        home_el = row.select_one(".event__homeParticipant span")
        away_el = row.select_one(".event__awayParticipant span")
        time_el = row.select_one(".event__stageTime")

        out.append({
            "match_id": match_id,
            "mid": mid,
            "match_url": href,
            "home": home_el.get_text(strip=True) if home_el else None,
            "away": away_el.get_text(strip=True) if away_el else None,
            "kickoff_text": time_el.get_text(strip=True) if time_el else None,
        })
    return out


# --- Parsing: fixtures list from HTML ---
from typing import Optional


def parse_fixtures_html(html: str) -> list[dict]:
    """
    Извлекает список матчей из HTML страницы /fixtures/ или /results/.
    Возвращает: [{match_id, mid, match_url, home, away, kickoff_text}].
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("div.event__match[data-event-row='true']")

    out: list[dict] = []
    for row in rows:
        row_id = row.get("id", "")
        match_id = row_id.replace("g_1_", "", 1) if row_id.startswith("g_1_") else None

        link = row.select_one("a.eventRowLink")
        href = link.get("href") if link else None
        mid = None
        if href and "mid=" in href:
            mid = href.split("mid=", 1)[1].split("&", 1)[0]

        home_el = row.select_one(".event__homeParticipant span")
        away_el = row.select_one(".event__awayParticipant span")
        time_el = row.select_one(".event__stageTime")

        out.append({
            "match_id": match_id,
            "mid": mid,
            "match_url": href,
            "home": home_el.get_text(strip=True) if home_el else None,
            "away": away_el.get_text(strip=True) if away_el else None,
            "kickoff_text": time_el.get_text(strip=True) if time_el else None,
        })
    return out
