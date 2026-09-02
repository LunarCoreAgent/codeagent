"""Skill evolution: distill task experience into reusable skills.

Inspired by SkillClaw (skills evolve from real interactions) and
self-improving-agent (evolution rules): after a task completes, an LLM
reflects on what worked and writes/updates a SKILL.md in the library, so
the agent gets better at similar tasks next time.
"""

from __future__ import annotations

import re
from pathlib import Path

from codeagent.core.types import Message
from codeagent.llm.base import LLMProvider
from codeagent.skills.skill import Skill, SkillLibrary

EVOLVE_PROMPT = """\
You are the skill-evolution module of a coding agent. The agent just \
finished a task. Decide whether the experience contains a REUSABLE lesson \
worth saving as a skill for future tasks.

TASK:
{task}

FINAL ANSWER (truncated):
{answer}

EXISTING SKILLS:
{existing}

Rules:
- Only distill GENERAL, REUSABLE techniques (e.g. "how to debug flaky \
pytest fixtures"), never task-specific trivia or secrets.
- If an existing skill covers it but could be improved, rewrite that skill \
with the same name.
- If nothing reusable was learned, reply with exactly: NONE
- Otherwise reply with a SKILL.md document in exactly this format:

---
name: short-kebab-case-name
description: one sentence describing when to use this skill
---

# Title
Concrete, actionable instructions for the agent.
"""


def _looks_like_skill(text: str) -> bool:
    return bool(re.search(r"^---\s*\n.*?name:\s*\S+", text, re.DOTALL))


class SkillEvolver:
    """Reflects on completed tasks and grows a :class:`SkillLibrary`."""

    def __init__(
        self,
        provider: LLMProvider,
        library: SkillLibrary,
        directory: str | Path,
        max_answer_chars: int = 3000,
    ) -> None:
        self.provider = provider
        self.library = library
        self.directory = Path(directory).expanduser()
        self.max_answer_chars = max_answer_chars

    async def evolve(self, task: str, answer: str) -> Skill | None:
        """Distill a finished task into a skill. Returns it, or None."""
        existing = (
            "\n".join(f"- {s.name}: {s.description}" for s in self.library)
            or "(none yet)"
        )
        prompt = EVOLVE_PROMPT.format(
            task=task[:2000],
            answer=answer[: self.max_answer_chars],
            existing=existing,
        )
        response = await self.provider.complete(
            messages=[Message.user(prompt)],
            system="You distill agent experience into reusable skills.",
        )
        text = response.content.strip()
        if not text or text.upper().startswith("NONE"):
            return None
        if not _looks_like_skill(text):
            return None
        skill = Skill.parse(text)
        if not skill.name or skill.name == "unnamed" or not skill.content:
            return None
        self.library.save(skill, self.directory)
        return skill
