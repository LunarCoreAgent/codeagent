"""Memory tools: let the agent save and recall long-term memories."""

from __future__ import annotations

from typing import Any

from codeagent.memory.store import MemoryStore
from codeagent.security.policy import RiskLevel
from codeagent.tools.base import Tool


class MemorySaveTool(Tool):
    name = "memory_save"
    description = (
        "Save a fact, user preference, decision, or lesson learned to "
        "long-term memory. It will be retrievable in future sessions."
    )
    parameters = {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "What to remember, as a concise statement."},
            "tags": {"type": "string", "description": "Optional comma-separated tags."},
        },
        "required": ["content"],
    }
    risk_level = RiskLevel.WRITE

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    async def execute(self, content: str, tags: str = "", **_: Any) -> str:
        metadata = {"tags": [t.strip() for t in tags.split(",") if t.strip()]}
        memory = await self.store.add(content, metadata)
        return f"Saved memory {memory.id}: {content[:80]}"


class MemorySearchTool(Tool):
    name = "memory_search"
    description = "Search long-term memories saved in previous sessions."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to look for."},
            "limit": {"type": "integer", "description": "Max results.", "minimum": 1, "default": 5},
        },
        "required": ["query"],
    }

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    async def execute(self, query: str, limit: int = 5, **_: Any) -> str:
        memories = await self.store.search(query, limit=limit)
        if not memories:
            return "(no matching memories)"
        return "\n".join(f"- [{m.id}] {m.content}" for m in memories)


class MemoryListTool(Tool):
    name = "memory_list"
    description = "List recently saved long-term memories."
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Max results.", "minimum": 1, "default": 20},
        },
    }

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    async def execute(self, limit: int = 20, **_: Any) -> str:
        memories = await self.store.list(limit=limit)
        if not memories:
            return "(no memories saved yet)"
        return "\n".join(f"- [{m.id}] {m.content}" for m in memories)


def memory_tools(store: MemoryStore) -> list[Tool]:
    """The standard memory tool set bound to a store."""
    return [MemorySaveTool(store), MemorySearchTool(store), MemoryListTool(store)]
