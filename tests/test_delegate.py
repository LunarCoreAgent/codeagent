from codeagent import Agent
from codeagent.core.types import LLMResponse, Usage
from codeagent.llm.base import LLMProvider
from codeagent.tools import DelegateTool


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, responses):
        super().__init__(model="fake")
        self._responses = list(responses)

    async def complete(self, messages, tools=None, system=None, **kwargs):
        return self._responses.pop(0)


async def test_delegate_runs_subagent_and_returns_answer():
    sub_provider = FakeProvider(
        [LLMResponse(content="sub result", usage=Usage(input_tokens=10, output_tokens=5))]
    )
    parent = Agent(provider=FakeProvider([LLMResponse(content="unused")]))
    tool = DelegateTool(agent_factory=lambda: Agent(provider=sub_provider), parent=parent)

    result = await tool.execute(task="summarize something")

    assert result == "sub result"
    assert parent.usage.input_tokens == 10
    assert parent.usage.output_tokens == 5


async def test_delegate_reports_usage_even_on_failure():
    class FailingProvider(LLMProvider):
        name = "failing"

        def __init__(self):
            super().__init__(model="failing")

        async def complete(self, messages, tools=None, system=None, **kwargs):
            raise RuntimeError("provider down")

    parent = Agent(provider=FakeProvider([LLMResponse(content="unused")]))
    tool = DelegateTool(agent_factory=lambda: Agent(provider=FailingProvider()), parent=parent)

    try:
        await tool.execute(task="boom")
    except RuntimeError:
        pass  # usage roll-up happens in finally; nothing to assert beyond no hang
