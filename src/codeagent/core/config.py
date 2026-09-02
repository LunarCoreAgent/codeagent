"""Configuration for building an agent from declarative settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Everything needed to construct an :class:`~codeagent.core.agent.Agent`."""

    provider: str = "anthropic"
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    max_tokens: int = 8192
    max_iterations: int = 50
    system_prompt: str | None = None
    root_dir: Path = Field(default_factory=Path.cwd)
    restrict_to_root: bool = True
    shell_timeout: int = 120
    # "auto" approves every tool call; "strict" auto-approves read-only
    # calls and denies the rest; "prompt" is like strict but expects an
    # approval handler to be attached via Agent(permissions=...).
    approval: Literal["auto", "strict", "prompt"] = "strict"
    budget_tokens: int | None = None
    mcp_config: Path | None = None

    def build_agent(self, **agent_kwargs):
        """Construct an Agent from this config.

        Extra keyword arguments (e.g. ``on_event``) are forwarded to the
        Agent constructor. MCP servers from ``mcp_config`` are not connected
        here — use :class:`codeagent.mcp.MCPManager` as an async context.
        """
        from codeagent.core.agent import Agent
        from codeagent.core.budget import Budget
        from codeagent.llm.registry import create_provider
        from codeagent.security.policy import PermissionPolicy
        from codeagent.tools import default_tools

        provider_kwargs: dict = {"max_tokens": self.max_tokens}
        if self.model:
            provider_kwargs["model"] = self.model
        if self.api_key:
            provider_kwargs["api_key"] = self.api_key
        if self.base_url:
            provider_kwargs["base_url"] = self.base_url

        permissions = (
            PermissionPolicy.permissive()
            if self.approval == "auto"
            else PermissionPolicy.strict()
        )
        budget = (
            Budget(max_total_tokens=self.budget_tokens)
            if self.budget_tokens is not None
            else None
        )

        return Agent(
            provider=create_provider(self.provider, **provider_kwargs),
            tools=default_tools(self.root_dir, self.restrict_to_root, self.shell_timeout),
            system_prompt=self.system_prompt,
            max_iterations=self.max_iterations,
            permissions=permissions,
            budget=budget,
            **agent_kwargs,
        )
