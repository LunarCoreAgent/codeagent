"""Leader: receives voice/text commands, plans, dispatches to worker models.

Fuses HomeRail's ideas into a single seat:
- one leader, many worker models (smart brain, efficient workers)
- workers may collaborate on one task or run several tasks in parallel
- progress board is queryable at any moment (voice readout included)
- every worker understands the project and can use all skills/tools
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from codeagent.settings import Settings

from codeagent.core.budget import Budget
from codeagent.core.types import Message
from codeagent.harness.adapters import CliHarness, discover_harnesses
from codeagent.harness.tool import AskHarnessTool
from codeagent.leader.archive import RunArchive
from codeagent.leader.progress import ProgressBoard
from codeagent.leader.worker import WorkerConfig, build_worker_agent
from codeagent.llm.base import LLMProvider
from codeagent.memory.facts import parse_json_object
from codeagent.skills.skill import SkillLibrary
from codeagent.tools import ToolRegistry, default_tools

PLAN_PROMPT = """\
你是领导。下面是你的工人花名册、项目概况和老板的命令。把命令拆解成任务 \
分派给工人：可以多人协作一个任务（用依赖串行），也可以多人并行多个任务。

工人花名册：
{roster}

项目概况：
{project}

老板命令：
{command}

规则：
- 每个分派指定 worker（必须是花名册里的 name）、task（具体、可执行）、
  depends_on（依赖的其他分派序号列表，从 0 开始；无依赖则空列表）
- 按工人特长分配；不确定时给第一个工人
- 任务描述要自包含——工人看不到老板的原始命令
- 只返回 JSON：
{{"assignments": [{{"worker": "名字", "task": "...", "depends_on": []}}], \
"reply": "一句给老板的简短回话"}}"""

_PROGRESS_PATTERN = re.compile(
    r"进度|进展|状态|怎么样|完成了吗|做好了吗|progress|status|report", re.IGNORECASE
)


def _is_progress_query(text: str) -> bool:
    return bool(_PROGRESS_PATTERN.search(text))


def project_context(root: Path, max_entries: int = 40, readme_chars: int = 1200) -> str:
    """A compact project brief so every worker understands the workspace."""
    root = Path(root)
    parts: list[str] = []
    try:
        entries = sorted(p.name for p in root.iterdir() if not p.name.startswith("."))
        parts.append("根目录: " + ", ".join(entries[:max_entries]))
    except OSError:
        pass
    for name in ("README.md", "README.zh-CN.md", "README.txt"):
        readme = root / name
        if readme.is_file():
            try:
                parts.append(f"{name} 摘要:\n" + readme.read_text(encoding="utf-8")[:readme_chars])
            except OSError:
                pass
            break
    return "\n\n".join(parts) or "(空项目目录)"


class Leader:
    """The boss seat: command in, coordinated work out, progress anytime."""

    def __init__(
        self,
        provider: LLMProvider,
        workers: list[WorkerConfig],
        root: str | Path = ".",
        skills: SkillLibrary | None = None,
        registry_factory: Callable[[], ToolRegistry] | None = None,
        board: ProgressBoard | None = None,
        budget: Budget | None = None,
        max_iterations: int = 30,
        harnesses: list[CliHarness] | None = None,
        escalate: bool = True,
        archive: RunArchive | None = None,
        settings: "Settings | None" = None,
        on_event: Callable[[str, Any], None] | None = None,
        worker_retries: int = 2,
        max_parallel: int | None = None,
    ) -> None:
        if not workers:
            raise ValueError("Leader needs at least one worker")
        self.provider = provider
        self.worker_configs = {w.name: w for w in workers}
        self.root = Path(root)
        self.skills = skills
        self._registry_factory = registry_factory or (lambda: default_tools(self.root))
        self.board = board or ProgressBoard()
        self.budget = budget
        self.max_iterations = max_iterations
        self.harnesses = harnesses if harnesses is not None else discover_harnesses()
        self.escalate = escalate
        self.archive = archive
        self.settings = settings
        self.on_event = on_event
        self.worker_retries = max(0, worker_retries)
        # Cap in-flight workers; local multi-model on one server 503s otherwise
        self.max_parallel = max(1, max_parallel) if max_parallel else None
        self._project = project_context(self.root)
        self._task_counter = 0

    def _emit(self, kind: str, data: Any = None) -> None:
        if self.on_event is not None:
            self.on_event(kind, data)

    # ------------------------------------------------------------------
    # main entry
    # ------------------------------------------------------------------

    async def command(self, text: str) -> str:
        """Handle one boss command (from text or voice transcription)."""
        text = text.strip()
        if not text:
            return "没听清，请再说一次。"
        if _is_progress_query(text):
            return self.board.summary()

        plan = await self._plan(text)
        assignments = plan.get("assignments") or []
        if not assignments:
            return plan.get("reply") or "这个命令我没拆出任务，请说得更具体些。"

        report = await self._dispatch(assignments)
        ack = plan.get("reply", "")
        reply = (ack + "\n\n" if ack else "") + report
        if self.archive is not None:
            try:
                self.archive.save(self.root, text, reply, self.board.snapshot())
            except OSError:
                pass  # archiving must never break the command loop
        return reply

    # ------------------------------------------------------------------
    # planning
    # ------------------------------------------------------------------

    async def _plan(self, command: str) -> dict[str, Any]:
        roster = "\n".join(
            f"- {w.name}（{w.provider}{'/' + w.model if w.model else ''}）"
            f"{': ' + w.description if w.description else ''}"
            for w in self.worker_configs.values()
        )
        prompt = PLAN_PROMPT.format(
            roster=roster, project=self._project, command=command
        )
        system = "你是任务拆解与分派专家，只输出 JSON。"
        if self.settings is not None:
            block = self.settings.prompt_block()
            if block:
                system += "\n\n" + block
        response = await self.provider.complete(
            messages=[Message.user(prompt)],
            system=system,
        )
        plan = parse_json_object(response.content)
        if not plan:
            # planner answered in prose instead of JSON: pass it through
            return {"assignments": [], "reply": response.content.strip()[:500]}
        valid: list[dict[str, Any]] = []
        for item in plan.get("assignments") or []:
            if not isinstance(item, dict):
                continue
            worker = item.get("worker")
            task = item.get("task")
            if worker in self.worker_configs and isinstance(task, str) and task.strip():
                deps = item.get("depends_on") or []
                valid.append(
                    {
                        "worker": worker,
                        "task": task.strip(),
                        "depends_on": [int(d) for d in deps if isinstance(d, int) or (isinstance(d, str) and d.isdigit())],
                    }
                )
        return {"assignments": valid, "reply": str(plan.get("reply", ""))}

    # ------------------------------------------------------------------
    # dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, assignments: list[dict[str, Any]]) -> str:
        """Run assignments in dependency batches; parallel within a batch."""
        remaining = list(enumerate(assignments))
        done_outputs: dict[int, str] = {}
        failures: dict[int, str] = {}

        while remaining:
            ready = [
                (i, a)
                for i, a in remaining
                if all(d in done_outputs or d in failures for d in a["depends_on"])
            ]
            if not ready:  # dependency cycle or dangling index
                ready = remaining
            sem = (
                asyncio.Semaphore(self.max_parallel)
                if self.max_parallel is not None
                else None
            )

            async def guarded(i: int, a: dict[str, Any]) -> tuple[bool, str]:
                if sem is None:
                    return await self._run_assignment(i, a, done_outputs)
                async with sem:
                    return await self._run_assignment(i, a, done_outputs)

            results = await asyncio.gather(*(guarded(i, a) for i, a in ready))
            ready_ids = {i for i, _ in ready}
            for (i, _), (ok, output) in zip(ready, results):
                if ok:
                    done_outputs[i] = output
                else:
                    failures[i] = output
            remaining = [(i, a) for i, a in remaining if i not in ready_ids]

        lines = ["📋 工作汇报："]
        for i, a in enumerate(assignments):
            if i in done_outputs:
                lines.append(f"\n### 任务 {i + 1}（{a['worker']}）\n{done_outputs[i]}")
            else:
                lines.append(f"\n### 任务 {i + 1}（{a['worker']}）❌ 失败：{failures[i]}")
        return "\n".join(lines)

    async def _run_assignment(
        self, index: int, assignment: dict[str, Any], done_outputs: dict[int, str]
    ) -> tuple[bool, str]:
        self._task_counter += 1
        task_id = f"t{self._task_counter}"
        title = assignment["task"][:60]
        worker_name = assignment["worker"]
        self.board.register(task_id, title, worker_name)
        self.board.update(task_id, "running")
        self._emit("task_start", {"id": task_id, "worker": worker_name, "task": title})

        config = self.worker_configs[worker_name]
        registry = self._registry_factory()
        if self.harnesses:
            registry.register(AskHarnessTool(self.harnesses, cwd=self.root))
        agent = build_worker_agent(
            config,
            self.root,
            registry=registry,
            skills=self.skills,
            settings=self.settings,
            project_context=self._project,
            max_iterations=self.max_iterations,
            budget=self.budget,
        )
        task_text = assignment["task"]
        dep_context = [
            done_outputs[d] for d in assignment["depends_on"] if d in done_outputs
        ]
        if dep_context:
            task_text += "\n\n[上游成果]\n" + "\n\n".join(dep_context)
        output: str | None = None
        last_error = ""
        for attempt in range(self.worker_retries + 1):
            try:
                output = await agent.run(task_text)
                break
            except Exception as exc:  # noqa: BLE001 — retried, then escalated
                last_error = str(exc)
                if attempt < self.worker_retries:
                    delay = 5 * (attempt + 1)
                    self.board.update(
                        task_id, "running", f"第 {attempt + 1} 次失败，{delay}s 后重试"
                    )
                    self._emit(
                        "task_retry",
                        {"id": task_id, "attempt": attempt + 1, "error": last_error[:200]},
                    )
                    await asyncio.sleep(delay)
        if output is None:
            escalated = await self._escalate(task_id, assignment, last_error)
            if escalated is not None:
                return True, escalated
            self.board.update(task_id, "failed", last_error[:200])
            self._emit("task_failed", {"id": task_id, "error": last_error})
            return False, last_error
        self.board.update(task_id, "done", output[:120])
        self._emit("task_done", {"id": task_id, "output": output})
        return True, output

    async def _escalate(
        self, task_id: str, assignment: dict[str, Any], error: str
    ) -> str | None:
        """Worker failed: hand the task to an external agent platform."""
        if not self.escalate or not self.harnesses:
            return None
        harness = self.harnesses[0]
        self._emit("task_escalated", {"id": task_id, "harness": harness.name})
        prompt = (
            f"项目目录：{self.root}\n\n"
            f"任务：{assignment['task']}\n\n"
            f"背景：另一个 agent 尝试完成此任务但失败了（{error[:300]}）。"
            "请你直接在该项目目录中完成它，并简要汇报做了什么。"
        )
        result = await harness.run(prompt, cwd=self.root)
        if not result.ok:
            return None
        output = f"（由外部平台 {harness.name} 完成）\n{result.output}"
        self.board.update(task_id, "done", f"升级至 {harness.name} 完成")
        self._emit("task_done", {"id": task_id, "output": output})
        return output
