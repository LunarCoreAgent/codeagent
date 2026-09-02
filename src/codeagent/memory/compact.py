"""Short-term memory: conversation compaction.

When the message history grows past a threshold, older turns are summarized
by the model itself and replaced with a compact summary, keeping the most
recent turns verbatim. This mirrors the "local summary" short-term memory
pattern (and Codex's compaction): unbounded sessions without unbounded
context growth.
"""

from __future__ import annotations

from dataclasses import dataclass

from codeagent.core.types import Message, Role
from codeagent.llm.base import LLMProvider

SUMMARY_INSTRUCTION = """\
Summarize the conversation transcript below so work can continue without it.

Preserve exactly:
- the user's goal and any explicit requirements or preferences
- decisions made and why
- files created/modified (paths) and what changed
- commands run and their outcomes (especially failures)
- current task state: what is done, what remains

Be concise and factual. Write the summary in the conversation's language.

Transcript:
"""

SUMMARY_PREFIX = "[Summary of earlier conversation — details compacted]\n"


@dataclass
class CompactionConfig:
    max_messages: int = 40  # compact when history exceeds this
    keep_recent: int = 10   # trailing messages kept verbatim


class ConversationCompactor:
    """Summarizes old conversation turns using an LLM provider."""

    def __init__(
        self,
        provider: LLMProvider,
        config: CompactionConfig | None = None,
    ) -> None:
        self.provider = provider
        self.config = config or CompactionConfig()

    async def maybe_compact(self, messages: list[Message]) -> list[Message]:
        if len(messages) <= self.config.max_messages:
            return messages
        boundary = len(messages) - self.config.keep_recent
        old, recent = messages[:boundary], messages[boundary:]
        summary = await self._summarize(old)
        return [Message.user(SUMMARY_PREFIX + summary)] + recent

    async def _summarize(self, messages: list[Message]) -> str:
        transcript = self._render(messages)
        response = await self.provider.complete(
            messages=[Message.user(SUMMARY_INSTRUCTION + transcript)],
            tools=None,
            system=None,
        )
        return response.content

    @staticmethod
    def _render(messages: list[Message]) -> str:
        lines: list[str] = []
        for msg in messages:
            role = msg.role.value
            if msg.role in (Role.USER, Role.SYSTEM, Role.ASSISTANT) and msg.content:
                lines.append(f"{role}: {msg.content[:800]}")
            for call in msg.tool_calls:
                lines.append(f"{role} [tool_call] {call.name}({str(call.arguments)[:300]})")
            for result in msg.tool_results:
                status = "error" if result.is_error else "ok"
                lines.append(f"tool [{status}] {result.content[:400]}")
        return "\n".join(lines)
