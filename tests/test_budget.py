import pytest

from codeagent import Agent, Budget, BudgetExceededError, ToolRegistry
from codeagent.core.types import LLMResponse, ToolCall, Usage
from codeagent.llm.base import LLMProvider
from codeagent.tools import DelegateTool


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, responses):
        super().__init__(model="fake")
        self._responses = list(responses)

    async def complete(self, messages, tools=None, system=None, **kwargs):
        if not self._responses:
            return LLMResponse(content="done")
        return self._responses.pop(0)


def test_budget_exceeded():
    budget = Budget(max_total_tokens=100)
    assert not budget.exceeded(Usage(input_tokens=60, output_tokens=40))
    assert budget.exceeded(Usage(input_tokens=60, output_tokens=41))


def test_budget_unlimited():
    assert not Budget().exceeded(Usage(input_tokens=10**9, output_tokens=10**9))


async def test_finished_answer_kept_even_if_slightly_over_budget():
    """A completed reply must not be thrown away just because it crossed the cap."""
    provider = FakeProvider(
        [LLMResponse(content="hi", usage=Usage(input_tokens=80, output_tokens=30))]
    )
    agent = Agent(provider=provider, budget=Budget(max_total_tokens=100))
    assert await agent.run("task") == "hi"


async def test_agent_budget_exceeded_raises_when_more_work_needed():
    provider = FakeProvider(
        [
            LLMResponse(
                content="working",
                tool_calls=[ToolCall(name="noop", arguments={}, id="t1")],
                usage=Usage(input_tokens=80, output_tokens=30),
            )
        ]
    )
    agent = Agent(provider=provider, budget=Budget(max_total_tokens=100))
    with pytest.raises(BudgetExceededError, match="110 tokens"):
        await agent.run("task")


async def test_soft_budget_wraps_up_instead_of_raising():
    provider = FakeProvider(
        [
            LLMResponse(
                content="partial",
                tool_calls=[ToolCall(name="noop", arguments={}, id="t1")],
                usage=Usage(input_tokens=80, output_tokens=30),
            ),
            LLMResponse(content="here is what I have"),
        ]
    )
    agent = Agent(provider=provider, budget=Budget(max_total_tokens=100, soft=True))
    assert await agent.run("task") == "here is what I have"


async def test_usage_resets_each_run():
    """Desktop/CLI reuse the same Agent; the cap is per task, not lifetime."""
    provider = FakeProvider(
        [
            LLMResponse(content="one", usage=Usage(input_tokens=80, output_tokens=20)),
            LLMResponse(content="two", usage=Usage(input_tokens=80, output_tokens=20)),
        ]
    )
    agent = Agent(provider=provider, budget=Budget(max_total_tokens=100))
    assert await agent.run("first") == "one"
    assert await agent.run("second") == "two"
    assert agent.usage.input_tokens == 80
    assert agent.usage.output_tokens == 20


async def test_agent_within_budget():
    provider = FakeProvider(
        [LLMResponse(content="hi", usage=Usage(input_tokens=50, output_tokens=30))]
    )
    agent = Agent(provider=provider, budget=Budget(max_total_tokens=100))
    assert await agent.run("task") == "hi"


async def test_subagent_usage_rolls_up_to_parent_budget():
    """Sub-agent tokens count toward the root budget (Codex-style)."""
    sub_provider = FakeProvider(
        [LLMResponse(content="sub done", usage=Usage(input_tokens=70, output_tokens=40))]
    )
    sub_agent = Agent(provider=sub_provider)

    parent_provider = FakeProvider(
        [
            LLMResponse(
                content="delegating",
                tool_calls=[ToolCall(name="delegate", arguments={"task": "sub"}, id="t1")],
                usage=Usage(input_tokens=10, output_tokens=5),
            ),
            LLMResponse(content="parent done"),
        ]
    )
    parent = Agent(provider=parent_provider, budget=Budget(max_total_tokens=1000))
    parent.tools.register(DelegateTool(agent_factory=lambda: sub_agent, parent=parent))

    answer = await parent.run("do it")

    assert answer == "parent done"
    # sub-agent's 110 tokens rolled up into the parent's totals
    assert parent.usage.input_tokens == 80
    assert parent.usage.output_tokens == 45


async def test_subagent_usage_can_exceed_parent_budget():
    sub_provider = FakeProvider(
        [LLMResponse(content="sub done", usage=Usage(input_tokens=500, output_tokens=500))]
    )
    sub_agent = Agent(provider=sub_provider)

    parent_provider = FakeProvider(
        [LLMResponse(tool_calls=[ToolCall(name="delegate", arguments={"task": "x"}, id="t1")])]
    )
    parent = Agent(provider=parent_provider, budget=Budget(max_total_tokens=100))
    parent.tools.register(DelegateTool(agent_factory=lambda: sub_agent, parent=parent))

    with pytest.raises(BudgetExceededError):
        await parent.run("do it")
