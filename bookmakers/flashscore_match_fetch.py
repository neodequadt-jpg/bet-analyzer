"""
Fetch a single Flashscore match page via Playwright.

Reality (EVR-0007):
  Flashscore exposes 'missing players' block only around match day (~24h).
  Outside that window the block is absent.
  Callers must treat empty injuries as a valid result.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PwTimeout


CACHE_DIR = Path("data/cache/flashscore")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_PROXY = "http://127.0.0.1:18080"
MATCH_URL_TMPL = "https://www.flashscore.com/match/{mid}/"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

LINEUP_SELECTOR = '[data-testid^="wcl-lineupsParticipantGeneral-"]'


async def _fetch_async(mid: str, proxy: str | None, timeout_ms: int) -> str:
    url = MATCH_URL_TMPL.format(mid=mid)
    async with async_playwright() as pw:
        launch_kwargs: dict = {"headless": True}
        if proxy:
            launch_kwargs["proxy"] = {"server": proxy}
        browser = await pw.chromium.launch(**launch_kwargs)
        page = await browser.new_page(
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
        )
        try:
            await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            try:
                await page.wait_for_selector(LINEUP_SELECTOR, timeout=10_000)
            except PwTimeout:
                # Match outside publication window — injuries absent.
                pass
            await page.wait_for_timeout(1500)
            return await page.content()
        finally:
            await browser.close()


def fetch_match_html(mid: str, *,
                     proxy: str | None = DEFAULT_PROXY,
                     timeout_ms: int = 30_000) -> str:
    """Always fetch fresh HTML for a Flashscore match page."""
    if not mid:
        return ""
    return asyncio.run(_fetch_async(mid, proxy=proxy, timeout_ms=timeout_ms))


def fetch_and_cache(mid: str, *,
                    proxy: str | None = DEFAULT_PROXY,
                    timeout_ms: int = 30_000) -> str:
    """Fetch and save HTML to cache directory. Returns HTML."""
    html = fetch_match_html(mid, proxy=proxy, timeout_ms=timeout_ms)
    if html:
        (CACHE_DIR / f"match_{mid}.html").write_text(html, encoding="utf-8")
    return html
