"""ask_external_agent: a tool letting a stuck worker call another agent platform."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codeagent.harness.adapters import CliHarness, HarnessResult, discover_harnesses
from codeagent.security.policy import RiskLevel
from codeagent.tools.base import Tool


class AskHarnessTool(Tool):
    name = "ask_external_agent"
    description = (
        "当你遇到困难、不理解需求、或凭自身能力无法完成时，呼叫本机安装的"
        "其他 agent 平台（如 Claude Code / Codex / Gemini CLI）帮忙。"
        "把任务背景、你已尝试的方案、卡在哪里写清楚，它会直接在工作目录里操作。"
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "完整的求助描述：任务背景 + 已尝试方案 + 卡点。",
            },
            "harness": {
                "type": "string",
                "description": "指定平台名（如 claude-code/codex/gemini）；不填则自动选第一个可用的。",
            },
        },
        "required": ["prompt"],
    }
    risk_level = RiskLevel.EXECUTE  # external agent may modify the workspace

    def __init__(
        self,
        harnesses: list[CliHarness] | None = None,
        cwd: str | Path | None = None,
    ) -> None:
        self.harnesses = harnesses if harnesses is not None else discover_harnesses()
        self.cwd = Path(cwd) if cwd else None

    async def execute(self, prompt: str, harness: str | None = None) -> str:
        if not self.harnesses:
            return (
                "本机未发现可用的外部 agent 平台（claude/codex/gemini/"
                "cursor-agent/opencode 均未安装）。请换个思路自己解决。"
            )
        chosen = None
        if harness:
            chosen = next((h for h in self.harnesses if h.name == harness), None)
            if chosen is None:
                names = ", ".join(h.name for h in self.harnesses)
                return f"平台 {harness!r} 不可用；本机可用：{names}"
        else:
            chosen = self.harnesses[0]
        result: HarnessResult = await chosen.run(prompt, cwd=self.cwd)
        prefix = f"[{chosen.name}]"
        if result.ok:
            return f"{prefix} 外部平台完成：\n{result.output}"
        return f"{prefix} 外部平台也失败了：{result.output}\n请换平台重试或向用户求助。"
