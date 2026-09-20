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
    updated_at: float = field(default_factory=time.time)


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
    async def list(self, limit: int = 50, kinds: tuple[str, ...] | None = None) -> list[Memory]:
        """Return recent memories, newest first. Optional ``kinds`` filters metadata."""

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
        if not self.path.exists():
            self._memories = []
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self._memories = []
            return
        loaded: list[Memory] = []
        for item in data if isinstance(data, list) else []:
            if not isinstance(item, dict):
                continue
            raw = {k: item[k] for k in ("id", "content", "metadata", "created_at", "updated_at") if k in item}
            if "id" not in raw or "content" not in raw:
                continue
            memory = Memory(**raw)
            if "updated_at" not in raw:
                memory.updated_at = memory.created_at
            loaded.append(memory)
        self._memories = loaded

    def _reload(self) -> None:
        """Re-read disk so UI and Agent share the same JSON file."""
        self._load()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(m) for m in self._memories]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _haystack(self, memory: Memory) -> str:
        tags = memory.metadata.get("tags") if isinstance(memory.metadata, dict) else None
        extra = " ".join(str(t) for t in tags) if isinstance(tags, list) else ""
        return f"{memory.content} {extra}"

    async def add(self, content: str, metadata: dict[str, Any] | None = None) -> Memory:
        self._reload()
        now = time.time()
        memory = Memory(
            id=uuid.uuid4().hex[:12],
            content=content,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        self._memories.append(memory)
        self._save()
        return memory

    async def update(self, memory_id: str, content: str) -> Memory | None:
        self._reload()
        for memory in self._memories:
            if memory.id == memory_id:
                memory.content = content
                memory.updated_at = time.time()
                self._save()
                return memory
        return None

    async def search(self, query: str, limit: int = 5) -> list[Memory]:
        self._reload()
        query_tokens = set(_tokenize(query))
        if not query_tokens:
            return []
        scored = []
        for memory in self._memories:
            memory_tokens = set(_tokenize(self._haystack(memory)))
            overlap = len(query_tokens & memory_tokens)
            if overlap:
                score = overlap / (len(query_tokens) ** 0.5 * len(memory_tokens) ** 0.5)
                scored.append((score, memory))
        scored.sort(key=lambda pair: (-pair[0], -pair[1].updated_at))
        return [memory for _, memory in scored[:limit]]

    async def list(self, limit: int = 50, kinds: tuple[str, ...] | None = None) -> list[Memory]:
        self._reload()
        items = sorted(self._memories, key=lambda m: -m.updated_at)
        if kinds:
            allowed = set(kinds)
            items = [
                m for m in items
                if str((m.metadata or {}).get("kind") or "") in allowed
            ]
        return items[:limit]

    async def delete(self, memory_id: str) -> bool:
        self._reload()
        before = len(self._memories)
        self._memories = [m for m in self._memories if m.id != memory_id]
        if len(self._memories) < before:
            self._save()
            return True
        return False

    async def consolidate(self, threshold: float = 0.78) -> dict[str, int]:
        """Merge near-duplicate memories on disk. Local Jaccard, no cloud."""
        self._reload()
        kept: list[Memory] = []
        merged = 0
        for memory in sorted(self._memories, key=lambda m: m.created_at):
            tokens = set(_tokenize(memory.content))
            twin: Memory | None = None
            for other in kept:
                other_tokens = set(_tokenize(other.content))
                union = tokens | other_tokens
                if not union:
                    continue
                if len(tokens & other_tokens) / len(union) >= threshold:
                    twin = other
                    break
            if twin is None:
                kept.append(memory)
                continue
            merged += 1
            if len(memory.content) > len(twin.content):
                twin.content = memory.content
            twin.updated_at = time.time()
            tags: set[str] = set()
            for item in (twin, memory):
                raw = item.metadata.get("tags") if isinstance(item.metadata, dict) else None
                if isinstance(raw, list):
                    tags.update(str(t) for t in raw if str(t).strip())
            twin.metadata = {
                **(twin.metadata or {}),
                "tags": sorted(tags),
                "source": twin.metadata.get("source") or "merge",
            }
        self._memories = kept
        self._save()
        return {"merged": merged, "remaining": len(kept)}
