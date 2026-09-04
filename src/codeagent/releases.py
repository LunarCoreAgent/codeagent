"""Release history: single source of truth for version info.

Rendered by ``codeagent version`` / ``codeagent changelog`` and mirrored in
the repo's CHANGELOG.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Release:
    version: str
    date: str  # YYYY-MM-DD
    highlights: tuple[str, ...] = field(default_factory=tuple)


RELEASES: tuple[Release, ...] = (
    Release("0.1.0", "2026-08-22", (
        "初始框架：Agent 核心循环、工具注册表、文件/Shell/搜索工具",
        "权限系统：风险分级 + 交互式审批，多模型 Provider 抽象",
        "CLI：run / chat 命令（typer + rich）",
    )),
    Release("0.2.0", "2026-08-23", (
        "融合 OpenAI Codex 洞察：token 预算、Shell 命令风险分类、子代理模式",
    )),
    Release("0.3.0", "2026-08-23", (
        "融合 google-research：Self-Debugging 迭代修复、pass@1 评测体系（MBPP）",
    )),
    Release("0.4.0", "2026-08-24", (
        "MCP 客户端：stdio + streamable-HTTP 双传输，Keenable 搜索预设",
    )),
    Release("0.5.0", "2026-08-24", (
        "记忆系统：短期对话压缩 + 长期记忆持久化与检索，记忆工具三件套",
    )),
    Release("0.6.0", "2026-08-25", (
        "mem0 式智能记忆：事实提取 + ADD/UPDATE/DELETE 对账（SmartMemoryStore）",
    )),
    Release("0.7.0", "2026-08-25", (
        "语音模块：情绪模式对话（[emotion:xxx] 标签）、edge-tts 免费语音包、"
        "本地 Whisper ASR、连续对话 VoiceChatLoop",
    )),
    Release("0.8.0", "2026-08-26", (
        "台湾音色：晓晨（zh-TW-HsiaoChenNeural）等繁中语音预设，音色固定 + 情绪韵律",
    )),
    Release("0.9.0", "2026-08-26", (
        "三省六部多智能体：中书规划→门下封驳→尚书执行，状态机 + 审计日志",
    )),
    Release("0.10.0", "2026-08-27", (
        "Scrapling 爬虫工具：web_fetch / web_scrape，反检测浏览器抓取",
    )),
    Release("0.11.0", "2026-08-27", (
        "小智协议客户端：OTA 激活 + WebSocket 协议 + Opus 编解码，接入 xiaozhi.me",
    )),
    Release("0.12.0", "2026-08-28", (
        "技能系统：SKILL.md 生态兼容 + SkillEvolver 自进化；OCR 双引擎工具；"
        "Playwright / Chrome DevTools MCP 预设",
    )),
    Release("0.13.0", "2026-08-28", (
        "蓝图 DAG 编排（HiveWard）：并行调度、条件路由、人工审批门、YAML 严格加载",
    )),
    Release("0.14.0", "2026-08-29", (
        "领导模式（HomeRail 深度融合）：语音/文字指挥多模型工人，依赖分批并行，"
        "进度板实时可查；蓝图新增 join/loop/while/command 原语 + 运行评分卡",
    )),
    Release("0.15.0", "2026-08-29", (
        "外部增援：CLI harness 适配本机 agent 平台（自动发现），工人主动求助 + "
        "领导失败升级；RunArchive 运行记录本地存档",
    )),
    Release("0.16.0", "2026-08-30", (
        "个性化设置：称呼/语言/额外说明/主机上下文，注入本机所有对话",
    )),
    Release("0.17.0", "2026-08-30", (
        "三路模型接入：云端 API + 本地部署（LM Studio/vLLM/llama.cpp）+ "
        "聚合网关（OpenRouter/硅基流动/AiHubMix/One-API）；AggregateProvider "
        "故障转移与轮询，--provider a,b 逗号串联",
    )),
    Release("0.18.0", "2026-08-30", (
        "版本与日志：settings 显示版本号，version/changelog 命令查看更新历史，"
        "运行日志持久化到 ~/.codeagent/logs/（轮转），logs 命令查看",
    )),
    Release("0.19.0", "2026-08-31", (
        "桌面版 UI：pywebview 原生窗口聊天界面（气泡/流式/工具指示），"
        "图形化设置面板（模型连接 + 个性化），版本与更新日志页；"
        "打包为 macOS .app（DMG）与 Windows 窗口程序",
    )),
    Release("0.20.0", "2026-08-31", (
        "桌面版全新设计：侧边导航六大页面——对话、指挥中心（领导模式 + "
        "任务进度板 + 历史运行）、长期记忆（增删搜）、技能库、日志查看器、"
        "分组设置（模型/语音朗读/个性化/工人名册/外部平台）；"
        "卫星环 Logo + Developer ID 签名，修复 onedir 打包与 DMG 符号链接签名问题",
    )),
    Release("0.21.0", "2026-08-31", (
        "桌面版界面升级为 LunarCore Claw 风格：shadcn 式 zinc 深色主题、"
        "分组侧边导航（概览/能力/系统）、白色主色调按钮、新增总览仪表盘"
        "（版本/模型/技能记忆统计/外部平台 + 快速入口 + 最近运行）",
    )),
    Release("0.22.0", "2026-08-31", (
        "按 LunarCore Claw v0.17.4 架构重写设置与对话：模型资产体系"
        "（本地 Ollama 端点表并行探测 + API 模型双协议自动识别）、"
        "密钥指针化（secrets.json 0600，界面仅掩码）、识别与调用同一链路；"
        "Ollama 切换原生 /api/chat（think 顶层关闭，思考型模型不再烧光预算）、"
        "OpenAI 兼容层 reasoning_content 兜底与截断诊断、对话页模型选择器、"
        "指挥中心工人失败重试与并发上限",
    )),
    Release("0.23.0", "2026-08-31", (
        "设置体系与 LunarCore Claw 逐页对齐：左下角设置菜单展开"
        "（模型管理/路由引擎/权限控制/版本说明/偏好设置）；"
        "模型管理三 tab——聚合池（加权/级联/投票/规则四策略，成员混选本地与 API，"
        "真实构建聚合 provider 并可设为当前对话模型）、本地模型（端点名称/角色、"
        "参数规模/量化/体积元数据、启动停止载入显存、部署拉取、删除）、"
        "API 模型（八家服务商预设下拉、Base URL 推断提供方、测试记录状态与延迟）；"
        "路由引擎——任务类型规则（优先级排序/开关/兜底）、路由沙盒预览决策、"
        "成本/质量/本地三权重滑杆，对话真实按规则分发；"
        "权限控制——五能力矩阵四级（完全自主/执行前确认/只读/关闭），"
        "确认弹窗 10 分钟超时自动拒绝，全程审计留痕；"
        "OpenAI 兼容层支持免鉴权自建端点（EMPTY 占位 key）",
    )),
    Release("0.24.0", "2026-08-31", (
        "对齐 LunarCore Claw 卷三：新增「系统」导航域四个自治页面——"
        "自动化（工作流步骤链真实串行执行，上一步产出作为下一步上下文；"
        "连续性开关自动衔接下一轮，开启记 confirmed 审计）、"
        "定时任务（五字段 cron 真实调度线程，四个预设表达式，"
        "系统级夜间进化作业卡片不可删除仅可暂停）、"
        "自我学习（对话页赞/踩即时计入活动流，立刻学习现算当日准确率并回流"
        "路由权重，准确率趋势与每日反馈量图表，五步学习管线）、"
        "进化日志（五角色进化作业：复盘员/归因员/路由师/记忆官/教官，"
        "行为补丁 L0 自动生效 L2 待批准，四态状态机含回滚终态，"
        "生效补丁真实注入系统提示，技能草稿批准转正为正式工作流）；"
        "侧栏四字对齐标签、设置抽屉持久化与外点收起、"
        "底部状态区实时显示本地/API/聚合池计数",
    )),
    Release("0.25.0", "2026-09-04", (
        "局域网 Gradio 文生视频：识别 WAN（如 192.168.3.23:7860）为在线视频服务而非离线聊天模型；"
        "官方 Client.predict(/generate_video) 写入视频运营 02-generate/",
        "视频运营融合：选题/生成/剪辑/分析/多平台发布草稿（人工点发布）",
        "知识库（Obsidian/llmwiki 结构）一键布置；侧栏只保留项目；隐私条款",
        "本地端点双协议探测：Ollama /api/tags 与 OpenAI 兼容 /v1/models（如 DeepSeek LAN）",
    )),
    Release("0.26.0", "2026-09-04", (
        "对话页眉选择模型；输入区下方仅在选用文生视频模型后开放分辨率/帧数/推理步数下拉",
    )),
)


def latest() -> Release:
    return RELEASES[-1]


def get_release(version: str) -> Release | None:
    return next((r for r in RELEASES if r.version == version), None)


def changelog_text() -> str:
    """Render the full changelog as markdown-ish text, newest first."""
    blocks = []
    for release in reversed(RELEASES):
        lines = [f"## {release.version}（{release.date}）"]
        lines.extend(f"- {h}" for h in release.highlights)
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
