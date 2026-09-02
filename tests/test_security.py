import pytest

from codeagent import Agent, ToolRegistry
from codeagent.core.types import LLMResponse, ToolCall
from codeagent.llm.base import LLMProvider
from codeagent.security import (
    ApprovalDecision,
    PermissionPolicy,
    RiskLevel,
    classify_command,
)
from codeagent.tools import BashTool


@pytest.mark.parametrize(
    "command,expected",
    [
        ("ls -la", RiskLevel.READ_ONLY),
        ("git status", RiskLevel.READ_ONLY),
        ("cat file.txt | grep foo", RiskLevel.READ_ONLY),
        ("echo hello && pwd", RiskLevel.READ_ONLY),
        ("pytest -x", RiskLevel.EXECUTE),
        ("python script.py", RiskLevel.EXECUTE),
        ("pip install flask", RiskLevel.WRITE),
        ("echo hi > out.txt", RiskLevel.WRITE),
        ("git commit -m 'msg'", RiskLevel.WRITE),
        ("rm -rf build/", RiskLevel.DESTRUCTIVE),
        ("git push --force origin main", RiskLevel.DESTRUCTIVE),
        ("git reset --hard HEAD~1", RiskLevel.DESTRUCTIVE),
        ("dd if=/dev/zero of=/dev/sda", RiskLevel.DESTRUCTIVE),
    ],
)
def test_classify_command(command, expected):
    assert classify_command(command) == expected


def test_bash_tool_risk_for(tmp_path):
    tool = BashTool(tmp_path)
    assert tool.risk_for({"command": "ls"}) == RiskLevel.READ_ONLY
    assert tool.risk_for({"command": "rm -rf x"}) == RiskLevel.DESTRUCTIVE


async def test_policy_auto_approves_read_only():
    policy = PermissionPolicy.strict()
    call = ToolCall(name="read_file", arguments={"path": "a.py"})
    decision = await policy.authorize(call, RiskLevel.READ_ONLY)
    assert decision == ApprovalDecision.APPROVE


async def test_policy_fails_closed_without_handler():
    policy = PermissionPolicy.strict()
    call = ToolCall(name="bash", arguments={"command": "pytest"})
    decision = await policy.authorize(call, RiskLevel.EXECUTE)
    assert decision == ApprovalDecision.DENY


async def test_policy_handler_approve_and_deny():
    policy = PermissionPolicy(handler=lambda call, risk: ApprovalDecision.APPROVE)
    call = ToolCall(name="write_file", arguments={})
    assert await policy.authorize(call, RiskLevel.WRITE) == ApprovalDecision.APPROVE

    policy = PermissionPolicy(handler=lambda call, risk: ApprovalDecision.DENY)
    assert await policy.authorize(call, RiskLevel.WRITE) == ApprovalDecision.DENY


async def test_policy_always_allow_is_remembered():
    policy = PermissionPolicy(handler=lambda call, risk: ApprovalDecision.ALWAYS_ALLOW)
    call = ToolCall(name="bash", arguments={"command": "pytest"})
    assert await policy.authorize(call, RiskLevel.EXECUTE) == ApprovalDecision.APPROVE
    # second time: approved without invoking the handler
    policy.handler = None
    assert await policy.authorize(call, RiskLevel.EXECUTE) == ApprovalDecision.APPROVE


async def test_policy_always_deny_wins():
    policy = PermissionPolicy.permissive()
    policy.always_deny.add("bash")
    call = ToolCall(name="bash", arguments={"command": "ls"})
    assert await policy.authorize(call, RiskLevel.READ_ONLY) == ApprovalDecision.DENY


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, responses):
        super().__init__(model="fake")
        self._responses = list(responses)

    async def complete(self, messages, tools=None, system=None, **kwargs):
        return self._responses.pop(0)


async def test_agent_denies_risky_tool_call(tmp_path):
    """A denied tool call returns an error result and is never executed."""
    tool_call = ToolCall(name="bash", arguments={"command": "rm -rf /"}, id="tc1")
    provider = FakeProvider(
        [
            LLMResponse(content="deleting", tool_calls=[tool_call]),
            LLMResponse(content="ok, I will not do that"),
        ]
    )
    registry = ToolRegistry([BashTool(tmp_path)])
    agent = Agent(provider=provider, tools=registry, permissions=PermissionPolicy.strict())

    answer = await agent.run("delete everything")

    assert answer == "ok, I will not do that"
    tool_message = agent.messages[2]
    assert tool_message.tool_results[0].is_error
    assert "denied" in tool_message.tool_results[0].content


async def test_agent_emits_approval_events(tmp_path):
    events = []
    tool_call = ToolCall(name="bash", arguments={"command": "rm -rf /"}, id="tc1")
    provider = FakeProvider(
        [LLMResponse(tool_calls=[tool_call]), LLMResponse(content="done")]
    )
    registry = ToolRegistry([BashTool(tmp_path)])
    agent = Agent(
        provider=provider,
        tools=registry,
        permissions=PermissionPolicy.strict(),
        on_event=lambda e: events.append(e.type),
    )
    await agent.run("task")
    assert "approval" in events
