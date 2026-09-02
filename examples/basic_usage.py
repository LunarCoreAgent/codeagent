"""Minimal example: run a coding task with the agent.

Set ANTHROPIC_API_KEY (or OPENAI_API_KEY) before running:

    python examples/basic_usage.py
"""

import asyncio
from pathlib import Path

from codeagent import Agent, create_provider, default_tools


async def main() -> None:
    provider = create_provider("anthropic")  # or "openai", "ollama"
    agent = Agent(
        provider=provider,
        tools=default_tools(root_dir=Path.cwd()),
        max_iterations=20,
    )
    answer = await agent.run("List the files in this directory and summarize the project layout.")
    print(answer)
    print(f"\ntokens used: {agent.usage.input_tokens} in / {agent.usage.output_tokens} out")


if __name__ == "__main__":
    asyncio.run(main())
