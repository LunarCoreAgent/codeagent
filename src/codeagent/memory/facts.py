"""Phase 1 of mem0-style memory writing: extract atomic facts with an LLM.

Given raw text (a conversation snippet, a user statement), the model pulls
out self-contained atomic facts — e.g. "名字叫张三", "李四在小米工作" —
instead of storing the raw text verbatim.
"""

from __future__ import annotations

import json

from codeagent.core.types import Message
from codeagent.llm.base import LLMProvider

EXTRACT_FACTS_PROMPT = """\
Extract atomic facts from the text below.

Rules:
- Each fact is a single, self-contained statement.
- Split compound sentences into separate facts.
- Preserve concrete details: names, dates, preferences, decisions, paths.
- Write facts in the same language as the text.
- If the text contains nothing worth remembering, return an empty list.

Return ONLY JSON: {"facts": ["fact 1", "fact 2", ...]}

Text:
"""


def parse_json_object(text: str) -> dict:
    """Leniently parse the first JSON object in an LLM response."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}


class FactExtractor:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def extract(self, text: str) -> list[str]:
        response = await self.provider.complete(
            messages=[Message.user(EXTRACT_FACTS_PROMPT + text)],
            tools=None,
            system=None,
        )
        data = parse_json_object(response.content)
        facts = data.get("facts", [])
        if not isinstance(facts, list):
            return []
        return [f.strip() for f in facts if isinstance(f, str) and f.strip()]
