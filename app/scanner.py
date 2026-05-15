"""Сбор артефактов целевой страницы.

Структуры: `PageArtifacts`, `Cookie`, `NetworkEntry`.
Функция `collect(url, timeout)` поднимает headless Chromium через Playwright,
ходит по URL, ждёт `load`, опционально пытается дождаться `networkidle` под коротким
таймаутом — собирает DOM/headers/cookies/network-лог.
В итерации 3 — только главная страница; многостраничный обход — итерация 4.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime
from typing import Literal

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Request, async_playwright
from pydantic import BaseModel, ConfigDict


class ScanError(Exception):
    """Ошибка сбора артефактов целевой страницы (DNS, timeout, нет ответа)."""


class Cookie(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    value: str
    domain: str
    secure: bool = False
    http_only: bool = False
    same_site: Literal["Strict", "Lax", "None"] | None = None


class NetworkEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str
    method: str
    resource_type: str


class PageArtifacts(BaseModel):
    """Снимок страницы после загрузки headless Chromium.

    Содержит финальный URL (после редиректов), HTTP-статус ответа на главный
    запрос, HTML после `networkidle`, response-headers, cookies, network-лог
    запросов и метки времени.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str
    status: int
    html: str
    headers: dict[str, str]
    cookies: tuple[Cookie, ...] = ()
    network_log: tuple[NetworkEntry, ...] = ()
    scan_started_at: datetime
    scan_finished_at: datetime


logger = logging.getLogger(__name__)

_SAME_SITE_MAP: dict[str, Literal["Strict", "Lax", "None"] | None] = {
    "Strict": "Strict",
    "Lax": "Lax",
    "None": "None",
}


async def collect(url: str, timeout: int, user_agent: str) -> PageArtifacts:
    """Headless-сбор артефактов страницы через Playwright Chromium.

    На каждый скан поднимается свежий браузер и контекст (vision: «свежий
    Browser на каждый скан — нет утечек состояния»). `timeout` — общий
    таймаут на `page.goto` в секундах.

    Бросает `ScanError`, если страница не отдала ответ или Playwright упал
    с `PlaywrightError` / `TimeoutError`.
    """

    started_at = datetime.now(UTC)
    network_log: list[NetworkEntry] = []

    def _on_request(request: Request) -> None:
        network_log.append(
            NetworkEntry(
                url=request.url,
                method=request.method,
                resource_type=request.resource_type,
            )
        )

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                context = await browser.new_context(user_agent=user_agent)
                page = await context.new_page()
                page.on("request", _on_request)

                # `networkidle` ненадёжен: на сайтах с аналитикой/long-poll сеть не утихает
                # и goto падает по таймауту. Ждём `load`, затем коротко пытаемся достичь
                # `networkidle` — даём шанс ленивым скриптам выставить cookies, но не блокируемся.
                response = await page.goto(url, timeout=timeout * 1000, wait_until="load")
                if response is None:
                    raise ScanError(f"no response from {url!r}")
                with contextlib.suppress(PlaywrightError):
                    await page.wait_for_load_state("networkidle", timeout=3000)

                final_url = page.url
                status = response.status
                headers = dict(await response.all_headers())
                html = await page.content()

                playwright_cookies = await context.cookies()
                cookies = tuple(
                    Cookie(
                        name=c["name"],
                        value=c["value"],
                        domain=c.get("domain", ""),
                        secure=bool(c.get("secure", False)),
                        http_only=bool(c.get("httpOnly", False)),
                        same_site=_SAME_SITE_MAP.get(c.get("sameSite", "")),
                    )
                    for c in playwright_cookies
                )
            finally:
                await browser.close()
    except PlaywrightError as exc:
        raise ScanError(f"playwright error scanning {url!r}: {exc}") from exc

    return PageArtifacts(
        url=final_url,
        status=status,
        html=html,
        headers=headers,
        cookies=cookies,
        network_log=tuple(network_log),
        scan_started_at=started_at,
        scan_finished_at=datetime.now(UTC),
    )
