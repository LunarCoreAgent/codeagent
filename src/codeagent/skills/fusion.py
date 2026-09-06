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
- 网页时间线、交错、SVG 描边/路径动画 → anime-js（必要时叠 react-bits）
- 中文要像人话、去 AI 味、改稿 → stop-slop-zh、humanizer-zh、shuorenhua、chinese-style
- 判断一段话像不像 AI 写的 → aigc-detect
- 长文、公众号、连载 → aiwritex
- 论文、开题、综述、投稿结构 → paper-spine、paper-craft
- 通宵无人值守调研 / 多步研究 → research-overnight、research-skills
- 蒸馏某个人的思维方式 → nuwa-distill
- 从零讲清模型/系统 → karpathy-craft
- 本地扩散工作流 / 节点图 / 文生图 / ComfyUI → comfyui，直接调用 comfy 工具；成片也可用 video_generate provider=comfy
- CPython 内核 / C API / GIL / 从源码编 Python / 给解释器加模块 → cpython（写普通 .py 应用不要套）
- 打开网页 / 登录站 / 点按钮 / 填表 / 操作已登录浏览器 → 直接调用 browser 工具；技能 browser-skill 或 ego-browser
- 语音面 / 麦克风 / 播报 / 嗲音 / barge-in → voice-surface
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
- CodeCoreAgent 桌面端：偏好设置「语音面」；打字提问同样播报回答
""",
    ),
    "browser-skill": (
        "BrowserSkill：用 bsk 驱动用户已登录的 Chrome/Edge，Agent 窗口不抢标签",
        "浏览器,BrowserSkill,bsk,打开网页,填表,点按钮,已登录",
        "https://github.com/Tencent/BrowserSkill/",
        """# BrowserSkill
来源：https://github.com/Tencent/BrowserSkill/
用本机 `bsk` CLI + 浏览器扩展，在独立 Agent 窗口操作**用户已登录**的 Chrome/Edge。
需要打开网页、点按钮、填表、读已登录页时：直接调用工具 `browser`，不要让用户去点，不要只用 web_fetch。
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
有 `ego-browser`、没有 `bsk` 时，`browser` 工具走这条后端。两者都有时优先 BrowserSkill。
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
- 源码：clone 后按 README 建 venv，`python main.py --listen 0.0.0.0 --port 8188`
- 打开 `http://127.0.0.1:8188`。权重放 `models/checkpoints`（或 extra_model_paths.yaml）
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
- 一次做完再验收：桌面+移动各看一遍，缺陷一批改，最多再确认一轮
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
    return written


def ensure_fusion_skills(directory: Path | None = None) -> list[str]:
    """Write the fusion pack the app ships (refresh on every launch)."""
    return install_fusion_skills(directory)
