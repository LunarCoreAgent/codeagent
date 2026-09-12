"""Split model chain-of-thought from the user-visible answer.

Phase-1 UI shows thinking in a collapsed ``<details>`` block. Providers may
put CoT in ``reasoning_content`` / ``thinking``, or models may wrap it in
``<think>`` / ``<thinking>`` tags when prompted.
"""

from __future__ import annotations

import re

_THINK_RE = re.compile(
    r"<\s*(?:think|thinking)\s*>(.*?)<\s*/\s*(?:think|thinking)\s*>",
    re.IGNORECASE | re.DOTALL,
)


def split_thinking(content: str, reasoning: str = "") -> tuple[str, str]:
    """Return ``(visible_answer, thinking_text)``.

    Tag bodies and an explicit ``reasoning`` field are merged into thinking;
    remaining content is the visible answer. If the whole reply is only
    reasoning (no separate answer), thinking is kept and visible stays empty
    so the caller can fall back.
    """
    text = content or ""
    chunks: list[str] = []
    if reasoning and reasoning.strip():
        chunks.append(reasoning.strip())

    def _take(match: re.Match[str]) -> str:
        body = (match.group(1) or "").strip()
        if body:
            chunks.append(body)
        return "\n"

    visible = _THINK_RE.sub(_take, text)
    visible = re.sub(r"\n{3,}", "\n\n", visible).strip()
    thinking = "\n\n".join(chunks).strip()
    return visible, thinking
