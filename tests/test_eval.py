import json

from codeagent.core.types import Usage
from codeagent.eval import EvalTask, evaluate, extract_code, load_mbpp


def test_extract_code_from_markdown():
    answer = "Here is the solution:\n```python\ndef add(a, b):\n    return a + b\n```\nDone."
    assert extract_code(answer) == "def add(a, b):\n    return a + b"


def test_extract_code_falls_back_to_raw():
    assert extract_code("x = 1") == "x = 1"


def test_extract_code_prefers_last_block():
    answer = "```python\nv1 = 1\n```\nactually, better:\n```python\nv2 = 2\n```"
    assert extract_code(answer) == "v2 = 2"


def test_load_mbpp_from_local_jsonl(tmp_path):
    rows = [
        {
            "task_id": 1,
            "text": "Write a function to add two numbers.",
            "code": "def add(a, b):\n    return a + b",
            "test_list": ["assert add(1, 2) == 3"],
        },
        {
            "task_id": 2,
            "text": "Write a function to double a number.",
            "code": "def double(n):\n    return n * 2",
            "test_list": ["assert double(4) == 8"],
            "test_setup_code": "",
        },
    ]
    path = tmp_path / "mbpp.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows))

    tasks = load_mbpp(path)
    assert len(tasks) == 2
    assert tasks[0].id == "mbpp-1"
    assert "add two numbers" in tasks[0].prompt
    assert "assert add(1, 2) == 3" in tasks[0].test_code

    limited = load_mbpp(path, limit=1)
    assert len(limited) == 1


class StubAgent:
    """Stands in for Agent: returns a canned answer."""

    def __init__(self, answer: str):
        self._answer = answer
        self.usage = Usage(input_tokens=5, output_tokens=5)

    async def run(self, prompt: str) -> str:
        return self._answer


async def test_evaluate_pass_and_fail():
    tasks = [
        EvalTask(id="t1", prompt="add", test_code="assert add(1, 2) == 3"),
        EvalTask(id="t2", prompt="sub", test_code="assert sub(5, 2) == 3"),
    ]

    def factory_for(answer):
        return lambda: StubAgent(answer)

    good = await evaluate(factory_for("```python\ndef add(a, b):\n    return a + b\n```"), [tasks[0]])
    assert good.pass_at_1 == 1.0
    assert good.results[0].passed

    bad = await evaluate(factory_for("```python\ndef sub(a, b):\n    return a - b - 1\n```"), [tasks[1]])
    assert bad.pass_at_1 == 0.0
    assert not bad.results[0].passed
    assert bad.results[0].error  # assertion error surfaced


async def test_evaluate_handles_agent_exception():
    class BrokenAgent:
        usage = Usage()

        async def run(self, prompt):
            raise RuntimeError("provider down")

    report = await evaluate(lambda: BrokenAgent(), [EvalTask(id="x", prompt="p", test_code="pass")])
    assert report.pass_at_1 == 0.0
    assert "provider down" in report.results[0].error


async def test_report_summary_format():
    tasks = [EvalTask(id="t1", prompt="p", test_code="assert True")]
    report = await evaluate(lambda: StubAgent("pass"), tasks)
    text = report.summary()
    assert "pass@1: 100.0%" in text
    assert "[PASS] t1" in text
