"""Drive a browser for the agent.

Default is the software's own internal browser (desktop window, or HTTP
fetch). Optional bridges: BrowserSkill (bsk) or ego-lite, if installed.
"""

from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path
from typing import Any

from codeagent.browser.engine import InternalBrowser
from codeagent.security.policy import RiskLevel
from codeagent.tools.base import Tool

SESSION_PATH = Path("~/.codeagent/bsk-session").expanduser()
MAX_OUTPUT = 40_000

INSTALL_HINT = (
    "需要操作你已经登录的 Chrome/Edge 时，可另装外接桥（内置浏览器无需安装）：\n"
    "1) BrowserSkill（Chrome/Edge，macOS/Linux/Windows）：\n"
    "   curl -fsSL https://raw.githubusercontent.com/Tencent/BrowserSkill/main/install.sh | sh\n"
    "   再从 Chrome 应用店或 Edge 附加组件安装 BrowserSkill 扩展。\n"
    "   https://github.com/Tencent/BrowserSkill/\n"
    "2) ego-lite（目前 macOS）：安装 App 后得到 ego-browser。\n"
    "   https://github.com/citrolabs/ego-lite\n"
    "装好扩展/App 后执行 browser action=status 自检。"
)

_READ_ACTIONS = frozenset({"status", "observe", "screenshot"})


def detect_browser_backend(which: Any = None) -> str:
    """Return 'bsk', 'ego', or ''."""
    lookup = which or shutil.which
    if lookup("bsk"):
        return "bsk"
    if lookup("ego-browser"):
        return "ego"
    return ""


def parse_bsk_session_id(text: str) -> str:
    """Pick the 4-letter session id BrowserSkill prints on start."""
    match = re.search(r"session(?:\s+id)?[:\s]+([A-Za-z0-9]{4})\b", text, re.I)
    if match:
        return match.group(1)
    skip = {"true", "false", "none", "done", "wait", "open", "help", "info"}
    for token in reversed(re.findall(r"\b([A-Za-z]{4})\b", text)):
        if token.lower() not in skip:
            return token
    return ""


class BrowserTool(Tool):
    name = "browser"
    description = (
        "Open pages, read them, click and fill forms in the software's "
        "built-in browser. Prefer this over web_fetch when the page needs "
        "interaction. On desktop the user sees a live window. When a website "
        "or frontend task is finished, navigate to the local preview URL "
        "(http://127.0.0.1 / localhost — never file://) to showcase the "
        "product before summarizing. Optional: BrowserSkill (bsk) or ego-lite "
        "if installed, for the user's already logged-in Chrome. Call this "
        "yourself — do not ask the user to browse."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": (
                    "status | navigate | observe | click | fill | press | "
                    "select | screenshot | evaluate | script | stop"
                ),
            },
            "url": {"type": "string", "description": "URL for navigate."},
            "target": {
                "type": "string",
                "description": "Element ref from observe (@e1 / @21) or CSS.",
            },
            "value": {"type": "string", "description": "Text for fill/select/press."},
            "script": {
                "type": "string",
                "description": "JS for evaluate, or a full ego-browser heredoc body.",
            },
            "out": {"type": "string", "description": "Screenshot / download path."},
            "session": {"type": "string", "description": "Reuse a known bsk session id."},
            "timeout": {"type": "integer", "description": "Seconds (default 90)."},
        },
        "required": ["action"],
    }
    risk_level = RiskLevel.EXECUTE

    def __init__(
        self,
        session_path: str | Path | None = None,
        default_timeout: int = 90,
        engine: InternalBrowser | None = None,
    ) -> None:
        self.session_path = Path(session_path or SESSION_PATH).expanduser()
        self.default_timeout = default_timeout
        self.engine = engine if engine is not None else InternalBrowser()

    def risk_for(self, arguments: dict[str, Any]) -> RiskLevel:
        action = str(arguments.get("action") or "").strip().lower()
        if action in _READ_ACTIONS:
            return RiskLevel.READ_ONLY
        return RiskLevel.EXECUTE

    async def execute(
        self,
        action: str,
        url: str | None = None,
        target: str | None = None,
        value: str | None = None,
        script: str | None = None,
        out: str | None = None,
        session: str | None = None,
        timeout: int | None = None,
        **_: Any,
    ) -> str:
        action = (action or "").strip().lower()
        wait = int(timeout or self.default_timeout)
        backend = detect_browser_backend()
        if action == "status":
            return self._status(backend)
        # Desktop injects a live in-app window — always use it.
        if self.engine.has_gui:
            return await self.engine.run(
                action, url=url, target=target, value=value, script=script, timeout=wait,
            )
        if backend == "bsk":
            return await self._bsk(action, url, target, value, script, out, session, wait)
        if backend == "ego":
            return await self._ego(action, url, target, value, script, out, wait)
        return await self.engine.run(
            action, url=url, target=target, value=value, script=script, timeout=wait,
        )

    def _status(self, backend: str) -> str:
        lines = [self.engine.status_text()]
        if backend == "bsk":
            sid = self._read_session()
            extra = f" 当前会话 {sid}" if sid else " 尚无会话（navigate 会自动开）"
            lines.append("外接 BrowserSkill (bsk) 可用。" + extra)
        elif backend == "ego":
            lines.append("外接 ego-lite (ego-browser) 可用。用 task space，不打扰你的标签。")
        else:
            lines.append(INSTALL_HINT)
        return "\n".join(lines)

    def _read_session(self) -> str:
        try:
            return self.session_path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def _write_session(self, sid: str) -> None:
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_path.write_text(sid, encoding="utf-8")

    def _clear_session(self) -> None:
        try:
            self.session_path.unlink()
        except OSError:
            pass

    async def _ensure_bsk_session(self, session: str | None, timeout: int) -> str:
        if session:
            self._write_session(session)
            return session
        existing = self._read_session()
        if existing:
            return existing
        raw = await self._run(["bsk", "session", "start", "--no-focus"], timeout=timeout)
        sid = parse_bsk_session_id(raw)
        if not sid:
            return ""
        self._write_session(sid)
        return sid

    async def _bsk(
        self,
        action: str,
        url: str | None,
        target: str | None,
        value: str | None,
        script: str | None,
        out: str | None,
        session: str | None,
        timeout: int,
    ) -> str:
        if action == "stop":
            sid = session or self._read_session()
            if not sid:
                return "没有进行中的 bsk 会话。"
            raw = await self._run(["bsk", "session", "stop", sid], timeout=timeout)
            self._clear_session()
            return raw
        sid = await self._ensure_bsk_session(session, timeout)
        if not sid:
            return "无法解析 bsk 会话 id。请运行 bsk doctor，或把 session start 的输出发回来。"
        args: list[str]
        if action == "navigate":
            if not url:
                return "navigate 需要 url。"
            nav = await self._run(["bsk", "navigate", url, "--session", sid], timeout=timeout)
            obs = await self._run(["bsk", "observe", "--session", sid], timeout=timeout)
            return f"{nav}\n\n{obs}"
        if action == "observe":
            args = ["bsk", "observe", "--session", sid]
        elif action == "click":
            if not target:
                return "click 需要 target（observe 得到的 @eN）。"
            args = ["bsk", "click", target, "--session", sid]
        elif action == "fill":
            if not target or value is None:
                return "fill 需要 target 和 value。"
            args = ["bsk", "fill", target, "--value", value, "--session", sid]
        elif action == "select":
            if not target or value is None:
                return "select 需要 target 和 value（option 的 value 属性）。"
            args = ["bsk", "select", target, "--value", value, "--session", sid]
        elif action == "press":
            if not value and not target:
                return "press 需要 value（按键名）。"
            args = ["bsk", "press", value or target or "", "--session", sid]
        elif action == "screenshot":
            dest = out or str(Path("~/.codeagent/browser-shot.png").expanduser())
            args = ["bsk", "screenshot", "--out", dest, "--session", sid]
        elif action in ("evaluate", "script"):
            if not script:
                return "evaluate/script 需要 script。"
            args = ["bsk", "evaluate", script, "--session", sid]
        else:
            return f"未知 action：{action}。可用：status navigate observe click fill press select screenshot evaluate script stop"
        return await self._run(args, timeout=timeout)

    async def _ego(
        self,
        action: str,
        url: str | None,
        target: str | None,
        value: str | None,
        script: str | None,
        out: str | None,
        timeout: int,
    ) -> str:
        if action == "stop":
            body = (
                "const task = await useOrCreateTaskSpace('codeagent')\n"
                "cliLog(await completeTaskSpace(task.id, { keep: false }))\n"
            )
            return await self._run(["ego-browser", "nodejs"], stdin=body, timeout=timeout)
        if action == "script":
            if not script:
                return "script 需要 script（ego-browser 的 JS 正文）。"
            return await self._run(["ego-browser", "nodejs"], stdin=script, timeout=timeout)
        pieces = [
            "const task = await useOrCreateTaskSpace('codeagent')",
            "cliLog('task space ' + task.id)",
        ]
        if action == "navigate":
            if not url:
                return "navigate 需要 url。"
            pieces.append(f"await openOrReuseTab({url!r}, {{ wait: true, timeout: 20 }})")
            pieces.append("cliLog(await snapshotText())")
        elif action == "observe":
            pieces.append("cliLog(await snapshotText())")
        elif action == "click":
            if not target:
                return "click 需要 target。"
            pieces.append(f"await click({target!r})")
            pieces.append("cliLog(await snapshotText())")
        elif action == "fill":
            if not target or value is None:
                return "fill 需要 target 和 value。"
            pieces.append(f"await fillInput({target!r}, {value!r})")
            pieces.append("cliLog(await snapshotText())")
        elif action == "press":
            pieces.append(f"await pressKey({(value or target or '')!r})")
        elif action == "screenshot":
            dest = out or str(Path("~/.codeagent/browser-shot.png").expanduser())
            pieces.append(f"cliLog(await captureScreenshot({{ path: {dest!r} }}))")
        elif action == "evaluate":
            if not script:
                return "evaluate 需要 script。"
            pieces.append(f"cliLog(await js({script!r}))")
        else:
            return f"未知 action：{action}。"
        return await self._run(
            ["ego-browser", "nodejs"], stdin="\n".join(pieces) + "\n", timeout=timeout,
        )

    async def _run(
        self,
        args: list[str],
        stdin: str | None = None,
        timeout: int = 90,
    ) -> str:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE if stdin is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        payload = stdin.encode() if stdin is not None else None
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(payload), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return f"浏览器命令超时（{timeout}s）：{' '.join(args)}"
        text = stdout.decode(errors="replace")
        if len(text) > MAX_OUTPUT:
            text = text[:MAX_OUTPUT] + "\n... [truncated]"
        return f"exit {process.returncode}\n{text}".rstrip()


def browser_tools() -> list[Tool]:
    return [BrowserTool()]
