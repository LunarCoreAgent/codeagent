"""Automation: workflow orchestration with continuous autonomy (LCA style).

一个工作流 = 触发方式 + 步骤数组 + 运行状态。步骤的 tool 字段是模型
引用（local:/api:/mix: 前缀）或留空走当前激活模型。执行是真实的：
每个步骤作为一次 agent 调用，上一步产出作为下一步上下文。
「连续性」开启后，结束后自动衔接下一轮，直至暂停或权限系统拦截。
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from codeagent.desktop.activity import log_activity
from codeagent.desktop.permissions import append_audit

WORKFLOWS_PATH = Path("~/.codeagent/workflows.json").expanduser()

TRIGGERS = ("manual", "cron", "event", "feishu")
CONTINUOUS_DELAY_S = 5.0  # 两轮之间的衔接间隔


@dataclass
class WorkflowStep:
    name: str
    tool: str = ""  # 模型引用（local:/api:/mix:）或空 = 当前激活模型


@dataclass
class Workflow:
    name: str
    desc: str = ""
    trigger: str = "manual"
    continuous: bool = False  # 自动化连续性：结束后自动衔接下一轮
    steps: list[WorkflowStep] = field(default_factory=list)
    status: str = "idle"  # idle | running | paused
    runs: int = 0
    last_run: str = "-"
    id: str = field(default_factory=lambda: "wf-" + uuid.uuid4().hex[:6])


@dataclass
class WorkflowStore:
    workflows: list[Workflow] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> "WorkflowStore":
        path = path or WORKFLOWS_PATH
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        return cls(workflows=[
            Workflow(**{**w, "steps": [WorkflowStep(**s) for s in w.get("steps", [])]})
            for w in data.get("workflows", [])
        ])

    def save(self, path: Path | None = None) -> None:
        path = path or WORKFLOWS_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"workflows": [
                {**asdict(w), "steps": [asdict(s) for s in w.steps]}
                for w in self.workflows
            ]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, wf_id: str) -> Workflow | None:
        return next((w for w in self.workflows if w.id == wf_id), None)


class WorkflowRunner:
    """真实执行器：步骤链顺序调用 agent，连续性模式自动衔接。"""

    def __init__(
        self,
        store: WorkflowStore,
        run_step: Callable[[WorkflowStep, str], str],
        on_change: Callable[[Workflow], None] | None = None,
    ) -> None:
        self.store = store
        self._run_step = run_step
        self._on_change = on_change or (lambda w: None)
        self._threads: dict[str, threading.Thread] = {}

    def _changed(self, wf: Workflow) -> None:
        self.store.save()
        self._on_change(wf)

    def start(self, wf_id: str) -> bool:
        wf = self.store.get(wf_id)
        if wf is None or wf.status == "running":
            return False
        wf.status = "running"
        wf.runs += 1
        wf.last_run = time.strftime("%Y-%m-%d %H:%M:%S")
        log_activity("workflow", f"「{wf.name}」开始执行（第 {wf.runs} 次）")
        append_audit("workflow", f"执行工作流「{wf.name}」", "allowed")
        self._changed(wf)
        t = threading.Thread(target=self._loop, args=(wf_id,), daemon=True)
        self._threads[wf_id] = t
        t.start()
        return True

    def _loop(self, wf_id: str) -> None:
        while True:
            wf = self.store.get(wf_id)
            if wf is None or wf.status != "running":
                return
            try:
                context = ""
                for step in wf.steps:
                    context = self._run_step(step, context)
                log_activity(
                    "workflow",
                    f"「{wf.name}」执行完成"
                    + ("，连续性模式已排队下一轮" if wf.continuous else ""),
                )
            except Exception as exc:  # noqa: BLE001 — 失败留痕后回到 idle
                log_activity("workflow", f"「{wf.name}」执行失败：{str(exc)[:120]}")
                wf.status = "idle"
                self._changed(wf)
                return
            wf = self.store.get(wf_id)  # 取最新状态，避免过期快照
            if wf is None:
                return
            if wf.continuous and wf.status == "running":
                time.sleep(CONTINUOUS_DELAY_S)
                continue  # 衔接下一轮
            wf.status = "idle"
            self._changed(wf)
            return

    def pause(self, wf_id: str) -> bool:
        wf = self.store.get(wf_id)
        if wf is None:
            return False
        wf.status = "idle" if wf.status == "paused" else "paused"
        log_activity("workflow",
                     f"「{wf.name}」{'已恢复' if wf.status == 'idle' else '已暂停'}")
        self._changed(wf)
        return True

    def set_continuous(self, wf_id: str, on: bool) -> bool:
        wf = self.store.get(wf_id)
        if wf is None:
            return False
        wf.continuous = on
        append_audit("user",
                     f"{'开启' if on else '关闭'}「{wf.name}」连续性自治",
                     "confirmed" if on else "allowed")
        self._changed(wf)
        return True
