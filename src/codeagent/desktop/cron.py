"""Cron scheduling for the desktop app (LCA CronPage style, real scheduler).

五字段 cron 表达式（分 时 日 月 周），支持 * , - / 语法。调度线程每
30 秒对齐检查一次，到点即执行动作（当前动作 = 用指定/激活模型跑一次
agent 提示词），结果写回 lastRun/lastResult 并留活动流痕迹。
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from codeagent.desktop.activity import log_activity

CRON_PATH = Path("~/.codeagent/cron.json").expanduser()

PRESETS = [
    {"label": "每 30 分钟", "cron": "*/30 * * * *"},
    {"label": "每天 08:00", "cron": "0 8 * * *"},
    {"label": "每小时", "cron": "0 * * * *"},
    {"label": "每周五 20:00", "cron": "0 20 * * 5"},
]


def _parse_field(spec: str, lo: int, hi: int) -> set[int] | None:
    """Parse one cron field → set of matching ints; None = invalid."""
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            return None
        step = 1
        if "/" in part:
            part, s = part.split("/", 1)
            if not s.isdigit() or int(s) < 1:
                return None
            step = int(s)
        if part == "*":
            start, end = lo, hi
        elif "-" in part:
            a, b = part.split("-", 1)
            if not (a.isdigit() and b.isdigit()):
                return None
            start, end = int(a), int(b)
        elif part.isdigit():
            start = end = int(part)
        else:
            return None
        if start < lo or end > hi or start > end:
            return None
        out.update(range(start, end + 1, step))
    return out


def cron_matches(expr: str, tm: time.struct_time) -> bool:
    """5-field cron match against a local time (分 时 日 月 周, 周日=0/7)."""
    fields = expr.split()
    if len(fields) != 5:
        return False
    minute = _parse_field(fields[0], 0, 59)
    hour = _parse_field(fields[1], 0, 23)
    day = _parse_field(fields[2], 1, 31)
    month = _parse_field(fields[3], 1, 12)
    weekday = _parse_field(fields[4], 0, 7)
    if None in (minute, hour, day, month, weekday):
        return False
    wd = (tm.tm_wday + 1) % 7  # python 周一=0 → cron 周日=0
    return (
        tm.tm_min in minute
        and tm.tm_hour in hour
        and tm.tm_mday in day
        and tm.tm_mon in month
        and (wd in weekday or (wd == 0 and 7 in weekday))
    )


def next_run_hint(expr: str) -> str:
    """Forward-scan up to 7 days for the next matching minute."""
    now = time.time()
    t = now - now % 60 + 60  # 下一分钟整
    for _ in range(7 * 24 * 60):
        tm = time.localtime(t)
        if cron_matches(expr, tm):
            return time.strftime("%m-%d %H:%M", tm)
        t += 60
    return "待调度器计算"


@dataclass
class CronJob:
    name: str
    schedule: str
    action: str  # 动作描述 = 交给 agent 的提示词
    target: str = "workflow"
    enabled: bool = True
    last_run: str = "-"
    next_run: str = "待调度器计算"
    last_result: str = "-"  # success | failed | -
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


@dataclass
class CronStore:
    jobs: list[CronJob] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> "CronStore":
        path = path or CRON_PATH
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        return cls(jobs=[CronJob(**j) for j in data.get("jobs", [])])

    def save(self, path: Path | None = None) -> None:
        path = path or CRON_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"jobs": [asdict(j) for j in self.jobs]},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class CronScheduler:
    """后台调度线程：每 30s 对齐检查，到点执行。"""

    def __init__(
        self,
        store: CronStore,
        run_action: Callable[[CronJob], bool],
        on_tick: Callable[[], None] | None = None,
        evolution_enabled: Callable[[], bool] | None = None,
        evolution_cron: Callable[[], str] | None = None,
        run_evolution: Callable[[], None] | None = None,
    ) -> None:
        self.store = store
        self._run_action = run_action
        self._on_tick = on_tick or (lambda: None)
        self._evo_enabled = evolution_enabled or (lambda: False)
        self._evo_cron = evolution_cron or (lambda: "0 2 * * *")
        self._run_evolution = run_evolution
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_minute = ""

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(30):
            try:
                self.tick()
            except Exception:  # noqa: BLE001 — 调度器永不崩溃
                continue

    def tick(self, now: float | None = None) -> list[str]:
        """Check all jobs once; returns fired job ids (testable)."""
        tm = time.localtime(now or time.time())
        minute_key = time.strftime("%Y-%m-%d %H:%M", tm)
        if minute_key == self._last_minute:
            return []
        fired: list[str] = []
        for job in self.store.jobs:
            if not job.enabled or not cron_matches(job.schedule, tm):
                continue
            job.last_run = time.strftime("%Y-%m-%d %H:%M:%S", tm)
            try:
                ok = bool(self._run_action(job))
            except Exception:  # noqa: BLE001
                ok = False
            job.last_result = "success" if ok else "failed"
            job.next_run = next_run_hint(job.schedule)
            log_activity("cron", f"定时任务「{job.name}」执行"
                                 f"{'成功' if ok else '失败'}")
            fired.append(job.id)
        # 系统级夜间进化作业（不在 jobs 数组里，不可删除）
        if (self._evo_enabled() and self._run_evolution is not None
                and cron_matches(self._evo_cron(), tm)):
            log_activity("cron", "系统进化作业触发（夜间调度）")
            try:
                self._run_evolution()
            except Exception:  # noqa: BLE001
                pass
            fired.append("__evolution__")
        if fired:
            self.store.save()
        self._last_minute = minute_key
        self._on_tick()
        return fired
