"""Example: extend the agent with a custom tool."""

import asyncio
from typing import Any

from codeagent import Agent, Tool, ToolRegistry, create_provider, default_tools


class WordCountTool(Tool):
    name = "word_count"
    description = "Count lines, words and characters in a file."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file."},
        },
        "required": ["path"],
    }

    async def execute(self, path: str, **_: Any) -> str:
        with open(path) as f:
            text = f.read()
        return f"{len(text.splitlines())} lines, {len(text.split())} words, {len(text)} chars"


async def main() -> None:
    tools = default_tools(root_dir=".")
    tools.register(WordCountTool())

    agent = Agent(provider=create_provider("anthropic"), tools=tools)
    answer = await agent.run("Use the word_count tool on README.md and report the result.")
    print(answer)


if __name__ == "__main__":
    asyncio.run(main())
