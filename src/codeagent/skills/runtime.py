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
video_ops_status / video_ops_log / video_ops_draft / video_generate / video_studio）在相关时直接调用。
文生视频用 video_generate：wan（局域网 Gradio）、minimax（Hailuo）、kimi、comfy（ComfyUI 工作流）。
完整拍片走导演台：企划、分镜、生成、ffmpeg 合成，工具 video_studio；Comfy 不是聊天模型。
本机 ComfyUI 出图/跑节点图：直接调用 comfy 工具（status / queue），不要把它当聊天模型。
打开网页、登录站、点按钮、填表、截图时，直接调用 browser 工具（软件内置浏览器，桌面有窗口），\
不要只用 web_fetch，不要让用户自己去点浏览器。
网站 / 落地页 / 前端界面做完后必须展示成品：先启动本地 HTTP 预览（vite preview / \
serve dist / python -m http.server，后台运行），再 browser action=navigate 打开 \
http://127.0.0.1:端口/（禁止 file://），最后才文字总结。用户要的是看见页面，不是只听描述。
手机 App 界面走 mobile-app-ui；微信小程序从需求到提审走 wechat-miniprogram。
Material 3 Expressive 草图用 browser 打开 m3e-canvas 站点，不要把画布拷进工程。
在微信开发者工具里点页面或截图时按 weapp-agent-mcp（需本机开发者工具与 npx MCP）。
情感陪伴 / AI 伴侣 / 人设与长期记忆：按 y-ai-accompany、ai-companion；语音叠 voice-surface。
剪映专业版自动化剪辑 → jianying-editor；HTML 确定性成片 → hyperframes；\
自然语言 draw.io / 架构图 → next-ai-draw-io（MCP `@next-ai-drawio/mcp-server`）。
AutoCAD / 源 DWG 精确重绘 → autocad-dwg-redraw；图纸照片/扫描件转 DWG → autocad-image-redraw\
（均需 Windows + AutoCAD + pywin32；勿仅凭像素声称尺寸精确）。
连库查表 / SQL / Redis·Mongo → dbx（MCP `@dbx-app/mcp-server`，先装本机 DBX 配连接）；\
低代码业务库 / Limbas 表单应用 → limbas（Docker/Web 安装器，独立部署）。
知识库随软件自动部署（本机 LLM Wiki）；分层检索思路 → openviking；\
团队四类记忆资产 → tencentdb-agent-memory（默认同本地 Wiki，外挂 Docker 可选）。
鸿蒙 / HarmonyOS NEXT / ArkTS API → harmony-next；.ets 语法与迁移 → arkts-syntax-assistant；\
编译装机 / UI / hilog → deveco-mcp（MCP `deveco-mcp-server`，需本机 DevEco）。
可视化无代码建站 / Silex / GrapesJS → silex（本机 MCP :6807，先开 Desktop）。\
MotionSites 付费提示词 → motionsites-mcp（需账号 OAuth）。\
用哪个 MCP 插件由任务自动提取，自己调用 use_plugin，不要问用户点选。
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
    (re.compile(r"短视频|短剧|剪辑|分镜|成片|口播|发布|运营|文生视频|海螺|Hailuo|ComfyUI|comfy|导演台|拍片|短片|剪映|jianying|HyperFrames|hyperframes", re.I),
     " 视频 短剧 剪辑 Comfy 文生视频 导演台 剪映 HyperFrames"),
    (re.compile(
        r"draw\.?\s*io|drawio|架构图|流程图|时序图|ER\s*图|UML|"
        r"next-ai-draw-io|自然语言画图|示意图",
        re.I,
    ), " draw.io 架构图 流程图 next-ai-draw-io"),
    (re.compile(
        r"AutoCAD|DWG|DXF|CAD\s*图纸|图纸重绘|精确复刻|"
        r"autocad-dwg-redraw|autocad-image-redraw|"
        r"扫描件转\s*DWG|截图转\s*DWG|照片转\s*DWG|光栅.*DWG",
        re.I,
    ), " AutoCAD DWG DXF 重绘 autocad-dwg-redraw autocad-image-redraw"),
    (re.compile(
        r"\bDBX\b|\bdbx\b|数据库客户端|连库|查库|写\s*SQL|执行\s*SQL|"
        r"MySQL|PostgreSQL|Postgres|SQLite|Redis|MongoDB|达梦|"
        r"@dbx-app/mcp-server|数据库管理工具",
        re.I,
    ), " DBX 数据库 SQL 查库 dbx"),
    (re.compile(
        r"Limbas|\blimbas\b|低代码数据库|数据库框架|业务表单应用|openlimbas|"
        r"PHP\s*低代码",
        re.I,
    ), " Limbas 低代码 数据库框架 limbas"),
    (re.compile(
        r"OpenViking|openviking|viking://|上下文数据库|分层检索|L0\s*/\s*L1|"
        r"会话编译|上下文编译",
        re.I,
    ), " OpenViking 上下文 分层 openviking"),
    (re.compile(
        r"TencentDB|Agent\s*Memory|Memory\s*Hub|tencentdb-agent-memory|"
        r"团队记忆|Chat\s*Memory|Code-Graph|代码图谱",
        re.I,
    ), " TencentDB Agent Memory 团队记忆 tencentdb-agent-memory"),
    (re.compile(r"文生图|图生图|出一张图|出图|节点图|8188", re.I),
     " Comfy 工作流 文生图"),
    (re.compile(r"通宵|挂机|调研|文献|值守"), " 研究 通宵"),
    (re.compile(r"从零|原理|nanoGPT|卡帕西|karpathy", re.I), " 原理 Karpathy"),
    (re.compile(r"蒸馏|按.+的方式|导师口吻"), " 蒸馏 女娲"),
    (re.compile(r"公众号|长文|选题|提纲|专栏"), " 写作 长文"),
    (re.compile(r"文档|README|changelog|体例"), " 文档 中文 体例"),
    (re.compile(
        r"cpython|C API|PyObject|稳定\s*ABI|Limited API|ceval|"
        r"解释器内核|从源码编[译譯]? ?Python|给\s*CPython|贡献\s*CPython|"
        r"PCbuild|DevGuide",
        re.I,
    ), " CPython ceval GIL CAPI 解释器"),
    (re.compile(
        r"浏览器|打开网页|打开网站|访问网站|填表单|点按钮|截图网页|"
        r"已登录的|BrowserSkill|ego-lite|ego-browser|\bbsk\b|自动化浏览",
        re.I,
    ), " 浏览器 browser bsk"),
    (re.compile(
        r"语音面|Voice Surface|麦克风|播报|嗲音|嗲嗲声|faster-whisper|barge-in|Alt\+Space",
        re.I,
    ), " 语音面 Voice Surface 播报 TTS"),
    (re.compile(
        r"情感陪伴|AI\s*陪伴|AI\s*伴侣|智能伴侣|永久记忆|人设YAML|口癖|"
        r"生命节律|OCEAN|倾诉|恋人预设|y-ai-accompany|ai-companion",
        re.I,
    ), " 情感陪伴 AI伴侣 人设 记忆 y-ai-accompany"),
    (re.compile(
        r"手机\s*App|手机应用|拇指热区|健身App|iOS\s*App|Android\s*App",
        re.I,
    ), " 手机App 移动端 拇指热区 8pt"),
    (re.compile(
        r"微信小程序|小程序|AppID|提审|体验版|wxml|wxss",
        re.I,
    ), " 微信小程序 AppID 提审 wxml"),
    (re.compile(
        r"微信开发者工具|小程序调试|weapp-agent|mp_screenshot|element_tap",
        re.I,
    ), " 微信开发者工具 小程序调试 weapp-agent"),
    (re.compile(
        r"Material\s*3|M3E|m3e-canvas|Material You|Expressive",
        re.I,
    ), " Material 3 M3E 画布 m3e-canvas"),
    (re.compile(
        r"鸿蒙|HarmonyOS|Harmony\s*OS\s*NEXT|harmony-next|@ohos|"
        r"ArkUI|ApplicationKit|\.ets\b|ArkTS|arkts|"
        r"DevEco|deveco-mcp|deveco-toolbox|hilog|hvigor|\bhdc\b|HAP\b",
        re.I,
    ), " 鸿蒙 HarmonyOS ArkTS DevEco harmony-next arkts-syntax-assistant deveco-mcp"),
    (re.compile(
        r"Silex|GrapesJS|可视化建站|无代码建站|拖拽建站|开源\s*Webflow|silex\.me",
        re.I,
    ), " Silex GrapesJS 可视化建站 silex"),
    (re.compile(
        r"MotionSites|motionsites|付费设计提示词|Premium Website Design|motionsites\.ai",
        re.I,
    ), " MotionSites 设计提示词 motionsites-mcp"),
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
    ".wxml": "微信小程序 wxml 页面",
    ".wxss": "微信小程序 wxss 样式",
    ".wxs": "微信小程序 wxs",
    ".tex": "论文 latex 投稿",
    ".bib": "论文 相关工作",
    ".md": "文档 中文 体例",
    ".mp4": "视频 剪辑 发布",
    ".mov": "视频 剪辑",
    ".srt": "视频 字幕 剪辑",
    ".dwg": "AutoCAD DWG 重绘 CAD",
    ".dxf": "AutoCAD DXF CAD 重绘",
    ".ets": "鸿蒙 ArkTS ets HarmonyOS",
}

_DIR_HINTS: dict[str, str] = {
    "00-desk": "导演台 分镜 视频",
    "01-script": "短剧 剧本 视频",
    "02-generate": "视频 生成",
    "03-edit": "视频 剪辑",
    "04-analyze": "运营 分析",
    "05-publish": "发布 视频",
    "components": "React 界面 组件",
    "wiki": "知识库 文档",
    "PCbuild": "CPython Windows 构建",
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
    if (
        (path / "Include" / "Python.h").is_file()
        and (path / "Python" / "ceval.c").is_file()
        and (path / "Lib" / "os.py").is_file()
    ):
        parts.append("CPython 解释器 ceval GIL C API")
    if (path / "app.json").is_file() and (path / "project.config.json").is_file():
        parts.append("微信小程序 AppID 提审 wxml")
    exts: Counter[str] = Counter()
    dir_hits: set[str] = set()
    try:
        import os

        max_files = 400
        seen_files = 0
        for dirpath, dirnames, filenames in os.walk(path):
            # prune heavy / irrelevant trees
            dirnames[:] = [
                d for d in dirnames
                if d not in _SKIP_DIR and not d.startswith(".")
            ]
            try:
                rel = Path(dirpath).relative_to(path)
                depth = len(rel.parts)
            except ValueError:
                depth = 0
            if depth > 3:
                dirnames.clear()
                continue
            for name in list(dirnames):
                if name in _DIR_HINTS:
                    dir_hits.add(name)
            for fn in filenames:
                seen_files += 1
                if seen_files > max_files:
                    dirnames.clear()
                    break
                suf = Path(fn).suffix.lower()
                if suf:
                    exts[suf] += 1
            if seen_files > max_files:
                break
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
