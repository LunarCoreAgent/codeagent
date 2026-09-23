"""Shell command execution tool."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from codeagent.security.policy import RiskLevel, classify_command
from codeagent.tools.base import Tool

MAX_OUTPUT_CHARS = 50_000


class BashTool(Tool):
    name = "bash"
    risk_level = RiskLevel.EXECUTE
    description = (
        "Execute a shell command and return its combined stdout/stderr and "
        "exit code. Use for running tests, builds, git, and system commands."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to execute."},
            "timeout": {"type": "integer", "description": "Timeout in seconds.", "minimum": 1},
        },
        "required": ["command"],
    }

    def __init__(self, cwd: str | Path = ".", default_timeout: int = 120) -> None:
        self.cwd = Path(cwd).resolve()
        self.default_timeout = default_timeout

    def risk_for(self, arguments: dict[str, Any]) -> RiskLevel:
        return classify_command(str(arguments.get("command", "")))

    async def execute(self, command: str, timeout: int | None = None, **_: Any) -> str:
        effective_timeout = timeout or self.default_timeout
        from codeagent.node_runtime import augment_env

        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=self.cwd,
            env=augment_env(),
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=effective_timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return f"Command timed out after {effective_timeout}s: {command}"

        output = stdout.decode(errors="replace")
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n... [truncated]"
        return f"exit code: {process.returncode}\n{output}".rstrip()
