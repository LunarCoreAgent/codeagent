"""Agent tools for the CodeCoreAgent knowledge vault (Obsidian / LLM Wiki)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codeagent.knowledge import (
    KnowledgeConfig,
    ensure_knowledge_vault,
    ingest_text,
    is_vault_ready,
    list_pages,
    read_page,
)
from codeagent.security.policy import RiskLevel
from codeagent.tools.base import Tool


class KnowledgeSearchTool(Tool):
    name = "knowledge_search"
    description = (
        "Search the CodeCoreAgent knowledge base (Obsidian / LLM Wiki vault). "
        "Use for concepts, project notes, and prior decisions stored in the wiki."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Keywords to find."},
            "limit": {
                "type": "integer",
                "description": "Max pages.",
                "minimum": 1,
                "default": 8,
            },
        },
        "required": ["query"],
    }

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    async def execute(self, query: str, limit: int = 8, **_: Any) -> str:
        pages = list_pages(self.root, query=query, limit=int(limit or 8))
        if not pages:
            return "(knowledge base: no matching pages)"
        lines = [f"- [{p.rel}] {p.title}: {p.preview[:100]}" for p in pages]
        return "\n".join(lines)


class KnowledgeReadTool(Tool):
    name = "knowledge_read"
    description = "Read one markdown page from the knowledge vault by relative path."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path, e.g. wiki/overview.md",
            },
        },
        "required": ["path"],
    }

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    async def execute(self, path: str, **_: Any) -> str:
        page = read_page(self.root, path)
        if page is None:
            return f"(not found: {path})"
        body = page["content"]
        if len(body) > 6000:
            body = body[:6000] + "\n…(truncated)"
        return f"# {page['title']}\n\n{body}"


class KnowledgeIngestTool(Tool):
    name = "knowledge_ingest"
    description = (
        "Save raw source material into knowledge vault raw/inbox "
        "(immutable layer). Later compile into wiki pages as needed."
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["title", "content"],
    }
    risk_level = RiskLevel.WRITE

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    async def execute(self, title: str, content: str, **_: Any) -> str:
        r = ingest_text(self.root, title, content)
        return f"Saved to {r['rel']}"


def knowledge_tools(cfg: KnowledgeConfig | None = None) -> list[Tool]:
    """Return tools if vault is enabled; auto-deploy local wiki when missing."""
    cfg = cfg or KnowledgeConfig.load()
    if not cfg.enabled:
        return []
    root = cfg.vault_path()
    # 已就绪则跳过 ensure，避免每条对话卡磁盘
    if not is_vault_ready(root):
        ensure_knowledge_vault(cfg)
    if not is_vault_ready(root):
        return []
    return [
        KnowledgeSearchTool(root),
        KnowledgeReadTool(root),
        KnowledgeIngestTool(root),
    ]
