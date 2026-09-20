"""SmartMemoryStore: mem0-style two-phase writes over any MemoryStore.

``add()`` runs fact extraction → reconciliation → applies ADD/UPDATE/DELETE
operations, so the store stays canonical instead of accumulating raw,
possibly contradictory entries. It implements the full MemoryStore
interface by delegation, making it a drop-in replacement usable with
``Agent(memory=...)`` and ``memory_tools(...)``.
"""

from __future__ import annotations

from typing import Any

from codeagent.llm.base import LLMProvider
from codeagent.memory.facts import FactExtractor
from codeagent.memory.reconcile import MemoryOperation, MemoryReconciler
from codeagent.memory.store import Memory, MemoryStore


class SmartMemoryStore(MemoryStore):
    """A MemoryStore wrapper with LLM-driven write reconciliation."""

    def __init__(
        self,
        store: MemoryStore,
        provider: LLMProvider,
        recall_limit: int = 10,
    ) -> None:
        self._store = store
        self._extractor = FactExtractor(provider)
        self._reconciler = MemoryReconciler(provider)
        self._recall_limit = recall_limit

    @property
    def inner(self) -> MemoryStore:
        return self._store

    async def add(self, content: str, metadata: dict[str, Any] | None = None) -> Memory:
        operations = await self.add_with_operations(content, metadata)
        written = [op for op in operations if op.event in ("ADD", "UPDATE")]
        if written:
            last = written[-1]
            found = await self._store.search(last.text, limit=1)
            return found[0] if found else Memory(id="", content=last.text)
        related = await self._store.search(content, limit=1)
        if related:
            return related[0]  # already known, nothing changed
        if not operations:
            return await self._store.add(content, metadata)
        # DELETE-only reconciliation: the content was removed, not stored
        deleted = [op for op in operations if op.event == "DELETE"][-1]
        return Memory(id=deleted.id or "", content=content)

    async def add_with_operations(
        self, content: str, metadata: dict[str, Any] | None = None
    ) -> list[MemoryOperation]:
        """Full two-phase write; returns the operations that were applied."""
        facts = await self._extractor.extract(content)
        if not facts:
            await self._store.add(content, metadata)
            return [MemoryOperation(event="ADD", text=content)]

        existing = await self._gather_related(facts)
        operations = await self._reconciler.reconcile(facts, existing)
        for op in operations:
            await self._apply(op, metadata)
        return operations

    async def _gather_related(self, facts: list[str]) -> list[Memory]:
        seen: dict[str, Memory] = {}
        for fact in facts:
            for memory in await self._store.search(fact, limit=3):
                seen.setdefault(memory.id, memory)
            if len(seen) >= self._recall_limit:
                break
        return list(seen.values())[: self._recall_limit]

    async def _apply(
        self, op: MemoryOperation, metadata: dict[str, Any] | None
    ) -> None:
        if op.event == "ADD":
            await self._store.add(op.text, metadata)
        elif op.event == "UPDATE" and op.id:
            await self._store.update(op.id, op.text)
        elif op.event == "DELETE" and op.id:
            await self._store.delete(op.id)

    # -- MemoryStore delegation -------------------------------------------

    async def update(self, memory_id: str, content: str) -> Memory | None:
        return await self._store.update(memory_id, content)

    async def search(self, query: str, limit: int = 5) -> list[Memory]:
        return await self._store.search(query, limit=limit)

    async def list(self, limit: int = 50, kinds: tuple[str, ...] | None = None) -> list[Memory]:
        return await self._store.list(limit=limit, kinds=kinds)

    async def delete(self, memory_id: str) -> bool:
        return await self._store.delete(memory_id)
