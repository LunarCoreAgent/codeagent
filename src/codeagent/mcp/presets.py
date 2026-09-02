"""Ready-made MCP server presets."""

from __future__ import annotations

from codeagent.mcp.client import MCPServerConfig

KEENABLE_MCP_URL = "https://api.keenable.ai/mcp"


def keenable(api_key: str | None = None) -> MCPServerConfig:
    """Keenable web search + clean-markdown page fetch (hosted MCP server).

    Provides the ``search_web_pages`` and ``fetch_page_content`` tools.
    Keyless by default (1,000 requests/hour); pass ``api_key`` to lift
    the rate limit.
    """
    headers = {"X-API-Key": api_key} if api_key else None
    return MCPServerConfig(name="keenable", url=KEENABLE_MCP_URL, headers=headers)


def playwright_mcp(headless: bool = True, browser: str = "chromium") -> MCPServerConfig:
    """Microsoft Playwright MCP: full browser automation for the agent.

    Requires Node.js; the server is launched via ``npx @playwright/mcp``.
    Provides tools like ``browser_navigate``, ``browser_click``,
    ``browser_type``, ``browser_take_screenshot`` etc.
    """
    args = ["@playwright/mcp@latest", "--browser", browser]
    if headless:
        args.append("--headless")
    return MCPServerConfig(name="playwright", command="npx", args=args)


def chrome_devtools_mcp(headless: bool = True) -> MCPServerConfig:
    """Chrome DevTools MCP: inspect, debug and profile pages in Chrome.

    Requires Node.js; the server is launched via
    ``npx chrome-devtools-mcp``. Provides performance tracing, network
    inspection, console messages, DOM snapshots and more.
    """
    args = ["chrome-devtools-mcp@latest"]
    if headless:
        args.append("--headless")
    return MCPServerConfig(name="chrome-devtools", command="npx", args=args)
