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


def test_fusion_pack_and_chinese_routing():
    from codeagent.skills.fusion import FUSION_SKILLS, fusion_library

    assert "impeccable-craft" in FUSION_SKILLS
    assert "paper-craft" in FUSION_SKILLS
    assert "anime-js" in FUSION_SKILLS
    assert "comfyui" in FUSION_SKILLS
    assert "cpython" in FUSION_SKILLS
    assert "browser-skill" in FUSION_SKILLS
    assert "ego-browser" in FUSION_SKILLS
    assert "voice-surface" in FUSION_SKILLS
    lib = fusion_library()
    anime = lib.search("用 anime.js 做入场交错")
    assert anime[0].name == "anime-js"
    comfy = lib.search("用 ComfyUI 跑工作流")
    assert comfy[0].name == "comfyui"
    draw = lib.search("文生图 节点图 8188")
    assert draw[0].name == "comfyui"
    core = lib.search("改 CPython 的 ceval 和 C API")
    assert core[0].name == "cpython"
    brow = lib.search("用 BrowserSkill 打开已登录网页")
    assert brow[0].name == "browser-skill"
    hits = lib.search("把这段中文去AI味")
    assert {s.name for s in hits} & {"stop-slop-zh", "humanizer-zh"}
    ui = lib.search("做个落地页")
    assert ui[0].name == "impeccable-craft"
    block = lib.prompt_block(query="通宵挂机调研")
    assert "### Skill: research-overnight" in block


def test_install_fusion_skills(tmp_path):
    from codeagent.skills.fusion import ensure_fusion_skills, install_fusion_skills

    written = install_fusion_skills(tmp_path)
    assert "fusion-router" in written
    assert "anime-js" in written
    assert "cpython" in written
    assert (tmp_path / "karpathy-craft" / "SKILL.md").is_file()
    assert (tmp_path / "anime-js" / "SKILL.md").is_file()
    assert (tmp_path / "cpython" / "SKILL.md").is_file()
    assert "fusion-router" in ensure_fusion_skills(tmp_path)


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


def test_prompt_block_active_names_come_first():
    library = SkillLibrary([Skill.parse(SKILL_MD), Skill.parse(PONYTAIL_MD)])
    block = library.prompt_block(max_chars=400, active=["ponytail"])
    assert block.index("### Skill: ponytail") < block.index("### Skill: pytest-patterns")


def test_expand_and_match_work_content():
    from codeagent.skills.fusion import fusion_library
    from codeagent.skills.runtime import expand_work_query, match_work_skills

    assert "界面" in expand_work_query("改一下首页")
    assert "anime" in expand_work_query("用 anime.js 做入场")
    lib = fusion_library()
    names = {s.name for s in match_work_skills(lib, "改一下首页")}
    assert "impeccable-craft" in names
    assert "anime-js" in {s.name for s in match_work_skills(lib, "用 anime.js 做入场")}
    zh = {s.name for s in match_work_skills(lib, "把这段润色成人话")}
    assert zh & {"stop-slop-zh", "humanizer-zh"}
    assert "CPython" in expand_work_query("从源码编译 CPython")
    assert "cpython" in {s.name for s in match_work_skills(lib, "给 CPython 加一个 C 模块")}
    assert "cpython" not in {s.name for s in match_work_skills(lib, "写个读取 csv 的脚本")}
    assert "browser" in expand_work_query("打开网页点一下登录按钮")
    names = {s.name for s in match_work_skills(lib, "用浏览器打开已登录的后台")}
    assert names & {"browser-skill", "ego-browser"}
    assert "Comfy" in expand_work_query("出一张图")
    assert "导演台" in expand_work_query("帮我拍一条短片")
    assert "comfyui" in {s.name for s in match_work_skills(lib, "用节点图出一张图")}
    assert "voice-surface" in {s.name for s in match_work_skills(lib, "把语音面嗲音调低一点")}


def test_workspace_hints_see_frontend_files(tmp_path):
    from codeagent.skills.runtime import workspace_skill_hints

    (tmp_path / "components").mkdir()
    (tmp_path / "components" / "Hero.tsx").write_text("export default function Hero(){return null}")
    hints = workspace_skill_hints(tmp_path)
    assert "React" in hints
    assert "界面" in hints


def test_workspace_hints_see_cpython_tree(tmp_path):
    from codeagent.skills.fusion import fusion_library
    from codeagent.skills.runtime import match_work_skills, workspace_skill_hints

    (tmp_path / "Include").mkdir()
    (tmp_path / "Include" / "Python.h").write_text("/* cpython */")
    (tmp_path / "Python").mkdir()
    (tmp_path / "Python" / "ceval.c").write_text("/* eval */")
    (tmp_path / "Lib").mkdir()
    (tmp_path / "Lib" / "os.py").write_text("pass\n")
    hints = workspace_skill_hints(tmp_path)
    assert "CPython" in hints
    names = {s.name for s in match_work_skills(fusion_library(), "", hints=hints)}
    assert "cpython" in names


async def test_use_skill_tool_loads_and_lists():
    from codeagent.skills.runtime import UseSkillTool

    library = SkillLibrary([Skill.parse(SKILL_MD)])
    activated: list[str] = []
    tool = UseSkillTool(library, lambda names: activated.extend(names) or [])
    listed = await tool.execute()
    assert "pytest-patterns" in listed
    body = await tool.execute(name="pytest-patterns")
    assert "tmp_path" in body
    assert "pytest-patterns" in activated
    missing = await tool.execute(name="no-such-skill")
    assert "未找到" in missing


async def test_agent_auto_activates_and_registers_use_skill():
    captured: list[str] = []
    events: list[str] = []

    class SpyProvider(ScriptedProvider):
        async def complete(self, messages, tools=None, system=None, **kwargs):
            captured.append(system or "")
            names = [t.get("name") for t in (tools or [])]
            assert "use_skill" in names
            return await super().complete(messages, tools, system, **kwargs)

    library = SkillLibrary([Skill.parse(SKILL_MD)])
    agent = Agent(
        provider=SpyProvider(["final answer"]),
        skills=library,
        on_event=lambda e: events.append(e.type),
    )
    assert await agent.run("write a pytest") == "final answer"
    assert "skills_activated" in events
    assert "pytest-patterns" in captured[0]
    assert "工作室技能运行时" in captured[0]


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
