"""Worker: a project-aware agent instance bound to its own model."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from typing import TYPE_CHECKING

from codeagent.core.agent import Agent
from codeagent.core.budget import Budget
from codeagent.llm.aggregate import parse_provider_spec
from codeagent.skills.skill import SkillLibrary
from codeagent.tools import ToolRegistry, default_tools

if TYPE_CHECKING:
    from codeagent.settings import Settings


@dataclass
class WorkerConfig:
    """One worker's identity: which model it runs and what it's good at."""

    name: str
    provider: str = "anthropic"
    model: str | None = None
    description: str = ""  # capabilities, for the leader's planning
    base_url: str | None = None
    api_key: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkerConfig":
        unknown = set(data) - {"name", "provider", "model", "description", "base_url", "api_key"}
        if unknown:
            raise ValueError(f"worker config: unknown field(s) {sorted(unknown)}")
        if not data.get("name"):
            raise ValueError("worker config needs a 'name'")
        return cls(
            name=data["name"],
            provider=data.get("provider", "anthropic"),
            model=data.get("model"),
            description=data.get("description", ""),
            base_url=data.get("base_url"),
            api_key=data.get("api_key"),
        )


def load_workers_yaml(path: str | Path) -> list[WorkerConfig]:
    """Load worker roster from YAML: ``workers: [{name, provider, ...}]``."""
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise ValueError("PyYAML is required: pip install pyyaml") from exc
    data = yaml.safe_load(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("workers"), list):
        raise ValueError("workers file must be a mapping with a 'workers' list")
    return [WorkerConfig.from_dict(item) for item in data["workers"]]


def build_worker_agent(
    config: WorkerConfig,
    root: Path,
    registry: ToolRegistry | None = None,
    skills: SkillLibrary | None = None,
    settings: "Settings | None" = None,
    project_context: str = "",
    max_iterations: int = 30,
    budget: Budget | None = None,
    on_event=None,
) -> Agent:
    """Build a worker agent with full tools, skills, and project understanding."""
    provider_kwargs: dict[str, Any] = {}
    if config.model:
        provider_kwargs["model"] = config.model
    if config.base_url:
        provider_kwargs["base_url"] = config.base_url
    if config.api_key:
        provider_kwargs["api_key"] = config.api_key
    provider = parse_provider_spec(config.provider, **provider_kwargs)

    system = (
        f"你是工人 '{config.name}'，由领导分派任务。"
        f"{config.description}\n\n"
        "你可以使用所有可用工具完成任务；遵循已加载的技能指引。\n"
        "完成后用中文简要汇报：做了什么、产出文件、遗留问题。"
    )
    if project_context:
        system += f"\n\n[项目概况]\n{project_context}"

    from codeagent.skills.runtime import workspace_skill_hints

    return Agent(
        provider=provider,
        tools=registry or default_tools(root),
        system_prompt=system,
        max_iterations=max_iterations,
        budget=budget,
        skills=skills,
        settings=settings,
        on_event=on_event,
        workspace_hints=workspace_skill_hints(root, extra=project_context),
    )
