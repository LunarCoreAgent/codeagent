"""MCP (Model Context Protocol) integration: load tools from MCP servers.

Server configs use the de-facto standard Claude-style JSON format, with
either a stdio ``command`` or a streamable-HTTP ``url``::

    {
      "mcpServers": {
        "filesystem": {
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
        },
        "keenable": {
          "type": "streamable-http",
          "url": "https://api.keenable.ai/mcp",
          "headers": {"X-API-Key": "..."}
        }
      }
    }
"""

from __future__ import annotations

import json
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codeagent.security.policy import RiskLevel
from codeagent.tools.base import Tool


@dataclass
class MCPServerConfig:
    """Connection settings for one MCP server.

    Stdio transport: set ``command`` (plus optional ``args`` / ``env``).
    Streamable-HTTP transport: set ``url`` (plus optional ``headers``).
    """

    name: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    url: str | None = None
    headers: dict[str, str] | None = None

    @property
    def transport(self) -> str:
        if self.url:
            return "http"
        if self.command:
            return "stdio"
        raise ValueError(
            f"MCP server {self.name!r} needs either 'command' (stdio) or 'url' (http)"
        )


def load_mcp_config(path: str | Path) -> list[MCPServerConfig]:
    """Parse a Claude-style MCP config file into server configs."""
    data = json.loads(Path(path).read_text())
    servers = data.get("mcpServers", data)
    if not isinstance(servers, dict):
        raise ValueError(f"Invalid MCP config in {path}: expected an object")
    configs = []
    for name, spec in servers.items():
        if "url" in spec:
            configs.append(
                MCPServerConfig(
                    name=name,
                    url=spec["url"],
                    headers=spec.get("headers"),
                )
            )
        elif "command" in spec:
            configs.append(
                MCPServerConfig(
                    name=name,
                    command=spec["command"],
                    args=list(spec.get("args", [])),
                    env=spec.get("env"),
                )
            )
        else:
            raise ValueError(
                f"MCP server {name!r} needs either 'command' (stdio) or 'url' (http)"
            )
    return configs


class MCPTool(Tool):
    """A codeagent tool proxied to a tool on a remote MCP server."""

    risk_level = RiskLevel.EXECUTE

    def __init__(
        self,
        session: Any,
        server_name: str,
        remote_name: str,
        description: str,
        input_schema: dict[str, Any] | None,
    ) -> None:
        self._session = session
        self._remote_name = remote_name
        self.server_name = server_name
        self.name = f"mcp__{server_name}__{remote_name}"
        self.description = f"[MCP:{server_name}] {description}".rstrip()
        self.parameters = input_schema or {"type": "object", "properties": {}}

    async def execute(self, **arguments: Any) -> str:
        result = await self._session.call_tool(self._remote_name, arguments)
        parts = []
        for block in getattr(result, "content", None) or []:
            text = getattr(block, "text", None)
            parts.append(text if text is not None else str(block))
        output = "\n".join(parts) or "(no output)"
        if getattr(result, "isError", False):
            raise RuntimeError(output)
        return output


class MCPManager:
    """Connects to MCP servers and exposes their tools as codeagent tools.

    Supports stdio and streamable-HTTP transports. Usage::

        async with MCPManager(configs) as mcp:
            registry = default_tools(".")
            for tool in mcp.tools():
                registry.register(tool)
            agent = Agent(provider=..., tools=registry)
    """

    def __init__(self, configs: list[MCPServerConfig]) -> None:
        self._configs = configs
        self._tools: list[MCPTool] = []
        self._stack: AsyncExitStack | None = None

    async def connect(self) -> MCPManager:
        if not self._configs:
            return self
        try:
            import httpx
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            from mcp.client.streamable_http import streamable_http_client
        except ImportError as exc:
            raise ImportError(
                "The 'mcp' package is required for MCP support. "
                "Install it with: pip install codeagent[mcp]"
            ) from exc

        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        try:
            for config in self._configs:
                if config.transport == "http":
                    http_client = httpx.AsyncClient(headers=config.headers or {})
                    await self._stack.enter_async_context(http_client)
                    read, write = await self._stack.enter_async_context(
                        streamable_http_client(config.url, http_client=http_client)
                    )
                else:
                    from codeagent.node_runtime import augment_env, resolve_launcher

                    params = StdioServerParameters(
                        command=resolve_launcher(config.command or ""),
                        args=config.args,
                        env=augment_env(config.env),
                    )
                    read, write = await self._stack.enter_async_context(
                        stdio_client(params)
                    )
                session = await self._stack.enter_async_context(
                    ClientSession(read, write)
                )
                await session.initialize()
                listed = await session.list_tools()
                for tool_def in listed.tools:
                    # mcp 1.x exposes inputSchema; mcp 2.x uses input_schema
                    input_schema = getattr(tool_def, "input_schema", None) or getattr(
                        tool_def, "inputSchema", None
                    )
                    self._tools.append(
                        MCPTool(
                            session=session,
                            server_name=config.name,
                            remote_name=tool_def.name,
                            description=tool_def.description or "",
                            input_schema=input_schema,
                        )
                    )
        except Exception:
            await self._stack.aclose()
            self._stack = None
            raise
        return self

    def tools(self) -> list[MCPTool]:
        return list(self._tools)

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
            self._tools = []

    async def __aenter__(self) -> MCPManager:
        return await self.connect()

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()
