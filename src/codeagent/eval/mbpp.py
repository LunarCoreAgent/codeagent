"""Loader for MBPP — the Mostly Basic Python Problems benchmark.

MBPP lives in google-research/google-research (CC BY 4.0). Each row has:
``task_id``, ``text`` (problem statement), ``code`` (reference solution),
``test_list`` (assert statements) and optional ``test_setup_code``.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from codeagent.eval.harness import EvalTask

MBPP_URL = (
    "https://raw.githubusercontent.com/google-research/google-research/master/mbpp/mbpp.jsonl"
)

_PROMPT_TEMPLATE = """\
Write a Python function for the following task:

{text}

Your solution must pass these tests:
{tests}

Respond with a single ```python code block containing the complete solution.\
"""


def _row_to_task(row: dict) -> EvalTask:
    tests = "\n".join(row.get("test_list", []))
    setup = row.get("test_setup_code") or ""
    test_code = f"{setup}\n{tests}".strip()
    return EvalTask(
        id=f"mbpp-{row['task_id']}",
        prompt=_PROMPT_TEMPLATE.format(text=row["text"], tests=tests),
        test_code=test_code,
    )


def load_mbpp(
    path: str | Path | None = None,
    limit: int | None = None,
    sanitized: bool = False,
) -> list[EvalTask]:
    """Load MBPP tasks from a local jsonl file, or download from GitHub.

    ``sanitized=True`` loads the human-verified subset file instead.
    """
    if path is not None:
        text = Path(path).read_text()
    else:
        url = MBPP_URL.replace("mbpp.jsonl", "sanitized-mbpp.json") if sanitized else MBPP_URL
        with urllib.request.urlopen(url, timeout=60) as response:
            text = response.read().decode()

    tasks: list[EvalTask] = []
    stripped = text.strip()
    if stripped.startswith("["):  # sanitized file is a JSON array
        rows = json.loads(stripped)
    else:  # full file is JSON Lines
        rows = [json.loads(line) for line in stripped.splitlines() if line.strip()]

    for row in rows:
        tasks.append(_row_to_task(row))
        if limit is not None and len(tasks) >= limit:
            break
    return tasks
