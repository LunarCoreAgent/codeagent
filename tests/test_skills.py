"""Skill system: SKILL.md parsing, library, prompt injection, evolution."""

from codeagent import Agent, Skill, SkillEvolver, SkillLibrary
from codeagent.core.types import LLMResponse
from codeagent.llm.base import LLMProvider

SKILL_MD = """\
---
name: pytest-patterns
description: Battle-tested pytest patterns
---

# Pytest Patterns
Always prefer tmp_path over tempfile.
"""

PONYTAIL_MD = """\
---
name: ponytail
description: The lazy senior dev — minimal diffs, maximal signal
---

# Ponytail
Write the smallest change that could possibly work.
"""


class ScriptedProvider(LLMProvider):
    name = "scripted"

    def __init__(self, responses: list[str]):
        super().__init__(model="scripted")
        self._responses = list(responses)

    async def complete(self, messages, tools=None, system=None, **kwargs):
        content = self._responses.pop(0) if self._responses else "done"
        return LLMResponse(content=content)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_parse_skill_with_frontmatter():
    skill = Skill.parse(SKILL_MD)
    assert skill.name == "pytest-patterns"
    assert skill.description == "Battle-tested pytest patterns"
    assert "tmp_path" in skill.content
    assert "---" not in skill.content


def test_parse_plain_markdown_falls_back_to_dirname(tmp_path):
    folder = tmp_path / "my-skill"
    folder.mkdir()
    path = folder / "SKILL.md"
    path.write_text("# No frontmatter\nJust do the thing.")
    skill = Skill.parse(path.read_text(), path)
    assert skill.name == "my-skill"
    assert skill.description == ""


def test_skill_roundtrip_via_markdown():
    skill = Skill.parse(SKILL_MD)
    reparsed = Skill.parse(skill.to_markdown())
    assert reparsed.name == skill.name
    assert reparsed.description == skill.description
    assert reparsed.content == skill.content


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


def test_library_loads_nested_skill_dirs(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "SKILL.md").write_text(SKILL_MD)
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "SKILL.md").write_text(PONYTAIL_MD)
    library = SkillLibrary.load(tmp_path)
    assert len(library) == 2
    assert library.get("ponytail") is not None
    assert library.get("pytest-patterns") is not None


def test_library_ignores_missing_dir(tmp_path):
    library = SkillLibrary.load(tmp_path / "nope")
    assert len(library) == 0


def test_library_search_ranks_by_keyword_overlap(tmp_path):
    library = SkillLibrary([Skill.parse(SKILL_MD), Skill.parse(PONYTAIL_MD)])
    hits = library.search("pytest fixtures")
    assert hits[0].name == "pytest-patterns"


def test_prompt_block_contains_index_and_bodies():
    library = SkillLibrary([Skill.parse(SKILL_MD), Skill.parse(PONYTAIL_MD)])
    block = library.prompt_block()
    assert "pytest-patterns: Battle-tested pytest patterns" in block
    assert "### Skill: ponytail" in block
    assert "smallest change" in block


def test_prompt_block_respects_budget():
    library = SkillLibrary([Skill.parse(SKILL_MD), Skill.parse(PONYTAIL_MD)])
    block = library.prompt_block(max_chars=200)
    assert len(block) <= 400  # index always included; bodies truncated
    assert "pytest-patterns:" in block


def test_empty_library_prompt_block_is_empty():
    assert SkillLibrary().prompt_block() == ""


# ---------------------------------------------------------------------------
# Agent integration
# ---------------------------------------------------------------------------


async def test_agent_injects_skills_into_system_prompt():
    captured: list[str] = []

    class SpyProvider(ScriptedProvider):
        async def complete(self, messages, tools=None, system=None, **kwargs):
            captured.append(system or "")
            return await super().complete(messages, tools, system, **kwargs)

    library = SkillLibrary([Skill.parse(SKILL_MD)])
    agent = Agent(provider=SpyProvider(["final answer"]), skills=library)
    answer = await agent.run("write a test")
    assert answer == "final answer"
    assert "pytest-patterns" in captured[0]
    assert "tmp_path" in captured[0]


# ---------------------------------------------------------------------------
# Evolution
# ---------------------------------------------------------------------------


async def test_evolver_saves_new_skill(tmp_path):
    library = SkillLibrary()
    provider = ScriptedProvider([SKILL_MD])
    evolver = SkillEvolver(provider, library, tmp_path)
    skill = await evolver.evolve("fix flaky tests", "I used tmp_path everywhere")
    assert skill is not None
    assert skill.name == "pytest-patterns"
    assert library.get("pytest-patterns") is not None
    assert (tmp_path / "pytest-patterns" / "SKILL.md").is_file()


async def test_evolver_returns_none_on_none(tmp_path):
    library = SkillLibrary()
    provider = ScriptedProvider(["NONE"])
    evolver = SkillEvolver(provider, library, tmp_path)
    assert await evolver.evolve("say hi", "hi") is None
    assert len(library) == 0


async def test_evolver_rejects_malformed_skill(tmp_path):
    library = SkillLibrary()
    provider = ScriptedProvider(["here is some prose without frontmatter"])
    evolver = SkillEvolver(provider, library, tmp_path)
    assert await evolver.evolve("task", "answer") is None
    assert len(library) == 0


async def test_agent_evolves_skill_after_successful_run(tmp_path):
    library = SkillLibrary()
    provider = ScriptedProvider(["task done", SKILL_MD])
    evolver = SkillEvolver(provider, library, tmp_path)
    events: list[str] = []
    agent = Agent(
        provider=provider,
        skill_evolver=evolver,
        on_event=lambda e: events.append(e.type),
    )
    answer = await agent.run("write tests")
    assert answer == "task done"
    assert library.get("pytest-patterns") is not None
    assert "skill_evolved" in events


async def test_agent_survives_evolver_failure(tmp_path):
    class ExplodingProvider(ScriptedProvider):
        async def complete(self, messages, tools=None, system=None, **kwargs):
            if len(self._responses) == 0:
                raise RuntimeError("evolution exploded")
            return await super().complete(messages, tools, system, **kwargs)

    library = SkillLibrary()
    evolver = SkillEvolver(ExplodingProvider([]), library, tmp_path)
    agent = Agent(provider=ScriptedProvider(["fine"]), skill_evolver=evolver)
    assert await agent.run("task") == "fine"
