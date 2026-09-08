"""Harness adapters: discovery, headless execution, worker tool, escalation."""

import json
import os
import stat

from codeagent import (
    AskHarnessTool,
    CliHarness,
    Leader,
    RunArchive,
    WorkerConfig,
    discover_harnesses,
)
from codeagent.core.types import LLMResponse
from codeagent.llm.base import LLMProvider


def make_fake_harness(tmp_path, name="fakeagent", script_body=None) -> CliHarness:
    """Create a fake CLI agent executable on disk."""
    exe = tmp_path / name
    body = script_body or f'#!/bin/bash\necho "FAKE-OUTPUT: $2"\n'
    exe.write_text(body)
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return CliHarness(name, (str(exe), "run", "{prompt}"), timeout=10)


# ---------------------------------------------------------------------------
# discovery & execution
# ---------------------------------------------------------------------------


def test_discover_harnesses_finds_available(tmp_path):
    fake = make_fake_harness(tmp_path)
    found = discover_harnesses(extra=[fake])
    assert any(h.name == "fakeagent" for h in found)


def test_discover_harnesses_skips_missing(tmp_path):
    ghost = CliHarness("ghost", ("/nonexistent/path/ghost", "{prompt}"))
    # 不存在的 binary 必须被过滤；机器上已安装的 harness 不应混入
    found = discover_harnesses(extra=[ghost])
    assert all(h.name != "ghost" for h in found)


async def test_harness_run_returns_output(tmp_path):
    fake = make_fake_harness(tmp_path)
    result = await fake.run("帮我修 bug")
    assert result.ok
    assert "帮我修 bug" in result.output


async def test_harness_run_reports_failure(tmp_path):
    fake = make_fake_harness(tmp_path, script_body="#!/bin/bash\nexit 3\n")
    result = await fake.run("task")
    assert not result.ok
    assert result.exit_code == 3


# ---------------------------------------------------------------------------
# ask_external_agent tool
# ---------------------------------------------------------------------------


async def test_tool_calls_first_available_harness(tmp_path):
    fake = make_fake_harness(tmp_path)
    tool = AskHarnessTool([fake], cwd=tmp_path)
    result = await tool.execute("帮忙写个函数")
    assert "fakeagent" in result
    assert "帮忙写个函数" in result


async def test_tool_reports_when_no_harness():
    tool = AskHarnessTool([])
    result = await tool.execute("help")
    assert "未发现可用的外部 agent 平台" in result


async def test_tool_rejects_unknown_harness_name(tmp_path):
    fake = make_fake_harness(tmp_path)
    tool = AskHarnessTool([fake])
    result = await tool.execute("help", harness="nonexistent")
    assert "不可用" in result and "fakeagent" in result


def test_tool_risk_level_is_execute():
    from codeagent import RiskLevel

    assert AskHarnessTool([]).risk_level == RiskLevel.EXECUTE


# ---------------------------------------------------------------------------
# leader escalation
# ---------------------------------------------------------------------------


class ExplodingProvider(LLMProvider):
    name = "exploding"

    def __init__(self):
        super().__init__(model="exploding")

    async def complete(self, messages, tools=None, system=None, **kwargs):
        raise RuntimeError("模型能力不足，无法完成")


class ScriptedProvider(LLMProvider):
    name = "scripted"

    def __init__(self, responses: list[str]):
        super().__init__(model="scripted")
        self._responses = list(responses)

    async def complete(self, messages, tools=None, system=None, **kwargs):
        content = self._responses.pop(0) if self._responses else "ok"
        return LLMResponse(content=content)


async def test_leader_escalates_failed_task_to_harness(monkeypatch, tmp_path):
    import codeagent.leader.leader as leader_mod
    from codeagent.core.agent import Agent

    monkeypatch.setattr(
        leader_mod,
        "build_worker_agent",
        lambda config, root, **kw: Agent(provider=ExplodingProvider()),
    )
    fake = make_fake_harness(tmp_path)
    plan = {"assignments": [{"worker": "w1", "task": "困难任务", "depends_on": []}], "reply": ""}
    leader = Leader(
        provider=ScriptedProvider([json.dumps(plan)]),
        workers=[WorkerConfig(name="w1")],
        root=tmp_path,
        harnesses=[fake],
    )
    reply = await leader.command("做这个")
    assert "外部平台 fakeagent 完成" in reply
    assert "困难任务" in reply
    snap = leader.board.snapshot()
    assert snap["done"] == 1 and snap["failed"] == 0


async def test_leader_marks_failure_when_escalation_disabled(monkeypatch, tmp_path):
    import codeagent.leader.leader as leader_mod
    from codeagent.core.agent import Agent

    monkeypatch.setattr(
        leader_mod,
        "build_worker_agent",
        lambda config, root, **kw: Agent(provider=ExplodingProvider()),
    )
    fake = make_fake_harness(tmp_path)
    plan = {"assignments": [{"worker": "w1", "task": "困难任务", "depends_on": []}], "reply": ""}
    leader = Leader(
        provider=ScriptedProvider([json.dumps(plan)]),
        workers=[WorkerConfig(name="w1")],
        root=tmp_path,
        harnesses=[fake],
        escalate=False,
    )
    reply = await leader.command("做这个")
    assert "失败" in reply
    assert leader.board.snapshot()["failed"] == 1


async def test_worker_registry_gets_harness_tool(monkeypatch, tmp_path):
    """Workers can see ask_external_agent in their tool registry."""
    import codeagent.leader.leader as leader_mod
    from codeagent.core.agent import Agent

    captured = {}

    def spy_build(config, root, **kw):
        captured["registry"] = kw.get("registry")
        return Agent(provider=ScriptedProvider(["done"]))

    monkeypatch.setattr(leader_mod, "build_worker_agent", spy_build)
    fake = make_fake_harness(tmp_path)
    plan = {"assignments": [{"worker": "w1", "task": "t", "depends_on": []}], "reply": ""}
    leader = Leader(
        provider=ScriptedProvider([json.dumps(plan)]),
        workers=[WorkerConfig(name="w1")],
        root=tmp_path,
        harnesses=[fake],
    )
    await leader.command("go")
    assert captured["registry"].get("ask_external_agent") is not None


# ---------------------------------------------------------------------------
# local archive
# ---------------------------------------------------------------------------


def test_archive_save_and_list(tmp_path):
    archive = RunArchive(tmp_path / "runs")
    archive.save("/tmp/myproj", "写测试", "完成了", {"total": 1})
    archive.save("/tmp/myproj", "写文档", "也完成了", {"total": 2})
    archive.save("/tmp/other", "别的项目", "ok", {"total": 1})

    runs = archive.list("/tmp/myproj")
    assert len(runs) == 2
    assert runs[0]["command"] == "写文档"  # newest first
    assert runs[0]["board"]["total"] == 2
    assert len(archive.list()) == 3
    # files live under the archive root — all local
    for path in (tmp_path / "runs").rglob("*.json"):
        assert "runs" in str(path)


async def test_leader_archives_each_command(monkeypatch, tmp_path):
    import codeagent.leader.leader as leader_mod
    from codeagent.core.agent import Agent

    monkeypatch.setattr(
        leader_mod,
        "build_worker_agent",
        lambda config, root, **kw: Agent(provider=ScriptedProvider(["干完了"])),
    )
    archive = RunArchive(tmp_path / "runs")
    plan = {"assignments": [{"worker": "w1", "task": "存档任务", "depends_on": []}], "reply": ""}
    leader = Leader(
        provider=ScriptedProvider([json.dumps(plan)]),
        workers=[WorkerConfig(name="w1")],
        root=tmp_path,
        harnesses=[],
        archive=archive,
    )
    await leader.command("把这件事存档")
    runs = archive.list(tmp_path)
    assert len(runs) == 1
    assert runs[0]["command"] == "把这件事存档"
    assert "干完了" in runs[0]["reply"]


async def test_progress_query_not_archived(tmp_path):
    archive = RunArchive(tmp_path / "runs")
    leader = Leader(
        provider=ScriptedProvider([]),
        workers=[WorkerConfig(name="w1")],
        root=tmp_path,
        harnesses=[],
        archive=archive,
    )
    await leader.command("进度怎么样？")
    assert archive.list(tmp_path) == []
