"""Ask the app to use or install a built-in runtime."""

from __future__ import annotations

from typing import Any

from codeagent.security.policy import RiskLevel
from codeagent.skills.language import ensure_runtime
from codeagent.tools.base import Tool


class EnsureRuntimeTool(Tool):
    name = "ensure_runtime"
    description = (
        "Use the app's own browser, terminal, Python, or Node.js. "
        "If Node.js is missing, download the official build into ~/.codeagent/runtime. "
        "Call this before telling the user to install those tools."
    )
    parameters = {
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "description": "One of: browser, terminal, python, node.",
            },
        },
        "required": ["kind"],
    }
    risk_level = RiskLevel.EXECUTE

    async def execute(self, kind: str = "", **_: Any) -> str:
        return ensure_runtime(kind)
