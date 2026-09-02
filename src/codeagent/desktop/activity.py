"""Activity stream & self-learning records (LCA Learning.tsx style).

活动流是全系统统一的事件条带（kind 分类 + 文本）；学习信号藏在
kind == "learn" 的条目里——赞/踩、学习完成、进化作业都走这条流。
统计是纯函数式现算：不维护中间计数器，活动流即真相。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ACTIVITY_PATH = Path("~/.codeagent/activity.jsonl").expanduser()
LEARNING_PATH = Path("~/.codeagent/learning.json").expanduser()

MAX_ACTIVITY = 2000  # 环形上限，防止无限增长


def log_activity(kind: str, text: str, path: Path | None = None) -> dict[str, Any]:
    """Append one entry to the activity stream (user-visible trace)."""
    path = path or ACTIVITY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": uuid.uuid4().hex[:8],
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "kind": kind,
        "text": text,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    _trim(path)
    return entry


def _trim(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if len(lines) > MAX_ACTIVITY:
        path.write_text("\n".join(lines[-MAX_ACTIVITY:]) + "\n", encoding="utf-8")


def read_activity(limit: int = 100, path: Path | None = None) -> list[dict[str, Any]]:
    path = path or ACTIVITY_PATH
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(out))


def record_feedback(positive: bool, path: Path | None = None) -> dict[str, Any]:
    """对话页赞/踩 → kind=learn 条目（LCA：赞记「正向」，踩记「点踩」）。"""
    text = "对话反馈：正向点赞" if positive else "对话反馈：点踩"
    return log_activity("learn", text, path)


@dataclass
class LearnRecord:
    day: str  # MM-DD
    accuracy: int  # 路由准确率 %
    thumbs_up: int = 0
    thumbs_down: int = 0
    samples: int = 0


@dataclass
class LearningStore:
    records: list[LearnRecord] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> "LearningStore":
        path = path or LEARNING_PATH
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        return cls(records=[LearnRecord(**r) for r in data.get("records", [])])

    def save(self, path: Path | None = None) -> None:
        path = path or LEARNING_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"records": [asdict(r) for r in self.records]},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def upsert_today(self, record: LearnRecord) -> None:
        """同日覆盖、异日追加（LCA learnNow 语义）。"""
        self.records = [r for r in self.records if r.day != record.day]
        self.records.append(record)
        self.records.sort(key=lambda r: r.day)


def learn_now(
    activity_path: Path | None = None,
    learning_path: Path | None = None,
) -> dict[str, Any]:
    """从活动流现算当日准确率并 upsert 学习记录（活动流即真相）。"""
    entries = read_activity(limit=MAX_ACTIVITY, path=activity_path)
    ups = sum(1 for e in entries
              if e.get("kind") == "learn" and "正向" in e.get("text", ""))
    downs = sum(1 for e in entries
                if e.get("kind") == "learn" and "点踩" in e.get("text", ""))
    total = ups + downs
    if total == 0:
        return {"ok": False, "error": "暂无反馈样本：请先在「对话」页对模型回复点赞/点踩"}
    acc = round(ups / total * 100)
    today = time.strftime("%m-%d")
    store = LearningStore.load(learning_path)
    store.upsert_today(LearnRecord(
        day=today, accuracy=acc, thumbs_up=ups, thumbs_down=downs, samples=total,
    ))
    store.save(learning_path)
    log_activity(
        "learn",
        f"立即学习完成：复盘反馈 {total} 条（赞 {ups} / 踩 {downs}），"
        f"当日路由准确率 {acc}%，路由权重已修正",
        activity_path,
    )
    return {"ok": True, "accuracy": acc, "samples": total,
            "thumbs_up": ups, "thumbs_down": downs}
