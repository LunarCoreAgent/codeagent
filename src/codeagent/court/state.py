"""Task state machine with protected transitions.

Illegal jumps (e.g. DOING back to PLANNING) are rejected, so the workflow
cannot silently bypass the review gate — the institutional guarantee that
makes the pipeline trustworthy.
"""

from __future__ import annotations

from enum import Enum


class TaskState(str, Enum):
    RECEIVED = "received"        # 旨意已接收
    PLANNING = "planning"        # 中书省规划中
    REVIEWING = "reviewing"      # 门下省审议中
    REJECTED = "rejected"        # 封驳（打回重规划）
    DISPATCHED = "dispatched"    # 尚书省已派发
    DOING = "doing"              # 六部执行中
    REPORTING = "reporting"      # 尚书省汇总回奏中
    DONE = "done"                # 已完成
    FAILED = "failed"            # 失败


VALID_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.RECEIVED: frozenset({TaskState.PLANNING, TaskState.FAILED}),
    TaskState.PLANNING: frozenset({TaskState.REVIEWING, TaskState.FAILED}),
    TaskState.REVIEWING: frozenset({
        TaskState.REJECTED,     # 封驳
        TaskState.DISPATCHED,   # 准奏
        TaskState.FAILED,
    }),
    TaskState.REJECTED: frozenset({TaskState.PLANNING, TaskState.FAILED}),
    TaskState.DISPATCHED: frozenset({TaskState.DOING, TaskState.FAILED}),
    TaskState.DOING: frozenset({TaskState.REPORTING, TaskState.FAILED}),
    TaskState.REPORTING: frozenset({TaskState.DONE, TaskState.FAILED}),
    TaskState.DONE: frozenset(),
    TaskState.FAILED: frozenset(),
}


class IllegalTransitionError(RuntimeError):
    pass


class TaskStateMachine:
    """Tracks one edict's state; every transition is validated."""

    def __init__(self) -> None:
        self.state = TaskState.RECEIVED
        self.history: list[TaskState] = [TaskState.RECEIVED]

    def transition(self, target: TaskState) -> TaskState:
        if target not in VALID_TRANSITIONS[self.state]:
            raise IllegalTransitionError(
                f"Illegal transition: {self.state.value} → {target.value}"
            )
        self.state = target
        self.history.append(target)
        return target
