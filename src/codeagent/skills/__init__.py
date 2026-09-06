"""Skill system: loadable SKILL.md packs + self-evolution."""

from codeagent.skills.evolve import SkillEvolver
from codeagent.skills.fusion import (
    FUSION_SKILLS,
    ensure_fusion_skills,
    fusion_library,
    install_fusion_skills,
)
from codeagent.skills.runtime import (
    UseSkillTool,
    expand_work_query,
    match_work_skills,
    workspace_skill_hints,
)
from codeagent.skills.skill import Skill, SkillLibrary

__all__ = [
    "Skill",
    "SkillLibrary",
    "SkillEvolver",
    "FUSION_SKILLS",
    "fusion_library",
    "install_fusion_skills",
    "ensure_fusion_skills",
    "UseSkillTool",
    "expand_work_query",
    "match_work_skills",
    "workspace_skill_hints",
]
