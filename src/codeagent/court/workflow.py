"""The Court: 三省六部 multi-agent orchestration workflow.

一道旨意的完整旅程：

    旨意 → 中书省规划 → 门下省审议（可封驳，打回重规划）
        → 尚书省派发 → 六部并行执行 → 尚书省汇总回奏

Every step is validated by a protected state machine and written to an
audit trail, so results are reproducible, auditable, and reviewable —
the institutional quality gate that plain "agents chatting" lacks.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codeagent.core.agent import Agent
from codeagent.core.types import Usage
from codeagent.court.audit import AuditLog
from codeagent.court.roles import (
    DEFAULT_ROLES,
    EXECUTOR_DEPTS,
    FALLBACK_DEPT,
    MENXIA,
    SHANGSHU,
    ZHONGSHU,
    CourtRole,
)
from codeagent.court.state import TaskState, TaskStateMachine
from codeagent.llm.base import LLMProvider
from codeagent.memory.facts import parse_json_object
from codeagent.tools.base import ToolRegistry


@dataclass
class SubTask:
    dept: str
    title: str
    task: str


@dataclass
class SubTaskResult:
    subtask: SubTask
    output: str
    ok: bool


@dataclass
class CourtReport:
    edict: str
    plan: list[SubTask]
    review_rounds: int          # how many times 门下省 reviewed (>1 means 封驳 happened)
    results: list[SubTaskResult]
    report: str                 # 回奏：final aggregated summary
    usage: Usage = field(default_factory=Usage)
    audit: AuditLog | None = None


class ReviewRejectedError(RuntimeError):
    """Strict mode: the plan was still rejected after all review rounds."""


class Court:
    """Orchestrates role agents through the plan→review→execute pipeline."""

    def __init__(
        self,
        provider: LLMProvider,
        roles: dict[str, CourtRole] | None = None,
        tools: ToolRegistry | None = None,
        max_review_rounds: int = 3,
        strict_review: bool = False,
        audit_path: str | Path | None = None,
        max_subtask_iterations: int = 20,
    ) -> None:
        self.provider = provider
        self.roles = roles or DEFAULT_ROLES
        self.tools = tools
        self.max_review_rounds = max_review_rounds
        self.strict_review = strict_review
        self.audit = AuditLog(audit_path)
        self.max_subtask_iterations = max_subtask_iterations
        self._agents: list[Agent] = []

    def _agent(self, role: CourtRole) -> Agent:
        agent = Agent(
            provider=self.provider,
            tools=self.tools,
            system_prompt=role.system_prompt,
            max_iterations=self.max_subtask_iterations,
        )
        self._agents.append(agent)
        return agent

    async def run(self, edict: str) -> CourtReport:
        sm = TaskStateMachine()
        self._agents = []
        self.audit.record("edict", text=edict)

        # -- 中书省规划 → 门下省审议（封驳循环） ------------------------------
        plan: list[SubTask] = []
        feedback: str | None = None
        rounds = 0
        approved = False

        sm.transition(TaskState.PLANNING)
        while rounds < self.max_review_rounds and not approved:
            plan = await self._plan(edict, feedback)
            self.audit.record("plan", round=rounds + 1,
                              subtasks=[s.__dict__ for s in plan])

            sm.transition(TaskState.REVIEWING)
            rounds += 1
            verdict, feedback = await self._review(edict, plan)
            self.audit.record("review", round=rounds, verdict=verdict,
                              feedback=feedback or "")

            if verdict == "approve":
                sm.transition(TaskState.DISPATCHED)
                approved = True
            else:
                sm.transition(TaskState.REJECTED)   # 封驳
                if rounds < self.max_review_rounds:
                    sm.transition(TaskState.PLANNING)  # 打回重规划

        if not approved:
            if self.strict_review:
                self.audit.record("failed", reason="review rejected")
                raise ReviewRejectedError(
                    f"门下省封驳：{self.max_review_rounds} 轮审议仍未通过。"
                    f"最后意见：{feedback}"
                )
            # 默认宽松模式：记录在案，按最后一版方案执行
            self.audit.record("review_override", feedback=feedback or "")
            if sm.state is TaskState.REJECTED:
                sm.transition(TaskState.PLANNING)
                sm.transition(TaskState.REVIEWING)
            sm.transition(TaskState.DISPATCHED)

        # -- 尚书省派发 → 六部并行执行 ----------------------------------------
        sm.transition(TaskState.DOING)
        self.audit.record("dispatch", depts=[s.dept for s in plan])
        results = await asyncio.gather(
            *(self._execute(sub) for sub in plan)
        )
        for res in results:
            self.audit.record("result", dept=res.subtask.dept,
                              title=res.subtask.title, ok=res.ok,
                              output=res.output[:500])

        # -- 尚书省汇总回奏 ----------------------------------------------------
        sm.transition(TaskState.REPORTING)
        report_text = await self._report(edict, results)
        self.audit.record("report", text=report_text[:500])
        sm.transition(TaskState.DONE)

        usage = Usage()
        for agent in self._agents:
            usage = usage + agent.own_usage
        return CourtReport(
            edict=edict, plan=plan, review_rounds=rounds,
            results=list(results), report=report_text,
            usage=usage, audit=self.audit,
        )

    # -- pipeline stages ----------------------------------------------------

    async def _plan(self, edict: str, feedback: str | None) -> list[SubTask]:
        prompt = f"旨意：{edict}"
        if feedback:
            prompt += f"\n\n门下省封驳意见（必须逐条解决）：{feedback}"
        raw = await self._agent(ZHONGSHU).run(prompt)
        data = parse_json_object(raw)
        subtasks = []
        for item in data.get("subtasks", []):
            if not isinstance(item, dict) or not item.get("task"):
                continue
            dept = item.get("dept") if item.get("dept") in EXECUTOR_DEPTS else FALLBACK_DEPT
            subtasks.append(SubTask(
                dept=dept,
                title=str(item.get("title") or item["task"][:30]),
                task=str(item["task"]),
            ))
        if not subtasks:  # 解析失败兜底：整旨交兵部
            subtasks = [SubTask(dept=FALLBACK_DEPT, title=edict[:30], task=edict)]
        return subtasks

    async def _review(self, edict: str, plan: list[SubTask]) -> tuple[str, str | None]:
        plan_text = "\n".join(
            f"- [{s.dept}] {s.title}: {s.task}" for s in plan
        )
        raw = await self._agent(MENXIA).run(f"旨意：{edict}\n\n中书省方案：\n{plan_text}")
        data = parse_json_object(raw)
        verdict = data.get("verdict")
        if verdict not in ("approve", "reject"):
            verdict = "approve"  # 审议结果无法解析时不阻塞流程
        return verdict, data.get("feedback")

    async def _execute(self, subtask: SubTask) -> SubTaskResult:
        role = self.roles.get(subtask.dept, self.roles[FALLBACK_DEPT])
        try:
            output = await self._agent(role).run(subtask.task)
            return SubTaskResult(subtask=subtask, output=output, ok=True)
        except Exception as exc:  # 一部受阻不拖累全局
            return SubTaskResult(subtask=subtask, output=f"{type(exc).__name__}: {exc}", ok=False)

    async def _report(self, edict: str, results: list[SubTaskResult]) -> str:
        results_text = "\n\n".join(
            f"【{r.subtask.dept} · {r.subtask.title}】{'✅' if r.ok else '❌'}\n{r.output}"
            for r in results
        )
        return await self._agent(SHANGSHU).run(
            f"旨意：{edict}\n\n各部执行结果：\n{results_text}\n\n请汇总回奏。"
        )
