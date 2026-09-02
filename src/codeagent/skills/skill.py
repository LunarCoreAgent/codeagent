"""Agent skills: reusable instruction packs in SKILL.md format.

A skill is a markdown file with YAML-ish frontmatter::

    ---
    name: pytest-patterns
    description: Battle-tested pytest patterns for fixtures and parametrization
    ---

    # Pytest Patterns
    ... instructions the agent should follow ...

This is the format used by community skill packs (taste-skill, darwin-skill,
gsap-skills, impeccable, qaskills, ponytail, ...), so any of them can be
dropped into a skills directory and loaded by :class:`SkillLibrary`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

FRONTMATTER_DELIMITER = "---"


@dataclass
class Skill:
    """A single loaded skill."""

    name: str
    description: str
    content: str
    path: Path | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def parse(cls, text: str, path: Path | None = None) -> "Skill":
        """Parse SKILL.md text (frontmatter + markdown body)."""
        metadata: dict[str, str] = {}
        body = text
        lines = text.splitlines()
        if lines and lines[0].strip() == FRONTMATTER_DELIMITER:
            for i, line in enumerate(lines[1:], start=1):
                if line.strip() == FRONTMATTER_DELIMITER:
                    body = "\n".join(lines[i + 1 :]).strip()
                    break
                if ":" in line:
                    key, _, value = line.partition(":")
                    metadata[key.strip()] = value.strip().strip('"').strip("'")
            else:
                body = text  # unterminated frontmatter: treat as plain markdown
        name = metadata.get("name") or (path.parent.name if path else "unnamed")
        description = metadata.get("description", "")
        return cls(
            name=name,
            description=description,
            content=body,
            path=path,
            metadata=metadata,
        )

    def to_markdown(self) -> str:
        """Serialize back to SKILL.md format."""
        return (
            f"{FRONTMATTER_DELIMITER}\n"
            f"name: {self.name}\n"
            f"description: {self.description}\n"
            f"{FRONTMATTER_DELIMITER}\n\n"
            f"{self.content.strip()}\n"
        )


class SkillLibrary:
    """A collection of skills loaded from one or more directories."""

    def __init__(self, skills: list[Skill] | None = None) -> None:
        self._skills: dict[str, Skill] = {}
        for skill in skills or []:
            self.add(skill)

    def add(self, skill: Skill) -> Skill:
        """Add or replace a skill (keyed by name)."""
        self._skills[skill.name] = skill
        return skill

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def remove(self, name: str) -> bool:
        return self._skills.pop(name, None) is not None

    def __len__(self) -> int:
        return len(self._skills)

    def __iter__(self):
        return iter(self._skills.values())

    @classmethod
    def load(cls, *directories: str | Path) -> "SkillLibrary":
        """Load every ``SKILL.md`` found under the given directories.

        Layout is flexible: both ``dir/SKILL.md`` and
        ``dir/<skill-name>/SKILL.md`` are picked up.
        """
        library = cls()
        for directory in directories:
            root = Path(directory).expanduser()
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("SKILL.md")):
                library.add(Skill.parse(path.read_text(encoding="utf-8"), path))
        return library

    def save(self, skill: Skill, directory: str | Path) -> Path:
        """Persist a skill to ``directory/<name>/SKILL.md`` and register it."""
        folder = Path(directory).expanduser() / skill.name
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "SKILL.md"
        path.write_text(skill.to_markdown(), encoding="utf-8")
        skill.path = path
        self.add(skill)
        return path

    def search(self, query: str, limit: int = 5) -> list[Skill]:
        """Keyword-overlap search over name + description + content."""
        words = {w.lower() for w in query.split() if len(w) > 1}
        if not words:
            return []
        scored: list[tuple[int, Skill]] = []
        for skill in self._skills.values():
            haystack = f"{skill.name} {skill.description} {skill.content}".lower()
            score = sum(1 for w in words if w in haystack)
            if score:
                scored.append((score, skill))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [skill for _, skill in scored[:limit]]

    def prompt_block(self, max_chars: int = 6000) -> str:
        """Render skills as a system-prompt block.

        Includes an index of every skill (name + description) plus the full
        body of as many skills as fit within ``max_chars``.
        """
        if not self._skills:
            return ""
        index_lines = [
            f"- {skill.name}: {skill.description or '(no description)'}"
            for skill in self._skills.values()
        ]
        parts = [
            "[Available skills — follow these instructions when relevant]",
            "\n".join(index_lines),
        ]
        budget_left = max_chars - sum(len(p) for p in parts)
        for skill in self._skills.values():
            block = f"\n### Skill: {skill.name}\n{skill.content.strip()}"
            if budget_left - len(block) < 0:
                break
            parts.append(block)
            budget_left -= len(block)
        return "\n".join(parts)
