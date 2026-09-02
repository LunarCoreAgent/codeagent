"""Leader: command planning, multi-model dispatch, progress board."""

import json

from codeagent import Leader, ProgressBoard, WorkerConfig, load_workers_yaml
from codeagent.core.types import LLMResponse
from codeagent.llm.base import LLMProvider


class ScriptedProvider(LLMProvider):
    name = "scripted"

    def __init__(self, responses: list[str]):
        super().__init__(model="scripted")
        self._responses = list(responses)
        self.prompts: list[str] = []

    async def complete(self, messages, tools=None, system=None, **kwargs):
        self.prompts.append(messages[-1].content)
        content = self._responses.pop(0) if self._responses else "ok"
        return LLMResponse(content=content)


class WorkerSpyProvider(ScriptedProvider):
    """Pretends to use tools: on first call issues nothing, just answers."""

    def __init__(self, tag: str, answer: str):
        super().__init__([answer])
        self.tag = tag
        self.systems: list[str] = []

    async def complete(self, messages, tools=None, system=None, **kwargs):
        self.systems.append(system or "")
        return await super().complete(messages, tools, system, **kwargs)


def roster() -> list[WorkerConfig]:
    return [
        WorkerConfig(name="claude", provider="anthropic", description="代码与审查"),
        WorkerConfig(name="qwen", provider="ollama", model="qwen2.5-coder:7b", description="本地快速执行"),
    ]


# ---------------------------------------------------------------------------
# ProgressBoard
# ---------------------------------------------------------------------------


def test_board_tracks_and_summarizes():
    board = ProgressBoard()
    board.register("t1", "写测试", "claude")
    board.register("t2", "写文档", "qwen")
    board.update("t1", "running")
    board.update("t1", "done", "完成 5 个用例")
    board.update("t2", "failed", "模型超时")
    snap = board.snapshot()
    assert snap["total"] == 2 and snap["done"] == 1 and snap["failed"] == 1
    text = board.summary()
    assert "写测试" in text and "失败" in text and "qwen" in text


def test_board_empty_summary():
    assert "没有任务" in ProgressBoard().summary()


def test_board_on_change_fires():
    seen = []
    board = ProgressBoard(on_change=lambda r: seen.append((r.task_id, r.status)))
    board.register("t1", "x", "w")
    board.update("t1", "done")
    assert seen == [("t1", "pending"), ("t1", "done")]


# ---------------------------------------------------------------------------
# workers yaml
# ---------------------------------------------------------------------------


def test_load_workers_yaml(tmp_path):
    f = tmp_path / "workers.yaml"
    f.write_text(
        "workers:\n"
        "  - name: claude\n"
        "    provider: anthropic\n"
        "    description: 代码\n"
        "  - name: local\n"
        "    provider: ollama\n"
        "    model: qwen2.5-coder:7b\n"
    )
    workers = load_workers_yaml(f)
    assert len(workers) == 2
    assert workers[1].model == "qwen2.5-coder:7b"


def test_load_workers_yaml_rejects_unknown_field(tmp_path):
    f = tmp_path / "workers.yaml"
    f.write_text("workers:\n  - name: x\n    provder: typo\n")
    try:
        load_workers_yaml(f)
        assert False, "should have raised"
    except ValueError as exc:
        assert "unknown field" in str(exc)


# ---------------------------------------------------------------------------
# Leader
# ---------------------------------------------------------------------------


def _make_leader(monkeypatch, tmp_path, plan: dict, worker_answers: dict[str, str]):
    """Leader with scripted planner + spy workers (no real LLM calls)."""
    import codeagent.leader.worker as worker_mod

    spies: dict[str, WorkerSpyProvider] = {}

    def fake_build(config, root, **kwargs):
        spy = WorkerSpyProvider(config.name, worker_answers[config.name])
        spies[config.name] = spy
        from codeagent.core.agent import Agent

        return Agent(provider=spy, system_prompt=kwargs.get("project_context", ""))

    monkeypatch.setattr("codeagent.leader.leader.build_worker_agent", fake_build)

    planner = ScriptedProvider([json.dumps(plan, ensure_ascii=False)])
    leader = Leader(provider=planner, workers=roster(), root=tmp_path)
    return leader, spies


async def test_leader_dispatches_parallel_tasks(monkeypatch, tmp_path):
    plan = {
        "assignments": [
            {"worker": "claude", "task": "写单元测试", "depends_on": []},
            {"worker": "qwen", "task": "写 README", "depends_on": []},
        ],
        "reply": "好的，两路并行。",
    }
    leader, spies = _make_leader(
        monkeypatch, tmp_path, plan, {"claude": "测试已写", "qwen": "文档已写"}
    )
    reply = await leader.command("把测试和文档都搞了")
    assert "两路并行" in reply
    assert "测试已写" in reply and "文档已写" in reply
    assert leader.board.snapshot()["done"] == 2
    # both workers actually received their tasks
    assert any("写单元测试" in p for p in spies["claude"].prompts)
    assert any("写 README" in p for p in spies["qwen"].prompts)


async def test_leader_respects_dependencies(monkeypatch, tmp_path):
    plan = {
        "assignments": [
            {"worker": "claude", "task": "设计 schema", "depends_on": []},
            {"worker": "qwen", "task": "按 schema 写迁移", "depends_on": [0]},
        ],
        "reply": "",
    }
    leader, spies = _make_leader(
        monkeypatch, tmp_path, plan, {"claude": "schema-v1", "qwen": "migration done"}
    )
    reply = await leader.command("设计数据库并写迁移")
    assert "migration done" in reply
    # worker 2 received worker 1's output as upstream context
    assert any("schema-v1" in p for p in spies["qwen"].prompts)


async def test_leader_answers_progress_query_without_llm(monkeypatch, tmp_path):
    plan = {"assignments": [{"worker": "claude", "task": "干活", "depends_on": []}], "reply": ""}
    leader, _ = _make_leader(monkeypatch, tmp_path, plan, {"claude": "done"})
    await leader.command("干活")
    answer = await leader.command("现在进度怎么样？")
    assert "已完成" in answer or "完成" in answer
    assert "干活" in answer


async def test_leader_handles_unplannable_command(monkeypatch, tmp_path):
    planner = ScriptedProvider(["这不是 JSON，直接回答"])
    leader = Leader(provider=planner, workers=roster(), root=tmp_path)
    reply = await leader.command("你好")
    assert "这不是 JSON" in reply
    assert leader.board.snapshot()["total"] == 0


async def test_leader_marks_failures(monkeypatch, tmp_path):
    import codeagent.leader.leader as leader_mod
    from codeagent.core.agent import Agent

    class ExplodingProvider(ScriptedProvider):
        async def complete(self, messages, tools=None, system=None, **kwargs):
            raise RuntimeError("model exploded")

    def fake_build(config, root, **kwargs):
        return Agent(provider=ExplodingProvider([]))

    monkeypatch.setattr("codeagent.leader.leader.build_worker_agent", fake_build)
    plan = {"assignments": [{"worker": "claude", "task": "会失败的任务", "depends_on": []}], "reply": ""}
    leader = Leader(
        provider=ScriptedProvider([json.dumps(plan)]),
        workers=roster(), root=tmp_path, worker_retries=0,
    )
    reply = await leader.command("试试")
    assert "失败" in reply
    assert leader.board.snapshot()["failed"] == 1


async def test_leader_retries_transient_failure(monkeypatch, tmp_path):
    """A worker that fails once then succeeds is recovered by retry."""
    import asyncio as asyncio_mod

    from codeagent.core.agent import Agent

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(asyncio_mod, "sleep", no_sleep)

    class FlakyProvider(ScriptedProvider):
        def __init__(self):
            super().__init__(["修好了"])
            self.calls = 0

        async def complete(self, messages, tools=None, system=None, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("Error code: 503")
            return await super().complete(messages, tools=tools, system=system, **kwargs)

    flaky = FlakyProvider()

    def fake_build(config, root, **kwargs):
        return Agent(provider=flaky)

    monkeypatch.setattr("codeagent.leader.leader.build_worker_agent", fake_build)
    plan = {"assignments": [{"worker": "claude", "task": "先 503 后成功", "depends_on": []}], "reply": ""}
    leader = Leader(provider=ScriptedProvider([json.dumps(plan)]), workers=roster(), root=tmp_path)
    reply = await leader.command("试试")
    assert "修好了" in reply
    assert "失败" not in reply
    assert flaky.calls == 2
    assert leader.board.snapshot()["done"] == 1


async def test_leader_retry_exhausted_marks_failure(monkeypatch, tmp_path):
    """Retries exhausted → task marked failed (with backoff between tries)."""
    import asyncio as asyncio_mod

    from codeagent.core.agent import Agent

    sleeps: list[float] = []

    async def spy_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio_mod, "sleep", spy_sleep)

    class ExplodingProvider(ScriptedProvider):
        async def complete(self, messages, tools=None, system=None, **kwargs):
            raise RuntimeError("Error code: 503")

    def fake_build(config, root, **kwargs):
        return Agent(provider=ExplodingProvider([]))

    monkeypatch.setattr("codeagent.leader.leader.build_worker_agent", fake_build)
    plan = {"assignments": [{"worker": "claude", "task": "一直 503", "depends_on": []}], "reply": ""}
    leader = Leader(
        provider=ScriptedProvider([json.dumps(plan)]),
        workers=roster(), root=tmp_path, worker_retries=2,
    )
    reply = await leader.command("试试")
    assert "失败" in reply
    assert sleeps == [5, 10]
    assert leader.board.snapshot()["failed"] == 1


async def test_leader_max_parallel_limits_concurrency(monkeypatch, tmp_path):
    """max_parallel caps how many workers run at once."""
    import asyncio as asyncio_mod

    from codeagent.core.agent import Agent

    active = 0
    peak = 0

    class SlowProvider(ScriptedProvider):
        async def complete(self, messages, tools=None, system=None, **kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio_mod.sleep(0.05)
            active -= 1
            return await super().complete(messages, tools=tools, system=system, **kwargs)

    def fake_build(config, root, **kwargs):
        return Agent(provider=SlowProvider(["done"]))

    monkeypatch.setattr("codeagent.leader.leader.build_worker_agent", fake_build)
    plan = {
        "assignments": [
            {"worker": "claude", "task": "a", "depends_on": []},
            {"worker": "qwen", "task": "b", "depends_on": []},
            {"worker": "claude", "task": "c", "depends_on": []},
        ],
        "reply": "",
    }
    leader = Leader(
        provider=ScriptedProvider([json.dumps(plan)]),
        workers=roster(), root=tmp_path, worker_retries=0, max_parallel=1,
    )
    reply = await leader.command("试试")
    assert reply.count("done") == 3
    assert peak == 1
