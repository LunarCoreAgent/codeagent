"""Tests for host-wide personalization settings."""

from __future__ import annotations

import json

from codeagent import Agent, Settings
from codeagent.core.types import LLMResponse
from codeagent.leader import Leader, WorkerConfig
from codeagent.llm.base import LLMProvider


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(self, responses: list[str]):
        super().__init__(model="mock")
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def complete(self, messages, tools=None, system=None, **kwargs):
        self.calls.append({"messages": messages, "system": system})
        content = self._responses.pop(0) if self._responses else "ok"
        return LLMResponse(content=content)


# ---------------------------------------------------------------------------
# persistence
# ---------------------------------------------------------------------------


def test_settings_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    s = Settings(
        nickname="石头",
        language="中文",
        instructions="回答先给结论",
        context="M4 Mac，项目在 ~/code",
    )
    s.save(path)

    loaded = Settings.load(path)
    assert loaded.nickname == "石头"
    assert loaded.language == "中文"
    assert loaded.instructions == "回答先给结论"
    assert loaded.context == "M4 Mac，项目在 ~/code"


def test_settings_load_missing_file_returns_empty(tmp_path):
    loaded = Settings.load(tmp_path / "nope.json")
    assert loaded.is_empty()


def test_settings_load_corrupt_file_returns_empty(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    assert Settings.load(path).is_empty()


def test_settings_ignores_unknown_fields(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"nickname": "石头", "evil": "rm -rf /"}), encoding="utf-8")
    loaded = Settings.load(path)
    assert loaded.nickname == "石头"
    assert not hasattr(loaded, "evil")


def test_settings_clear(tmp_path):
    path = tmp_path / "settings.json"
    Settings(nickname="x").save(path)
    assert Settings.clear(path) is True
    assert Settings.load(path).is_empty()
    assert Settings.clear(path) is False  # already gone


# ---------------------------------------------------------------------------
# prompt block
# ---------------------------------------------------------------------------


def test_prompt_block_empty_when_unset():
    assert Settings().prompt_block() == ""


def test_prompt_block_renders_all_fields():
    block = Settings(
        nickname="石头", language="中文",
        instructions="简洁", context="M4 Mac",
    ).prompt_block()
    assert "石头" in block
    assert "中文" in block
    assert "简洁" in block
    assert "M4 Mac" in block
    assert "Personalization" in block


# ---------------------------------------------------------------------------
# agent integration
# ---------------------------------------------------------------------------


def test_agent_injects_settings_into_system_prompt():
    provider = MockProvider(["你好"])
    agent = Agent(
        provider=provider,
        settings=Settings(nickname="石头", instructions="先给结论"),
    )
    prompt = agent._system_prompt()
    assert "石头" in prompt
    assert "先给结论" in prompt


def test_agent_without_settings_unchanged():
    provider = MockProvider(["你好"])
    agent = Agent(provider=provider, system_prompt="基础提示")
    assert agent._system_prompt() == "基础提示"


# ---------------------------------------------------------------------------
# leader / worker integration
# ---------------------------------------------------------------------------


def test_worker_agent_receives_settings(tmp_path):
    from codeagent.leader.worker import build_worker_agent

    config = WorkerConfig(name="w1", provider="openai", api_key="test-key")
    agent = build_worker_agent(
        config, tmp_path, settings=Settings(context="测试上下文")
    )
    assert "测试上下文" in agent._system_prompt()


def test_leader_planner_uses_settings(tmp_path):
    provider = MockProvider(['{"assignments": []}'])
    leader = Leader(
        provider=provider,
        workers=[WorkerConfig(name="w1", provider="openai")],
        root=tmp_path,
        settings=Settings(language="中文"),
    )
    import asyncio

    asyncio.run(leader.command("做点什么"))
    planner_call = next(
        c for c in provider.calls if "任务拆解" in (c.get("system") or "")
    )
    assert "中文" in planner_call["system"]
