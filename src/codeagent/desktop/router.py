"""Routing engine for the desktop app (LunarCore Claw RouterPage style).

规则 → 分类 → 级联 → 学习：rules are matched by keyword against the
incoming message; the first hit (by priority) picks the target — a
mixture, an API model, or a local model. The sandbox previews the
decision without calling any model.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROUTER_PATH = Path("~/.codeagent/router.json").expanduser()

# 对话模型选择器里的「自由路由」= 本页路由引擎按规则分发
FREE_ROUTE_REF = "route:free"
FREE_ROUTE_LABEL = "自由路由"


def is_free_route(ref: str) -> bool:
    """Empty (legacy) and ``route:free`` both mean: let the routing engine decide."""
    return (ref or "").strip() in ("", FREE_ROUTE_REF)


def split_keywords(raw: str) -> list[str]:
    """Split rule keywords on ASCII/Chinese commas and enumeration pauses."""
    text = (raw or "").replace("、", ",").replace("，", ",").replace(";", ",")
    return [k.strip() for k in text.split(",") if k.strip()]


# 内置任务类型关键词（命中即归类，与 LCA engine 的分类器一致思路）
BUILTIN_TASK_TYPES: dict[str, list[str]] = {
    "代码调试": ["报错", "错误", "bug", "debug", "修复", "fix", "异常", "traceback", "error"],
    "代码生成": ["写一个", "实现", "生成", "create", "write", "开发", "做个"],
    "代码解释": ["解释", "什么意思", "原理", "explain", "这段代码"],
    "翻译": ["翻译", "translate", "英文", "中文"],
    "文档写作": ["文档", "readme", "说明", "总结", "摘要", "summarize"],
    "数据分析": ["分析", "统计", "图表", "数据", "analyze"],
}


@dataclass
class RouteRule:
    task_type: str
    keywords: str = ""  # 逗号分隔；空 = 兜底规则
    target: str = ""  # "mix:{id}" | "api:{id}" | "local:model@epid"
    priority: int = 50
    enabled: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


@dataclass
class RouteWeights:
    cost: int = 60  # 成本敏感
    quality: int = 80  # 质量偏好
    local_first: int = 40  # 本地优先


@dataclass
class RouterStore:
    rules: list[RouteRule] = field(default_factory=list)
    weights: RouteWeights = field(default_factory=RouteWeights)

    @classmethod
    def load(cls, path: Path | None = None) -> "RouterStore":
        path = path or ROUTER_PATH
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        return cls(
            rules=[RouteRule(**r) for r in data.get("rules", [])],
            weights=RouteWeights(**data.get("weights", {})),
        )

    def save(self, path: Path | None = None) -> None:
        path = path or ROUTER_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"rules": [asdict(r) for r in self.rules],
                 "weights": asdict(self.weights)},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def sorted_rules(self) -> list[RouteRule]:
        return sorted(self.rules, key=lambda r: r.priority, reverse=True)


def classify_task(text: str) -> str:
    """Built-in classifier: keyword hit → task type; else 通用对话."""
    low = text.lower()
    for task_type, keywords in BUILTIN_TASK_TYPES.items():
        if any(k.lower() in low for k in keywords):
            return task_type
    return "通用对话"


def route_message(text: str, store: RouterStore, resolve_label) -> dict[str, Any]:
    """Preview a routing decision without calling any model.

    ``resolve_label(ref)`` maps a target ref to its display name.
    Returns the LCA-shaped decision: taskType / strategy / reason /
    candidates / chosen / latencyMs / cost.
    """
    started = time.monotonic()
    enabled = [r for r in store.sorted_rules() if r.enabled]
    low = text.lower()

    hit: RouteRule | None = None
    for rule in enabled:
        keys = split_keywords(rule.keywords)
        if keys and any(k.lower() in low for k in keys):
            hit = rule
            break

    fallback_rule = next((r for r in enabled if not split_keywords(r.keywords)), None)

    if hit is not None:
        task_type, target = hit.task_type, hit.target
        reason = f"命中规则「{hit.task_type}」（关键词：{hit.keywords}），按优先级 {hit.priority} 分发"
        strategy = "规则直通"
    elif fallback_rule is not None:
        task_type, target = classify_task(text), fallback_rule.target
        reason = "未命中关键词规则，走兜底规则"
        strategy = "兜底分发"
    else:
        task_type = classify_task(text)
        target = ""
        reason = "无路由规则，使用默认直连（当前激活模型）"
        strategy = "默认直连"

    chosen = resolve_label(target) if target else "（当前激活模型）"
    is_local = target.startswith("local:")
    latency = 800 if is_local else 500
    cost = 0.0 if is_local else (None if not target else 0.005)

    return {
        "taskType": task_type,
        "strategy": strategy,
        "reason": reason,
        "target": target,
        "candidates": [chosen] if target else [],
        "chosen": chosen,
        "latencyMs": latency + int((time.monotonic() - started) * 1000),
        "cost": cost,
    }
