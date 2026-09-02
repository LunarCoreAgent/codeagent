"""External agent platform adapters (HiveWard's "harness employees").

When a worker is stuck, confused, or fails outright, it can hand the task to
another agent platform installed on this computer — Claude Code, Codex,
Gemini CLI, cursor-agent, opencode — via its CLI, in headless mode.
"""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HarnessResult:
    harness: str
    ok: bool
    output: str
    exit_code: int | None = None


@dataclass(frozen=True)
class CliHarness:
    """A headless CLI agent platform. ``argv`` contains a {prompt} slot."""

    name: str
    argv: tuple[str, ...]
    timeout: float = 300.0
    description: str = ""

    @property
    def executable(self) -> str:
        return self.argv[0]

    def available(self) -> bool:
        return shutil.which(self.executable) is not None

    async def run(self, prompt: str, cwd: str | Path | None = None) -> HarnessResult:
        if not self.available():
            return HarnessResult(self.name, False, f"{self.executable} 未安装")
        argv = [part.replace("{prompt}", prompt) for part in self.argv]
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(cwd) if cwd else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), self.timeout)
        except asyncio.TimeoutError:
            return HarnessResult(self.name, False, f"超时（{self.timeout}秒）")
        except OSError as exc:
            return HarnessResult(self.name, False, f"启动失败: {exc}")
        out = stdout.decode(errors="replace").strip()
        err = stderr.decode(errors="replace").strip()
        if proc.returncode != 0:
            return HarnessResult(self.name, False, err or out or f"exit {proc.returncode}", proc.returncode)
        return HarnessResult(self.name, True, out or "(无输出)", proc.returncode)


HARNESS_PRESETS: dict[str, CliHarness] = {
    "claude-code": CliHarness(
        "claude-code",
        ("claude", "-p", "{prompt}", "--output-format", "text"),
        description="Claude Code（Anthropic 官方 CLI）",
    ),
    "codex": CliHarness(
        "codex",
        ("codex", "exec", "{prompt}"),
        description="OpenAI Codex CLI",
    ),
    "gemini": CliHarness(
        "gemini",
        ("gemini", "-p", "{prompt}"),
        description="Google Gemini CLI",
    ),
    "cursor-agent": CliHarness(
        "cursor-agent",
        ("cursor-agent", "-p", "{prompt}", "--output-format", "text"),
        description="Cursor CLI agent",
    ),
    "opencode": CliHarness(
        "opencode",
        ("opencode", "run", "{prompt}"),
        description="OpenCode CLI",
    ),
}


def discover_harnesses(extra: list[CliHarness] | None = None) -> list[CliHarness]:
    """Return the agent platforms actually installed on this machine."""
    candidates = list(HARNESS_PRESETS.values()) + list(extra or [])
    return [h for h in candidates if h.available()]
