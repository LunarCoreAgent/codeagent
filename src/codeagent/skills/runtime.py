"""Studio skill runtime: recognize work, auto-enable, let the model invoke any skill."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable

from codeagent.security.policy import RiskLevel
from codeagent.skills.skill import Skill, SkillLibrary
from codeagent.tools.base import Tool

STUDIO_SKILL_RULES = """\
[工作室技能运行时]
根据用户任务和项目文件自动识别工作内容，并启用匹配的技能。你必须遵守已启用技能正文。
目录里的每一条技能都可以由你自己调用 use_skill 加载，不要让用户点选或确认。
只启用与当前任务相关的技能；禁止把全部规则同时套到一句话上。
知识库、视频运营等插件工具（knowledge_search / knowledge_read / knowledge_ingest / \
video_ops_status / video_ops_log / video_ops_draft / video_generate）在相关时直接调用。
文生视频用 video_generate：wan（局域网 Gradio）、minimax（Hailuo）、kimi、comfy（ComfyUI 工作流）。
"""

# Everyday phrasing → skill-search tokens (CJK has no spaces).
_QUERY_EXPAND: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"首页|落地页|网站|页面|改样式|改界面|仪表盘|后台|组件|按钮|视觉|排版"),
     " 界面 前端 UI UX 设计 品味"),
    (re.compile(r"react|动效|动画|bits|anime\.?js|animejs|时间线|stagger|描边", re.I),
     " React 动效 组件 动画 anime"),
    (re.compile(r"润色|改写|人话|AI味|套话|口语化|去AI|机翻|翻译腔"),
     " 中文 人性化 slop 改写"),
    (re.compile(r"论文|开题|投稿|审稿|latex|综述|实验表"), " 论文 投稿 脊柱"),
    (re.compile(r"短视频|短剧|剪辑|分镜|成片|口播|发布|运营|文生视频|海螺|Hailuo|ComfyUI|comfy", re.I),
     " 视频 短剧 剪辑 Comfy 文生视频"),
    (re.compile(r"通宵|挂机|调研|文献|值守"), " 研究 通宵"),
    (re.compile(r"从零|原理|nanoGPT|卡帕西|karpathy", re.I), " 原理 Karpathy"),
    (re.compile(r"蒸馏|按.+的方式|导师口吻"), " 蒸馏 女娲"),
    (re.compile(r"公众号|长文|选题|提纲|专栏"), " 写作 长文"),
    (re.compile(r"文档|README|changelog|体例"), " 文档 中文 体例"),
)

_EXT_HINTS: dict[str, str] = {
    ".tsx": "React 界面 前端 UI 组件",
    ".jsx": "React 界面 前端 UI",
    ".vue": "界面 前端 组件",
    ".css": "界面 设计 品味",
    ".scss": "界面 设计",
    ".html": "界面 前端 UX",
    ".svg": "界面 视觉",
    ".py": "代码 实现",
    ".ts": "代码 前端",
    ".js": "代码 前端",
    ".tex": "论文 latex 投稿",
    ".bib": "论文 相关工作",
    ".md": "文档 中文 体例",
    ".mp4": "视频 剪辑 发布",
    ".mov": "视频 剪辑",
    ".srt": "视频 字幕 剪辑",
}

_DIR_HINTS: dict[str, str] = {
    "01-script": "短剧 剧本 视频",
    "02-generate": "视频 生成",
    "03-edit": "视频 剪辑",
    "04-analyze": "运营 分析",
    "05-publish": "发布 视频",
    "components": "React 界面 组件",
    "wiki": "知识库 文档",
}

_SKIP_DIR = {".git", "node_modules", "__pycache__", "conversations", "dist", "build"}


def expand_work_query(query: str) -> str:
    """Turn colloquial / CJK task text into searchable skill tokens."""
    text = (query or "").strip()
    if not text:
        return ""
    bits = [text]
    for pattern, extra in _QUERY_EXPAND:
        if pattern.search(text):
            bits.append(extra)
    return " ".join(bits)


def workspace_skill_hints(root: str | Path | None = None, extra: str = "") -> str:
    """Describe the current project so skill search can see file types."""
    parts: list[str] = []
    extra = (extra or "").strip()
    if extra:
        parts.append(extra)
    if root is None:
        return " ".join(parts)
    path = Path(root).expanduser()
    if not path.is_dir():
        return " ".join(parts)
    parts.append(f"项目目录 {path.name}")
    exts: Counter[str] = Counter()
    dir_hits: set[str] = set()
    try:
        for item in path.rglob("*"):
            if any(part in _SKIP_DIR for part in item.parts):
                continue
            if item.is_dir():
                if item.name in _DIR_HINTS:
                    dir_hits.add(item.name)
                continue
            if item.is_file():
                suf = item.suffix.lower()
                if suf:
                    exts[suf] += 1
    except OSError:
        return " ".join(parts)
    for suf, _count in exts.most_common(16):
        hint = _EXT_HINTS.get(suf)
        if hint:
            parts.append(hint)
    for name in dir_hits:
        parts.append(_DIR_HINTS[name])
    if exts:
        parts.append("文件类型 " + " ".join(f"{k}:{v}" for k, v in exts.most_common(8)))
    return " ".join(parts)


def match_work_skills(
    library: SkillLibrary,
    query: str,
    hints: str = "",
    limit: int = 8,
) -> list[Skill]:
    """Pick skills for this task + workspace. Empty query still uses hints."""
    blob = expand_work_query(" ".join(x for x in (query, hints) if x).strip())
    if not blob.strip():
        return []
    return library.search(blob, limit=limit)


class UseSkillTool(Tool):
    """Let the model independently load any catalogued skill."""

    name = "use_skill"
    description = (
        "Load one or more skill packs by name and follow them for this task. "
        "Call this yourself whenever a catalog skill is relevant. "
        "Do not ask the user to pick skills. Omit names to list the catalog."
    )
    parameters = {
        "type": "object",
        "properties": {
            "names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Skill names from the catalog (e.g. impeccable-craft).",
            },
            "name": {
                "type": "string",
                "description": "Single skill name if not using names.",
            },
        },
    }
    risk_level = RiskLevel.READ_ONLY

    def __init__(
        self,
        library: SkillLibrary,
        activate: Callable[[list[str]], list[Skill]] | None = None,
    ) -> None:
        self.library = library
        self._activate = activate

    def _wanted(self, names: Any, name: Any) -> list[str]:
        wanted: list[str] = []
        if isinstance(names, str) and names.strip():
            wanted.extend(part.strip() for part in names.split(",") if part.strip())
        elif isinstance(names, Iterable):
            wanted.extend(str(item).strip() for item in names if str(item).strip())
        if isinstance(name, str) and name.strip():
            wanted.append(name.strip())
        # de-dupe, keep order
        seen: set[str] = set()
        ordered: list[str] = []
        for item in wanted:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(item)
        return ordered

    def _resolve(self, raw: str) -> Skill | None:
        hit = self.library.get(raw)
        if hit is not None:
            return hit
        key = raw.lower().replace("_", "-")
        for skill in self.library:
            if skill.name.lower() == key:
                return skill
        return None

    async def execute(self, names: Any = None, name: Any = None, **_: Any) -> str:
        wanted = self._wanted(names, name)
        if not wanted:
            lines = [
                f"- {skill.name}: {skill.description or '(无说明)'}"
                for skill in self.library
            ]
            return "技能目录（用 use_skill 加载正文）：\n" + "\n".join(lines)
        found: list[Skill] = []
        missing: list[str] = []
        for raw in wanted:
            skill = self._resolve(raw)
            if skill is None:
                missing.append(raw)
            else:
                found.append(skill)
        if self._activate is not None and found:
            self._activate([skill.name for skill in found])
        parts: list[str] = []
        if found:
            parts.append("已加载技能：")
            for skill in found:
                parts.append(f"### Skill: {skill.name}\n{skill.content.strip()}")
        if missing:
            available = ", ".join(sorted(s.name for s in self.library))
            parts.append("未找到：" + ", ".join(missing) + f"。可选：{available}")
        return "\n\n".join(parts)
