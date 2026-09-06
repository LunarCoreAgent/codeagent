# Changelog

所有版本更新记录。数据源：`src/codeagent/releases.py`（CLI 里 `codeagent changelog` 可查）。

## 0.34.0（2026-09-07）

- 融合 LunarCore 语音面 v3.3.17：内置 voice-surface 技能；偏好设置对齐嗲音/晓晨，播报去掉 markdown

## 0.33.0（2026-09-06）

- ComfyUI（Comfy-Org）融合补强：内置 `comfy` 工具，对话要出图/跑节点图时模型自动调用，不把它当聊天模型

## 0.32.0（2026-09-06）

- 融合 BrowserSkill（Tencent/bsk）与 ego-lite（citrolabs）：蒸馏为内置技能；对话要开网页时模型自动调用 `browser` 工具

## 0.31.0（2026-09-06）

- 融合 CPython（python/cpython）：内核、C API、构建与贡献写入软件本体；写普通脚本不启用，打开官方源码树或提到解释器时自动启用

## 0.30.0（2026-09-06）

- 融合 ComfyUI：节点图 HTTP API 技能；video_generate 可调用 MiniMax Hailuo、Kimi 视频模型与本机 ComfyUI
- 通义等云端 500 / InternalError.Algo：中文提示、自动重试，自由路由失败后改走聚合池

## 0.29.0（2026-09-06）

- 融合 Anime.js v4（juliangarnier/anime）：时间线、交错、SVG 描边/路径，对话提到动画时自动启用

## 0.28.0（2026-09-06）

- 工作室模型自动识别工作内容：按任务和项目文件启用匹配技能，并可用 use_skill 独立调用全部技能与知识库/视频运营插件，无需手动点选

## 0.27.0（2026-09-06）

- 融合技能包写入软件本体：Impeccable/React Bits/Taste、中文去 AI 味、女娲蒸馏、Karpathy 工艺、论文脊柱、通宵研究等 18 条，对话按主题注入；技能库分页展示融合 / 视频 / 本地

## 0.26.0（2026-09-04）

- 对话页眉选择模型；输入区下方仅在选用文生视频模型后开放分辨率/帧数/推理步数下拉

## 0.25.0（2026-09-04）

- 局域网 Gradio 文生视频：识别 WAN（如 192.168.3.23:7860）为在线视频服务而非离线聊天模型；官方 Client.predict(/generate_video) 写入视频运营 02-generate/
- 视频运营融合：选题/生成/剪辑/分析/多平台发布草稿（人工点发布）
- 知识库（Obsidian/llmwiki 结构）一键布置；侧栏只保留项目；隐私条款
- 本地端点双协议探测：Ollama /api/tags 与 OpenAI 兼容 /v1/models（如 DeepSeek LAN）

## 0.18.0（2026-08-30）

- 版本与日志：settings 显示版本号，version/changelog 命令查看更新历史，运行日志持久化到 ~/.codeagent/logs/（轮转），logs 命令查看

## 0.17.0（2026-08-30）

- 三路模型接入：云端 API + 本地部署（LM Studio/vLLM/llama.cpp）+ 聚合网关（OpenRouter/硅基流动/AiHubMix/One-API）；AggregateProvider 故障转移与轮询，--provider a,b 逗号串联

## 0.16.0（2026-08-30）

- 个性化设置：称呼/语言/额外说明/主机上下文，注入本机所有对话

## 0.15.0（2026-08-29）

- 外部增援：CLI harness 适配本机 agent 平台（自动发现），工人主动求助 + 领导失败升级；RunArchive 运行记录本地存档

## 0.14.0（2026-08-29）

- 领导模式（HomeRail 深度融合）：语音/文字指挥多模型工人，依赖分批并行，进度板实时可查；蓝图新增 join/loop/while/command 原语 + 运行评分卡

## 0.13.0（2026-08-28）

- 蓝图 DAG 编排（HiveWard）：并行调度、条件路由、人工审批门、YAML 严格加载

## 0.12.0（2026-08-28）

- 技能系统：SKILL.md 生态兼容 + SkillEvolver 自进化；OCR 双引擎工具；Playwright / Chrome DevTools MCP 预设

## 0.11.0（2026-08-27）

- 小智协议客户端：OTA 激活 + WebSocket 协议 + Opus 编解码，接入 xiaozhi.me

## 0.10.0（2026-08-27）

- Scrapling 爬虫工具：web_fetch / web_scrape，反检测浏览器抓取

## 0.9.0（2026-08-26）

- 三省六部多智能体：中书规划→门下封驳→尚书执行，状态机 + 审计日志

## 0.8.0（2026-08-26）

- 台湾音色：晓晨（zh-TW-HsiaoChenNeural）等繁中语音预设，音色固定 + 情绪韵律

## 0.7.0（2026-08-25）

- 语音模块：情绪模式对话（[emotion:xxx] 标签）、edge-tts 免费语音包、本地 Whisper ASR、连续对话 VoiceChatLoop

## 0.6.0（2026-08-25）

- mem0 式智能记忆：事实提取 + ADD/UPDATE/DELETE 对账（SmartMemoryStore）

## 0.5.0（2026-08-24）

- 记忆系统：短期对话压缩 + 长期记忆持久化与检索，记忆工具三件套

## 0.4.0（2026-08-24）

- MCP 客户端：stdio + streamable-HTTP 双传输，Keenable 搜索预设

## 0.3.0（2026-08-23）

- 融合 google-research：Self-Debugging 迭代修复、pass@1 评测体系（MBPP）

## 0.2.0（2026-08-23）

- 融合 OpenAI Codex 洞察：token 预算、Shell 命令风险分类、子代理模式

## 0.1.0（2026-08-22）

- 初始框架：Agent 核心循环、工具注册表、文件/Shell/搜索工具
- 权限系统：风险分级 + 交互式审批，多模型 Provider 抽象
- CLI：run / chat 命令（typer + rich）
