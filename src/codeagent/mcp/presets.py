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


def weapp_agent_mcp(endpoint: str = "ws://localhost:9420") -> MCPServerConfig:
    """WeChat DevTools automation via ``@chaixueyuan/weapp-agent-mcp``.

    Requires Node.js and WeChat DevTools with the automation / service
    port open. Default WebSocket is ``ws://localhost:9420``.
    """
    return MCPServerConfig(
        name="weapp-agent-mcp",
        command="npx",
        args=["-y", "@chaixueyuan/weapp-agent-mcp"],
        env={"WEAPP_WS_ENDPOINT": endpoint},
    )


def drawio_mcp() -> MCPServerConfig:
    """Next AI Draw.io MCP: natural-language draw.io diagrams in a browser.

    Requires Node.js. Launches ``npx @next-ai-drawio/mcp-server@latest``.
    Pair with the ``next-ai-draw-io`` fusion skill.
    """
    return MCPServerConfig(
        name="drawio",
        command="npx",
        args=["-y", "@next-ai-drawio/mcp-server@latest"],
    )


def dbx_mcp(
    web_url: str | None = None,
    web_password: str | None = None,
    data_dir: str | None = None,
) -> MCPServerConfig:
    """DBX MCP: query databases via connections configured in DBX.

    Requires Node.js (or a prebuilt binary from DBX releases). The desktop /
    Docker DBX app must be installed and connections allowlisted under
    Settings → MCP. Pair with the ``dbx`` fusion skill.

    Optional env: ``DBX_WEB_URL`` / ``DBX_WEB_PASSWORD`` for Web/Docker,
    ``DBX_DATA_DIR`` for Windows portable builds.
    """
    env: dict[str, str] = {}
    if web_url:
        env["DBX_WEB_URL"] = web_url
    if web_password:
        env["DBX_WEB_PASSWORD"] = web_password
    if data_dir:
        env["DBX_DATA_DIR"] = data_dir
    return MCPServerConfig(
        name="dbx",
        command="npx",
        args=["-y", "@dbx-app/mcp-server"],
        env=env or None,
    )
