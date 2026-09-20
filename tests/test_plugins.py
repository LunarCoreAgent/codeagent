"""Agent auto-extracts which MCP / builtin plugin to use."""

from codeagent import Agent
from codeagent.core.types import LLMResponse
from codeagent.llm.base import LLMProvider
from codeagent.mcp.presets import MOTIONSITES_MCP_URL, SILEX_MCP_URL, motionsites_mcp, silex_mcp
from codeagent.plugins import (
    PLUGIN_CATALOG,
    UsePluginTool,
    match_work_plugins,
    plugin_prompt_block,
)


class ScriptedProvider(LLMProvider):
    name = "scripted"

    def __init__(self, responses: list[str]):
        super().__init__(model="scripted")
        self._responses = list(responses)

    async def complete(self, messages, tools=None, system=None, **kwargs):
        content = self._responses.pop(0) if self._responses else "done"
        return LLMResponse(content=content)


def test_generic_landing_page_does_not_force_silex():
    names = {p.name for p in match_work_plugins("做个落地页")}
    assert "silex" not in names
    assert "motionsites" not in names


def test_silex_task_extracts_silex_plugin():
    names = {p.name for p in match_work_plugins("用 Silex 可视化建站")}
    assert "silex" in names
    assert match_work_plugins("GrapesJS 无代码拖拽建站")[0].name == "silex"


def test_motionsites_task_extracts_motionsites_plugin():
    names = {p.name for p in match_work_plugins("用 MotionSites 付费设计提示词")}
    assert "motionsites" in names


def test_plugin_prompt_mentions_oauth_and_local():
    block = plugin_prompt_block(["silex", "motionsites"])
    assert "silex" in block
    assert "6807" in block
    assert "401" in block or "OAuth" in block or "授权" in block


async def test_use_plugin_lists_and_loads():
    activated: list[str] = []
    tool = UsePluginTool(lambda names: activated.extend(names) or [])
    catalog = await tool.execute()
    assert "silex" in catalog
    assert "motionsites" in catalog
    loaded = await tool.execute(name="silex")
    assert "127.0.0.1:6807" in loaded
    assert "silex" in activated
    missing = await tool.execute(name="no-such-plugin")
    assert "未找到" in missing


def test_plugin_catalog_covers_existing_mcp_presets():
    names = {p.name for p in PLUGIN_CATALOG}
    assert {"silex", "motionsites", "drawio", "dbx", "deveco-mcp", "keenable"} <= names


def test_silex_and_motionsites_presets():
    silex = silex_mcp()
    assert silex.url == SILEX_MCP_URL
    assert silex.transport == "http"
    ms = motionsites_mcp()
    assert ms.url == MOTIONSITES_MCP_URL
    assert ms.transport == "http"


async def test_agent_auto_extracts_silex_plugin():
    captured: list[str] = []
    events: list[str] = []

    class SpyProvider(ScriptedProvider):
        async def complete(self, messages, tools=None, system=None, **kwargs):
            captured.append(system or "")
            names = [t.get("name") for t in (tools or [])]
            assert "use_plugin" in names
            return await super().complete(messages, tools, system, **kwargs)

    agent = Agent(
        provider=SpyProvider(["ok"]),
        on_event=lambda e: events.append(e.type),
    )
    assert await agent.run("用 Silex 可视化建站") == "ok"
    assert "plugins_activated" in events
    assert "silex" in captured[0]
    assert "本次插件" in captured[0]


async def test_agent_generic_landing_skips_silex_plugin():
    events: list[tuple[str, object]] = []
    agent = Agent(
        provider=ScriptedProvider(["ok"]),
        on_event=lambda e: events.append((e.type, e.data)),
    )
    assert await agent.run("做个落地页") == "ok"
    plugin_names = [
        name
        for typ, data in events
        if typ == "plugins_activated" and isinstance(data, list)
        for name in data
    ]
    assert "silex" not in plugin_names
    assert "motionsites" not in plugin_names
