"""Long-term memory: persistent storage and retrieval across sessions.

The store abstraction is deliberately small so production deployments can
swap in mem0 / vector databases / graph stores (neo4j) without changing
agent code.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Memory:
    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class MemoryStore(ABC):
    """Persistence backend for long-term agent memory."""

    @abstractmethod
    async def add(self, content: str, metadata: dict[str, Any] | None = None) -> Memory:
        """Store a memory and return it."""

    @abstractmethod
    async def update(self, memory_id: str, content: str) -> Memory | None:
        """Replace a memory's content. Returns the updated memory, or None."""

    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> list[Memory]:
        """Return the most relevant memories for ``query``."""

    @abstractmethod
    async def list(self, limit: int = 50) -> list[Memory]:
        """Return recent memories, newest first."""

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by id. Returns True if it existed."""


_TOKEN_RE = re.compile(r"[a-z0-9_]+|[一-鿿]")


def _tokenize(text: str) -> list[str]:
    """English words plus individual CJK characters."""
    return _TOKEN_RE.findall(text.lower())


class LocalMemoryStore(MemoryStore):
    """JSON-file memory store with keyword-overlap retrieval.

    Zero external dependencies — a sensible default. For semantic search,
    implement :class:`MemoryStore` over an embedding index instead.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._memories: list[Memory] = []
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            data = json.loads(self.path.read_text())
            self._memories = [Memory(**item) for item in data]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(m) for m in self._memories]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    async def add(self, content: str, metadata: dict[str, Any] | None = None) -> Memory:
        memory = Memory(
            id=uuid.uuid4().hex[:12],
            content=content,
            metadata=metadata or {},
        )
        self._memories.append(memory)
        self._save()
        return memory

    async def update(self, memory_id: str, content: str) -> Memory | None:
        for memory in self._memories:
            if memory.id == memory_id:
                memory.content = content
                self._save()
                return memory
        return None

    async def search(self, query: str, limit: int = 5) -> list[Memory]:
        query_tokens = set(_tokenize(query))
        if not query_tokens:
            return []
        scored = []
        for memory in self._memories:
            memory_tokens = set(_tokenize(memory.content))
            overlap = len(query_tokens & memory_tokens)
            if overlap:
                score = overlap / (len(query_tokens) ** 0.5 * len(memory_tokens) ** 0.5)
                scored.append((score, memory))
        scored.sort(key=lambda pair: (-pair[0], -pair[1].created_at))
        return [memory for _, memory in scored[:limit]]

    async def list(self, limit: int = 50) -> list[Memory]:
        return sorted(self._memories, key=lambda m: -m.created_at)[:limit]

    async def delete(self, memory_id: str) -> bool:
        before = len(self._memories)
        self._memories = [m for m in self._memories if m.id != memory_id]
        if len(self._memories) < before:
            self._save()
            return True
        return False
