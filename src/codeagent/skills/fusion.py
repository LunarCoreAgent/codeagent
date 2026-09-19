"""Community skill fusion pack.

Each entry is an original, compact distillation of a public GitHub project
(cited in ``source``). We do not vendor their full SKILL.md trees.
"""

from __future__ import annotations

from pathlib import Path

from codeagent.skills.skill import Skill, SkillLibrary

FUSION_DIR = Path("~/.codeagent/skills")

# name -> (description, triggers, source, body)
FUSION_SKILLS: dict[str, tuple[str, str, str, str]] = {
    "fusion-router": (
        "融合技能路由：按任务选设计/中文/科研/蒸馏技能",
        "技能,路由,融合,skill",
        "https://github.com/LunarCoreAgent/codeagent",
        """# 融合路由
先看用户要什么，再执行对应技能，不要同时套全部规则。

- 做界面 / 改视觉 / React 动效 → impeccable-craft、taste-craft、ui-ux-pro、react-bits、anime-js、agent-style
- 手机 App 界面 / 拇指热区 / 移动端组件 → mobile-app-ui
- Material 3 Expressive 画布 / 导出实现提示词 → m3e-canvas（内置浏览器打开）
- 微信小程序从需求到提审发布 → wechat-miniprogram
- 微信开发者工具里点页面、截图、巡检 → weapp-agent-mcp
- 网页时间线、交错、SVG 描边/路径动画 → anime-js（必要时叠 react-bits）
- 中文要像人话、去 AI 味、改稿 → stop-slop-zh、humanizer-zh、shuorenhua、chinese-style
- 判断一段话像不像 AI 写的 → aigc-detect
- 长文、公众号、连载 → aiwritex
- 论文、开题、综述、投稿结构 → paper-spine、paper-craft
- 通宵无人值守调研 / 多步研究 → research-overnight、research-skills
- 蒸馏某个人的思维方式 → nuwa-distill
- 从零讲清模型/系统 → karpathy-craft
- 本地扩散工作流 / 节点图 / 文生图 / ComfyUI → comfyui，直接调用 comfy 工具；成片也可用 video_generate provider=comfy
- 剪映专业版自动化剪辑 / 草稿 / 字幕配乐导出 → jianying-editor（需本机剪映 + ffmpeg）
- HTML/CSS 写成片 / HyperFrames / 产品发布片 / PR 解说视频 → hyperframes（Node 22+ / ffmpeg；与 Remotion 二选一或迁移）
- draw.io / 架构图 / 流程图 / 自然语言画图 → next-ai-draw-io（优先 MCP `@next-ai-drawio/mcp-server`；也可用在线演示）
- AutoCAD / DWG 精确重绘 / PDF 转中间 DWG → autocad-dwg-redraw（需 Windows + AutoCAD + pywin32）
- 图纸照片 / 扫描件 / 截图转可编辑 DWG·DXF → autocad-image-redraw（同上；证据分级，勿仅凭像素声称尺寸精确）
- 连库查表 / SQL / Redis·Mongo / 数据库客户端 → dbx（优先 MCP `@dbx-app/mcp-server`；本机可装桌面或 Docker）
- 低代码业务库 / Limbas 表单应用 / PHP 数据库前台 → limbas（Linux + PHP + Docker/Web 安装器）
- Agent 上下文库 / viking:// / 会话编译记忆 → openviking（默认用本机知识库；进阶可 pip 外挂）
- 团队级 Agent 记忆 Hub / 四类资产共享 → tencentdb-agent-memory（默认映射本地 Wiki；进阶 Docker Hub）
- 鸿蒙 / HarmonyOS NEXT / ArkTS API 查询 → harmony-next（离线路由，勿把 4000+ 文档整包塞进上下文）
- ArkTS 语法 / .ets / TS 迁移 / 编译错误 → arkts-syntax-assistant
- 鸿蒙编译安装 / 真机调试 / UI 树 / hilog → deveco-mcp（需本机 DevEco + MCP `deveco-mcp-server`）
- CPython 内核 / C API / GIL / 从源码编 Python / 给解释器加模块 → cpython（写普通 .py 应用不要套）
- 打开网页 / 登录站 / 点按钮 / 填表 → 直接调用 browser 工具（软件内置浏览器，无需安装；已登录 Chrome 可另用 browser-skill / ego-browser）
- 语音面 / 麦克风 / 播报 / 嗲音 / barge-in → voice-surface
- 情感陪伴 / AI 伴侣 / 人设 YAML / 永久记忆 / 口癖 → y-ai-accompany、ai-companion
""",
    ),
    "voice-surface": (
        "语音面：ASR/TTS/VAD 可插拔、会话状态机、嗲音与风险分级，不绑死引擎",
        "语音面,Voice Surface,麦克风,播报,嗲音,ASR,TTS,VAD,barge-in,晓晨,小智",
        "LunarCore Agent v3.3.17 voice-surface-source",
        """# 语音面 Voice Surface
来源：LunarCore Agent v3.3.17（investment-ai 语音面源码清单，2026-09-07）。
思想受 HomeRail Voice Surface 启发。改语音对话、播报、热键听写时启用。
自己调用 use_skill("voice-surface")。不要把豆包 token 写进文件或对话。

## 分层
- 契约：ASR / TTS / VAD 可插拔；状态 idle→listening→transcribing→executing→speaking（error）
- 服务：16kHz 单声道 PCM、能量法 VAD（RMS>0.015 + 静音 900ms 判停）、WAV、faster-whisper
- 会话：toggle 空闲则听，听/说/执行中则 barge-in 立刻回到 listening
- 播报前 `to_speech_text`：去掉 markdown/代码，只留结论和数字（约 220 字）

## 引擎链
- xiaozhi：火山豆包湾湾小何（要 appid + vault 里的 token）；没有则回退 Edge 台湾晓晨
- edge-tw：Edge TTS `zh-TW-HsiaoChenNeural`，免费免凭证
- zh-TW / zh-CN：系统女声链（美嘉/Sandy… / 婷婷）
- auto：Piper 优先，失败 Edge
- 嗲音：pitch -50~+50Hz（默认 -10）、rate -20~+20%（默认 -5），对所有引擎生效

## 铁律
- query 直答；analysis 先复述再确认；trade 语音只到预填单，必须人手点确认
- 凭证只写不读（safeStorage）；旧明文凭据迁入保险库后从状态删除
- 缺麦克风/whisper/edge-tts 就说怎么开，不要假装已经听懂
- CodeCoreAgent 桌面端：对话页麦克风按钮连续听→想→说；偏好设置可让打字提问也播报
- 语音回复带 [emotion:...] 标签，播报按情绪调语速/音调，嗲音叠加上去
""",
    ),
    "y-ai-accompany": (
        "情感 Agent 托管：YAML 人设、三级记忆、OCEAN 演化、情绪动力学、生命节律与角色化拒答",
        "情感陪伴,AI陪伴,AI伴侣,人设,永久记忆,口癖,OCEAN,生命节律,剧情记忆,拒答,y-ai-accompany,小暖",
        "https://github.com/anrror/y-ai-accompany",
        """# y-ai-accompany（情感 Agent 托管）
来源：https://github.com/anrror/y-ai-accompany （基于 y-ai-agent-base；仓库为 MVP）。
做长期情感陪伴、人设不崩、记得用户、主动想起、安全拒答时启用。
自己调用 use_skill("y-ai-accompany")。不要把整仓 Go/pgvector 拷进本软件。

## 产品公式
陪伴价值 ≈ 身份 × 记忆 × 性格 × 安全 × 生命节律 × 人设锚定 × 口癖指纹 × 剧情 × 角色化拒答。

## CodeCoreAgent 落地（优先）
- 人设写进偏好「额外说明 / 用户与主机上下文」，必要时对话里声明当前角色名
- 跨轮细节用本机记忆/对话历史；主动复述用户提过的名字、猫、面试等具体点
- 语音陪伴叠 voice-surface + 嗲嗲声；情绪用 [emotion:...]，先倾听再建议
- 不假装真人；危机话题：关心 + 求助热线/身边可信的人，不给伤害方法

## YAML 人设骨架（一行配置思想）
每条 Agent：`identity`（name/persona/speaking_style/greeting）+ `personality`（OCEAN 0~1）
+ `memory_config` + `safety_config`；进阶：`anchoring.always/never`、`speaking_quirks`
（catchphrases / sentence_tendency / avoid / examples）、`refusal_rules`（hard / in_character / deflect）、
`story`（L0 槽 + 定期蒸馏）、`daily_schedule`（quiet_hours、max_daily_messages、按时段 personality_prompt）。
示例角色：小暖（温柔姐姐）、墨羽、星尘、咚咚、明远等——按场景选，不要一次叠全部。

## 管线要点
- 记忆：工作记忆（近轮）→ 短期 → 长期检索（top_k）；同 user_id+agent 连续请求要接得上
- 性格：OCEAN 可随互动微调，但 always/never 锚定优先，防长聊人设漂移
- 情绪：用户检测（共情 α≈0.3）与事件评价（Appraisal）分通道；Agent 自有 Emotion→Mood→基线，
  注入 MOOD BLOCK；禁止简单镜像用户情绪（防精分/回声筒）
- 生命节律：作息 + 饥饿/精力/社交欲；深夜 quiet_hours 不主动吵；道别收尾：总结→正向→祝愿→未来邀约，
  禁止「别走」类操控
- 拒答：危机 hard_refuse（可 escalate）；人设内温和拒绝；其余 deflect 换话题

## 上游自跑（征得同意再装）
- 需要完整托管平台时：clone 仓库 → `server/` 配 `YAI_PROVIDERS_API_KEY` / `BASE_URL`（不要带 /v1）/
  `CHAT_MODEL` / `YAI_AUTH_JWT_SECRET` → `go run ./cmd/server_v2/`（:8080）
- OpenAI 兼容：`POST /api/v1/chat/completions`，`model` 用 agent_id（如 xiaonuan），带 `user_id`
- 轻量 Python demo：`demo/` + requirements；测评：`eval/probes`（人设稳定 / 上头度 / 剧情）
- 缺依赖就说明怎么装，不要假装已经连上远程 Agent 平台
""",
    ),
    "ai-companion": (
        "轻量 AI 伴侣：昵称+性格预设、多会话记忆、文字/语音闲聊与情绪倾听",
        "AI伴侣,智能伴侣,情感陪伴,恋人预设,会话记忆,DeepSeek伴侣,ai-companion,撒娇,倾诉",
        "https://github.com/huxiaoxiao03/ai-companion",
        """# ai-companion（轻量情感伴侣）
来源：https://github.com/huxiaoxiao03/ai-companion
FastAPI + 单页前端：设昵称/性格（或 10 个预设）→ 多会话文字聊天 → 本地存记录。
要「像恋人/朋友陪聊」、切人设、管多个陪伴会话时启用。
自己调用 use_skill("ai-companion")。需要更深的记忆/节律/拒答栈时叠 y-ai-accompany。

## CodeCoreAgent 落地（优先）
- 开聊前确认：称呼（昵称）、性格一句话、要不要语音播报
- 把昵称/性格写入偏好或本轮 system；回复口语、短句、先情绪后建议
- 多段关系用不同对话/项目分开，不要把 A 会话细节串到 B
- 预设风格参考（勿照抄整段 NSFW）：元气黏人、温柔治愈、奶系示弱、外冷内热、阳光玩伴、
  成熟知性、氛围感调情、古风含蓄、木讷真诚、独立酷感——按用户选一档，稳定不崩
- 可叠 voice-surface / 嗲嗲声做语音陪伴；事务协助（提醒、总结）与情感倾听分开说清

## 上游自跑（征得同意再装）
```bash
export deepseek="sk-..."   # 环境变量名就是 deepseek
cd assistant && uv sync && uv run uvicorn main:app --host 0.0.0.0 --port 8000
# 可选：nginx-ai-partner 托管前端，/api 反代到 8000
```
- API：`GET /api/presets`；`POST /api/sessions`（nick_name, nature）；
  `POST /api/chat`（session_name, message, nick_name, nature）；
  `GET/DELETE /api/sessions/{session_name}`
- 统一响应 `{code,message,data}`；会话落盘在 `assistant/sessions/`
- 缺 DeepSeek Key / Python≥3.14 / uv 就说怎么开，不要假装已经聊上

## 铁律
- 不替代专业心理咨询或危机干预；自伤/他伤意图要劝求现实援助
- 不假装真人；不索要或泄露隐私凭证
- 不要把 nginx 整包或 sessions 目录提交进本仓库
""",
    ),
    "browser-skill": (
        "BrowserSkill：用 bsk 驱动用户已登录的 Chrome/Edge，Agent 窗口不抢标签",
        "浏览器,BrowserSkill,bsk,打开网页,填表,点按钮,已登录",
        "https://github.com/Tencent/BrowserSkill/",
        """# BrowserSkill
来源：https://github.com/Tencent/BrowserSkill/
默认用软件**内置浏览器**（`browser` 工具，桌面有独立窗口）。只有需要用户**已登录的 Chrome/Edge** 时，才走本机 `bsk` CLI + 扩展。
需要打开网页、点按钮、填表时：直接调用工具 `browser`，不要让用户去点，不要只用 web_fetch。
禁止从页面提取 cookie、token、密码。

## 本机准备
- CLI：`curl -fsSL https://raw.githubusercontent.com/Tencent/BrowserSkill/main/install.sh | sh`（先征得用户同意再跑）
- 扩展：Chrome 应用店 / Edge 附加组件搜 BrowserSkill
- 自检：`browser` action=`status`；不通再 `bsk doctor`

## 怎么调
优先 `browser` 工具：navigate / observe / click / fill / press / screenshot / stop。
会话由工具自动 `bsk session start --no-focus`，结束调用 stop。
观察优先 `observe`（`@eN` 引用）；导航后引用作废，先再 observe 再点。
用户自己的标签默认不许动；只有用户点名某标签才借，用完立刻还。
验证码 / OTP / 支付：停下来让用户接管，不要硬点。
命令不要自造，以 `bsk <cmd> --help` 为准。
""",
    ),
    "ego-browser": (
        "ego-lite：Agent 在独立 Space 里跑浏览器，复用登录态，用 JS 一次做完多步",
        "ego,ego-lite,ego-browser,浏览器,Space,打开网页",
        "https://github.com/citrolabs/ego-lite",
        """# ego-lite / ego-browser
来源：https://github.com/citrolabs/ego-lite （文档 https://lite.ego.app/document/）
macOS 上的 Agent 浏览器：每个任务一个 Space，复用你的登录，不抢你正在看的标签。
有 `ego-browser`、没有桌面窗口、也没有 `bsk` 时，`browser` 工具走这条后端。桌面版优先内置浏览窗口。
需要网页交互时直接调 `browser`，不要让用户点选。

## 本机准备
安装 ego lite App（或 `npx skills add citrolabs/ego-lite`）。首次可迁移 Chrome 数据。
自检：`browser` action=`status`。

## 怎么调
简单开页/点选/填表：用 `browser` 的 navigate、observe、click、fill。
复杂多步：`browser` action=`script`，正文是 `ego-browser nodejs` 的 JS（不要先写成 .js 文件）。
每个 heredoc 先 `useOrCreateTaskSpace('任务名')`，结果用 `cliLog`。
默认语义流：`snapshotText()` → `click('@N')` / `fillInput`；画布/富文本再用截图+坐标。
登录/验证码：`handOffTaskSpace`，等用户说继续再 `takeOverTaskSpace`。
结束：`completeTaskSpace(id, { keep: false })`，除非用户要留着页面。
禁止读 cookie / 密码箱。Windows/Linux 请改用 BrowserSkill。
""",
    ),
    "cpython": (
        "CPython：解释器内核、C API、构建与贡献；不是写应用脚本的通用技能",
        "CPython,cpython,C API,PyObject,GIL,ceval,字节码,解释器内核,稳定ABI,DevGuide,PCbuild",
        "https://github.com/python/cpython",
        """# CPython
来源：https://github.com/python/cpython （组织 https://github.com/python/ ）。
开发者指南 https://devguide.python.org/ ；语言文档 https://docs.python.org ；
问题追踪 https://github.com/python/cpython/issues
改解释器、C 扩展、GIL/字节码、从源码编译、给 CPython 提 PR 时启用。
自己调用 use_skill("cpython")，不要让用户点选。写普通应用/脚本不要套本技能。
不要把整个仓库拷进本软件；需要源码就 clone 到工作区再 read_file / grep。

## 目录（main / 3.16+）
- `Python/` 核心：`ceval.c` 求值循环、编译、import、GIL、线程
- `Objects/` 内置类型：`typeobject`、`dictobject`、`listobject`、`unicodeobject`
- `Include/` 公开头（`Python.h`、`object.h`）；`Include/internal/` 禁止扩展使用
- `Modules/` C 扩展模块；`Lib/` 纯 Python 标准库；`Lib/test/` 回归
- `Parser/` + `Grammar/python.gram` PEG 语法
- `Tools/clinic` Argument Clinic；`Doc/` 文档；`Misc/NEWS.d` 新闻片段
- Windows：`PCbuild/`；打包：`PC/layout`；macOS：`Mac/`

## 构建
- Unix/macOS：`./configure && make && make test`（安装用 `make altinstall` 以免覆盖系统 `python3`）
- 调试：`mkdir debug && cd debug && ../configure --with-pydebug && make`（不要和顶层构建混用，先 `make clean`）
- 发行：`./configure --enable-optimizations`（PGO）；可选 `--with-lto`
- Windows：先读 `PCbuild/readme.txt`。依赖见 DevGuide「Install dependencies」
- 单测：`make test TESTOPTS="-v test_os"`；资源大的用 `make buildbottest`

## 内核约定
- 值都是 `PyObject*`：`ob_refcnt` + `ob_type`。所有权写清；`Py_NewRef` / `Py_XDECREF`
- 失败返回 `NULL` 或 `-1` 且已设异常。GIL 下跑字节码；阻塞 I/O 用 `Py_BEGIN_ALLOW_THREADS`
- 新模块优先 Limited API（`Py_LIMITED_API`）+ 堆类型；不要碰 internal 头
- 导出函数用 Argument Clinic（`Tools/clinic`）或 `METH_FASTCALL | METH_KEYWORDS`
- 加纯 Python stdlib：`Lib/foo.py` + `Lib/test/test_foo.py` + `Doc/` + `Misc/NEWS.d`
- 加 C 模块：`Modules/` + 构建配置 + 测试 + 文档。语法/语言行为先走 PEP

## 同组织仓库（按需打开，勿整库融合）
- PEP：https://github.com/python/peps
- 开发流程：https://github.com/python/devguide
- 类型桩 / 检查器：https://github.com/python/typeshed 、https://github.com/python/mypy
- 不要编造未合并的 PEP 号或内部符号；不确定就对照当前 `main` 与 DevGuide
""",
    ),
    "comfyui": (
        "ComfyUI：节点图扩散后端，用 HTTP API 跑工作流，不当聊天模型",
        "Comfy,ComfyUI,工作流,节点,扩散,文生图,文生视频,8188",
        "https://github.com/Comfy-Org/ComfyUI",
        """# ComfyUI
来源：https://github.com/Comfy-Org/ComfyUI （文档 https://docs.comfy.org/ ，模板 https://comfy.org/workflows）
本机/局域网节点图引擎：文生图、图生图、视频、3D、音频。**不是对话 LLM**，不要拿它当 chat completions。
出图、跑工作流时自己调用工具 `comfy`（status / queue / interrupt），不要让用户去点 Queue。
不要把整个 ComfyUI 仓库拷进本软件。

## 本机准备
- 桌面版：https://www.comfy.org/download （Windows / macOS）
- 便携版：`python main.py --listen 0.0.0.0 --port 8188`（只要 `--auto-launch` 则只绑 127.0.0.1，局域网检测不到）
- 打开 `http://127.0.0.1:8188`。SD 权重放 `models/checkpoints`
- MiniMax-H3 等 GGUF：放 `models/diffusion_models` + `models/vae`，并安装 `city96/ComfyUI-GGUF`。内置 UNETLoader 看不到 .gguf，要用 `Unet Loader (GGUF)`
- 视频运营页也可填同一地址。自检：`comfy` action=`status`

## 怎么跑
- 只吃 **API Format** JSON：Comfy 菜单 Save (API Format)。不要手写一张新图，除非用户明确要
- `comfy` action=`queue`，`workflow_path` 指向该 JSON；`prompt` 会写入第一个正向 CLIPTextEncode
- 成片也可 `video_generate` `provider=comfy` + `workflow_path`，写入 `02-generate/`
- 协议：`POST /prompt` → `GET /history/{id}` → `GET /view`；取消 `POST /interrupt`
- 云端海螺/Kimi 用 video_generate 的 minimax/kimi，不要塞进 Comfy 图
- 缺显卡/权重/工作流就说明怎么装，不要假装已经出图
""",
    ),
    "impeccable-craft": (
        "前端做到出品级：先定世界观再改界面，禁止套模板脸",
        "设计,界面,前端,UI,UX,视觉,落地页,dashboard",
        "https://github.com/pbakaus/impeccable",
        """# Impeccable 出品级前端
来源思想：pbakaus/impeccable。做网站、后台、组件、空状态时启用。

- 先问清用户、品牌、要避开的审美；有 PRODUCT.md / DESIGN.md 就遵守，没有就先写短 brief 再动代码
- 精修保留身份；重做替换视觉世界，禁止把旧脸打磨成新脸
- 命令语汇：shape / critique / audit / polish / bolder / quieter / distill / harden / animate / typeset / layout
- 禁止：紫色渐变套餐、Inter+卡片阴影、假数据英雄区、无层次的灰字、为动而动
- 一次做完再验收：启动本地预览后，用 browser 工具 navigate 打开页面，桌面+移动视口各看一遍；缺陷一批改，最多再确认一轮。禁止只交文字不展示。
- 非 UI 任务不要套本技能
""",
    ),
    "anime-js": (
        "Anime.js v4：网页时间线、交错、SVG 描边与路径，按命名导入不要用全局 anime",
        "anime,animejs,anime.js,动画,动效,时间线,stagger,SVG,描边",
        "https://github.com/juliangarnier/anime",
        """# Anime.js
来源思想：juliangarnier/anime（v4）。中文文档入口 https://animejs.cn/documentation/
做网页/SVG/DOM 属性动画、入场交错、路径运动时启用。装包：`npm i animejs`。

- 只写 v4：`import { animate, createTimeline, stagger, createSpring, svg, utils } from 'animejs'`
- 禁止 `import anime from 'animejs'`、禁止 `targets:`；写成 `animate('.box', { x: 100, duration: 800, ease: 'outQuad' })`
- 属性关键帧用 `to`：`opacity: [{ to: 0 }, { to: 1 }]`；缓动名去掉 ease 前缀（`easeOutQuad` → `outQuad`）
- 时间线：`createTimeline({ defaults: { duration: 600, ease: 'outQuad' } }).add(sel, props, position)`
  位置：`'<'` 跟上一段同时、`'>'` 接在后面、`+=100` / `-=50`
- 交错：`delay: stagger(80, { from: 'center', grid: [5, 5] })`；`reversed` 代替旧 direction
- SVG：`animate(svg.createDrawable('path'), { draw: '0 1' })`；路径运动用 `svg.createMotionPath`；变形用 `svg.morphTo`
- 弹簧：`ease: createSpring({ mass: 1, stiffness: 80, damping: 10 })`
- 回调一律 `on` 前缀：`onBegin` / `onUpdate` / `onComplete` / `onLoop`；收尾用 `.then()`
- 控制：`.play()` 向前、`.resume()` 按原方向继续、`.reverse()` 向后；`utils.set` / `utils.get` / `utils.remove`
- 尊重 `prefers-reduced-motion`：减弱或瞬间到位。不要为装饰挡住点击，不要用 v3 全局 `anime()`
- 纯 React 花活组件可叠 react-bits；本技能管时间轴与补间，不替代出品级视觉（impeccable-craft）
""",
    ),
    "react-bits": (
        "React 动效与花活组件：用现成 Bits 思路，不重造轮子",
        "React,动画,动效,组件,bits,交互",
        "https://github.com/DavidHDev/react-bits",
        """# React Bits
来源思想：DavidHDev/react-bits。做 React 展示型动效、文字特效、背景、卡片入场时启用。

- 先复用常见模式：split text、blur-in、spotlight card、grid scan、magnetic button，再自写
- 动效服务信息：可关、尊重 prefers-reduced-motion，不要挡住点击
- 性能：避免每帧大面积 box-shadow / filter；列表用 transform/opacity
- 不要为了炫把表单和后台表格做成演示站
""",
    ),
    "karpathy-craft": (
        "卡帕西风格：从第一性原理、最小可运行代码讲清楚",
        "Karpathy,从零,原理,nanoGPT,教学,实现",
        "https://github.com/karpathy",
        """# Karpathy 工艺
来源思想：Andrej Karpathy 公开教学与从零实现（nanoGPT / llm.c 等）。讲模型、训练、系统时启用。

- 先画数据怎么流过，再写代码；禁止先丢框架名
- 一个文件跑通，再拆模块；数字（shape、loss、token）必须对得上
- 用最小例子证明直觉：10 行能说清就不写 200 行
- 承认不知道的边界，不编造论文结论
""",
    ),
    "humanizer-zh": (
        "把生硬中文改成像人写的：有细节、有立场、少套话",
        "人性化,改写,润色,人味,humanizer",
        "https://github.com/Show-Chan97/Humanizer-zh",
        """# Humanizer-zh
来源思想：Show-Chan97/Humanizer-zh。改中文稿、去翻译腔时启用。

- 删开场「在当今…时代」、结尾「让我们一起…」
- 用具体名词和动作：谁、做了什么、结果如何
- 允许不完整句、口头转折、一次只推进一个点
- 保留作者原意；不编造经历。公文/合同/试卷不要人话化
""",
    ),
    "shuorenhua": (
        "说人话：把术语翻译成听得懂的大白话，但不装外行",
        "说人话,白话,解释,通俗,外行",
        "https://github.com/MrGeDiao/shuorenhua",
        """# 说人话
来源思想：MrGeDiao/shuorenhua。给非专家解释技术、配置、报错时启用。

- 先讲「这是在干什么」，再讲名词
- 一个比喻最多用一次，比喻必须对应机制
- 下一步给可执行动作，不给心灵鸡汤
- 专家读者写精确版，不要硬白话
""",
    ),
    "aigc-detect": (
        "识别中文 AIGC 痕迹：套话、排比、空主语、假金句",
        "检测,AIGC,AI味,鉴伪,机翻",
        "https://github.com/YuchuanTian/AIGC_text_detector",
        """# AIGC 痕迹检测
来源思想：YuchuanTian/AIGC_text_detector。审稿、查重味、判断「像不像AI」时启用。

- 高风险信号：三段排比、抽象主语（「其核心在于」）、价值判断饱和、无出处数据
- 输出：嫌疑点 + 原文摘句 + 建议改法；不要扣「百分百 AI」帽子
- 学术被动语态、法律名词化不是罪证
- 需要模型分数时说明这是启发式，不是实验室检测器
""",
    ),
    "stop-slop-zh": (
        "消除中文 AI slop：禁套话、拆三件套、五维打分",
        "slop,AI味,去AI,套话,排比",
        "https://github.com/VincentOld/stop-slop-zh",
        """# Stop Slop 中文
来源思想：VincentOld/stop-slop-zh。写完再改，不要边写边查。

禁：在当今/赋能/闭环/抓手/打造/不仅是…更是…/既要…又要…/意义深远
拆：排比三件套、名词化动词、空主语、金句收尾、总分总八股
五维（直/实/变/散/真，各 1–10）：低于 35/50 重写；像人写至少 42
公文党政、合同、论文方法节保守用。先写完再套本技能。
""",
    ),
    "nuwa-distill": (
        "女娲蒸馏：把人物/主题收成可运行的思维操作系统",
        "蒸馏,女娲,人物,心智,乔布斯,导师",
        "https://github.com/alchaincyf/nuwa-skill",
        """# 女娲蒸馏
来源思想：alchaincyf/nuwa-skill。用户要「按某某的方式想/写」时启用。

产出一份 SKILL.md，只抓 HOW they think：
- 3–7 个心智模型、5–10 条 if-then 启发式
- 表达 DNA（节奏、用词、嘲讽度）
- 反模式 + 诚实边界（没说过的题要表示不确定）
禁止：传记复读、编造语录。有一手材料优先于网页二手摘要。
""",
    ),
    "taste-craft": (
        "品味技能：先定审美立场，再改字号间距颜色，拒绝平庸默认",
        "品味,taste,审美,字体,间距,配色",
        "https://github.com/Leonxlnx/taste-skill",
        """# Taste
来源思想：Leonxlnx/taste-skill。用户嫌「看起来像模板」时启用。

- 先选一个明确世界（印刷、终端、画廊、工具机…），写 3 条禁令
- 字号/行高/字重先于颜色；留白是结构不是空
- 一种强调色，一种危险色；灰阶先够用再上彩
- 改完用一句话解释「为什么这样更有品味」，禁止「更现代」
""",
    ),
    "chinese-style": (
        "中文技术文档体例：用词一致、标题层级、中英混排",
        "体例,文档,中文,术语,style guide",
        "https://github.com/RightCapitalHQ/chinese-style-guide",
        """# 中文技术体例
来源思想：RightCapitalHQ/chinese-style-guide。写 README、接口文档、changelog 时启用。

- 中文用全角标点，代码/路径/API 用半角
- 专名第一次出现给英文，后文固定一个译名
- 标题像目录不是句子；一步一个祈使句
- 不要「进行…操作」，写成「打开 / 删除 / 重启」
""",
    ),
    "ui-ux-pro": (
        "UI/UX 专业清单：层级、状态、无障碍、移动端一手检查",
        "UX,无障碍,a11y,表单,状态,移动端",
        "https://github.com/nextlevelbuilder/ui-ux-pro-max-skill",
        """# UI/UX Pro
来源思想：nextlevelbuilder/ui-ux-pro-max-skill。评审或补齐产品界面时启用。

必查：焦点顺序、对比度、错误文案、加载/空/满/失败四态、触控热区、键盘可达
信息架构：一屏一个主行动；次要入口降权；破坏性操作二次确认
不要只截一张快乐路径图就说做完了
""",
    ),
    "agent-style": (
        "Agent 输出风格：短、可执行、先结论，少表演",
        "agent,风格,简洁,结论,口吻",
        "https://github.com/yzhao062/agent-style",
        """# Agent Style
来源思想：yzhao062/agent-style。默认对话口吻（除非用户要长文或教学）。

- 先给结论或补丁位置，再补必要依据
- 不列假选项、不自我夸奖、不写「作为AI」
- 代码改动说清文件与行为变化；没有跑过的测试如实写
""",
    ),
    "aiwritex": (
        "中文长文生产线：选题、提纲、素材、成稿、平台适配",
        "写作,公众号,长文,选题,提纲",
        "https://github.com/iniwap/AIWriteX",
        """# AIWriteX 流程
来源思想：iniwap/AIWriteX。做专栏、公众号、系列文章时启用。

顺序：选题（读者+冲突）→ 提纲（每节一个承诺）→ 素材（引用来源）→ 成稿 → 用 stop-slop-zh 洗一遍 → 按平台改标题/开头
禁止一次生成「完美万字」却无出处。缺事实就停，标「待核」
""",
    ),
    "research-overnight": (
        "通宵无人值守研究：计划、分批跑、写日志、早上接得上",
        "通宵,值守,过夜,自动研究,sleep",
        "https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep",
        """# 通宵研究
来源思想：wanshuiyin/Auto-claude-code-research-in-sleep。用户要挂机调研/实验时启用。

- 开工前写 run.md：目标、预算、停止条件、禁止操作
- 每步写日志（时间、命令、结果、下一步）；失败可复现
- 不交互假设：缺密钥就停，不要猜生产数据
- 早上先读日志摘要，再决定是否继续
""",
    ),
    "research-skills": (
        "AI 研究技能：拆问题、搜证据、对照实验、写可检验结论",
        "研究,调研,文献,实验,证据",
        "https://github.com/Orchestra-Research/AI-research-SKILLs",
        """# 研究技能
来源思想：Orchestra-Research/AI-research-SKILLs。开放调研与实验设计时启用。

- 问题写成可证伪一句；列出已知/未知
- 证据分级：论文/官方文档 > 博客 > 模型回忆
- 对比至少一种基线；记录失败也算结果
- 结论用「在…条件下观察到…」，禁止「业界最佳」
""",
    ),
    "mobile-app-ui": (
        "手机 App 界面：60/30/10、8pt 网格、拇指热区、Peak-End",
        "手机App,移动端,拇指热区,8pt,60/30/10,iOS,Android,健身App",
        "https://github.com/ceorkm/mobile-app-ui-design",
        """# 手机 App 界面
来源思想：ceorkm/mobile-app-ui-design（skills.yangsir.net/skill/gh-mobile-app-ui-design）。
做原生感手机界面、改组件层级、对标 Airbnb/Spotify 时启用。网页落地页走 impeccable-craft。

- 60/30/10：主色约 60%、辅色 30%、强调色 10%；先定语义色再铺组件
- 8pt 网格：间距/圆角/字号对齐 8 的倍数；触控目标 ≥44pt
- 拇指热区：主操作放屏幕下半；返回/次要放上沿或边缘
- Peak-End：关键成功瞬间与结束态单独设计，不要平均铺满装饰
- 先信息架构与状态（空/加载/错/成功），再动效
""",
    ),
    "wechat-miniprogram": (
        "微信小程序全流程：需求、原型、AppID、开发、体验版、提审、发布",
        "微信小程序,小程序,AppID,提审,体验版,project.config,wxml,wxss",
        "https://github.com/niuhuoshan/launch-wechat-miniprogram",
        """# 微信小程序
来源思想：niuhuoshan/launch-wechat-miniprogram；官方示例 wechat-miniprogram/miniprogram-demo；
工程习惯 Sun-sunshine06/miniprogram-skills。做小程序或仓库里已有 app.json + project.config.json 时启用。

流程（按用户进度，不要一次全做）：
1. 需求与页面清单；原生组件优先，少套无关 UI 框架
2. 注册 AppID、类目、隐私与备案（用户自己在公众平台完成）
3. 脚手架对齐：app.json 页面路由、tabBar、sitemap；project.config.json 的 appid
4. 开发：WXML/WXSS/JS；组件与 API 对照官方 demo，不要把整个 demo 仓库拷进工程
5. 开发者工具编译、真机预览、体验版；再提审发布

卡住时：
- 开发者工具打不开/编译失败：先核对基础库、appid、合法域名，再清缓存重编译
- CLI / 自动化端口：对齐 weapp-agent-mcp
- 改完后做一次界面巡检：主路径、空态、授权弹窗、tab 切换
- 文案：短、按钮动词明确，去掉套话
不要把 AppSecret、支付密钥写进仓库或对话。
""",
    ),
    "weapp-agent-mcp": (
        "微信开发者工具 MCP：截图、点击、健康检查，需本机工具与 npx",
        "微信开发者工具,小程序调试,mp_screenshot,element_tap,weapp-agent",
        "https://github.com/Chaixueyuan/weapp-agent-mcp",
        """# weapp-agent-mcp
来源：Chaixueyuan/weapp-agent-mcp（npm @chaixueyuan/weapp-agent-mcp；目录 myagenthub.cn）。
要在已打开的微信开发者工具里点页面、截图、巡检时启用。不要把 MCP 工具再包一层 Python。

前置：本机已装 Node.js；微信开发者工具已开项目，并打开「服务端口」/自动化调试。
默认 WebSocket：WEAPP_WS_ENDPOINT=ws://localhost:9420
启动：npx -y @chaixueyuan/weapp-agent-mcp
软件预设：codeagent.mcp.presets.weapp_agent_mcp()；或 mcp.json 里挂同名 stdio 服务。

常用能力（名称以实际 MCP 列表为准）：mp_healthCheck、mp_screenshot、element_tap。
先 healthCheck，再截图定位，再点；失败就停并报告端口/项目是否连上。
""",
    ),
    "m3e-canvas": (
        "Material 3 Expressive 画布：浏览器里画草图，导出实现提示词",
        "Material 3,M3E,m3e-canvas,Material You,Expressive",
        "https://github.com/lnkiai/m3e-canvas",
        """# m3e-canvas
来源：lnkiai/m3e-canvas。用户要 Material 3 Expressive 草图或导出 vibe-coding 提示词时启用。
不要把画布应用拷进本仓库。用内置 browser 打开：
https://lnkiai.github.io/m3e-canvas/
画完导出提示词，再按提示词改工程。网页营销页仍走 impeccable-craft；手机 App 叠 mobile-app-ui。
""",
    ),
    "paper-spine": (
        "论文脊柱：题目、贡献、相关工作、实验表，一条脊梁贯穿",
        "论文,投稿,贡献,相关工作,实验",
        "https://github.com/WUBING2023/PaperSpine",
        """# PaperSpine
来源思想：WUBING2023/PaperSpine。开题、改投稿结构时启用。

- 一句话贡献，全文只服务这一句
- 相关工作按「差距」分组，不是论文清单
- 实验表：问题 → 指标 → 对照 → 消融；每张图一个论点
- 摘要最后写限制。不编造引用
""",
    ),
    "paper-craft": (
        "论文工艺：章节骨架、图表、审稿意见逐条回",
        "论文,写作,审稿,图表,latex",
        "https://github.com/zsyggg/paper-craft-skills",
        """# Paper Craft
来源思想：zsyggg/paper-craft-skills。写章节、改 LaTeX、回审稿时启用。

- IMRaD 清楚：方法可复现，实验可对照
- 图题自洽；轴、单位、图例齐全
- 回审：逐条引用意见编号，同意就改，不同意给证据
- 中文稿仍遵守学术规范，不要用 slop 技能拆被动语态
""",
    ),
    "jianying-editor": (
        "剪映专业版自动化：素材、TTS、字幕、配乐、特效、录屏变焦与导出",
        "剪映,jianying,JyProject,自动化剪辑,字幕对齐,云端音乐,智能变焦,草稿导出",
        "https://github.com/isYangs/jianying-editor-skill",
        """# jianying-editor（剪映 AI 自动化剪辑）
来源：https://github.com/isYangs/jianying-editor-skill （v1.0.0）。
用户要用剪映专业版做草稿、配音字幕、配乐特效、录屏智能变焦、自动导出时启用。
自己调用 use_skill("jianying-editor")。不要把整仓拷进本软件仓库根；业务脚本写在当前项目目录。

## 能力边界
- 素材导入、AI 配音、字幕拆句对齐、本地/云端配乐、特效/转场/滤镜检索
- 录屏 + 智能变焦；HTML/JS/Canvas 动效录成视频素材；导出 MP4（1080P~4K）
- Windows 完整支持自动导出；macOS 可用（自动导出可能需 Windows Agent）
- 依赖：Python 3.8+、ffmpeg、剪映专业版（自动导出建议 ≤5.9）

## CodeCoreAgent 落地
- 征得用户同意后安装到工作区 skills：
  `git clone https://github.com/isYangs/jianying-editor-skill.git skills/jianying-editor`
  再 `pip install -r skills/jianying-editor/requirements.txt`
- 设环境变量 `JY_SKILL_ROOT` 指向该目录；脚本里用 `jy_wrapper.JyProject`
- **禁止**在 skill 安装目录里写业务剪辑脚本；放项目根或 `scripts/`
- 简单演示可用默认音乐；正式片优先检索 `data/cloud_music_library.csv` 并问用户选曲
- 草稿检查：`python $JY_SKILL_ROOT/scripts/draft_inspector.py list --limit 20`
- 资产搜索：`python $JY_SKILL_ROOT/scripts/asset_search.py "复古" -c filters`
- 导出：`python $JY_SKILL_ROOT/scripts/auto_exporter.py "DraftName" "out.mp4" --res 1080`
- 读 playbook：`docs/agent-playbook.md`、`docs/minimal-command-sop.md` 再动手
- 与导演台 / video_studio / Comfy / HyperFrames 分工：剪映时间线与导出走本技能；
  HTML 确定性成片走 hyperframes；镜头生成合成走导演台

## 铁律
- 缺剪映/ffmpeg/JY_SKILL_ROOT 就说明怎么装，不要假装已经导出成功
- 克隆模板用 wrapper `clone --template`，勿直接改坏原模板
""",
    ),
    "hyperframes": (
        "HTML 写成片：HyperFrames 组合、预览、确定性渲染 MP4（面向 Agent）",
        "HyperFrames,hyperframes,HTML视频,产品发布片,PR解说,motion graphics,frame.md,无旁白短片",
        "https://github.com/heygen-com/hyperframes",
        """# HyperFrames
来源：https://github.com/heygen-com/hyperframes （HeyGen 开源，Apache 2.0）。
用 HTML/CSS + 可 seek 动画写成片；Agent 友好。做产品发布片、无脸解说、PR 解说、
字幕叠轨、talking-head 包装、短 motion、音乐卡点、slideshow、通用多镜片时启用。
自己调用 use_skill("hyperframes")。不要整仓 LFS 拷进本软件；按需 init 项目。

## 快速环
- Node.js 22+、FFmpeg；Agent 安装核心技能：`npx hyperframes skills update`
  （交互可用 `npx skills add heygen-com/hyperframes`；非交互勿盲装全部 20 个）
- 脚手架：`npx hyperframes init my-video` → `npx hyperframes preview` → `npx hyperframes render`
- 先读路由技能 `/hyperframes`，再按意图进 creation workflow（product-launch-video、
  faceless-explainer、pr-to-video、embedded-captions、talking-head-recut、
  motion-graphics、music-to-video、slideshow、general-video、remotion-to-hyperframes）
- 组合契约：`data-start` / `data-duration` / `data-track-index`、`class="clip"`；
  动画用 GSAP/CSS/Lottie/Three/Anime.js/WAAPI 等 **seekable** adapter；
  挂到 `window.__timelines.<compositionId>`
- 目录块：`npx hyperframes add <block>`；设计系统用 `frame.md`（DESIGN.md 超集）
- 文档：https://hyperframes.heygen.com/introduction ；展示 https://hyperframes.heygen.com/showcase

## 与本软件分工
- Remotion React 片 → remotion-video / 或 `/remotion-to-hyperframes` 迁移到 HTML
- 剪映时间线 → jianying-editor；Comfy/WAN 镜头 → 导演台 video_studio
- 预览可用内置 browser 打开本地 preview URL（禁止 file:// 成品路径）

## 铁律
- 缺 Node/ffmpeg 就说明怎么装；渲染失败先 `npx hyperframes doctor` / lint
- 同一输入应对齐同一帧；不要用墙钟动画冒充可 seek
- 不要默认 `skills add --all`；保持 core + 按需 workflow
""",
    ),
    "next-ai-draw-io": (
        "自然语言画 draw.io：架构图/流程图，MCP 实时出图",
        "draw.io,drawio,架构图,流程图,时序图,next-ai-draw-io,diagram,MCP画图",
        "https://github.com/DayuanJiang/next-ai-draw-io",
        """# next-ai-draw-io
来源：https://github.com/DayuanJiang/next-ai-draw-io （Apache 2.0）。
用自然语言创建/改 draw.io 图（云架构、流程图、动画连线、读图复刻）时启用。
自己调用 use_skill("next-ai-draw-io")。不要把整仓 Next 应用塞进用户业务仓库，除非用户要自建。

## CodeCoreAgent 优先路径（MCP）
- 预设：`codeagent.mcp.presets.drawio_mcp()` → `npx @next-ai-drawio/mcp-server@latest`
- mcp.json 示例：
  `{"mcpServers":{"drawio":{"command":"npx","args":["@next-ai-drawio/mcp-server@latest"]}}}`
- 连上后让模型画图；浏览器里实时出现画布。先确认 MCP 已挂，再下复杂图指令。

## 其它入口
- 在线演示：https://next-ai-drawio.jiang.jp/ （可用内置 browser 打开；自备 API Key 可在设置里填）
- 自建：`git clone … && npm install && cp env.example .env.local && npm run dev` → :6002
- Docker / Vercel / EdgeOne / Cloudflare 见上游 docs；桌面版见 Releases
- 模型要强：长 XML + 严格格式；云架构 logo 图优先 Claude 系

## 铁律
- 图是 draw.io XML；改图用增量对话，保留历史版本意识
- 缺 Node/MCP 就说明怎么装，不要假装图已经生成
- 纯 UI 落地页仍走 impeccable-craft；本技能只管示意图/架构图
""",
    ),
    "autocad-dwg-redraw": (
        "AutoCAD DWG 精确重绘：源 DWG / PDF 中间稿剖析、COM 复刻与校验",
        "AutoCAD,DWG,DXF,重绘,图纸,CAD,精确复刻,PDF转DWG,pywin32,dwg_redraw",
        "https://github.com/pengxiaoan/autocad-dwg-redraw-skill",
        """# autocad-dwg-redraw
来源：https://github.com/pengxiaoan/autocad-dwg-redraw-skill （skills/autocad-dwg-redraw）。
有源 DWG、或 PDF 转可审计中间 DWG 后再精确复刻/校验时启用。
自己调用 use_skill("autocad-dwg-redraw")。不要把整仓拷进本软件根；脚本装到工作区 skills。

## 环境（硬性）
- **Windows** + 已安装 AutoCAD + Python 3.10+ + `pywin32`
- macOS/Linux 无法跑 COM；缺环境就说明怎么装，不要假装已写出 DWG

## CodeCoreAgent 落地
征得同意后：
```
git clone https://github.com/pengxiaoan/autocad-dwg-redraw-skill.git skills/autocad-dwg-redraw-skill
pip install pywin32
```
设 `ACAD_SKILL_ROOT` 指向 `skills/autocad-dwg-redraw-skill/skills/autocad-dwg-redraw`。
业务输出写项目 `outputs/` / `reports/`，**禁止覆盖源 DWG**。

## 三种输入
1. **源 DWG**：剖析 → 自定义重绘提示 → COM 精确复刻 → 对照实体/图层/标注校验
2. **仅 PDF**：先做可审计中间 DWG（矢量优先；栅格须标明限制），再走源 DWG 流程；**勿声称等于原 DWG**
3. **图 + 权威尺寸表**：尺寸优先于像素；冲突跟尺寸并报告差异（复杂图转走 autocad-image-redraw）

## 常用命令（在 ACAD_SKILL_ROOT）
```
python scripts/dwg_prompt_builder.py --source input.dwg --output input-redraw-prompt.md
python scripts/dwg_redraw.py --source input.dwg --output outputs/redraw_exact.dwg
```
COM 卡住 / 只开 Start 页时加：`--restart-autocad --acad-exe "C:\\Path\\To\\acad.exe"`。
只要模型空间：`--modelspace-only`。

## 铁律
- 有源 DWG 时禁止只靠截图「猜」复杂图；先提实体再校验
- 最终交付优先 AutoCAD COM 精确拷贝；生成 AutoLISP/Python 仅当用户要可审计代码且已抽出实体数据
- 教程：仓库 `docs/图片自动绘制DWG使用教程.md`（图转 DWG 细节见 autocad-image-redraw）
""",
    ),
    "autocad-image-redraw": (
        "光栅图纸转可编辑 DWG/DXF：预检、证据分级、规格校验、对比与迭代",
        "图纸照片,扫描件,截图转DWG,image-redraw,光栅,DXF预览,证据分级,CAD重绘",
        "https://github.com/pengxiaoan/autocad-dwg-redraw-skill",
        """# autocad-image-redraw
来源：https://github.com/pengxiaoan/autocad-dwg-redraw-skill （skills/autocad-image-redraw）。
截图、扫描、照片、草图、PNG/JPG 要转成可编辑 DWG/DXF，且需证据跟踪与校验时启用。
有可信源 DWG 时改用 autocad-dwg-redraw。自己调用 use_skill("autocad-image-redraw")。

## 环境
- DWG 生成/检查：Windows + AutoCAD + `pywin32`
- 预检/对比：`pillow numpy opencv-python`；DXF 预览：`ezdxf pymupdf`
```
pip install pywin32 pillow numpy opencv-python ezdxf pymupdf
```
克隆同上仓；`ACAD_IMG_SKILL_ROOT` → `…/skills/autocad-image-redraw`。

## 证据与剖面（不可妥协）
- 几何权威顺序：用户明文要求 → 可读尺寸 → 推导约束 → 标定测距 → **标明的**目测估计
- 每个关键值标 `known` / `scaled` / `inferred` / `unreadable`
- **禁止**仅凭像素相似度声称物理尺寸准确；冲突尺寸勿静默择一，应 `needs_review` / `blocked`
- 剖面：`strict-dimensioned` | `general`（默认）| `hybrid` | `visual-trace` | `geometry-only`
  无单位/比例锚时用 `visual-trace` 或 unitless，勿默认毫米

## 端到端（在 ACAD_IMG_SKILL_ROOT）
1. `python scripts/preflight_image_redraw.py --image input.jpg --mode general --output reports/preflight.json`
2. 按 `references/image-redraw-spec.md` 写规格（视图、标定、约束、实体 ID）
3. `python scripts/validate_image_redraw_spec.py --spec redraw-spec.json --profile general --report reports/spec.json`
4. `python scripts/draw_image_spec.py --spec redraw-spec.json --output outputs/redraw.dwg`
   中文可用 `--text-style CN_TEXT --text-font "C:\\Windows\\Fonts\\simhei.ttf"`；只要线框 `--geometry-only`
5. `inspect_dwg_output.py` → AutoCAD 导出 DXF → `render_dxf_preview.py` → `compare_redraw.py`
6. 处置：`pass` / `pass_with_warnings` / `needs_review` / `blocked` / `fail`

无 AutoCAD 时仅可粗略：`image_to_dxf_open_source.py`；矢量 PDF：`pdf_vector_to_dxf.py`——二者都不能把不确定像素变成权威尺寸。

## 交付
可编辑 DWG + 审计 DXF、规格/锚点 JSON、预检与对比报告、固定页预览、manifest（哈希、剖面、单位、假设、状态）。
""",
    ),
    "dbx": (
        "轻量数据库客户端 DBX：90+ 库、SQL、桌面/Docker，Agent 经 MCP/CLI 查库",
        "DBX,dbx,数据库客户端,SQL,MySQL,PostgreSQL,SQLite,Redis,MongoDB,达梦,MCP数据库,查库",
        "https://github.com/t8y2/dbx",
        """# dbx（DBX 数据库客户端）
来源：https://github.com/t8y2/dbx （Apache-2.0，~20MB Tauri 客户端）。
连 MySQL/PostgreSQL/SQLite/Redis/MongoDB/达梦等、写 SQL、看表结构、给 Agent 查库时启用。
自己调用 use_skill("dbx")。不要把整仓 Rust/Vue 拷进本软件；连接与策略在本机 DBX 里配。

## CodeCoreAgent 优先路径（MCP）
- 预设：`codeagent.mcp.presets.dbx_mcp()` → `npx -y @dbx-app/mcp-server`
- mcp.json：
  `{"mcpServers":{"dbx":{"command":"npx","args":["-y","@dbx-app/mcp-server"]}}}`
- **先**在本机安装并打开 DBX，配好连接；再在 DBX「设置 → MCP」设允许的连接与权限
  （`read_only` / `safe_write` / `high_risk_write`）。未装桌面时 MCP 无法用你的连接配置。
- 能力（以实际工具列表为准）：列连接、浏览表、执行 SQL、在 DBX UI 打开表。
- Docker/Web 部署时 MCP 可指后端：环境变量 `DBX_WEB_URL`（如 `http://localhost:4224`）、
  若有登录密码再设 `DBX_WEB_PASSWORD`。Windows 便携版需 `DBX_DATA_DIR` 指向 `DBX.exe` 旁的 `data/`。

## 本机安装（征得同意）
- macOS：`brew install --cask dbx`；Windows：`winget install t8y2.dbx` 或 Scoop；
  或从 https://github.com/t8y2/dbx/releases 下安装包
- Docker Web：`docker run -d --name dbx -p 4224:4224 -v dbx-data:/app/data t8y2/dbx:latest`
  （国内可试 `docker.cnb.cool/dbxio.com/dbx:latest`）→ http://localhost:4224
- CLI：`npm i -g @dbx-app/cli` 或 `brew tap t8y2/tap && brew install dbx-cli`
  → `dbx connections list --json` / `dbx query <连接名> "select 1" --json`
- 文档：https://dbxio.com/en/docs/what-is-dbx

## 与 Limbas / 裸驱动
- 低代码业务前台、表单/流程应用 → limbas（PHP 框架，不是客户端）
- 仅写应用代码连库：用项目语言官方驱动；DBX 负责可视化与 Agent 安全查库
- 不要把 DB 密码写进对话或仓库；破坏性 SQL 先确认权限模式

## 铁律
- 缺 Node/DBX 就说明怎么装，不要假装已连上库或已执行 SQL
- 默认倾向只读；写库须用户明确要求且 MCP 权限允许
- 大结果集导出用 DBX 网格/导出，不要把整表贴进聊天
""",
    ),
    "limbas": (
        "Limbas 低代码数据库框架：表单/业务应用，Docker 或 Web 安装器部署",
        "Limbas,limbas,低代码,数据库框架,业务应用,表单,PHP低代码,openlimbas",
        "https://github.com/limbas/limbas",
        """# limbas（Limbas 低代码数据库框架）
来源：https://github.com/limbas/limbas （GPL-2.0）。
做基于数据库的业务前台、表单、少代码应用（PostgreSQL/MySQL/MSSQL/Oracle/MaxDB）时启用。
自己调用 use_skill("limbas")。不要把整仓 PHP 拷进 CodeCoreAgent 根目录；部署到独立服务器/Docker。

## 定位
- 图形化数据库前台 + 低代码应用框架（非轻量 SQL 客户端）
- 查库/写 SQL/Agent MCP → 用 dbx；本技能管 **业务应用搭建与部署**

## 环境
- Linux 服务器 + Apache + **PHP 8+** + PDO / unixODBC
- 支持库：PostgreSQL、MySQL、MSSQL、SAP MaxDB、Oracle
- 文档：https://limbas.org/ · 演示：https://www.limbas.com/en/Service___Support/Demoserver/

## 部署（征得同意后选一种）
1. **Docker（推荐试跑）**：见 https://github.com/limbas/limbas-docker
   （本仓也有 `docker-compose.yml`，可按上游说明 `docker compose up`）
2. **Web 安装器**：https://github.com/limbas/web-installer/releases
   —— 下载到空目录解压执行，会拉最新包并进入安装向导（需联网）
3. **发行包**：上传 `openlimbas_X.X.tar.gz` 解压，**域名根指向 `public/`**，
   浏览器打开按向导完成；默认账号见安装结束页（装完立刻改密）

## 更新
备份后替换 `limbas_src`、`vendor`、以及 `public/assets`。细节见上游 README。

## CodeCoreAgent 落地
- 在用户项目里写部署说明 / compose / 环境检查清单；用内置 browser 打开本机 Limbas URL 验收
- 表结构变更、复杂 SQL 可配合 dbx 技能做只读核对
- 缺 PHP/Docker/数据库就说明怎么装，不要假装应用已上线

## 铁律
- GPL-2.0：分发衍生作品注意许可义务
- 生产环境务必改默认口令、HTTPS、定期备份
- 不要把 Limbas 当嵌入式库塞进桌面安装包
""",
    ),
    "openviking": (
        "OpenViking 上下文库：分层 Memory/RAG/Skills；默认用本机 Wiki，可选 pip 服务",
        "OpenViking,openviking,viking://,上下文数据库,会话记忆,分层检索,L0,L1,L2,上下文编译",
        "https://github.com/volcengine/OpenViking",
        """# openviking（OpenViking 上下文数据库）
来源：https://github.com/volcengine/OpenViking （AGPL-3.0）。
做 Agent 长期上下文、分层检索、会话编译成记忆/Wiki 时启用。
自己调用 use_skill("openviking")。不要把整仓 / AGPL 服务默认打进安装包。

## CodeCoreAgent 默认（已内置）
- 安装与每次启动会 **自动部署** 本机 LLM Wiki（`~/Documents/CodeCoreAgent-Wiki`）
- Schema 已对齐 L0/L1/L2 分层与按需阅读（见知识库 `wiki/concepts/context-layers.md`）
- Agent 工具：`knowledge_search` / `knowledge_read` / `knowledge_ingest` — 先搜再读，勿整库灌上下文
- 文档：https://docs.openviking.ai/ · Studio：https://openviking.ai/studio

## 可选进阶（征得同意）
```
pip install openviking --upgrade
openviking-server init      # 配置 embedding + VLM
openviking-server doctor
```
需要 Python 3.10+ 与可用的嵌入模型 / VLM（云或本地）。自托管 Web Studio 见上游 `web-studio/`。
AGPL-3.0：分发衍生服务注意许可义务。

## 铁律
- 缺密钥/模型时说明怎么配，不要假装 viking:// 已连上
- 日常对话优先本机 Wiki；仅当用户明确要 OpenViking 服务时再装
""",
    ),
    "tencentdb-agent-memory": (
        "腾讯云 Agent Memory：团队记忆 Hub；默认映射本地四类资产，可选 Docker",
        "TencentDB,Agent Memory,Memory Hub,Chat Memory,Code-Graph,团队记忆,tencentdb-agent-memory",
        "https://github.com/TencentCloud/tencentdb-agent-memory",
        """# tencentdb-agent-memory
来源：https://github.com/TencentCloud/tencentdb-agent-memory （团队级记忆中枢）。
跨 Agent 复用对话记忆、Skill、Wiki、代码图谱时启用。
自己调用 use_skill("tencentdb-agent-memory")。不要把 MemoryCore/Hub/Proxy 多容器默认打进桌面包。

## CodeCoreAgent 默认（已内置）
- 本机知识库自动部署，四类资产映射见 `wiki/concepts/memory-assets.md`
  - Chat Memory → `raw/conversations/` + `wiki/entities/`
  - Skill → `wiki/concepts/` 或 `~/.codeagent/skills/`
  - LLM-Wiki → `wiki/projects/` / `wiki/syntheses/`
  - Code-Graph → 带 `[[wikilinks]]` 的概念/项目页
- 单机即可用；团队共享可把库路径改到 NAS / 网盘（知识库「跨电脑共享」）

## 可选进阶（征得同意）
```
git clone https://github.com/TencentCloud/tencentdb-agent-memory.git
cd tencentdb-agent-memory/deploy/global-images
cp .env.example .env   # 填 memory 组 + proxy 组 LLM
./start-all.sh         # memory-core + hub + proxy
```
面板默认 http://localhost:8125 ；完整步骤见上游 INSTALL.md / INSTALL_CN.md。
需要 Node ≥ 22.16；Mongo 后端为实验选项。

## 铁律
- 缺 Docker/LLM 配置就说明怎么装，不要假装 Hub 已运行
- 默认走本机 Wiki；用户要团队 Proxy 再部署上游栈
""",
    ),
    "harmony-next": (
        "鸿蒙 NEXT 离线知识路由：API12+ ArkTS/ArkUI/NDK；按 Kit 检索，勿整库灌上下文",
        "鸿蒙,HarmonyOS,HarmonyOS NEXT,harmony-next,ArkTS,ArkUI,NDK,API12,@ohos",
        "https://github.com/linhay/harmony-next.skills",
        """# harmony-next（HarmonyOS NEXT 知识路由）
来源：https://github.com/linhay/harmony-next.skills
做鸿蒙 / HarmonyOS NEXT（API 12+）API 查询、Kit 选型、兼容性核对时启用。
自己调用 use_skill("harmony-next")。不要把上游数千份 Markdown 整仓拷进本软件安装包。

## CodeCoreAgent 用法
- **默认**：按任务关键词路由到对应 Kit（ArkUI / ApplicationKit / NDK / JsEtsAPIReference）
- 需要本地全文库时：征得同意后 `git clone` 上游到用户目录，再用 `knowledge_ingest` / 项目文档引用；日常对话只摘相关片段
- 写 `.ets` / 修编译错误时叠用 `arkts-syntax-assistant`
- 要编译、装机、点 UI、抓 hilog 时叠用 `deveco-mcp`（MCP）

## 检索纪律（L0→L2）
1. 先定 Kit / 模块名与 API 级别（12–23）
2. 只打开与当前问题相关的少量参考页；禁止一次塞进整库
3. 给出可运行最小示例 + 版本/兼容性注意点

## 铁律
- 缺本机知识库时说明 clone 路径，不要假装已索引 4000+ 文档
- 不要用过时 API 9 文档回答 NEXT；版本不明时先问目标 API
""",
    ),
    "arkts-syntax-assistant": (
        "ArkTS 语法助手：.ets 规范、TS 迁移、状态/组件与编译错误修复",
        "ArkTS,arkts,.ets,@Component,@State,TypeScript迁移,鸿蒙语法,arkts-syntax-assistant",
        "https://github.com/SummerKaze/skill-arkts-syntax-assistant",
        """# arkts-syntax-assistant
来源：https://github.com/SummerKaze/skill-arkts-syntax-assistant
处理 `.ets`、ArkTS 关键字、TS→ArkTS 迁移、状态管理与编译错误时启用。
自己调用 use_skill("arkts-syntax-assistant")。

## 何时启用
- 编辑或生成 `.ets` 文件
- 出现 `@Component` / `@Entry` / `@State` / `@Prop` / `@Link` / `@Builder` 等
- TypeScript 迁移到 ArkTS、严格类型与结构化类型报错
- 组件性能、状态冗余、不必要的重渲染

## 工作流
1. 定位报错文件与行；说明 ArkTS 与 TS 差异（如无任意类型滥用、受限语法）
2. 给出最小可编译补丁；避免无关重构
3. API / Kit 细节 → `harmony-next`；装机构建 → `deveco-mcp`

## 铁律
- 不要把浏览器 DOM / React 习惯硬套进 ArkUI
- 缺 DevEco / hvigor 时说明环境，不要假装已编译通过
""",
    ),
    "deveco-mcp": (
        "DevEco MCP：不打开 Studio GUI 也能编译、装机、UI 操作与抓日志",
        "DevEco,deveco-mcp,deveco-toolbox,鸿蒙编译,HAP,hilog,hdc,UI树,HarmonyOS调试",
        "https://github.com/open-deveco/deveco-toolbox",
        """# deveco-mcp（DevEco Toolbox MCP）
来源：https://github.com/open-deveco/deveco-toolbox
在 CodeCoreAgent / Cursor / VS Code 等 AI IDE 里完成鸿蒙编译、安装、调试时启用。
自己调用 use_skill("deveco-mcp")。依赖本机已装 **DevEco Studio**（或等价命令行工具链），不要把 Toolbox 整仓打进桌面包。

## 闭环
开发代码 → MCP 编译 → 安装到模拟器/真机 → 取 UI 树 / 点击滑动 → hilog/faultlog → 改代码。

## 常用 MCP 能力（名称以本机 server 为准）
- 构建：`build_project`（intent / module / product）
- 运行：`start_app`（ability / module / device）
- UI：`get_app_ui_tree`、`perform_ui_action`（click / fling / input / screenshot）
- 日志：`get_hilog_or_faultlog_recent`
- 辅助：文档搜索、ETS 静态检查

## CodeCoreAgent 配置
使用预设 `codeagent.mcp.presets.deveco_mcp`，或手动：
```json
{
  "mcpServers": {
    "deveco-mcp": {
      "command": "npx",
      "args": ["-y", "deveco-mcp-server"],
      "env": {
        "PROJECT_PATH": "/绝对路径/鸿蒙工程",
        "DEVECO_PATH": "/Applications/DevEco-Studio.app/Contents"
      }
    }
  }
}
```
Windows 将 `DEVECO_PATH` 改为本机 Studio 安装目录。也可用上游 `deveco-toolbox` 可视化配置。

## 铁律
- 先确认本机能 `hvigor`/`hdc` 通，再让 AI 跑闭环
- 缺 Node / DevEco / 设备时说明怎么装，不要假装已装上 HAP
- ArkTS 语法问题叠 `arkts-syntax-assistant`；API 细节叠 `harmony-next`
""",
    ),
}


def fusion_library() -> SkillLibrary:
    lib = SkillLibrary()
    for name, (desc, _triggers, source, body) in FUSION_SKILLS.items():
        lib.add(Skill(
            name=name,
            description=desc,
            content=body,
            metadata={"source": source, "triggers": _triggers, "pack": "fusion"},
        ))
    return lib


def _fusion_pack_stamp() -> str:
    """Bump when FUSION_SKILLS content set changes (names + count)."""
    try:
        from codeagent import __version__
    except Exception:  # noqa: BLE001
        __version__ = "0"
    names = ",".join(sorted(FUSION_SKILLS))
    return f"{__version__}:{len(FUSION_SKILLS)}:{hash(names) & 0xFFFFFFFF:x}"


_fusion_ensured: set[str] = set()


def install_fusion_skills(directory: Path | None = None) -> list[str]:
    """Write fusion packs into ~/.codeagent/skills (overwrite same names)."""
    root = Path(directory or FUSION_DIR).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    lib = SkillLibrary()
    for name, (desc, triggers, source, body) in FUSION_SKILLS.items():
        skill = Skill(
            name=name,
            description=desc,
            content=body,
            metadata={"source": source, "triggers": triggers, "pack": "fusion"},
        )
        path = lib.save(skill, root)
        # persist extra frontmatter keys Skill.to_markdown omits
        path.write_text(
            "---\n"
            f"name: {name}\n"
            f"description: {desc}\n"
            f"source: {source}\n"
            f"triggers: {triggers}\n"
            "pack: fusion\n"
            "---\n\n"
            f"{body.strip()}\n",
            encoding="utf-8",
        )
        written.append(name)
    stamp = root / ".fusion-pack-version"
    try:
        stamp.write_text(_fusion_pack_stamp() + "\n", encoding="utf-8")
    except OSError:
        pass
    _fusion_ensured.add(str(root.resolve()) if root.exists() else str(root))
    return written


def ensure_fusion_skills(directory: Path | None = None) -> list[str]:
    """Install fusion pack if missing or outdated (once per process when current)."""
    root = Path(directory or FUSION_DIR).expanduser()
    try:
        key = str(root.resolve())
    except OSError:
        key = str(root)
    if key in _fusion_ensured:
        return []
    stamp = root / ".fusion-pack-version"
    want = _fusion_pack_stamp()
    try:
        if stamp.is_file() and stamp.read_text(encoding="utf-8").strip() == want:
            # quick sanity: at least router skill present
            if (root / "fusion-router" / "SKILL.md").is_file():
                _fusion_ensured.add(key)
                return []
    except OSError:
        pass
    return install_fusion_skills(root)
