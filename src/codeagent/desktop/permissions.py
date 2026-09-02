"""Permission control for the desktop app (LunarCore Claw Permissions style).

能力矩阵：each capability maps to a set of agent tools and carries one of
four levels — full（完全自主）/ confirm（执行前确认）/ readonly（只读）/
off（关闭）. Every non-trivial decision is written to the audit log.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from codeagent.core.types import ToolCall
from codeagent.security.policy import ApprovalDecision, PermissionPolicy, RiskLevel

PERMS_PATH = Path("~/.codeagent/permissions.json").expanduser()
AUDIT_PATH = Path("~/.codeagent/audit.jsonl").expanduser()

LEVELS = ("full", "confirm", "readonly", "off")

# 能力矩阵（与 LCA Permissions.tsx 同构：能力 / 描述 / 范围 / 级别）
CAPABILITIES: list[dict[str, Any]] = [
    {
        "id": "fs_read",
        "capability": "文件读取",
        "desc": "读取项目文件、列目录、代码搜索",
        "scope": "项目目录",
        "tools": ["read_file", "list_dir", "grep", "glob"],
        "readonly_tools": ["read_file", "list_dir", "grep", "glob"],
    },
    {
        "id": "fs_write",
        "capability": "文件写入",
        "desc": "创建、修改、删除项目文件",
        "scope": "项目目录",
        "tools": ["write_file", "edit_file"],
        "readonly_tools": [],
    },
    {
        "id": "shell",
        "capability": "命令执行",
        "desc": "在本机执行 shell 命令（含构建、测试、git）",
        "scope": "本机终端",
        "tools": ["bash"],
        "readonly_tools": [],
    },
    {
        "id": "network",
        "capability": "网络访问",
        "desc": "抓取网页、调用外部 API、OCR 识别",
        "scope": "互联网",
        "tools": ["web_fetch", "web_scrape", "ocr"],
        "readonly_tools": ["web_fetch", "web_scrape", "ocr"],
    },
    {
        "id": "delegate",
        "capability": "子代理委派",
        "desc": "派生子代理并行处理子任务",
        "scope": "Agent 集群",
        "tools": ["delegate"],
        "readonly_tools": [],
    },
]

DEFAULT_LEVELS = {
    "fs_read": "full",
    "fs_write": "confirm",
    "shell": "confirm",
    "network": "full",
    "delegate": "confirm",
}


def load_levels(path: Path | None = None) -> dict[str, str]:
    path = path or PERMS_PATH
    levels = dict(DEFAULT_LEVELS)
    if path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            for cap in CAPABILITIES:
                v = saved.get(cap["id"])
                if v in LEVELS:
                    levels[cap["id"]] = v
        except (json.JSONDecodeError, OSError):
            pass
    return levels


def save_levels(levels: dict[str, str], path: Path | None = None) -> None:
    path = path or PERMS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(levels, ensure_ascii=False, indent=2), encoding="utf-8")


def append_audit(actor: str, action: str, result: str, path: Path | None = None) -> None:
    """Audit chain entry: actor（user/agent/system）· action · result."""
    path = path or AUDIT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": uuid.uuid4().hex[:8],
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "actor": actor,
        "action": action,
        "result": result,  # allowed | denied | confirmed
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_audit(limit: int = 12, path: Path | None = None) -> list[dict[str, Any]]:
    path = path or AUDIT_PATH
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    for line in reversed(lines[-limit:]):
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


class Confirmer:
    """执行前确认：push a prompt to the UI, wait for the user's decision.

    10 分钟未确认自动拒绝并记入审计（与 LCA 一致）。
    """

    TIMEOUT_S = 600.0

    def __init__(self, push: Callable[[str, dict[str, Any]], None]) -> None:
        self._push = push
        self._pending: dict[str, threading.Event] = {}
        self._decisions: dict[str, bool] = {}
        self._lock = threading.Lock()

    def ask(self, call: ToolCall, risk: RiskLevel) -> ApprovalDecision:
        cid = uuid.uuid4().hex[:8]
        ev = threading.Event()
        with self._lock:
            self._pending[cid] = ev
        self._push("confirm", {
            "id": cid,
            "tool": call.name,
            "args": json.dumps(call.arguments, ensure_ascii=False)[:300],
            "risk": risk.name,
        })
        ok = ev.wait(self.TIMEOUT_S)
        with self._lock:
            self._pending.pop(cid, None)
            approved = self._decisions.pop(cid, False)
        if not ok:
            append_audit("system", f"{call.name} 确认超时（10 分钟）", "denied")
            return ApprovalDecision.DENY
        append_audit("user", f"{'批准' if approved else '拒绝'} {call.name}", "confirmed" if approved else "denied")
        return ApprovalDecision.APPROVE if approved else ApprovalDecision.DENY

    def resolve(self, cid: str, approved: bool) -> bool:
        with self._lock:
            ev = self._pending.get(cid)
            if ev is None:
                return False
            self._decisions[cid] = approved
        ev.set()
        return True


class CapabilityPolicy(PermissionPolicy):
    """Per-capability levels: confirm tools always ask (before auto-approve),
    denials are written to the audit chain."""

    def __init__(
        self,
        confirm_tools: set[str],
        confirmer: Confirmer | None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._confirm_tools = confirm_tools
        self._confirmer = confirmer

    async def authorize(self, call: ToolCall, risk: RiskLevel) -> ApprovalDecision:
        if call.name in self._confirm_tools and self._confirmer is not None:
            return self._confirmer.ask(call, risk)
        decision = await super().authorize(call, risk)
        if decision == ApprovalDecision.DENY:
            append_audit("agent", f"调用 {call.name} 被策略拒绝", "denied")
        return decision


def build_policy(levels: dict[str, str], confirmer: Confirmer | None) -> PermissionPolicy:
    """Levels → PermissionPolicy (fail closed for unknown tools)."""
    allow: set[str] = set()
    deny: set[str] = set()
    confirm_tools: set[str] = set()
    for cap in CAPABILITIES:
        level = levels.get(cap["id"], "confirm")
        tools = set(cap["tools"])
        if level == "full":
            allow |= tools
        elif level == "off":
            deny |= tools
        elif level == "readonly":
            allow |= set(cap["readonly_tools"])
            deny |= tools - set(cap["readonly_tools"])
        else:  # confirm
            confirm_tools |= tools

    return CapabilityPolicy(
        confirm_tools=confirm_tools,
        confirmer=confirmer,
        auto_approve_up_to=RiskLevel.READ_ONLY,  # unlisted read-only tools pass
        handler=None,
        always_allow=allow,
        always_deny=deny,
    )
