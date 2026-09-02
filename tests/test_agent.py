"""Agent loop tests using a scripted fake provider (no API key needed)."""

import pytest

from codeagent import Agent, Tool, ToolRegistry
from codeagent.core.agent import MaxIterationsError
from codeagent.core.types import LLMResponse, ToolCall
from codeagent.llm.base import LLMProvider


class FakeProvider(LLMProvider):
    """Returns scripted responses in order."""

    name = "fake"

    def __init__(self, responses: list[LLMResponse]):
        super().__init__(model="fake")
        self._responses = list(responses)
        self.requests: list[list] = []

    async def complete(self, messages, tools=None, system=None, **kwargs):
        self.requests.append(messages)
        if not self._responses:
            return LLMResponse(content="done")
        return self._responses.pop(0)


class RecordTool(Tool):
    name = "record"
    description = "Record a value."
    parameters = {
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
    }

    def __init__(self):
        self.seen: list[str] = []

    async def execute(self, value: str, **_):
        self.seen.append(value)
        return f"recorded {value}"


async def test_agent_returns_final_text():
    provider = FakeProvider([LLMResponse(content="all done")])
    agent = Agent(provider=provider, tools=ToolRegistry())
    assert await agent.run("task") == "all done"


async def test_agent_executes_tool_and_feeds_result_back():
    tool_call = ToolCall(name="record", arguments={"value": "42"}, id="tc1")
    provider = FakeProvider(
        [
            LLMResponse(content="calling tool", tool_calls=[tool_call]),
            LLMResponse(content="finished"),
        ]
    )
    tool = RecordTool()
    agent = Agent(provider=provider, tools=ToolRegistry([tool]))

    answer = await agent.run("record something")

    assert answer == "finished"
    assert tool.seen == ["42"]
    # history: user, assistant(tool_call), tool(result), assistant(final)
    assert len(agent.messages) == 4
    tool_message = agent.messages[2]
    assert tool_message.tool_results[0].content == "recorded 42"
    assert tool_message.tool_results[0].tool_call_id == "tc1"


async def test_agent_max_iterations():
    provider = FakeProvider(
        [LLMResponse(tool_calls=[ToolCall(name="record", arguments={"value": "x"}, id=str(i))]) for i in range(10)]
    )
    agent = Agent(provider=provider, tools=ToolRegistry([RecordTool()]), max_iterations=3)
    with pytest.raises(MaxIterationsError):
        await agent.run("loop forever")


async def test_agent_emits_events():
    events = []
    provider = FakeProvider([LLMResponse(content="ok")])
    agent = Agent(provider=provider, on_event=lambda e: events.append(e.type))
    await agent.run("task")
    assert "iteration" in events
    assert "text" in events
    assert "done" in events
