"""Progress board: live, queryable view of who is doing what (HomeRail supervise)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

TaskStatus = Literal["pending", "running", "done", "failed"]

_STATUS_LABEL = {
    "pending": "待开工",
    "running": "进行中",
    "done": "已完成",
    "failed": "失败",
}


@dataclass
class TaskRecord:
    task_id: str
    title: str
    worker: str
    status: TaskStatus = "pending"
    detail: str = ""
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None

    @property
    def elapsed(self) -> float:
        return (self.ended_at or time.time()) - self.started_at


class ProgressBoard:
    """Tracks every dispatched task; safe to query while work is running."""

    def __init__(self, on_change: Callable[[TaskRecord], None] | None = None) -> None:
        self._records: dict[str, TaskRecord] = {}
        self._order: list[str] = []
        self._on_change = on_change

    def register(self, task_id: str, title: str, worker: str) -> TaskRecord:
        record = TaskRecord(task_id=task_id, title=title, worker=worker)
        self._records[task_id] = record
        self._order.append(task_id)
        self._notify(record)
        return record

    def update(self, task_id: str, status: TaskStatus, detail: str = "") -> None:
        record = self._records[task_id]
        record.status = status
        if detail:
            record.detail = detail
        if status in ("done", "failed"):
            record.ended_at = time.time()
        self._notify(record)

    def get(self, task_id: str) -> TaskRecord | None:
        return self._records.get(task_id)

    def records(self) -> list[TaskRecord]:
        return [self._records[tid] for tid in self._order]

    def snapshot(self) -> dict[str, Any]:
        return {
            "total": len(self._order),
            "running": sum(1 for r in self._records.values() if r.status == "running"),
            "done": sum(1 for r in self._records.values() if r.status == "done"),
            "failed": sum(1 for r in self._records.values() if r.status == "failed"),
            "tasks": [
                {
                    "id": r.task_id,
                    "title": r.title,
                    "worker": r.worker,
                    "status": r.status,
                    "detail": r.detail,
                    "elapsed_s": round(r.elapsed, 1),
                }
                for r in self.records()
            ],
        }

    def summary(self) -> str:
        """Voice-friendly Chinese progress readout."""
        if not self._order:
            return "目前还没有任务。下达一个命令我就会安排。"
        snap = self.snapshot()
        lines = [
            f"当前共 {snap['total']} 项任务：{snap['running']} 项进行中，"
            f"{snap['done']} 项完成，{snap['failed']} 项失败。"
        ]
        for r in self.records():
            label = _STATUS_LABEL[r.status]
            line = f"· [{label}] {r.title}（{r.worker}，{round(r.elapsed)}秒）"
            if r.detail:
                line += f"——{r.detail}"
            lines.append(line)
        return "\n".join(lines)

    def clear(self) -> None:
        self._records.clear()
        self._order.clear()

    def _notify(self, record: TaskRecord) -> None:
        if self._on_change is not None:
            self._on_change(record)
