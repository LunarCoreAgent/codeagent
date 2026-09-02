# Changelog

所有版本更新记录。数据源：`src/codeagent/releases.py`（CLI 里 `codeagent changelog` 可查）。

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
