"""Self-Debugging: iterative repair via execution feedback and rubber-ducking.

Implements the loop from "Teaching Large Language Models to Self-Debug"
(Chen et al., Google Research & UC Berkeley, ICLR 2024):

1. **Generation** — the agent produces code for the task.
2. **Execution feedback** — a verification command runs against the result.
3. **Explanation + fix** — on failure, the agent explains what the code does
   and why it fails (rubber-duck debugging), then applies a minimal fix.

The loop terminates when verification passes or ``max_turns`` is reached.
Conversation history is reused across turns, so failed attempts stay in
context — the paper shows this notably improves sample efficiency.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from codeagent.core.agent import Agent

FEEDBACK_TEMPLATE = """\
The verification command failed.

Command: `{command}`
Exit code: {exit_code}
Output:
```
{output}
```

Follow the self-debugging procedure:
1. Explain what the current code does and why it fails (rubber-duck debugging).
2. Identify the root cause.
3. Apply a minimal fix with your tools.
"""


@dataclass
class Attempt:
    turn: int
    exit_code: int
    output: str


@dataclass
class SelfDebugResult:
    success: bool
    turns: int
    final_answer: str
    attempts: list[Attempt] = field(default_factory=list)


class SelfDebugger:
    """Runs an agent on a task, then iterates execution-feedback repairs.

    Parameters
    ----------
    agent:
        The agent to drive. History is kept across turns so the model can
        compare against its failed predictions.
    max_turns:
        Maximum verification/repair rounds after the initial generation.
    cwd:
        Working directory for the verification command.
    timeout:
        Per-run timeout (seconds) for the verification command.
    """

    def __init__(
        self,
        agent: Agent,
        max_turns: int = 5,
        cwd: str | Path = ".",
        timeout: int = 60,
    ) -> None:
        self.agent = agent
        self.max_turns = max_turns
        self.cwd = Path(cwd).resolve()
        self.timeout = timeout

    async def _verify(self, command: str) -> tuple[int, str]:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=self.cwd,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return -1, f"verification timed out after {self.timeout}s"
        return process.returncode or 0, stdout.decode(errors="replace")

    async def run(self, task: str, verify_command: str) -> SelfDebugResult:
        """Generate a solution, then repair it until ``verify_command`` passes."""
        attempts: list[Attempt] = []
        answer = await self.agent.run(task)

        for turn in range(1, self.max_turns + 1):
            exit_code, output = await self._verify(verify_command)
            attempts.append(Attempt(turn=turn, exit_code=exit_code, output=output))
            if exit_code == 0:
                return SelfDebugResult(
                    success=True, turns=turn, final_answer=answer, attempts=attempts
                )
            answer = await self.agent.run(
                FEEDBACK_TEMPLATE.format(
                    command=verify_command, exit_code=exit_code, output=output.strip()
                )
            )

        return SelfDebugResult(
            success=False, turns=self.max_turns, final_answer=answer, attempts=attempts
        )
