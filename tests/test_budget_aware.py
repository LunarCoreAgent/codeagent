"""Budget-awareness: status injection into the system prompt (BATS-style)."""

from codeagent import Agent, Budget
from codeagent.core.types import LLMResponse, Usage
from codeagent.llm.base import LLMProvider


class RecordingProvider(LLMProvider):
    name = "recording"

    def __init__(self, responses):
        super().__init__(model="rec")
        self._responses = list(responses)
        self.seen_system_prompts: list[str] = []

    async def complete(self, messages, tools=None, system=None, **kwargs):
        self.seen_system_prompts.append(system or "")
        return self._responses.pop(0)


async def test_budget_status_injected_into_system_prompt():
    provider = RecordingProvider(
        [
            LLMResponse(content="working", usage=Usage(input_tokens=30, output_tokens=10)),
            LLMResponse(content="done", usage=Usage(input_tokens=30, output_tokens=10)),
        ]
    )
    # force a second iteration by giving the first response a tool call? no —
    # instead check the first call already contains the status line
    agent = Agent(provider=provider, budget=Budget(max_total_tokens=100))
    await agent.run("task")

    assert "[Budget status]" in provider.seen_system_prompts[0]
    assert "0/100 tokens used" in provider.seen_system_prompts[0]
    assert "100% remaining" in provider.seen_system_prompts[0]


async def test_budget_status_updates_with_usage():
    from codeagent.core.types import ToolCall

    provider = RecordingProvider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall(name="unknown_tool", arguments={}, id="t1")],
                usage=Usage(input_tokens=60, output_tokens=20),
            ),
            LLMResponse(content="done"),
        ]
    )
    agent = Agent(provider=provider, budget=Budget(max_total_tokens=100))
    await agent.run("task")

    second_prompt = provider.seen_system_prompts[1]
    assert "80/100 tokens used" in second_prompt
    assert "20% remaining" in second_prompt


async def test_no_budget_no_injection():
    provider = RecordingProvider([LLMResponse(content="done")])
    agent = Agent(provider=provider, system_prompt="BASE PROMPT")
    await agent.run("task")
    assert provider.seen_system_prompts[0] == "BASE PROMPT"


async def test_budget_aware_can_be_disabled():
    provider = RecordingProvider([LLMResponse(content="done")])
    agent = Agent(provider=provider, budget=Budget(max_total_tokens=100, aware=False))
    await agent.run("task")
    assert "[Budget status]" not in provider.seen_system_prompts[0]


def test_status_message_guidance_levels():
    budget = Budget(max_total_tokens=100)
    assert "Plenty" in budget.status_message(Usage(10, 10))
    assert "draining" in budget.status_message(Usage(30, 30))
    assert "nearly exhausted" in budget.status_message(Usage(45, 45))
