"""Plugin catalog: agent picks MCP / builtin connectors from the task.

Skills tell the model *how* to work. Plugins tell it *which connector* to
use. Matching is keyword overlap (same idea as ``match_work_skills``); the
model must not ask the user to pick from a list.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from codeagent.security.policy import RiskLevel
from codeagent.tools.base import Tool


@dataclass(frozen=True)
class PluginSpec:
    """One optional connector the agent may enable for a task."""

    name: str
    kind: str  # mcp | builtin
    description: str
    triggers: str
    skill: str = ""
    connect: str = ""
    auth: str = "none"  # none | local | oauth | npx
    preset: str = ""

    def haystack(self) -> str:
        return " ".join(
            (self.name, self.kind, self.description, self.triggers, self.skill, self.connect)
        ).lower()


PLUGIN_CATALOG: tuple[PluginSpec, ...] = (
    PluginSpec(
        name="silex",
        kind="mcp",
        description="本机 Silex 可视化建站画布（GrapesJS）。打开站点后动态加载编辑器工具，改完截图验收。",
        triggers="Silex,GrapesJS,可视化建站,无代码建站,拖拽建站,开源Webflow,silex.me",
        skill="silex",
        connect="http://127.0.0.1:6807/mcp （先开 Silex Desktop；编辑器本身在 :6805）",
        auth="local",
        preset="silex_mcp",
    ),
    PluginSpec(
        name="motionsites",
        kind="mcp",
        description="MotionSites 付费设计提示词库。按需取一条，不要把目录整包塞进上下文。",
        triggers="MotionSites,motionsites,付费设计提示词,Premium Website Design,motionsites.ai",
        skill="motionsites-mcp",
        connect="https://xgdzyqfalbibzelpdpvr.supabase.co/functions/v1/mcp",
        auth="oauth",
        preset="motionsites_mcp",
    ),
    PluginSpec(
        name="drawio",
        kind="mcp",
        description="自然语言画 draw.io / 架构图 / 流程图。",
        triggers="draw.io,drawio,架构图,流程图,next-ai-draw-io",
        skill="next-ai-draw-io",
        connect="npx @next-ai-drawio/mcp-server@latest",
        auth="npx",
        preset="drawio_mcp",
    ),
    PluginSpec(
        name="dbx",
        kind="mcp",
        description="本机 DBX 连库查表、执行 SQL。",
        triggers="DBX,dbx,SQL,查库,PostgreSQL,MySQL,Redis,MongoDB",
        skill="dbx",
        connect="npx -y @dbx-app/mcp-server（先在本机 DBX 配连接）",
        auth="npx",
        preset="dbx_mcp",
    ),
    PluginSpec(
        name="deveco-mcp",
        kind="mcp",
        description="鸿蒙 DevEco 编译、安装、UI 树、hilog。",
        triggers="DevEco,deveco-mcp,hilog,hvigor,hdc,HAP",
        skill="deveco-mcp",
        connect="npx -y deveco-mcp-server（需本机 DevEco）",
        auth="npx",
        preset="deveco_mcp",
    ),
    PluginSpec(
        name="weapp-agent-mcp",
        kind="mcp",
        description="微信开发者工具里点页面、截图、巡检。",
        triggers="微信开发者工具,weapp-agent,小程序调试,mp_screenshot",
        skill="weapp-agent-mcp",
        connect="npx -y @chaixueyuan/weapp-agent-mcp",
        auth="npx",
        preset="weapp_agent_mcp",
    ),
    PluginSpec(
        name="keenable",
        kind="mcp",
        description="托管网页搜索与干净 Markdown 抓取。",
        triggers="搜索网页,search_web_pages,keenable",
        connect="https://api.keenable.ai/mcp",
        auth="none",
        preset="keenable",
    ),
    PluginSpec(
        name="playwright",
        kind="mcp",
        description="Playwright 浏览器自动化（外部 MCP；优先用内置 browser 工具）。",
        triggers="Playwright,playwright mcp",
        connect="npx @playwright/mcp@latest",
        auth="npx",
        preset="playwright_mcp",
    ),
    PluginSpec(
        name="browser",
        kind="builtin",
        description="软件内置浏览器：打开页面、点击、填表、截图。落地页做完必须 navigate 展示。",
        triggers="打开网页,打开网站,点按钮,填表,截图网页,内置浏览器",
        connect="直接调用 browser 工具，无需安装",
        auth="none",
    ),
)


def get_plugin(name: str) -> PluginSpec | None:
    key = (name or "").strip().lower().replace("_", "-")
    for spec in PLUGIN_CATALOG:
        if spec.name.lower() == key:
            return spec
    return None


def match_work_plugins(
    query: str,
    hints: str = "",
    limit: int = 4,
) -> list[PluginSpec]:
    """Pick connectors for this task. Generic「做个网站」does not select Silex."""
    from codeagent.skills.runtime import expand_work_query

    blob = expand_work_query(" ".join(x for x in (query, hints) if x).strip()).lower()
    if not blob.strip():
        return []
    compact_blob = blob.replace(" ", "").replace("-", "")
    scored: list[tuple[int, PluginSpec]] = []
    for spec in PLUGIN_CATALOG:
        score = 0
        compact = spec.name.lower().replace("-", "")
        if compact and compact in compact_blob:
            score += 6
        for token in spec.triggers.replace("，", ",").split(","):
            token = token.strip().lower()
            if len(token) < 2:
                continue
            if token.lower() in blob:
                score += 4
        if score:
            scored.append((score, spec))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [spec for _, spec in scored[:limit]]


def plugin_prompt_block(active: list[str] | None = None) -> str:
    """Compact instructions for plugins auto-enabled this turn."""
    names = [n for n in (active or []) if get_plugin(n)]
    if not names:
        return ""
    lines = ["[本次插件 — 由任务自动提取，不要让用户点选]"]
    for name in names:
        spec = get_plugin(name)
        if spec is None:
            continue
        extra = f"；技能 {spec.skill}" if spec.skill else ""
        lines.append(f"- {spec.name}（{spec.kind}）{spec.description} 接法：{spec.connect}{extra}")
        if spec.auth == "oauth":
            lines.append("  需账号登录授权；未登录会 401，说明怎么配 mcp.json，不要假装已连上。")
        if spec.auth == "local":
            lines.append("  本机服务未开时说明怎么启动，不要把 AGPL 源码拷进本仓库。")
        if spec.auth == "npx":
            lines.append("  缺 Node / 本机应用时说明依赖，不要假装 MCP 已在跑。")
    lines.append("需要完整接法时调用 use_plugin。")
    return "\n".join(lines)


class UsePluginTool(Tool):
    """Let the model load connector instructions without asking the user."""

    name = "use_plugin"
    description = (
        "Load connector / MCP plugin instructions by name. "
        "Call this yourself when a catalog plugin matches the task. "
        "Do not ask the user to pick plugins. Omit names to list the catalog."
    )
    parameters = {
        "type": "object",
        "properties": {
            "names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Plugin names from the catalog (e.g. silex, motionsites).",
            },
            "name": {
                "type": "string",
                "description": "Single plugin name if not using names.",
            },
        },
    }
    risk_level = RiskLevel.READ_ONLY

    def __init__(
        self,
        activate: Callable[[list[str]], list[PluginSpec]] | None = None,
    ) -> None:
        self._activate = activate

    def _wanted(self, names: Any, name: Any) -> list[str]:
        wanted: list[str] = []
        if isinstance(names, str) and names.strip():
            wanted.extend(part.strip() for part in names.split(",") if part.strip())
        elif isinstance(names, Iterable) and not isinstance(names, (str, bytes)):
            wanted.extend(str(item).strip() for item in names if str(item).strip())
        if isinstance(name, str) and name.strip():
            wanted.append(name.strip())
        seen: set[str] = set()
        ordered: list[str] = []
        for item in wanted:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(item)
        return ordered

    async def execute(self, names: Any = None, name: Any = None, **_: Any) -> str:
        wanted = self._wanted(names, name)
        if not wanted:
            lines = [
                f"- {p.name} ({p.kind}): {p.description}"
                for p in PLUGIN_CATALOG
            ]
            return "插件目录（用 use_plugin 加载接法）：\n" + "\n".join(lines)
        found: list[PluginSpec] = []
        missing: list[str] = []
        for raw in wanted:
            spec = get_plugin(raw)
            if spec is None:
                missing.append(raw)
            else:
                found.append(spec)
        if self._activate is not None and found:
            self._activate([p.name for p in found])
        parts: list[str] = []
        if found:
            parts.append("已提取插件：")
            for spec in found:
                parts.append(
                    f"### Plugin: {spec.name}\n"
                    f"{spec.description}\n"
                    f"- 类型：{spec.kind}\n"
                    f"- 接法：{spec.connect}\n"
                    f"- 鉴权：{spec.auth}\n"
                    + (f"- 配对技能：use_skill(\"{spec.skill}\")\n" if spec.skill else "")
                    + (f"- 预设：codeagent.mcp.presets.{spec.preset}()\n" if spec.preset else "")
                )
        if missing:
            available = ", ".join(p.name for p in PLUGIN_CATALOG)
            parts.append("未找到：" + ", ".join(missing) + f"。可选：{available}")
        return "\n".join(parts)
