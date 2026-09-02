"""Evaluation harness: measure the agent on code-generation benchmarks.

Tasks carry a prompt plus test code; the agent's answer is mined for a code
block, combined with the tests, and executed. pass@1 is the headline metric,
matching how MBPP / HumanEval-style benchmarks are reported.

Note: verification executes generated code. Run evaluations inside a
sandbox or container.
"""

from __future__ import annotations

import asyncio
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from codeagent.core.types import Usage

_CODE_BLOCK_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)


def extract_code(answer: str) -> str:
    """Pull the last fenced code block out of an answer; fall back to raw text."""
    blocks = _CODE_BLOCK_RE.findall(answer)
    if blocks:
        return blocks[-1].strip()
    return answer.strip()


@dataclass
class EvalTask:
    """One benchmark item."""

    id: str
    prompt: str
    test_code: str
    timeout: int = 30


@dataclass
class EvalResult:
    task_id: str
    passed: bool
    answer: str
    usage: Usage = field(default_factory=Usage)
    error: str | None = None


@dataclass
class EvalReport:
    results: list[EvalResult]

    @property
    def pass_at_1(self) -> float:
        if not self.results:
            return 0.0
        passed = sum(1 for r in self.results if r.passed)
        return passed / len(self.results)

    def summary(self) -> str:
        lines = [
            f"pass@1: {self.pass_at_1:.1%} "
            f"({sum(r.passed for r in self.results)}/{len(self.results)})"
        ]
        for r in self.results:
            mark = "PASS" if r.passed else "FAIL"
            lines.append(f"  [{mark}] {r.task_id}" + (f" — {r.error}" if r.error else ""))
        return "\n".join(lines)


AgentFactory = Callable[[], "object"]


async def _run_task(
    task: EvalTask,
    agent_factory: AgentFactory,
    semaphore: asyncio.Semaphore,
) -> EvalResult:
    async with semaphore:
        agent = agent_factory()
        try:
            answer = await agent.run(task.prompt)  # type: ignore[attr-defined]
        except Exception as exc:
            return EvalResult(task_id=task.id, passed=False, answer="", error=str(exc))

        usage = getattr(agent, "usage", Usage())
        code = extract_code(answer)
        program = f"{code}\n\n{task.test_code}\n"
        passed, error = await _execute_program(program, task.timeout)
        return EvalResult(
            task_id=task.id, passed=passed, answer=answer, usage=usage, error=error
        )


async def _execute_program(program: str, timeout: int) -> tuple[bool, str | None]:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(program)
        path = Path(f.name)
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return False, f"timed out after {timeout}s"
        if process.returncode == 0:
            return True, None
        output = stdout.decode(errors="replace").strip()
        return False, output.splitlines()[-1] if output else "non-zero exit"
    finally:
        path.unlink(missing_ok=True)


async def evaluate(
    agent_factory: AgentFactory,
    tasks: list[EvalTask],
    max_concurrency: int = 4,
) -> EvalReport:
    """Run every task against a fresh agent and score the answers."""
    semaphore = asyncio.Semaphore(max_concurrency)
    results = await asyncio.gather(
        *(_run_task(task, agent_factory, semaphore) for task in tasks)
    )
    return EvalReport(results=list(results))
