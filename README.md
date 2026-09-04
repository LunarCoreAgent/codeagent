# CodeCoreAgent

开源的代码开发 Agent —— 产品名 **CodeCoreAgent**（简称 CCA），Python 包与 CLI 仍为 `codeagent`。

用统一接口构建能读写代码、执行命令、搜索代码库的 AI Agent，支持多模型切换；另提供桌面图形版（聊天 / 项目 / 停止生成 / 安装包）。

仓库：https://github.com/LunarCoreAgent/codeagent  
许可证：[MIT](./LICENSE) · 隐私条款：[PRIVACY.md](./PRIVACY.md)

## 特性

- **桌面版 CodeCoreAgent**：原生窗口、对话停止按钮、项目归档、本地配置；macOS DMG / Windows 安装包由 Actions 构建
- **多模型支持**：Anthropic Claude、OpenAI、Ollama（本地模型），统一接口，一行切换；可注册自定义 Provider
- **三路模型接入**：云端 API（Claude/OpenAI）+ 本地部署（Ollama/LM Studio/vLLM/llama.cpp，免 key）+ 聚合网关（OpenRouter/硅基流动/AiHubMix/One-API·sub2api 自建中转，一把 key 用遍所有模型）
- **聚合模式**：`--provider ollama,openrouter` 逗号串联多后端——fallback 故障转移（本地优先、云端兜底、坏了自动跳过）或 round-robin 轮询分流，工人名册同样支持
- **完整的 Agent 循环**：消息历史管理、工具调用调度、结果回传、迭代上限保护、token 用量统计
- **内置编码工具集**：文件读写/编辑、目录列举、正则搜索（grep）、文件匹配（glob）、Shell 执行
- **权限与安全**：工具风险分级（只读/写入/执行/危险）、Shell 命令自动分类、审批策略（交互确认 / 严格 / 放行）、路径逃逸防护、fail-closed 默认
- **MCP 生态**：从任意 MCP server 加载工具（Claude 风格配置），瞬间接入数据库、浏览器、第三方服务
- **预算控制**：token 预算上限；子 Agent 委派用量自动归入根预算（Codex 式记账）；预算状态实时注入上下文，模型自适应调整探索深度（BATS 式预算感知）
- **自我调试**：Self-Debugging 修复循环（Google Research, ICLR 2024）——生成 → 执行反馈 → 橡皮鸭解释 → 最小修复
- **记忆系统**：双层架构——短期记忆（对话压缩 compaction，超长历史自动总结）+ 长期记忆（跨会话持久化存储与检索，Agent 可主动存取）；mem0 式智能记忆（事实提取 + ADD/UPDATE/DELETE 对账）
- **技能系统与自进化**：兼容社区 SKILL.md 技能包生态（ponytail / taste-skill / impeccable 等），任务完成后自动反思蒸馏新技能，经验跨会话复利增长
- **领导模式**：一个领导席位指挥多模型工人团队——语音/文字下达命令，自动拆解分派，进度随时可查可播报
- **外部增援**：工人卡住可主动呼叫本机其他 agent 平台（Claude Code / Codex / Gemini CLI / cursor-agent / opencode，自动发现）；工人彻底失败时领导自动升级转派外部平台
- **本地存档**：每次指挥运行（命令/计划/结果/进度快照）持久化到 `~/.codeagent/runs/<项目>/`，全部数据留在本机，可复盘可审计
- **个性化设置**：主机级偏好（称呼/语言/额外说明/机器上下文）存于 `~/.codeagent/settings.json`，自动注入本机所有对话——chat、run、lead、每个工人、语音模式全部生效
- **双编排引擎**：三省六部（固定流水线：规划→封驳→执行→回奏）+ 蓝图 DAG（自由图：十种节点、并行调度、条件路由、人工审批门、join 仲裁、loop/while 循环、command 原语、YAML 严格加载、运行评分卡）
- **OCR 工具**：tesseract / EasyOCR 双引擎图像文字识别，自动回退
- **评测体系**：内置 pass@1 评测框架，直接加载 MBPP 基准（google-research）量化 Agent 能力
- **可观测性**：事件回调机制（tool_call / tool_result / approval / done），方便接入 UI、日志或人工审批流
- **可扩展**：实现 `Tool` 或 `LLMProvider` 抽象基类即可接入自定义工具与模型

## 安装

```bash
# 基础安装（按需选择模型后端）
pip install -e ".[anthropic]"   # Claude
pip install -e ".[openai]"      # OpenAI / OpenAI 兼容端点
pip install -e ".[mcp]"         # MCP 工具生态
pip install -e ".[all]"         # 全部

# 开发（含测试依赖）
pip install -e ".[all,dev]"
```

## 快速开始

```python
import asyncio
from codeagent import Agent, create_provider, default_tools

async def main():
    provider = create_provider("anthropic")  # 或 "openai" / "ollama"
    agent = Agent(provider=provider, tools=default_tools(root_dir="."))
    answer = await agent.run("阅读 src/ 目录，总结项目结构")
    print(answer)

asyncio.run(main())
```

设置 API Key：

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
# Ollama 无需 key，先运行: ollama pull qwen2.5-coder:7b
# 聚合网关（任选）：
export OPENROUTER_API_KEY="sk-or-..."      # openrouter.ai
export SILICONFLOW_API_KEY="sil-..."       # 硅基流动
export AIHUBMIX_API_KEY="..."              # aihubmix
export ONEAPI_API_KEY="..."                # One-API / New-API / sub2api 自建中转
```

### 三路模型接入

| 路线 | Provider | 说明 |
|---|---|---|
| 云端 API | `anthropic` `openai` | 官方直连，`--base-url` 可指向任何 OpenAI 兼容端点 |
| 本地部署 | `ollama` `lmstudio` `vllm` `llamacpp` | 免 key，模型跑在本机 |
| 聚合网关 | `openrouter` `siliconflow` `aihubmix` `oneapi` | 一把 key 调遍上游所有模型；`oneapi` 默认 `localhost:3000`，自建中转用 `--base-url` 指向你的服务 |

### 聚合模式：多后端合一

```bash
# 本地优先，本地挂了自动切云端（fallback 故障转移）
codeagent chat --provider ollama,openrouter

# 多把 key / 多个中转轮询分流
codeagent run "重构这个模块" --provider openrouter,siliconflow,oneapi --strategy round-robin

# 工人名册同样支持：workers.yaml 里写 provider: ollama,openrouter
```

```python
from codeagent import AggregateProvider, parse_provider_spec

provider = parse_provider_spec("ollama,openrouter", strategy="fallback")
print(provider.failures)  # 每个后端的累计失败次数，可观测
```

## CLI 使用

```bash
# 执行单个任务（写操作/命令执行会交互式请求批准）
codeagent run "给这个项目添加单元测试" --provider anthropic

# 交互式多轮对话
codeagent chat --provider ollama --model qwen2.5-coder:7b

# 全自动模式（跳过所有审批，慎用）
codeagent run "修复 lint 错误" --yes

# 限制 token 预算 + 接入 MCP 工具
codeagent run "查询数据库并生成报表" --budget 100000 --mcp-config mcp.json
```

## 权限与安全

每个工具都有风险等级：`READ_ONLY`（读文件/搜索）→ `WRITE`（写文件/git commit）→ `EXECUTE`（运行命令）→ `DESTRUCTIVE`（rm -rf / force push 等）。Shell 命令按内容自动分类。

```python
from codeagent import Agent, PermissionPolicy, RiskLevel, ApprovalDecision

# 严格模式：只读自动放行，其余一律拒绝（fail closed）
policy = PermissionPolicy.strict()

# 交互模式：风险操作交给审批回调（CLI 默认行为）
def my_handler(call, risk):
    print(f"agent 想执行 {call.name}，风险等级 {risk.name}")
    return ApprovalDecision.APPROVE  # 或 DENY / ALWAYS_ALLOW（本次会话记住）

policy = PermissionPolicy(auto_approve_up_to=RiskLevel.READ_ONLY, handler=my_handler)

agent = Agent(provider=provider, tools=tools, permissions=policy)
```

被拒绝的工具调用会作为错误结果回传给模型，Agent 会换用其他方式继续，而不会中断。

## MCP 支持

支持两种传输：**stdio**（本地命令）和 **streamable-HTTP**（远程托管服务）。创建 `mcp.json`（Claude 风格配置）：

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    },
    "keenable": {
      "type": "streamable-http",
      "url": "https://api.keenable.ai/mcp"
    }
  }
}
```

```python
from codeagent import Agent, create_provider, default_tools
from codeagent.mcp import MCPManager, load_mcp_config

async with MCPManager(load_mcp_config("mcp.json")) as mcp:
    tools = default_tools(".")
    for tool in mcp.tools():      # 远程工具以 mcp__<server>__<tool> 命名
        tools.register(tool)
    agent = Agent(provider=create_provider("anthropic"), tools=tools)
    answer = await agent.run("列出 /tmp 下的文件")
```

### 网页搜索（Keenable 预设）

内置 [Keenable](https://keenable.ai) 预设，一行接入实时网页搜索与网页正文提取（免密钥，1000 次/小时）：

```python
from codeagent.mcp import MCPManager, keenable

async with MCPManager([keenable()]) as mcp:   # keenable(api_key="...") 可提升限额
    tools = default_tools(".")
    for tool in mcp.tools():
        tools.register(tool)
    agent = Agent(provider=create_provider("anthropic"), tools=tools)
    answer = await agent.run("搜索最新的 Python 3.14 发布信息并总结")
```

提供 `mcp__keenable__search_web_pages` 与 `mcp__keenable__fetch_page_content` 两个工具。

## 预算与子 Agent

```python
from codeagent import Agent, Budget, DelegateTool

agent = Agent(provider=provider, tools=tools, budget=Budget(max_total_tokens=100_000))

# 让 agent 可以委派子任务；子 agent 的 token 计入父预算
sub_factory = lambda: Agent(provider=create_provider("anthropic"), tools=default_tools("."))
agent.tools.register(DelegateTool(agent_factory=sub_factory, parent=agent))
```

超出预算抛出 `BudgetExceededError`；`agent.usage` 始终包含子 Agent 的用量。

### 预算感知（BATS 式）

设置预算后，每次迭代都会把预算状态注入 system prompt，模型据此调整行为（预算充足时充分探索，紧张时收敛动作）——源自 Google Research 的 Budget-Aware Tool-Use：

```python
agent = Agent(provider=provider, tools=tools, budget=Budget(max_total_tokens=100_000))
# 每次 LLM 调用的 system prompt 自动附带：
# [Budget status] 12500/100000 tokens used, 88% remaining. Plenty of budget remains...
```

## 自我调试（Self-Debugging）

实现 Google Research 的 Self-Debugging 论文（ICLR 2024）：生成代码后自动执行验证，失败时让模型"橡皮鸭调试"（解释代码 → 定位根因 → 最小修复），循环直至通过：

```python
from codeagent import Agent, SelfDebugger, create_provider, default_tools

agent = Agent(provider=create_provider("anthropic"), tools=default_tools("."))
debugger = SelfDebugger(agent, max_turns=5)

result = await debugger.run(
    "实现一个 LRU 缓存并写入 lru.py",
    verify_command="python -m pytest tests/test_lru.py -x",
)
print(result.success, result.turns)   # 是否通过、用了几轮修复
```

## 记忆系统

双层记忆架构，让 Agent 既能撑住长会话，也能跨会话记住东西。

### 短期记忆：对话压缩

历史消息超过阈值时，自动用模型把旧对话总结成紧凑摘要，只保留最近几轮原文：

```python
from codeagent import Agent, ConversationCompactor, CompactionConfig

agent = Agent(
    provider=provider,
    tools=tools,
    compactor=ConversationCompactor(
        provider,  # 用同一个 provider 做总结
        CompactionConfig(max_messages=40, keep_recent=10),
    ),
)
```

### 长期记忆：跨会话存储与检索

```python
from codeagent import Agent, LocalMemoryStore, memory_tools

store = LocalMemoryStore("~/.codeagent/memory.json")   # JSON 持久化，零依赖
tools = default_tools(".")
for tool in memory_tools(store):   # memory_save / memory_search / memory_list
    tools.register(tool)

agent = Agent(provider=provider, tools=tools, memory=store)
# 每个任务开始时，相关记忆自动注入 system prompt；
# Agent 也可以通过工具主动保存/搜索记忆
```

生产环境可实现 `MemoryStore` 接口接入 mem0 / 向量数据库 / neo4j 图存储，Agent 代码无需改动。

### 智能记忆：两阶段写入（事实提取 + 对账）

`SmartMemoryStore` 在任意 `MemoryStore` 之上实现 mem0 风格的写入管线：
先用 LLM 从原文提取原子事实，再与已有记忆对账，自动执行
ADD / UPDATE / DELETE，避免重复和相互矛盾的记忆堆积。

```python
from codeagent import Agent, LocalMemoryStore, SmartMemoryStore

store = SmartMemoryStore(
    LocalMemoryStore("~/.codeagent/memory.json"),
    provider,                 # 用 LLM 做事实提取与对账
)

# "我改用 pytest 了" → 自动 UPDATE 已有的 "用户偏好 unittest"，而非新增一条矛盾记忆
await store.add("我改用 pytest 了")

# 完整 MemoryStore 接口，可直接传给 Agent / memory_tools
agent = Agent(provider=provider, tools=tools, memory=store)
```

需要审计写入细节时，用 `add_with_operations()` 获取实际执行的
`MemoryOperation` 列表。

## 网页抓取工具

集成 [Scrapling](https://github.com/D4Vinci/Scrapling)——自适应爬虫框架，
自带浏览器级 TLS 指纹（curl_cffi），可选 stealth 模式绕过 Cloudflare
等反爬系统。

```bash
pip install codeagent[scrape]
codeagent run "总结一下这个页面 https://example.com" --web
```

```python
from codeagent import web_tools

for tool in web_tools():       # web_fetch / web_scrape
    tools.register(tool)
```

- `web_fetch`：抓取页面返回干净正文（自动剥离 script/style），
  可用 CSS 选择器精确提取片段
- `web_scrape`：命名 CSS 选择器 → 结构化 JSON
  （支持 `::text` / `::attr(href)` 伪类）
- `stealth=True`：走 camoufox 浏览器绕过反爬（需 `scrapling install`
  下载浏览器，较重，按需开启）

## 语音与情感模式

借鉴小智（xiaozhi-esp32）的情绪通道设计：模型每条回复以 `[emotion:xxx]`
开头，框架解析后映射到对应音色（音调/语速），用**免费语音包**
（edge-tts 神经音色，无需 API key）朗读出来。

```bash
pip install codeagent[voice]

# 情感语音连续对话（自动开启情绪模式 + 长期记忆）
codeagent chat --voice --memory

# 只要情绪标签，不要语音
codeagent chat --emotion

# 换音色：预设名或完整 edge-tts 音色 ID 均可
codeagent chat --voice --voice-name hsiaochen   # 台湾国语女声「晓晨」
codeagent chat --voice --voice-name zh-CN-YunxiNeural

# 全语音闭环：麦克风输入（本地 Whisper 离线识别，免费）
pip install codeagent[voice-full]
codeagent chat --mic --memory
# 按 Enter 开始说话，说完再按 Enter → 识别 → 情感语音回复
```

```python
from codeagent import Agent, VoiceChatLoop, EdgeTTSProvider, EMOTION_PROMPT_SUFFIX

agent = Agent(provider=provider)
agent.system_prompt += EMOTION_PROMPT_SUFFIX   # 要求模型带情绪标签

loop = VoiceChatLoop(agent, tts=EdgeTTSProvider())
turn = await loop.turn("今天好累啊")
# turn.emotion == Emotion.LOVING / turn.reply_text == 去掉标签的回复
# 音频已用温柔音色自动播放
```

8 种情绪（neutral/happy/sad/angry/surprised/thinking/loving/sleepy）
各自映射到不同的中文神经音色与语速音调；`TTSProvider` 是可插拔抽象，
生产环境可换火山引擎（小智同款）/ CosyVoice / ElevenLabs。

内置免费音色预设（`VOICE_PRESETS`）：大陆普通话（晓晓/小艺/云希/云健/
晓晨）+ 台湾国语（**晓晨 hsiaochen**、晓宇 hsiaoyu、云哲 yunjhe）。
用 `--voice-name` 指定音色后会固定该音色，情绪只调节语速和音调。

语音输入侧同样可插拔：`ASRProvider` 抽象 + `WhisperASRProvider`
（faster-whisper 本地离线识别，免费，中文效果好，模型大小可选
tiny/base/small/medium/large-v3）。整条链路
**麦克风 → ASR → Agent → 情绪解析 → TTS 朗读** 不依赖任何云服务。

## 多 Agent 编排：三省六部工作流

借鉴 [edict](https://github.com/cft0808/edict) 的制度设计——用 1300 年前的
分权制衡架构组织多 Agent 协作：**中书省规划 → 门下省审议（可封驳打回）→
尚书省派发 → 六部并行执行 → 汇总回奏**。核心是"制度性审核"：任何方案
必须通过门下省质量关卡才能进入执行层，全程状态机保护 + 审计留痕。

```python
from codeagent import Court, create_provider, default_tools

court = Court(
    provider=create_provider("anthropic"),
    tools=default_tools("."),            # 六部执行时可用真实工具
    max_review_rounds=3,                 # 封驳最多打回 3 次
    audit_path="~/.codeagent/audit.jsonl",
)
report = await court.run("给我设计一个用户注册系统：FastAPI + PostgreSQL + JWT")

print(report.report)          # 回奏：尚书省汇总报告
print(report.review_rounds)   # 2 → 被封驳过一次
print(report.plan)            # 中书省的子任务拆解
for r in report.results:      # 各部执行结果
    print(r.subtask.dept, r.ok)
```

- **角色人格**：`CourtRole`（中书/门下/尚书 + 户礼兵刑工五部），可自定义替换
- **封驳循环**：门下省不合格就打回，中书省带着封驳意见重规划；
  `strict_review=True` 时超限直接抛 `ReviewRejectedError`
- **状态机保护**：`RECEIVED→PLANNING→REVIEWING→DISPATCHED→DOING→REPORTING→DONE`，
  非法跳转（如跳过审议）直接拒绝
- **审计留痕**：每个决策写入 JSONL，完整可追溯
- **故障隔离**：一部执行失败不拖累其他部，如实写入回奏

## 小智协议客户端（xiaozhi.me 免费服务器）

实现 [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) 的设备端协议，
把 codeagent 变成一台"虚拟小智设备"，直连 xiaozhi.me 免费服务器
（免费 Qwen 实时模型 + 官方音色）：

```python
from codeagent import XiaozhiClient

client = XiaozhiClient()          # 设备身份持久化在 ~/.codeagent/xiaozhi.json
await client.connect()            # OTA 签到；未激活时抛 ActivationRequiredError(含验证码)

events = await client.say(opus_frames)   # 一轮对话：发音频帧，收完整回复
print(events.stt_text)            # 服务器听到的文字
print(events.emotion)             # 官方情绪标签
print(events.sentences)           # TTS 逐句文本
# events.audio_frames → Opus 解码后播放（OpusCodec，需 libopus）
```

- **OTA 签到/激活**：未激活设备返回验证码，去 xiaozhi.me 控制台登记即可
- **协议层**：hello 握手、listen/abort 控制、stt/tts/llm(emotion)/iot 消息
  分发、二进制 Opus 帧——传输纯逻辑，可对接任意前端
- **音频**：`OpusCodec`（16kHz/60ms 帧，opuslib + libopus）可选安装

## 技能系统与自进化（SKILL.md 生态）

统一的技能层，兼容社区所有 SKILL.md 技能包（ponytail、taste-skill、
darwin-skill、gsap-skills、impeccable、qaskills……），并借鉴
SkillClaw / self-improving-agent 实现"经验 → 技能"的自进化闭环：

```python
from codeagent import Agent, SkillLibrary, SkillEvolver, create_provider

library = SkillLibrary.load("~/.codeagent/skills")   # 加载目录下所有 SKILL.md
evolver = SkillEvolver(create_provider("anthropic"), library, "~/.codeagent/skills")

agent = Agent(provider=create_provider("anthropic"), skills=library, skill_evolver=evolver)
await agent.run("修复 pytest fixture 偶发失败的问题")
# 任务完成后 evolver 自动反思：若学到可复用的经验，写成新的 SKILL.md 存入库中
# 下次运行自动注入 system prompt —— 经验跨会话复利增长
```

- **SKILL.md 格式**：YAML frontmatter（name/description）+ markdown 正文，
  与社区技能包完全兼容，把任意技能包目录丢进 `--skills` 即可用
- **注入策略**：system prompt 中先放全部技能索引（name + 一句话描述），
  再在字符预算内放完整正文，控制 token 开销
- **自进化**：任务成功后 LLM 反思提炼"可复用经验"，无收获则静默跳过；
  同名技能自动更新（进化而非堆积）
- CLI：`codeagent run "..." --skills ./my-skills --evolve`

## OCR 工具（图像文字识别）

融合 tesseract / pytesseract / EasyOCR 三条路线为一个 `ocr` 工具：

```bash
codeagent run "读取 screenshot.png 里的报错信息" --ocr
```

- `engine="auto"`（默认）：优先 tesseract 二进制（`brew install tesseract`），
  缺失时回退 EasyOCR（纯 pip 安装）
- 支持多语言：`lang="eng+chi_sim"`
- 安装：`pip install codeagent[ocr]`（或 `[ocr-easy]`）

## 浏览器 MCP 预设

两条 npx 即用的浏览器 MCP 预设（需 Node.js）：

```python
from codeagent.mcp.presets import playwright_mcp, chrome_devtools_mcp

# Playwright MCP（微软官方）：导航/点击/填表/截图
# Chrome DevTools MCP：性能追踪、网络检查、console、DOM 快照
configs = [playwright_mcp(), chrome_devtools_mcp()]
```

## 领导模式：多模型团队指挥（HomeRail 深度融合）

`codeagent lead` —— 一个领导席位，语音或文字下达命令，自动拆解任务、
分派给**不同模型**的工人，随时查看进度：

```bash
# workers.yaml 定义工人花名册（每个工人一个模型）
cat > workers.yaml <<'EOF'
workers:
  - name: claude
    provider: anthropic
    description: 擅长代码架构与审查
  - name: qwen
    provider: ollama
    model: qwen2.5-coder:7b
    description: 本地快速执行批量任务
EOF

codeagent lead --workers workers.yaml --mic --voice   # 语音指挥 + 语音汇报
codeagent lead --workers workers.yaml                 # 纯文字
```

```
boss> 给项目补上单元测试，同时把 README 翻译成英文
领导: 好的，两路并行。
  · 写单元测试 → running（claude）
  · 翻译 README → running（qwen）
  ...
boss> 进度怎么样？                       ← 随时问，不打断工作
领导: 当前共 2 项任务：1 项完成，1 项进行中……
```

- **领导拆解**：LLM 把命令拆成分派计划（worker/task/depends_on），
  无依赖的任务 `asyncio` 并行，有依赖的按批串行并传递上游成果
- **每工人独立模型**：聪明大脑规划、便宜模型干活（HomeRail 理念）
- **工人全装备**：每个工人自带完整工具集 + 已加载技能库 + 项目概况注入
  （根目录结构 + README 摘要），开工前就"理解项目"
- **进度板**：`ProgressBoard` 实时跟踪每任务状态/耗时/详情，
  文字问"进度"或语音问"做得怎么样了"即刻播报
- **外部增援（HiveWard harness 员工理念）**：工人遇到困难的三种自救——
  ① 工人中途主动调 `ask_external_agent` 工具求助本机其他 agent 平台；
  ② 工人彻底失败时领导自动把任务升级转派给可用平台（`--no-escalate` 关闭）；
  ③ 启动时自动发现本机已安装平台（claude / codex / gemini / cursor-agent / opencode）
- **本地存储**：每次命令运行自动存档到 `~/.codeagent/runs/<项目名-哈希>/`，
  含原始命令、分派计划、完整汇报、进度快照——项目历史永不丢失

## 个性化设置：本机所有对话生效

一次设置，`chat` / `run` / `lead` / 每个工人 / 语音模式全部生效：

```bash
codeagent settings set \
  --nickname 石头 \
  --language 中文 \
  --instructions "回答先给结论，再给细节；代码注释用中文" \
  --context "M4 Mac，项目在 ~/code，偏好 pytest"

codeagent settings show    # 查看当前个性化
codeagent settings clear   # 清除
```

设置存于 `~/.codeagent/settings.json`，作为 system prompt 段落注入每一次对话
（包括领导规划、工人执行、语音聊天），让模型始终知道你是谁、怎么称呼你、
你的机器环境和偏好。库用法：`Agent(provider=..., settings=Settings.load())`。

## 下载预编译版本（Windows / macOS）

不想装 Python？直接用安装包（无需安装 Python 环境）：

**桌面版 CodeCoreAgent（图形窗口，推荐）**

| 平台 | 安装包 | 用法 |
|---|---|---|
| macOS (Apple Silicon) | `codeagent-desktop-macos-arm64.dmg` | 挂载 → 拖 `CodeCoreAgent.app` 到 Applications |
| macOS (Intel) | `codeagent-desktop-macos-amd64.dmg` | 同上 |
| Windows (x64) | `codeagent-desktop-windows-amd64.zip` / `*-setup.exe` | 解压或运行安装程序 |

桌面版内含：聊天窗口（含停止生成）、项目归档、图形设置面板
（模型连接 + 聚合策略 + 个性化）、版本与更新日志页。
源码运行：`pip install -e ".[desktop]"` 然后 `codeagent desktop`。

**命令行版（单文件 CLI）**

| 平台 | 安装包 | 用法 |
|---|---|---|
| macOS | `codeagent-macos-*.dmg` | 双击挂载 → 双击「安装.command」装入 `/usr/local/bin` |
| Windows (x64) | `codeagent-windows-amd64.zip` | 解压得 `codeagent.exe`，命令行运行 |

打 `v*` 标签时 GitHub Actions 自动构建三平台安装包并挂到 Release
（workflow：`binaries.yml`）。本地自行构建：

```bash
pip install -e ".[anthropic,openai,mcp,voice,desktop,packaging]"
python packaging/make_icon.py    # 从 packaging/logo-art.png 生成 icon.png/icns/ico + 侧栏 mark
python scripts/build_binary.py   # CLI 单文件 → dist/binary/，自动冒烟测试
python scripts/build_dmg.py      # CLI 打包成 dist/*.dmg（macOS）
python scripts/build_desktop.py  # 桌面版 CodeCoreAgent.app / .exe + DMG/ZIP
python scripts/sign_macos.py     # Developer ID 签名 + 公证（macOS）
```

**macOS 签名与公证**：本机钥匙串里有 `Developer ID Application` 证书时，
`sign_macos.py` 自动完成签名（hardened runtime）并重建 DMG。
完整公证（消除"无法验证开发者"提示）需配置凭证，二选一：

```bash
# 方式一：钥匙串凭证（推荐，一次配置永久使用）
xcrun notarytool store-credentials AC_PASSWORD --apple-id 你的AppleID --team-id FXC38NGJH7
NOTARY_PROFILE=AC_PASSWORD python scripts/sign_macos.py

# 方式二：环境变量（APPLE_PASSWORD 用 appleid.apple.com 生成的 App 专用密码）
export APPLE_ID="you@example.com" APPLE_PASSWORD="xxxx-xxxx-xxxx-xxxx"
python scripts/sign_macos.py
```

CI 里配置 secrets `APPLE_ID` / `APPLE_PASSWORD` / `APPLE_TEAM_ID` 并把仓库变量
`MACOS_SIGNING_ENABLED` 设为 `true`，发版即自动签名公证。

二进制内置：核心框架 + Claude/OpenAI SDK + MCP 客户端 + edge-tts 语音包。
重量级可选项（Whisper 语音识别、Playwright 爬虫、EasyOCR）为保持体积未打包，
需要时请用 pip 安装完整版。

## 版本与日志

```bash
codeagent version     # 当前版本号 + 本次更新内容
codeagent changelog   # 全部版本的更新历史（数据源 src/codeagent/releases.py）
codeagent logs -n 50  # 查看最近运行日志
codeagent settings show  # 版本号 + 本次更新 + 日志路径 + 个性化，一屏总览
```

- **日志记录**：每次 `run` / `chat` / `lead` 自动写入 `~/.codeagent/logs/codeagent.log`
  （1MB × 5 轮转），记录命令调用、任务起止、工具调用与审批、token 用量、错误
- 日志级别用 `CODEAGENT_LOG_LEVEL=DEBUG` 调高；库用法 `codeagent.setup_logging()`

## 蓝图编排：自由 DAG 工作流（HiveWard 式）

融合 [HiveWard](https://github.com/Chaunyzhang/HiveWard) 的"业务蓝图"调度思想：
不同于三省六部的固定流水线，蓝图是自由的有向无环图——上游输出沿连线流向下游，
条件/管理节点决定激活哪些分支，审批节点暂停等待人工拍板：

```python
from codeagent import Blueprint, BlueprintRunner, Node, NodeKind, Edge, ApprovalResult, create_provider

bp = Blueprint(
    nodes=[
        Node("analyze", NodeKind.AGENT, label="分析", prompt="分析需求：{task}"),
        Node("route", NodeKind.CONDITION, label="路由"),
        Node("quick", NodeKind.AGENT, label="快修", prompt="快速修复：{inputs}"),
        Node("deep", NodeKind.AGENT, label="重构", prompt="深度重构：{inputs}"),
        Node("gate", NodeKind.APPROVAL, label="上线审批"),
        Node("ship", NodeKind.AGENT, label="发布", prompt="发布：{inputs}"),
    ],
    edges=[
        Edge("analyze", "route"),
        Edge("route", "quick", label="简单"),
        Edge("route", "deep", label="复杂"),
        Edge("quick", "gate"), Edge("deep", "gate"),
        Edge("gate", "ship"),
    ],
)

runner = BlueprintRunner(
    create_provider("anthropic"), bp,
    approval_handler=lambda node, out: ApprovalResult(approved=True),  # 接 UI 做人工审批
)
report = await runner.run("修复登录页样式 bug")
print(report.final_output(bp))
```

- **十种节点**：`agent`（LLM 执行）、`slot`（并行执行线）、`manager`（LLM 多选分支）、
  `condition`（LLM 单选分支）、`approval`（人工门：批准/拒绝/改稿）、`aggregate`（汇总），
  以及 HomeRail 原语——`join`（all/any/n_of_m 仲裁）、`loop`（有限循环收集每轮结果）、
  `while`（LLM 判断的有界循环）、`command`（allowlist 命令，无 shell，默认全拒）
- **并行调度**：按拓扑层级推进，同层节点 `asyncio.gather` 并行
- **每节点独立模型**：`providers={"planner": claude, "*": ollama}`——聪明大脑便宜手脚
- **审批语义**：拒绝 → 下游全部跳过；改稿 → 人工文本替换上游输出继续流转
- **YAML 蓝图**：`load_blueprint_yaml()` 严格校验，未知字段/拼写错误直接报错
  （WorkflowSpec 思想：静默错误不可接受）
- **运行评分卡**：`report.scorecard()` 输出节点成败/迭代次数/token 用量，可复盘
- **可审计**：复用 court 的 `AuditLog`，蓝图运行全程留痕可复盘
- **健壮性**：路由节点回答无法解析时自动回退到第一分支，流程不死锁

## 评测（MBPP）

用 google-research 的 MBPP 基准量化 Agent 的代码生成能力（pass@1）：

```python
from codeagent import Agent, create_provider, evaluate, load_mbpp

tasks = load_mbpp(limit=50)   # 自动从 GitHub 下载；也可传本地 jsonl 路径
report = await evaluate(
    agent_factory=lambda: Agent(provider=create_provider("anthropic")),
    tasks=tasks,
    max_concurrency=4,
)
print(report.summary())       # pass@1: 72.0% (36/50) ...
```

> 注意：评测会执行生成的代码，请在沙箱/容器中运行。

## 架构

```
src/codeagent/
├── core/            # Agent 循环、消息类型、预算、配置
│   ├── agent.py     #   Agent: run() 主循环 + 权限检查 + 事件回调
│   ├── types.py     #   Message / ToolCall / ToolResult / LLMResponse
│   ├── budget.py    #   Budget / BudgetExceededError
│   └── config.py    #   AgentConfig (pydantic) + build_agent()
├── llm/             # 多模型抽象层
│   ├── base.py      #   LLMProvider 抽象基类
│   ├── anthropic.py #   Claude
│   ├── openai.py    #   OpenAI 及兼容端点
│   ├── ollama.py    #   本地模型
│   └── registry.py  #   create_provider() 工厂
├── tools/           # 内置工具集
│   ├── base.py      #   Tool 抽象基类（含 risk_level）+ ToolRegistry
│   ├── filesystem.py#   read_file / write_file / edit_file / list_dir
│   ├── search.py    #   grep / glob
│   ├── shell.py     #   bash（命令自动风险分类）
│   ├── web.py       #   web_fetch / web_scrape（Scrapling 驱动）
│   ├── ocr.py       #   ocr（tesseract / EasyOCR 双引擎）
│   └── delegate.py  #   子 Agent 委派
├── security/        # 权限策略
│   └── policy.py    #   RiskLevel / PermissionPolicy / classify_command
├── mcp/             # MCP 生态接入
│   ├── client.py    #   MCPManager / MCPTool（stdio + streamable-HTTP 双传输）
│   └── presets.py   #   keenable() / playwright_mcp() / chrome_devtools_mcp() 预设
├── repair/          # 自我调试
│   └── self_debug.py#   SelfDebugger（生成→反馈→解释→修复）
├── court/           # 三省六部多 Agent 编排
│   ├── roles.py     #   CourtRole 角色人格（中书/门下/尚书 + 五部）
│   ├── state.py     #   任务状态机（受保护的流转路径）
│   ├── audit.py     #   审计日志（JSONL 奏折存档）
│   └── workflow.py  #   Court：规划→审议(封驳)→并行执行→回奏
├── blueprint/       # 蓝图编排（HiveWard/HomeRail 式 DAG）
│   ├── graph.py     #   Node/Edge/Blueprint：十种节点 + DAG 校验 + 拓扑分层
│   ├── runner.py    #   BlueprintRunner：并行调度 + 路由 + 审批门 + 评分卡
│   └── yaml_loader.py#  YAML 蓝图严格加载（未知字段报错）
├── leader/          # 领导模式（多模型团队指挥）
│   ├── leader.py    #   Leader：命令拆解 → 依赖分批 → 并行分派 → 失败升级
│   ├── worker.py    #   WorkerConfig + workers.yaml + 项目感知工人构建
│   ├── progress.py  #   ProgressBoard：实时进度，语音可播报
│   └── archive.py   #   RunArchive：运行记录本地持久化（~/.codeagent/runs/）
├── harness/         # 外部 agent 平台适配（harness 员工）
│   ├── adapters.py  #   CliHarness + 五大平台预设 + 本机自动发现
│   └── tool.py      #   ask_external_agent：工人主动求助工具
├── memory/          # 记忆系统
│   ├── store.py     #   MemoryStore 抽象 + LocalMemoryStore（JSON 持久化）
│   ├── facts.py     #   FactExtractor：LLM 提取原子事实
│   ├── reconcile.py #   MemoryReconciler：ADD/UPDATE/DELETE 对账
│   ├── smart.py     #   SmartMemoryStore：两阶段写入管线
│   ├── tools.py     #   memory_save / memory_search / memory_list
│   └── compact.py   #   ConversationCompactor 对话压缩
├── skills/          # 技能系统与自进化
│   ├── skill.py     #   Skill（SKILL.md 解析）+ SkillLibrary（加载/检索/注入）
│   └── evolve.py    #   SkillEvolver：任务经验 → 新技能（自进化闭环）
├── eval/            # 评测体系
│   ├── harness.py   #   evaluate() / pass@1 / 代码提取执行
│   └── mbpp.py      #   MBPP 基准加载器
├── voice/           # 语音与情感
│   ├── emotion.py   #   情绪标签解析 + 情绪→音色映射
│   ├── tts.py       #   TTS 抽象 + EdgeTTS 免费语音包 + 播放
│   ├── asr.py       #   ASR 抽象 + faster-whisper 免费离线识别
│   ├── recorder.py  #   麦克风录音（push-to-talk）
│   └── chat.py      #   VoiceChatLoop 连续对话循环
├── xiaozhi/         # 小智协议客户端（xiaozhi.me 免费服务器）
│   ├── config.py    #   设备身份（MAC + UUID 持久化）
│   ├── ota.py       #   OTA 签到 / 激活流程
│   ├── protocol.py  #   WebSocket 协议（握手 + 消息 + Opus 帧）
│   ├── audio.py     #   OpusCodec（opuslib 封装）
│   └── client.py    #   XiaozhiClient 高层对话客户端
└── cli/             # 命令行入口 (typer + rich)
```

## 扩展

### 自定义工具

```python
from codeagent import Tool, RiskLevel

class RunTestsTool(Tool):
    name = "run_tests"
    description = "Run the project test suite."
    parameters = {"type": "object", "properties": {}}
    risk_level = RiskLevel.EXECUTE   # 参与权限策略

    async def execute(self) -> str:
        import subprocess
        return subprocess.run(["pytest", "-x"], capture_output=True, text=True).stdout

tools = default_tools(".")
tools.register(RunTestsTool())
```

### 自定义模型 Provider

```python
from codeagent import LLMProvider, LLMResponse, register_provider

class MyProvider(LLMProvider):
    name = "myprovider"

    async def complete(self, messages, tools=None, system=None, **kwargs) -> LLMResponse:
        ...  # 调用你的模型 API，返回统一的 LLMResponse

register_provider("myprovider", MyProvider)
```

### 事件回调（接入 UI / 审批流）

```python
def on_event(event):
    if event.type == "tool_call":
        print(f"agent 调用工具: {event.data.name}")
    elif event.type == "approval":
        print(f"审批结果: {event.data['decision']}")

agent = Agent(provider=provider, tools=tools, on_event=on_event)
```

## 发布

仓库内置 GitHub Actions：

- **CI**（`.github/workflows/ci.yml`）：push / PR 时在 Python 3.10–3.13 矩阵上运行测试
- **Release**（`.github/workflows/release.yml`）：推送 `v*` 标签自动构建并发布到 PyPI（使用 trusted publishing，需在 PyPI 侧配置 OIDC）

```bash
git tag v0.2.0 && git push --tags   # 触发发布
```

## 测试

```bash
pytest
```

## License

[MIT](./LICENSE) © 2026 LunarCoreAgent · [隐私条款](./PRIVACY.md)
