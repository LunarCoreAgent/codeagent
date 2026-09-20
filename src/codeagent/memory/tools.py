"""Memory tools: let the agent save and recall long-term memories."""

from __future__ import annotations

from typing import Any

from codeagent.memory.store import MemoryStore
from codeagent.security.policy import RiskLevel
from codeagent.tools.base import Tool


class MemorySaveTool(Tool):
    name = "memory_save"
    description = (
        "把事实、用户偏好、决定或教训写入长期记忆，供以后会话自动检索。"
        "自己调用，不要问用户要不要记。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "要记住的一句话，尽量短而具体。"},
            "tags": {"type": "string", "description": "可选，逗号分隔标签。"},
        },
        "required": ["content"],
    }
    # 只写本机 ~/.codeagent/memory.json，不碰工作区；桌面默认策略只自动放行只读工具。
    risk_level = RiskLevel.READ_ONLY

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    async def execute(self, content: str, tags: str = "", **_: Any) -> str:
        metadata = {
            "tags": [t.strip() for t in tags.split(",") if t.strip()],
            "source": "agent",
            "kind": "fact",
        }
        memory = await self.store.add(content, metadata)
        return f"已保存记忆 {memory.id}：{content[:80]}"


class MemorySearchTool(Tool):
    name = "memory_search"
    description = "检索以往会话写入的长期记忆。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "要找的内容。"},
            "limit": {"type": "integer", "description": "最多返回几条。", "minimum": 1, "default": 5},
        },
        "required": ["query"],
    }

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    async def execute(self, query: str, limit: int = 5, **_: Any) -> str:
        memories = await self.store.search(query, limit=limit)
        if not memories:
            return "没有匹配的记忆。"
        return "\n".join(f"- [{m.id}] {m.content}" for m in memories)


class MemoryListTool(Tool):
    name = "memory_list"
    description = "列出最近保存的长期记忆。"
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "最多返回几条。", "minimum": 1, "default": 20},
        },
    }

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    async def execute(self, limit: int = 20, **_: Any) -> str:
        memories = await self.store.list(limit=limit)
        if not memories:
            return "还没有长期记忆。"
        return "\n".join(f"- [{m.id}] {m.content}" for m in memories)


def memory_tools(store: MemoryStore) -> list[Tool]:
    """The standard memory tool set bound to a store."""
    return [MemorySaveTool(store), MemorySearchTool(store), MemoryListTool(store)]
