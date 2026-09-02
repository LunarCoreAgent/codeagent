"""Tool abstraction and registry."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from codeagent.core.types import ToolCall, ToolResult
from codeagent.security.policy import RiskLevel


class Tool(ABC):
    """A capability the agent can invoke.

    Subclasses set ``name``, ``description`` and ``parameters`` (a JSON
    Schema object describing the arguments) and implement :meth:`execute`.
    ``risk_level`` feeds the permission policy; override :meth:`risk_for`
    to classify per-call (e.g. based on the actual command being run).
    """

    name: str
    description: str
    parameters: dict[str, Any]
    risk_level: RiskLevel = RiskLevel.READ_ONLY

    def risk_for(self, arguments: dict[str, Any]) -> RiskLevel:
        return self.risk_level

    @abstractmethod
    async def execute(self, **arguments: Any) -> str:
        """Run the tool and return its output as a string."""

    def to_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ToolRegistry:
    """Holds the tools available to an agent and dispatches calls to them."""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def __len__(self) -> int:
        return len(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.to_schema() for tool in self._tools.values()]

    async def execute(self, call: ToolCall) -> ToolResult:
        tool = self.get(call.name)
        if tool is None:
            return ToolResult(
                tool_call_id=call.id,
                content=f"Unknown tool {call.name!r}. Available: {sorted(self._tools)}",
                is_error=True,
            )
        try:
            output = await tool.execute(**call.arguments)
        except TypeError as exc:
            return ToolResult(
                tool_call_id=call.id,
                content=(
                    f"Invalid arguments for tool {call.name!r}: {exc}. "
                    f"Expected schema: {json.dumps(tool.parameters)}"
                ),
                is_error=True,
            )
        except Exception as exc:  # tools must never crash the agent loop
            return ToolResult(
                tool_call_id=call.id,
                content=f"{type(exc).__name__}: {exc}",
                is_error=True,
            )
        return ToolResult(tool_call_id=call.id, content=output)
