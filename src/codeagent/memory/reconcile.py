"""Phase 2 of mem0-style memory writing: reconcile facts against the store.

Newly extracted facts are compared with related existing memories, and the
model decides the operations: ADD new ones, UPDATE memories the facts
refine or contradict, DELETE memories that are no longer true. This keeps
the store free of duplicated or mutually contradictory entries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from codeagent.core.types import Message
from codeagent.llm.base import LLMProvider
from codeagent.memory.facts import parse_json_object
from codeagent.memory.store import Memory

RECONCILE_PROMPT = """\
You manage a long-term memory store. Compare NEW FACTS against EXISTING
MEMORIES and decide the operations to apply.

EXISTING MEMORIES:
{existing}

NEW FACTS:
{facts}

Rules:
- ADD: the fact is new information not covered by any existing memory.
- UPDATE: the fact refines, corrects, or contradicts an existing memory —
  keep the id, write the new canonical text.
- DELETE: an existing memory is no longer true given the facts.
- Do NOT add near-duplicates of existing memories.
- If nothing changes, return an empty operations list.

Return ONLY JSON:
{{"operations": [
  {{"event": "ADD", "text": "..."}},
  {{"event": "UPDATE", "id": "...", "text": "..."}},
  {{"event": "DELETE", "id": "..."}}
]}}
"""


@dataclass
class MemoryOperation:
    event: Literal["ADD", "UPDATE", "DELETE"]
    text: str = ""
    id: str | None = None


class MemoryReconciler:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def reconcile(
        self, facts: list[str], existing: list[Memory]
    ) -> list[MemoryOperation]:
        existing_text = (
            "\n".join(f"- [{m.id}] {m.content}" for m in existing) or "(empty)"
        )
        facts_text = "\n".join(f"- {f}" for f in facts)
        response = await self.provider.complete(
            messages=[
                Message.user(RECONCILE_PROMPT.format(existing=existing_text, facts=facts_text))
            ],
            tools=None,
            system=None,
        )
        return self._parse_operations(response.content)

    @staticmethod
    def _parse_operations(text: str) -> list[MemoryOperation]:
        data = parse_json_object(text)
        operations = data.get("operations", [])
        if not isinstance(operations, list):
            return []
        parsed: list[MemoryOperation] = []
        for op in operations:
            if not isinstance(op, dict):
                continue
            event = op.get("event")
            if event not in ("ADD", "UPDATE", "DELETE"):
                continue
            if event == "ADD" and not op.get("text"):
                continue
            if event in ("UPDATE", "DELETE") and not op.get("id"):
                continue
            parsed.append(
                MemoryOperation(event=event, text=op.get("text", ""), id=op.get("id"))
            )
        return parsed
