"""Control a USB-connected phone for install and smoke testing.

Harmony devices via ``hdc``, Android via ``adb``. The agent should call this
instead of asking the user to click DevEco / Android Studio install buttons.
"""

from __future__ import annotations

from typing import Any

from codeagent.phone.bridge import run_action
from codeagent.security.policy import RiskLevel
from codeagent.tools.base import Tool

_READ = frozenset({"status", "devices", "info", "log", "ui_dump", "screenshot"})
_DESTRUCTIVE = frozenset({"uninstall"})


class PhoneTool(Tool):
    name = "phone"
    description = (
        "Control a USB-connected phone or tablet: list devices, install "
        ".hap/.apk, launch/stop apps, screenshot, read logs, dump UI, tap/"
        "swipe/input for smoke tests. Uses hdc (Harmony) or adb (Android) "
        "on this Mac/PC. Prefer this over asking the user to install manually."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": (
                    "status | devices | info | install | uninstall | start | "
                    "stop | screenshot | log | ui_dump | tap | swipe | input | shell"
                ),
            },
            "prefer": {
                "type": "string",
                "description": "auto | hdc | adb（鸿蒙用 hdc，安卓用 adb）",
            },
            "serial": {
                "type": "string",
                "description": "设备序列号；省略则用第一台已连接设备",
            },
            "path": {
                "type": "string",
                "description": "install：本机 .hap / .app / .apk 路径",
            },
            "package": {
                "type": "string",
                "description": "bundleName / applicationId（uninstall/start/stop/log）",
            },
            "ability": {
                "type": "string",
                "description": "鸿蒙 Ability 名，默认 EntryAbility",
            },
            "activity": {
                "type": "string",
                "description": "安卓 Activity（package/.MainActivity）",
            },
            "out": {
                "type": "string",
                "description": "screenshot 保存路径",
            },
            "lines": {
                "type": "integer",
                "description": "log 行数，默认 80",
            },
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "x2": {"type": "integer"},
            "y2": {"type": "integer"},
            "duration_ms": {"type": "integer"},
            "text": {"type": "string", "description": "input 要输入的文字"},
            "command": {
                "type": "string",
                "description": "shell：在设备上执行的一条命令",
            },
        },
        "required": ["action"],
    }
    risk_level = RiskLevel.EXECUTE

    def risk_for(self, arguments: dict[str, Any]) -> RiskLevel:
        action = str(arguments.get("action") or "").strip().lower()
        if action in _READ:
            return RiskLevel.READ_ONLY
        if action in _DESTRUCTIVE:
            return RiskLevel.DESTRUCTIVE
        return RiskLevel.EXECUTE

    async def execute(
        self,
        action: str = "status",
        prefer: str = "auto",
        serial: str = "",
        path: str = "",
        package: str = "",
        ability: str = "EntryAbility",
        activity: str = "",
        out: str = "",
        lines: int = 80,
        x: int = 0,
        y: int = 0,
        x2: int = 0,
        y2: int = 0,
        duration_ms: int = 400,
        text: str = "",
        command: str = "",
        **_: Any,
    ) -> str:
        return run_action(
            action,
            prefer=prefer,
            serial=serial,
            path=path,
            package=package,
            ability=ability,
            activity=activity,
            out=out,
            lines=lines,
            x=x,
            y=y,
            x2=x2,
            y2=y2,
            duration_ms=duration_ms,
            text=text,
            command=command,
        )


def phone_tools() -> list[Tool]:
    return [PhoneTool()]
