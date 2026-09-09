#!/usr/bin/env python3
"""Generate detailed code annotations, convert chats, and zip a full archive."""

from __future__ import annotations

import ast
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "codeagent"
DOC = ROOT / "文档"
CHAT = DOC / "聊天与思考"
STAMP = datetime.now().strftime("%Y%m%d")
OUT_NAME = f"CodeCoreAgent-0.36.0-完整归档-{STAMP}"
DOWNLOADS = Path.home() / "Downloads"
TRANSCRIPTS = Path.home() / ".cursor/projects/Users-stone-codeagent/agent-transcripts"

SKIP_NAMES = {"brand_mark.py"}  # generated data-URI, huge

METHOD_FALLBACK = {
    "__init__": "构造并保存依赖（Provider、路径、配置等）。",
    "complete": "向模型请求一轮补全，返回统一 LLMResponse。",
    "execute": "执行工具副作用，返回给模型的文本。",
    "run": "跑完主流程并返回结果或最终回复。",
    "upstream": "返回指向该节点的上游节点 id。",
    "downstream": "返回该节点的下游节点 id。",
    "downstream_edges": "返回从该节点出发的边。",
    "roots": "没有入边的起始节点。",
    "leaves": "没有出边的结束节点。",
    "topo_levels": "按可并行层分组的拓扑序。",
}


def unparse(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return "?"


def first_doc(node: ast.AST) -> str:
    doc = ast.get_docstring(node) or ""
    return re.sub(r"\s+", " ", doc).strip()


def args_of(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    a = fn.args
    parts: list[str] = []
    pos = list(a.posonlyargs) + list(a.args)
    defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    for i, arg in enumerate(pos):
        if arg.arg in {"self", "cls"}:
            parts.append(arg.arg)
            continue
        piece = arg.arg
        if arg.annotation:
            piece += ": " + unparse(arg.annotation)
        if defaults[i] is not None:
            piece += " = " + unparse(defaults[i])
        parts.append(piece)
    if a.vararg:
        parts.append("*" + a.vararg.arg)
    for arg, default in zip(a.kwonlyargs, a.kw_defaults):
        piece = arg.arg
        if arg.annotation:
            piece += ": " + unparse(arg.annotation)
        if default is not None:
            piece += " = " + unparse(default)
        parts.append(piece)
    if a.kwarg:
        parts.append("**" + a.kwarg.arg)
    ret = unparse(fn.returns)
    prefix = "async def" if isinstance(fn, ast.AsyncFunctionDef) else "def"
    sig = f"{prefix} {fn.name}({', '.join(parts)})"
    if ret:
        sig += f" -> {ret}"
    return sig


def infer_zh(name: str, doc: str, kind: str) -> str:
    if doc:
        return doc
    table = {
        "load": "从磁盘或默认路径加载持久化数据。",
        "save": "把当前对象写回本机配置文件。",
        "get": "按键或标识读取一项。",
        "set": "写入或更新一项。",
        "add": "新增一条记录。",
        "delete": "删除一条记录。",
        "list": "列出集合中的条目。",
        "run": "执行主流程并返回结果。",
        "build": "按配置构造运行时对象。",
        "create": "创建并返回新实例。",
        "parse": "解析输入为结构化对象。",
        "probe": "探测远端服务是否在线及能力。",
        "test": "对连接或模型做一次连通性测试。",
        "send": "发送用户消息并驱动 Agent。",
        "stop": "请求停止当前生成。",
        "route": "按规则为文本选择模型。",
        "classify": "对输入做分类（风险或任务类型）。",
        "complete": "向模型请求一轮补全。",
        "execute": "真正执行工具副作用并返回文本。",
        "connect": "建立网络或设备连接。",
        "discover": "扫描本机已安装的外部程序。",
    }
    low = name.lower()
    for key, text in table.items():
        if low == key or low.startswith(key + "_") or low.endswith("_" + key):
            return text
    if kind == "class":
        return CLASS_ZH.get(name, f"`{name}`：该模块的数据结构或服务类型，详见源码 docstring 与调用处。")
    return METHOD_FALLBACK.get(name, f"`{name}`：该模块的公开接口，参数见签名，行为见同行源码。")


def walk_py(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    rel = path.relative_to(ROOT).as_posix()
    info = {
        "path": rel,
        "module_doc": first_doc(tree),
        "classes": [],
        "functions": [],
    }
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_") and node.name != "__init__":
                continue
            doc = first_doc(node)
            info["functions"].append({
                "sig": args_of(node),
                "doc": doc,
                "zh": infer_zh(node.name, doc, "func"),
                "name": node.name,
                "lineno": node.lineno,
            })
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(unparse(b) for b in node.bases) or "object"
            cdoc = first_doc(node)
            methods = []
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if item.name.startswith("_") and item.name not in {
                    "__init__", "__call__", "__aenter__", "__aexit__",
                }:
                    continue
                d = first_doc(item)
                methods.append({
                    "sig": args_of(item),
                    "doc": d,
                    "zh": infer_zh(item.name, d, "func"),
                    "name": item.name,
                    "lineno": item.lineno,
                })
            info["classes"].append({
                "name": node.name,
                "bases": bases,
                "doc": cdoc,
                "zh": infer_zh(node.name, cdoc, "class"),
                "lineno": node.lineno,
                "methods": methods,
            })
    return info


def write_annotations() -> None:
    files = sorted(p for p in SRC.rglob("*.py") if p.name not in SKIP_NAMES)
    blocks = [
        "# CodeCoreAgent 函数与类注解（全量）",
        "",
        "对照 **当前仓库源码 0.36.0** 自动抽取。每个公开类 / 函数给出：",
        "",
        "- **位置**：文件与行号",
        "- **签名**：参数与返回类型（以源码注解为准）",
        "- **功能说明**：优先用源码 docstring；没有则按命名约定补中文说明",
        "- **方法**：类的公开方法（含 `__init__`）同样列出",
        "",
        "下划线开头的内部辅助函数默认不收录，避免把实现细节当成稳定 API。",
        "生成器：`scripts/build_full_archive.py`。",
        "",
        f"共扫描 `{len(files)}` 个 `.py` 文件。",
        "",
    ]
    n_cls = n_fn = n_m = 0
    for path in files:
        info = walk_py(path)
        n_cls += len(info["classes"])
        n_fn += len(info["functions"])
        n_m += sum(len(c["methods"]) for c in info["classes"])
        blocks.append(f"## `{info['path']}`")
        blocks.append("")
        if info["module_doc"]:
            blocks.append(f"> 模块说明：{info['module_doc']}")
            blocks.append("")
        if not info["classes"] and not info["functions"]:
            blocks.append("（无公开类或函数；文件以常量、类型别名或再导出为主。）")
            blocks.append("")
            continue
        for c in info["classes"]:
            blocks.append(f"### 类 `{c['name']}`")
            blocks.append("")
            blocks.append(f"- **基类**：`{c['bases']}`")
            blocks.append(f"- **定义行**：{c['lineno']}")
            blocks.append(f"- **功能说明**：{c['zh']}")
            blocks.append("")
            if c["methods"]:
                blocks.append("| 方法 | 行 | 功能说明 |")
                blocks.append("|---|---|---|")
                for m in c["methods"]:
                    zh = m["zh"].replace("|", "\\|")
                    blocks.append(
                        f"| `{m['sig']}` | {m['lineno']} | {zh} |"
                    )
                blocks.append("")
        for f in info["functions"]:
            blocks.append(f"### `{f['sig']}`")
            blocks.append("")
            blocks.append(f"- **定义行**：{f['lineno']}")
            blocks.append(f"- **功能说明**：{f['zh']}")
            blocks.append("")
    header = [
        f"统计：公开类 **{n_cls}**，模块级函数 **{n_fn}**，公开方法 **{n_m}**。",
        "",
    ]
    text = "\n".join(blocks[:13] + header + blocks[13:])
    (DOC / "05-函数与类注解.md").write_text(text, encoding="utf-8")
    print(f"wrote 05-函数与类注解.md classes={n_cls} funcs={n_fn} methods={n_m}")


DESKTOP_API_ZH = {
    "get_state": "桌面启动时拉取总状态：版本、主题、个性化、当前项目、隐私是否已同意。",
    "get_privacy_policy": "返回隐私条款正文及本机是否已接受当前版本。",
    "accept_privacy": "记录用户同意当前隐私条款版本与时间。",
    "get_changelog": "返回 releases.py 渲染的完整更新历史。",
    "get_nav_status": "侧栏底部计数：本地在跑模型、API 在线、聚合池、当前激活标签。",
    "get_overview": "总览仪表盘：技能/记忆/运行/外部平台数量与最近运行。",
    "save_config": "保存桌面配置（模型、主题、思考强度、语音、自动同意）。",
    "save_settings": "保存主机级个性化（称呼、语言、额外说明、机器上下文）。",
    "send": "发送一条对话：选模型或自由路由，驱动 Agent；Gradio 时走文生视频。",
    "stop": "设置取消标志，中断当前生成并推 stopped 事件。",
    "reset": "清空当前对话上下文并开新会话。",
    "lead": "指挥中心：把老板命令交给 Leader 拆任务、分派工人。",
    "get_model_assets": "模型管理三 tab 所需的端点、API、聚合池列表。",
    "set_active_model": "把当前对话模型设为自由路由或某个本地/API/聚合池。",
    "add_endpoint": "登记本机或局域网推理端点。",
    "remove_endpoint": "从资产里去掉一条本地/局域网端点。",
    "detect_models": "对 Base URL 做双协议探测（/v1/models 与 /api/tags），带 key 识别需鉴权的服务。",
    "add_api_model": "登记云端或兼容 API 模型（密钥写 secrets.json）。",
    "remove_api_model": "删除一条 API 模型登记（不删远端账号）。",
    "test_model": "走与真实对话同一条 Provider 链路做连通性测试，记录延迟。",
    "get_models_page": "本地模型页：端点标签、是否在跑、量化/体积等元数据。",
    "set_local_loaded": "让 Ollama 把指定模型载入或卸出显存。",
    "delete_local_model": "从本机 Ollama 删除一个模型权重。",
    "pull_model": "后台线程向主推理端点拉取新模型。",
    "save_mixture": "保存聚合池策略与成员。",
    "delete_mixture": "删除一个聚合池。",
    "toggle_mixture": "启用或停用某个聚合池。",
    "add_route_rule": "新增或更新自由路由关键词规则。",
    "get_router": "读取全部路由规则、权重与兜底设置。",
    "delete_route_rule": "删除一条自由路由规则。",
    "toggle_route_rule": "打开或关闭某条路由规则。",
    "move_route_rule": "调整规则优先级（上移/下移）。",
    "save_route_weights": "保存成本/质量/本地三权重滑杆。",
    "route_sandbox": "不真正调用模型，只预览这条文本会分到哪。",
    "pick_attachments": "系统文件框选文件，拷入项目 files/。",
    "remove_attachment": "从当前待发送附件列表去掉一项。",
    "resolve_confirm": "前端确认弹窗的批准/拒绝回写。",
    "get_permissions": "读取五能力矩阵当前等级与最近审计。",
    "set_permission_level": "改某一能力的自主/确认/只读/关闭等级。",
    "get_versions": "版本页数据：当前版 + 全部 Release 列表。",
    "get_activity": "读取自我学习活动流。",
    "send_feedback": "对话赞/踩写入活动流，供学习管线统计准确率。",
    "get_learning": "学习页：当日准确率、趋势、权重回流状态。",
    "learn_now": "立刻跑一轮学习管线，把反馈折算进路由权重。",
    "get_workflows": "列出自动化步骤链。",
    "add_workflow": "新建一条工作流（步骤串行）。",
    "delete_workflow": "删除一条工作流定义。",
    "run_workflow": "立刻执行该工作流。",
    "pause_workflow": "暂停正在跑的工作流。",
    "set_workflow_continuous": "开关「完成后自动衔下一轮」。",
    "get_cron": "列出定时任务与下次触发提示。",
    "add_cron_job": "新增五字段 cron 作业。",
    "delete_cron_job": "删除用户 cron（系统夜间进化作业不可删）。",
    "toggle_cron_job": "暂停或恢复一条 cron。",
    "get_evolution": "进化页：补丁、技能草稿、五角色作业状态。",
    "run_evolution_now": "立刻跑一轮进化作业。",
    "set_patch_status": "批准/回滚/拒绝行为补丁。",
    "approve_skill": "把技能草稿转正为可 cron 触发的工作流。",
    "save_evolution_settings": "保存进化总开关与 cron 表达式。",
    "get_projects": "项目列表与当前激活项。",
    "create_project": "新建项目文件夹并写入索引。",
    "get_project_records": "当前项目的对话 + 文件夹内文件。",
    "open_project_folder": "用系统文件管理器打开项目目录。",
    "switch_project": "切换激活项目，后续对话与工具根目录跟着走。",
    "delete_project": "只从索引移除；磁盘文件夹与对话保留。",
    "get_conversations": "当前项目的会话列表。",
    "new_conversation": "开一个空会话并设为当前。",
    "load_conversation": "把某条历史会话载入对话页。",
    "get_runs": "指挥中心历史运行存档。",
    "get_memories": "长期记忆列表（可带搜索）。",
    "add_memory": "手工新增一条长期记忆。",
    "delete_memory": "删除一条长期记忆。",
    "get_knowledge": "知识库状态、路径、页面列表。",
    "save_knowledge_config": "保存知识库根路径等配置。",
    "bootstrap_knowledge": "一键布置 Obsidian / LLM Wiki 目录结构。",
    "search_knowledge": "在知识库里按关键词检索页面。",
    "read_knowledge_page": "读取某一 wiki 页正文。",
    "ingest_knowledge": "把一段文本写入 inbox。",
    "open_knowledge_folder": "打开知识库文件夹。",
    "get_video_ops": "视频运营页状态、选题、草稿、工具链是否就绪。",
    "save_video_ops_config": "保存 Gradio/Comfy 地址与运营根目录。",
    "bootstrap_video_ops": "一键创建选题/生成/剪辑/分析/发布目录。",
    "save_video_ops_draft": "保存多平台发布草稿（仍须人工点发布）。",
    "get_studio": "导演台：企划、分镜列表、成片路径。",
    "save_studio": "保存导演台企划与分镜字段。",
    "studio_import_script": "从「1. 画面」或 Markdown 标题导入分镜。",
    "studio_add_shot": "手工加一镜。",
    "studio_remove_shot": "删除一镜。",
    "studio_generate_shot": "按该镜引擎调用 Comfy/WAN/Hailuo/Kimi 出片。",
    "studio_assemble": "ffmpeg 按分镜顺序合成成片。",
    "studio_interrupt": "停止生成（含 Comfy /interrupt）。",
    "open_video_ops_folder": "打开视频运营工作区。",
    "get_skills": "技能库：融合 / 视频 / 本分页列表。",
    "get_harnesses": "本机已发现的外部 Agent 平台。",
    "get_logs": "读取最近运行日志行。",
}

CLASS_ZH = {
    "Agent": "工具循环主体：向模型要补全，审批并执行工具，直到结束或触及上限。",
    "AgentEvent": "循环向外抛的事件（文本、工具、审批、完成、错误）。",
    "AgentConfig": "用 pydantic 描述的 Agent 构造参数。",
    "Budget": "token 用量账本；子 Agent 用量记入根预算。",
    "BudgetExceededError": "超出 token 上限时抛出。",
    "MaxIterationsError": "模型/工具往返次数超过 max_iterations。",
    "Message": "一条对话消息（角色、文本、工具调用或结果）。",
    "Role": "消息角色：user / assistant / system / tool。",
    "ToolCall": "模型请求调用的工具名与参数。",
    "ToolResult": "工具执行后回灌给模型的文本。",
    "Usage": "一次 complete 的 token 计数。",
    "LLMResponse": "Provider 的统一返回：文本、工具调用、用量。",
    "LLMProvider": "所有模型后端的抽象基类，核心方法 complete。",
    "OpenAIProvider": "OpenAI 及兼容端点（含推理字段兜底）。",
    "AnthropicProvider": "Claude Messages API。",
    "OllamaProvider": "本机 Ollama /api/chat。",
    "AggregateProvider": "多个后端 fallback 或 round-robin。",
    "AggregateError": "聚合模式下所有后端都失败。",
    "Tool": "工具抽象：name / description / parameters / risk / execute。",
    "ToolRegistry": "按名查找并执行已注册工具。",
    "ReadFileTool": "读工作区内文件。",
    "WriteFileTool": "新建或覆盖文件。",
    "EditFileTool": "按旧/新字符串替换文件片段。",
    "ListDirTool": "列目录。",
    "GrepTool": "正则搜索文件内容。",
    "GlobTool": "按文件名模式匹配。",
    "BashTool": "执行 Shell，风险由 classify_command 决定。",
    "BrowserTool": "开页、点击、填表（BrowserSkill / ego-lite）。",
    "ComfyTool": "向 ComfyUI queue API 工作流。",
    "DelegateTool": "把子任务交给另一个 Agent。",
    "WebFetchTool": "抓网页正文。",
    "WebScrapeTool": "按 CSS 选择器抽结构化字段。",
    "OCRTool": "图像文字识别。",
    "PermissionPolicy": "按风险等级自动放行、询问或拒绝。",
    "RiskLevel": "只读 / 写入 / 执行 / 破坏 四级。",
    "ApprovalDecision": "批准、拒绝、本会话永远允许。",
    "CapabilityPolicy": "桌面五能力矩阵用的 PermissionPolicy 子类。",
    "Confirmer": "桌面确认队列：推弹窗，等 JS resolve_confirm。",
    "Settings": "主机级个性化，注入所有对话。",
    "Memory": "一条长期记忆。",
    "MemoryStore": "记忆存储抽象。",
    "LocalMemoryStore": "JSON 文件实现。",
    "SmartMemoryStore": "先抽事实再 ADD/UPDATE/DELETE 对账。",
    "ConversationCompactor": "历史过长时用 LLM 总结旧轮。",
    "Skill": "一份 SKILL.md。",
    "SkillLibrary": "加载、检索、按预算注入技能。",
    "SkillEvolver": "任务后反思并写成新技能。",
    "UseSkillTool": "让模型按名单独调用某技能或插件。",
    "Leader": "拆命令、按依赖分批、分派工人。",
    "WorkerConfig": "一个工人的模型与描述。",
    "ProgressBoard": "任务状态与耗时，可供语音播报。",
    "RunArchive": "一次指挥运行的本机存档。",
    "Court": "三省六部流水线。",
    "Blueprint": "校验过的 DAG。",
    "BlueprintRunner": "按拓扑层并行执行蓝图。",
    "Node": "蓝图节点（种类、提示词、标签）。",
    "Edge": "蓝图连线，可带条件标签。",
    "NodeKind": "十种节点类型枚举。",
    "DesktopAPI": "pywebview 暴露给前端的全部方法。",
    "DesktopConfig": "桌面窗口偏好（主题、语音、自动同意等）。",
    "ModelAssets": "本地端点 + API 模型 + 聚合池。",
    "RouterStore": "自由路由规则与权重。",
    "Shot": "导演台一镜。",
    "Desk": "导演台整场：企划 + 分镜 + 成片路径。",
    "XiaozhiClient": "小智协议高层客户端。",
    "SelfDebugger": "生成→验证→解释→最小修复循环。",
    "VoiceChatLoop": "麦克风/文字 → Agent → 情绪 TTS 的连续对话。",
}


def write_desktop_api() -> None:
    path = SRC / "desktop" / "api.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(
        n for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == "DesktopAPI"
    )
    rows = [
        "# 桌面桥 DesktopAPI 注解",
        "",
        "`src/codeagent/desktop/api.py` 的 `DesktopAPI` 暴露给 JS：`pywebview.api.方法名(...)`。",
        "前端在 `desktop/ui.py` 里直接调用。Python 用 `window._onEvent` 回推流式文本、工具、停止。",
        "",
        "| 方法 | 行 | 功能说明 |",
        "|---|---|---|",
    ]
    for item in cls.body:
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if item.name.startswith("_"):
            continue
        doc = first_doc(item)
        zh = DESKTOP_API_ZH.get(item.name) or infer_zh(item.name, doc, "func")
        rows.append(f"| `{item.name}` | {item.lineno} | {zh.replace('|', '\\|')} |")
    rows.append("")
    rows.append("内部 `_push` / `_on_event` / `_provider_for_message` 不对外，但决定流式与自由路由是否改道。")
    rows.append("")
    (DOC / "06-桌面桥API注解.md").write_text("\n".join(rows), encoding="utf-8")
    print("wrote 06-桌面桥API注解.md")


def extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text") or "")
        return "\n".join(parts)
    if isinstance(content, dict):
        return extract_text(content.get("content") or content.get("text") or "")
    return ""


def convert_transcript(src: Path, dest: Path, title: str) -> dict:
    users: list[str] = []
    thoughts: list[str] = []
    tools: list[str] = []
    lines_out: list[str] = [f"# {title}", "", f"原始文件：`{src}`", ""]
    if not src.exists():
        dest.write_text("# 缺失\n", encoding="utf-8")
        return {"users": 0, "thoughts": 0}
    for raw in src.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "turn_ended":
            lines_out.append(f"\n---\n*回合结束：{obj.get('status', '')}*\n")
            continue
        role = obj.get("role") or obj.get("type") or "unknown"
        msg = obj.get("message") or {}
        content = msg.get("content") if isinstance(msg, dict) else None
        text = extract_text(content if content is not None else obj.get("content"))
        thinking = ""
        if isinstance(msg, dict):
            thinking = msg.get("thinking") or msg.get("reasoning") or ""
        if not thinking and isinstance(obj, dict):
            thinking = obj.get("thinking") or ""
        if thinking:
            thoughts.append(thinking[:2000])
            clip = thinking if len(thinking) < 4000 else thinking[:4000] + "\n…(截断)"
            lines_out.append("### 思考\n")
            lines_out.append(clip)
            lines_out.append("")
        tool_names = []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_names.append(block.get("name") or "?")
        if tool_names:
            tools.extend(tool_names)
            lines_out.append(f"*调用工具：{', '.join(tool_names)}*\n")
        if text.strip():
            clean = re.sub(r"<timestamp>.*?</timestamp>\s*", "", text, flags=re.S)
            clean = re.sub(r"<user_query>\s*", "", clean)
            clean = re.sub(r"</user_query>", "", clean)
            if not clean.strip():
                continue
            if role == "user":
                first = next((ln for ln in clean.strip().splitlines() if ln.strip()), "(空消息)")
                users.append(first[:80])
                lines_out.append("## 用户\n")
            elif role == "assistant":
                lines_out.append("## 助手\n")
            else:
                lines_out.append(f"## {role}\n")
            if len(clean) > 12000:
                clean = clean[:12000] + "\n\n…(本段过长已截断，完整内容见原始 jsonl)"
            lines_out.append(clean.strip())
            lines_out.append("")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines_out), encoding="utf-8")
    return {"users": len(users), "thoughts": len(thoughts), "tools": len(tools), "queries": users}


def write_chats() -> None:
    CHAT.mkdir(parents=True, exist_ok=True)
    raw_dir = CHAT / "原始记录"
    raw_dir.mkdir(exist_ok=True)
    index = [
        "# 聊天与思考归档",
        "",
        "本目录收录本仓库相关 Cursor 会话的**可读转写**与**原始 jsonl**。",
        "「思考」来自助手在动手前写下的推理（若会话里有）；工具调用只记名称。",
        "",
        "| 会话 | 说明 | 转写 |",
        "|---|---|---|",
    ]

    mapping = [
        (
            TRANSCRIPTS / "2bed480b-89d5-4414-af8a-8a38c01f04ed" / "2bed480b-89d5-4414-af8a-8a38c01f04ed.jsonl",
            "01-立项与搭建-我想做专业的代码开发agent.md",
            "立项：从「我想做专业的代码开发 agent」到框架、CLI、桌面与打包",
        ),
        (
            TRANSCRIPTS / "7900823a-a715-4a0d-93a9-029925c243b7" / "7900823a-a715-4a0d-93a9-029925c243b7.jsonl",
            "02-本会话-logo与完整归档.md",
            "本会话：下载 fujitennka.jp logo，并按要求打完整 zip",
        ),
        (
            TRANSCRIPTS / "7a97d40e-62d5-46e7-8c17-498a8abf290c" / "7a97d40e-62d5-46e7-8c17-498a8abf290c.jsonl",
            "03-中断会话.md",
            "一次因额度切换模型而中断的会话",
        ),
    ]
    for src, name, desc in mapping:
        dest = CHAT / name
        stats = convert_transcript(src, dest, desc)
        if src.exists():
            shutil.copy2(src, raw_dir / src.name)
        qs = "；".join(stats.get("queries", [])[:6])
        index.append(f"| {desc} | 用户回合 {stats['users']}；思考段 {stats['thoughts']}。要点：{qs} | [{name}](./{name}) |")

    # subagents
    sub = TRANSCRIPTS / "2bed480b-89d5-4414-af8a-8a38c01f04ed" / "subagents"
    if sub.exists():
        for p in sorted(sub.glob("*.jsonl")):
            dest = CHAT / "子代理" / f"{p.stem}.md"
            convert_transcript(p, dest, f"立项会话子代理 {p.stem[:8]}")
            shutil.copy2(p, raw_dir / f"subagent-{p.name}")
        index.append("| 立项会话的子代理 jsonl | 并行调研/实现时的分支思考 | [子代理/](./子代理/) |")

    think = CHAT / "04-关键思考摘录.md"
    think.write_text(
        """# 关键思考摘录

整理自立项会话与本归档任务。不是模型隐藏链，而是当时写在回复里、决定架构的推理。

## 立项时的选择（2026-08-30）

用户要的是：**Python Agent 框架/库**，多模型可切换，项目名 `codeagent`。

当时的判断：

1. 先做库，再做 CLI，桌面是后加的壳，不要反过来绑死 UI。
2. 统一 `LLMProvider` + `Tool`，换模型或加工具不改主循环。
3. 权限默认 fail-closed：写文件和跑命令要确认。
4. 数据留本机 `~/.codeagent/`，不做云多租户。
5. 桌面用 pywebview 单文件 HTML，避免再开前端仓库。

## 下载富士天嘉 logo（2026-09-03）

1. 先看页头是 img 还是 CSS 背景，避免只存 favicon。
2. 从 HTML 拿到 `wp-content/uploads/2024/06/logo_2-01.png`（1343×459）。
3. 再用 WP REST `media?search=logo` 找图形标与 NEO-Q 印刷标。
4. 用像素统计确认主 logo 是透明底、品牌蓝 `#19327D`，站上没有 SVG。

## 本次打包（2026-09-07）

1. 仓库文档停在 0.26.0，源码已到 0.36.0，必须补功能总览与全量函数注解。
2. 聊天与思考单独成目录，原始 jsonl 一并放入，避免只给摘要。
3. zip **包含** 源码、测试、文档、工程脚本、`.git` 历史、聊天。
4. zip **不包含** `.venv`、`dist/`、`build/`、缓存——体积大且可再生成；安装包请自行 `build_desktop.py` 或用已有 `dist/`。
5. 不把 `~/.codeagent` 用户密钥与对话打进去。

## 本会话用户原话

- 「https://fujitennka.jp 把logo搞下来」
- 「把项目文档、代码、工程文件、聊天、思考，代码说明、功能说明注解要详细，所有内容全部打包zip文件」
""",
        encoding="utf-8",
    )
    index.append("| 关键思考摘录 | 立项取舍、logo 取证、本次打包原则 | [04-关键思考摘录.md](./04-关键思考摘录.md) |")
    index.append("")
    (CHAT / "README.md").write_text("\n".join(index), encoding="utf-8")
    print("wrote 聊天与思考")


def write_index_docs() -> None:
    (DOC / "00-阅读指引.md").write_text(
        """# CodeCoreAgent 文档阅读指引

版本 **0.36.0**（2026-09-07）  
产品名 **CodeCoreAgent**（CCA）  
Python 包 / CLI 名：`codeagent`  
仓库：https://github.com/LunarCoreAgent/codeagent  
许可证：MIT

本目录是正式交付文档。请按顺序阅读：

| 文件 | 读者 | 内容 |
|---|---|---|
| [01-项目书.md](./01-项目书.md) | 决策、交接、评审 | 背景、目标、范围、架构（正文版本号可能仍写 0.26，功能以 04 为准） |
| [02-操作说明书.md](./02-操作说明书.md) | 使用者、运维 | 安装、启动、桌面各页、CLI、排错 |
| [03-代码详解.md](./03-代码详解.md) | 开发者 | 目录、关键类、桌面桥、打包链路 |
| [04-功能说明.md](./04-功能说明.md) | 使用者 | 侧栏各页能做什么（0.36 界面口径） |
| [04-功能总览-v036.md](./04-功能总览-v036.md) | 所有人 | **对照 0.36.0 源码的完整功能说明** |
| [05-代码注解.md](./05-代码注解.md) | 开发者 | 目录职责与改动入口 |
| [05-函数与类注解.md](./05-函数与类注解.md) | 开发者 | **全量公开类/函数/方法签名与功能注解** |
| [06-导演台与Comfy.md](./06-导演台与Comfy.md) | 拍片 | 导演台五步与 Comfy API |
| [06-桌面桥API注解.md](./06-桌面桥API注解.md) | 桌面开发 | JS 可调用的 DesktopAPI 方法表 |
| [聊天与思考/](./聊天与思考/) | 交接、复盘 | 立项聊天、本会话、思考摘录、原始 jsonl |

仓库根目录还有：

- `README.md` — 安装与库用法
- `项目说明.md` — 较短工程交接稿
- `CHANGELOG.md` / `PRIVACY.md` / `LICENSE`
- `归档说明.md` — 本 zip 里有什么、没有什么
""",
        encoding="utf-8",
    )
    (DOC / "README.md").write_text("请从 [00-阅读指引.md](./00-阅读指引.md) 开始。\n", encoding="utf-8")
    (ROOT / "归档说明.md").write_text(
        f"""# CodeCoreAgent 完整归档说明

归档日期：{datetime.now().strftime("%Y-%m-%d")}  
软件版本：**0.36.0**  
压缩包名：`{OUT_NAME}.zip`

## 这个 zip 里有什么

- **源码**：`src/codeagent/` 全部模块（Agent、模型、工具、桌面、导演台、领导、蓝图等）
- **测试**：`tests/`
- **工程文件**：`pyproject.toml`、`uv.lock`、`packaging/`、`scripts/`、`.github/workflows/`、`examples/`
- **Git 历史**：完整 `.git`（可继续提交）
- **项目文档**：`README.md`、`项目说明.md`、`CHANGELOG.md`、`PRIVACY.md`、`LICENSE`、`文档/`
- **详细注解**：`文档/04-功能总览-v036.md`、`文档/05-函数与类注解.md`、`文档/06-桌面桥API注解.md`
- **聊天与思考**：`文档/聊天与思考/`（可读转写 + 原始 jsonl + 思考摘录）

## 刻意不装进 zip 的

| 排除 | 原因 |
|---|---|
| `.venv/` | 本机虚拟环境，约 500MB+，用 pip 重装即可 |
| `dist/` | 已打好的 DMG/exe，约 670MB，用 `scripts/build_desktop.py` 再打 |
| `build/` | PyInstaller 中间产物 |
| `__pycache__` / `.pytest_cache` | 缓存 |
| `.env` | 密钥（若有） |
| `~/.codeagent/` | 你的模型密钥、对话、记忆，不属于仓库 |

若需要现成 macOS 安装包，用仓库旁本机已生成的：

`dist/codeagent-desktop-macos-arm64.dmg`

## 解压后怎么跑

```bash
cd {OUT_NAME}/codeagent
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\activate
pip install -U pip
pip install -e ".[all,dev]"
codeagent version
codeagent desktop
pytest -q
```

先读 `文档/00-阅读指引.md`。
""",
        encoding="utf-8",
    )
    print("wrote index docs")


def make_zip() -> Path:
    staging = DOWNLOADS / OUT_NAME
    if staging.exists():
        shutil.rmtree(staging)
    dest = staging / "codeagent"

    exclude = {
        ".venv", "dist", "build", "__pycache__", ".pytest_cache",
        ".mypy_cache", ".ruff_cache", ".DS_Store",
    }
    def ignore(directory: str, names: list[str]) -> list[str]:
        dropped = []
        for n in names:
            if n in exclude or n.endswith(".pyc") or n.endswith(".egg-info") or n == ".env":
                dropped.append(n)
        return dropped

    shutil.copytree(ROOT, dest, ignore=ignore, symlinks=True)
    shutil.copy2(ROOT / "归档说明.md", staging / "请先读-归档说明.md")
    zip_path = DOWNLOADS / f"{OUT_NAME}.zip"
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(DOWNLOADS / OUT_NAME), "zip", root_dir=staging)
    size = zip_path.stat().st_size
    print(f"zip {zip_path} ({size/1024/1024:.1f} MB)")
    return zip_path


def main() -> int:
    DOC.mkdir(exist_ok=True)
    write_annotations()
    write_desktop_api()
    write_chats()
    write_index_docs()
    path = make_zip()
    print("DONE", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
