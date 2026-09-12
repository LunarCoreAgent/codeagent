import json
from types import SimpleNamespace

import pytest

from codeagent.mcp import MCPManager, MCPServerConfig, MCPTool, keenable, load_mcp_config
from codeagent.mcp.presets import (
    chrome_devtools_mcp,
    drawio_mcp,
    playwright_mcp,
    weapp_agent_mcp,
)


def test_load_mcp_config(tmp_path):
    config_file = tmp_path / "mcp.json"
    config_file.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "filesystem": {
                        "command": "npx",
                        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                        "env": {"DEBUG": "1"},
                    },
                    "simple": {"command": "my-server"},
                }
            }
        )
    )
    configs = load_mcp_config(config_file)
    assert len(configs) == 2
    fs = next(c for c in configs if c.name == "filesystem")
    assert fs.command == "npx"
    assert fs.args == ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    assert fs.env == {"DEBUG": "1"}
    simple = next(c for c in configs if c.name == "simple")
    assert simple.args == []


def test_load_mcp_config_missing_command(tmp_path):
    config_file = tmp_path / "bad.json"
    config_file.write_text(json.dumps({"mcpServers": {"broken": {"args": []}}}))
    with pytest.raises(ValueError, match="either 'command'"):
        load_mcp_config(config_file)


def test_load_mcp_config_http_server(tmp_path):
    config_file = tmp_path / "mcp.json"
    config_file.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "keenable": {
                        "type": "streamable-http",
                        "url": "https://api.keenable.ai/mcp",
                        "headers": {"X-API-Key": "secret"},
                    }
                }
            }
        )
    )
    configs = load_mcp_config(config_file)
    assert len(configs) == 1
    cfg = configs[0]
    assert cfg.url == "https://api.keenable.ai/mcp"
    assert cfg.headers == {"X-API-Key": "secret"}
    assert cfg.transport == "http"


def test_load_mcp_config_mixed_transports(tmp_path):
    config_file = tmp_path / "mcp.json"
    config_file.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "local": {"command": "my-server"},
                    "remote": {"url": "https://example.com/mcp"},
                }
            }
        )
    )
    configs = load_mcp_config(config_file)
    by_name = {c.name: c for c in configs}
    assert by_name["local"].transport == "stdio"
    assert by_name["remote"].transport == "http"


def test_config_transport_requires_command_or_url():
    with pytest.raises(ValueError, match="either 'command'"):
        _ = MCPServerConfig(name="empty").transport


def test_keenable_preset_keyless():
    cfg = keenable()
    assert cfg.name == "keenable"
    assert cfg.url == "https://api.keenable.ai/mcp"
    assert cfg.headers is None
    assert cfg.transport == "http"


def test_keenable_preset_with_api_key():
    cfg = keenable(api_key="abc123")
    assert cfg.headers == {"X-API-Key": "abc123"}


def test_playwright_mcp_preset():
    cfg = playwright_mcp()
    assert cfg.name == "playwright"
    assert cfg.command == "npx"
    assert "@playwright/mcp@latest" in cfg.args
    assert "--headless" in cfg.args
    assert cfg.transport == "stdio"


def test_chrome_devtools_mcp_preset():
    cfg = chrome_devtools_mcp(headless=False)
    assert cfg.name == "chrome-devtools"
    assert "chrome-devtools-mcp@latest" in cfg.args
    assert "--headless" not in cfg.args


def test_weapp_agent_mcp_preset():
    cfg = weapp_agent_mcp()
    assert cfg.name == "weapp-agent-mcp"
    assert cfg.command == "npx"
    assert cfg.args == ["-y", "@chaixueyuan/weapp-agent-mcp"]
    assert cfg.env == {"WEAPP_WS_ENDPOINT": "ws://localhost:9420"}
    assert cfg.transport == "stdio"
    custom = weapp_agent_mcp("ws://127.0.0.1:9421")
    assert custom.env == {"WEAPP_WS_ENDPOINT": "ws://127.0.0.1:9421"}


def test_drawio_mcp_preset():
    cfg = drawio_mcp()
    assert cfg.name == "drawio"
    assert cfg.command == "npx"
    assert cfg.args == ["-y", "@next-ai-drawio/mcp-server@latest"]
    assert cfg.transport == "stdio"


class FakeSession:
    def __init__(self, result):
        self._result = result
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return self._result


async def test_mcp_tool_execute_formats_text_blocks():
    result = SimpleNamespace(
        content=[SimpleNamespace(text="line one"), SimpleNamespace(text="line two")],
        isError=False,
    )
    session = FakeSession(result)
    tool = MCPTool(session, "fs", "read", "Read a file", {"type": "object"})

    assert tool.name == "mcp__fs__read"
    output = await tool.execute(path="/tmp/x")
    assert output == "line one\nline two"
    assert session.calls == [("read", {"path": "/tmp/x"})]


async def test_mcp_tool_error_raises():
    result = SimpleNamespace(content=[SimpleNamespace(text="boom")], isError=True)
    tool = MCPTool(FakeSession(result), "fs", "write", "", None)
    with pytest.raises(RuntimeError, match="boom"):
        await tool.execute()


async def test_mcp_manager_no_configs_is_noop():
    async with MCPManager([]) as mcp:
        assert mcp.tools() == []
