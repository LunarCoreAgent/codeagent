"""Web scraping tools powered by Scrapling.

Two agent-facing tools:

- ``web_fetch``: fetch a page and return readable text (or CSS-selected
  fragments) — the agent's window onto the live web.
- ``web_scrape``: extract structured data with named CSS selectors.

Both use Scrapling's ``AsyncFetcher`` (browser-grade TLS fingerprint via
curl_cffi). ``stealth=True`` routes through ``StealthyFetcher`` (camoufox
browser) to bypass anti-bot systems like Cloudflare — heavier, opt-in.

Requires ``pip install codeagent[scrape]``.
"""

from __future__ import annotations

import json
from typing import Any

from codeagent.security.policy import RiskLevel
from codeagent.tools.base import Tool

MAX_CHARS_CAP = 50_000


def _require_scrapling():
    try:
        from scrapling.fetchers import AsyncFetcher
    except ImportError as exc:
        raise RuntimeError(
            "Scrapling is required for web tools: pip install codeagent[scrape]"
        ) from exc
    return AsyncFetcher


async def _fetch_page(url: str, stealth: bool, timeout: int):
    """Fetch ``url`` and return a Scrapling Adaptor (parsed response)."""
    if stealth:
        try:
            from scrapling.fetchers import StealthyFetcher
        except ImportError as exc:
            raise RuntimeError(
                "Stealth mode needs the full browser stack: "
                "pip install 'scrapling[fetchers]' && scrapling install"
            ) from exc
        return await StealthyFetcher.async_fetch(
            url, headless=True, network_idle=True, timeout=timeout * 1000,
        )
    async_fetcher = _require_scrapling()
    return await async_fetcher.get(url, timeout=timeout)


def _page_text(page: Any, max_chars: int) -> str:
    """Readable text: main content if detectable, else full body text."""
    text = page.get_all_text(ignore_tags=("script", "style", "noscript"))
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)[:max_chars]


class WebFetchTool(Tool):
    name = "web_fetch"
    description = (
        "Fetch a web page and return its readable text content. "
        "Use selector to narrow to a CSS fragment; stealth for anti-bot pages."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The page URL (http/https)."},
            "selector": {"type": "string", "description": "Optional CSS selector to extract only matching fragments."},
            "max_chars": {"type": "integer", "description": "Truncate output (default 8000, max 50000)."},
            "stealth": {"type": "boolean", "description": "Bypass anti-bot protection via browser (slower)."},
            "timeout": {"type": "integer", "description": "Seconds (default 30)."},
        },
        "required": ["url"],
    }
    risk_level = RiskLevel.READ_ONLY

    async def execute(self, url: str, selector: str | None = None,
                      max_chars: int = 8000, stealth: bool = False,
                      timeout: int = 30, **_: Any) -> str:
        max_chars = min(max_chars, MAX_CHARS_CAP)
        page = await _fetch_page(url, stealth, timeout)
        status = getattr(page, "status", "?")
        if selector:
            fragments = [
                el.get_all_text(ignore_tags=("script", "style")).strip()
                for el in page.css(selector)
            ]
            fragments = [f for f in fragments if f]
            if not fragments:
                return f"HTTP {status}, but no elements matched selector: {selector}"
            body = "\n\n---\n\n".join(fragments)
        else:
            body = _page_text(page, max_chars)
        return f"[HTTP {status}] {page.url}\n\n{body[:max_chars]}"


class WebScrapeTool(Tool):
    name = "web_scrape"
    description = (
        "Extract structured data from a web page: give named CSS selectors, "
        "get back JSON rows. Selectors ending in ::attr(href) extract attributes."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The page URL (http/https)."},
            "selectors": {
                "type": "object",
                "description": "Map of field name → CSS selector, e.g. {\"title\": \"h2::text\", \"link\": \"a::attr(href)\"}.",
            },
            "limit": {"type": "integer", "description": "Max items per field (default 20)."},
            "stealth": {"type": "boolean", "description": "Bypass anti-bot protection via browser (slower)."},
            "timeout": {"type": "integer", "description": "Seconds (default 30)."},
        },
        "required": ["url", "selectors"],
    }
    risk_level = RiskLevel.READ_ONLY

    async def execute(self, url: str, selectors: dict[str, str],
                      limit: int = 20, stealth: bool = False,
                      timeout: int = 30, **_: Any) -> str:
        page = await _fetch_page(url, stealth, timeout)
        status = getattr(page, "status", "?")
        data: dict[str, list[str]] = {}
        for field, selector in selectors.items():
            values = [str(v).strip() for v in page.css(selector).getall()]
            data[field] = [v for v in values if v][:limit]
        return json.dumps(
            {"status": status, "url": str(page.url), "data": data},
            ensure_ascii=False, indent=2,
        )


def web_tools() -> list[Tool]:
    return [WebFetchTool(), WebScrapeTool()]
