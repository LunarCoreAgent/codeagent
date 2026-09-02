"""Sub-agent delegation with usage roll-up to the parent's budget."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from codeagent.security.policy import RiskLevel
from codeagent.tools.base import Tool

if TYPE_CHECKING:
    from codeagent.core.agent import Agent


class DelegateTool(Tool):
    """Spawn a fresh sub-agent for a self-contained subtask.

    The sub-agent starts with clean history; its token usage rolls up into
    the parent agent's totals, so root budgets account for delegation
    (the same accounting Codex applies to subagents and root goals).
    """

    name = "delegate"
    description = (
        "Delegate a self-contained subtask to a fresh sub-agent and return "
        "its final answer. Give complete instructions: the sub-agent does "
        "not see this conversation."
    )
    parameters = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Complete, self-contained instructions for the sub-agent.",
            },
        },
        "required": ["task"],
    }
    risk_level = RiskLevel.EXECUTE

    def __init__(self, agent_factory: Callable[[], "Agent"], parent: "Agent") -> None:
        self._factory = agent_factory
        self._parent = parent

    async def execute(self, task: str, **_: Any) -> str:
        sub_agent = self._factory()
        try:
            return await sub_agent.run(task)
        finally:
            self._parent._add_child_usage(sub_agent.usage)
