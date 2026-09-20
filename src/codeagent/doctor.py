"""Startup health check for the local CodeCoreAgent install.

Fast by default: no network. ``probe=True`` pings local model endpoints.
Never prints secrets — credentials are reported as set / missing only.
"""

from __future__ import annotations

import os
import shutil
import socket
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codeagent import __version__
from codeagent.releases import latest
from codeagent.settings import Settings

MIN_PYTHON = (3, 10)
HOME_DIR = Path("~/.codeagent")

# Cloud providers that need an env key. Local servers are key-free.
_CLOUD_KEYS: tuple[tuple[str, str], ...] = (
    ("CODEAGENT_API_KEY", "通用"),
    ("ANTHROPIC_API_KEY", "anthropic"),
    ("OPENAI_API_KEY", "openai"),
    ("OPENROUTER_API_KEY", "openrouter"),
    ("SILICONFLOW_API_KEY", "siliconflow"),
    ("AIHUBMIX_API_KEY", "aihubmix"),
    ("ONEAPI_API_KEY", "oneapi"),
)

_LOCAL_ENDPOINTS: tuple[tuple[str, str, int], ...] = (
    ("Ollama", "127.0.0.1", 11434),
    ("LM Studio", "127.0.0.1", 1234),
    ("llama.cpp", "127.0.0.1", 8080),
)


@dataclass
class Check:
    name: str
    status: str  # ok | warn | fail
    message: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {"name": self.name, "status": self.status, "message": self.message}
        if self.detail:
            payload["detail"] = self.detail
        return payload


@dataclass
class DoctorReport:
    ok: bool
    version: str
    checks: list[Check]

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "version": self.version,
            "checks": [c.to_dict() for c in self.checks],
        }


def _key_set(name: str) -> bool:
    value = os.environ.get(name, "")
    return bool(value.strip())


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".doctor-write"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def run_doctor(
    root: str | Path | None = None,
    *,
    probe: bool = False,
    settings_path: str | Path | None = None,
) -> DoctorReport:
    """Collect checks. ``ok`` is False only when a check has status ``fail``."""
    checks: list[Check] = []
    workspace = Path(root).expanduser().resolve() if root is not None else Path.cwd()

    py = sys.version_info
    py_label = f"{py.major}.{py.minor}.{py.micro}"
    if py[:2] >= MIN_PYTHON:
        checks.append(Check(
            "python", "ok",
            f"Python {py_label}（需要 ≥ {MIN_PYTHON[0]}.{MIN_PYTHON[1]}）",
            {"version": py_label},
        ))
    else:
        checks.append(Check(
            "python", "fail",
            f"Python {py_label} 过旧，需要 ≥ {MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
            {"version": py_label},
        ))

    if workspace.is_dir():
        checks.append(Check("workspace", "ok", f"工作区 {workspace}", {"path": str(workspace)}))
    else:
        checks.append(Check("workspace", "fail", f"工作区不存在：{workspace}", {"path": str(workspace)}))

    home = HOME_DIR.expanduser()
    if _writable(home):
        checks.append(Check("home", "ok", f"配置目录可写 {home}", {"path": str(home)}))
    else:
        checks.append(Check("home", "fail", f"配置目录不可写：{home}", {"path": str(home)}))

    settings = Settings.load(settings_path)
    if settings.is_empty():
        checks.append(Check("settings", "ok", "个性化未设置（可选）", {"empty": True}))
    else:
        checks.append(Check(
            "settings", "ok", "已加载个性化设置",
            {"empty": False, "nickname": bool(settings.nickname)},
        ))

    present = [label for env, label in _CLOUD_KEYS if _key_set(env)]
    if present:
        checks.append(Check(
            "credentials", "ok",
            "已配置：" + "、".join(present),
            {"configured": present},
        ))
    else:
        checks.append(Check(
            "credentials", "warn",
            "未检测到云端 API 密钥；可用本机 Ollama / LM Studio",
            {"configured": []},
        ))

    git = shutil.which("git")
    if git:
        checks.append(Check("git", "ok", f"git：{git}", {"path": git}))
    else:
        checks.append(Check("git", "warn", "未找到 git（部分工作流会用到）"))

    try:
        from codeagent.tools import default_tools

        n = len(default_tools(workspace if workspace.is_dir() else Path.cwd()))
        checks.append(Check("tools", "ok", f"内置工具 {n} 个可用", {"count": n}))
    except Exception as exc:  # noqa: BLE001 — doctor must not crash
        checks.append(Check("tools", "fail", f"工具加载失败：{exc}"))

    if probe:
        reachable: list[str] = []
        missing: list[str] = []
        for label, host, port in _LOCAL_ENDPOINTS:
            if _port_open(host, port):
                reachable.append(label)
            else:
                missing.append(label)
        if reachable:
            msg = "本机端点：" + "、".join(reachable)
            if missing:
                msg += "；未响应：" + "、".join(missing)
            checks.append(Check(
                "endpoints", "ok" if reachable else "warn", msg,
                {"reachable": reachable, "missing": missing},
            ))
        else:
            checks.append(Check(
                "endpoints", "warn",
                "本机模型端点均未响应（Ollama / LM Studio / llama.cpp）",
                {"reachable": [], "missing": missing},
            ))

    rel = latest()
    checks.append(Check(
        "release", "ok",
        f"CodeCoreAgent v{rel.version}（{rel.date}）",
        {"version": rel.version, "date": rel.date},
    ))

    ok = all(c.status != "fail" for c in checks)
    return DoctorReport(ok=ok, version=__version__, checks=checks)
