"""Self-debugging loop tests with a scripted provider (no API key needed)."""

from codeagent import Agent, ToolRegistry
from codeagent.core.types import LLMResponse, ToolCall
from codeagent.llm.base import LLMProvider
from codeagent.repair import SelfDebugger
from codeagent.tools import WriteFileTool


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, responses):
        super().__init__(model="fake")
        self._responses = list(responses)

    async def complete(self, messages, tools=None, system=None, **kwargs):
        if not self._responses:
            return LLMResponse(content="nothing left")
        return self._responses.pop(0)


def _write_call(path: str, content: str, call_id: str) -> ToolCall:
    return ToolCall(name="write_file", arguments={"path": path, "content": content}, id=call_id)


async def test_self_debug_repairs_until_verification_passes(tmp_path):
    """First attempt writes broken code; after feedback, the agent fixes it."""
    target = tmp_path / "solution.py"
    provider = FakeProvider(
        [
            # turn 0: generate broken code
            LLMResponse(tool_calls=[_write_call("solution.py", "x = 1\n", "t1")]),
            LLMResponse(content="wrote initial solution"),
            # turn 1 (after failure feedback): fix it
            LLMResponse(tool_calls=[_write_call("solution.py", "x = 2\n", "t2")]),
            LLMResponse(content="fixed the bug"),
        ]
    )
    agent = Agent(provider=provider, tools=ToolRegistry([WriteFileTool(tmp_path)]))
    debugger = SelfDebugger(agent=agent, cwd=tmp_path)

    result = await debugger.run(
        "write solution.py setting x",
        verify_command=f"grep -q 'x = 2' {target}",
    )

    assert result.success
    assert result.turns == 2
    assert result.attempts[0].exit_code != 0
    assert "x = 2" in target.read_text()


async def test_self_debug_stops_when_already_correct(tmp_path):
    target = tmp_path / "ok.py"
    provider = FakeProvider(
        [
            LLMResponse(tool_calls=[_write_call("ok.py", "x = 2\n", "t1")]),
            LLMResponse(content="done"),
        ]
    )
    agent = Agent(provider=provider, tools=ToolRegistry([WriteFileTool(tmp_path)]))
    debugger = SelfDebugger(agent=agent, cwd=tmp_path)

    result = await debugger.run("write ok.py", f"grep -q 'x = 2' {target}")

    assert result.success
    assert result.turns == 1


async def test_self_debug_gives_up_after_max_turns(tmp_path):
    provider = FakeProvider(
        [
            LLMResponse(tool_calls=[_write_call("bad.py", "x = 1\n", "t1")]),
            LLMResponse(content="attempt"),
            LLMResponse(content="attempt again"),
            LLMResponse(content="and again"),
        ]
    )
    agent = Agent(provider=provider, tools=ToolRegistry([WriteFileTool(tmp_path)]))
    debugger = SelfDebugger(agent=agent, max_turns=2, cwd=tmp_path)

    result = await debugger.run("write bad.py", "exit 1")

    assert not result.success
    assert result.turns == 2
    assert len(result.attempts) == 2


async def test_feedback_prompt_contains_error_details(tmp_path):
    """The rubber-duck feedback message must include command, exit code, output."""

    class RecordingProvider(LLMProvider):
        name = "recording"

        def __init__(self):
            super().__init__(model="rec")
            self.seen_messages = []
            self.calls = 0

        async def complete(self, messages, tools=None, system=None, **kwargs):
            self.calls += 1
            self.seen_messages = list(messages)
            return LLMResponse(content="ack")

    provider = RecordingProvider()
    agent = Agent(provider=provider, tools=ToolRegistry())
    debugger = SelfDebugger(agent=agent, max_turns=1, cwd=tmp_path)

    await debugger.run("do something", "echo some-error && exit 3")

    feedback = provider.seen_messages[-1].content
    assert "echo some-error && exit 3" in feedback
    assert "Exit code: 3" in feedback
    assert "some-error" in feedback
    assert "rubber-duck" in feedback
