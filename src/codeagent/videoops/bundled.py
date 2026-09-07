"""Bundled SKILL.md packs for video generation / publish / ops.

Workflows are distilled from public open-source projects (LibTV CLI,
Remotion skills, video-use-zh, short-drama, DeepAnalyze, auto-publish,
AutoPublish) into CodeCoreAgent-owned instruction packs. Do not paste
upstream repositories verbatim.
"""

from __future__ import annotations

BUNDLED_SKILLS: dict[str, tuple[str, str]] = {}


def _add(name: str, description: str, body: str) -> None:
    BUNDLED_SKILLS[name] = (description, body.strip() + "\n")


_add(
    "video-ops-pipeline",
    "视频生成发布运营总控：选题剧本→LibTV/Remotion生成→中文剪辑→运营分析→多平台发布草稿",
    """
# 视频生成发布运营（CodeCoreAgent）

用户提到短视频、短剧、分镜、成片、发布、运营数据时，按这条流水线推进，
工作区在「视频运营」页一键布置的目录（默认 `~/Documents/CodeCoreAgent-VideoOps`）。

## 阶段

1. **导演台** → 侧栏「导演台」（对话和指挥中心之间）：企划、分镜、Comfy/WAN 生成、ffmpeg 合成。工具 `video_studio`
2. **选题 / 剧本** → `01-script/`（技能 `short-drama-script`）
3. **生成** → `02-generate/`：局域网 Gradio WAN（工具 `video_generate`）优先；ComfyUI 节点图；否则 LibTV / Remotion
4. **剪辑** → `03-edit/`：竖屏 1080x1920、字幕、Ken Burns、成片自检
5. **运营分析** → `04-analyze/`：把播放/完播/互动表写成报告，再决定改脚本还是改封面
6. **发布** → `05-publish/draft.json`：填好多平台标题描述标签，**人工点发布**

## 硬规则

- 不代替用户登录平台，不保存平台密码，不自动点击「发布」。
- 每阶段产物写入对应文件夹，并在 `pipeline.md` 追加一行进度。
- 缺工具时说明安装方式，不要假装已经生成了 MP4。
""",
)

_add(
    "short-drama-script",
    "短剧/口播剧本：选题立项、角色、分集钩子、合规自检、国内或海外格式",
    """
# 短剧与口播剧本

覆盖从选题到分集撰写。参考短剧行业常见结构，用本软件当前模型写作。

## 立项先问清

题材（可组合两种）、受众（女频/男频/全龄）、调性（甜/虐/爽/燃/搞笑）、
结局（HE/BE/OE）、集数、国内或海外格式。写入 `01-script/.drama-state.json`。

## 产出顺序

1. `creative-plan.md` — 人物、主线副线、三幕、节奏（起势15% / 攀升30% / 风暴35% / 决战20%）
2. `characters.md` — 主角弧光 + 四层反派（小/中/大/隐藏）
3. `episode-directory.md` — 每集标题、一句话梗概、钩子类型、付费卡点约 10–15%
4. `episodes/epNNN.md` — 分集剧本
5. `reviews/` 与 `compliance-report.md`

## 国内镜头格式

```
## 场景一：地点·内/外·日/夜
♪ 配乐
△ 全景/中景/近景/特写：画面
**角色**：（动作）台词
```

海外用 INT./EXT. + WIDE/MEDIUM/CU。开篇 30 秒必须入戏。每集结尾必须有钩子。

## 合规

红线：违法美化、色情暴力、歧视侮辱、未成年人不当描写。不确定就标 ⚠️ 并改写。
""",
)

_add(
    "libtv-generate",
    "LibTV CLI 画布：文本/图/视频/音频/分镜节点、管道生成与下载",
    """
# LibTV 生成

局域网已接入 Gradio WAN（如 `http://192.168.3.23:7860`）时，用工具 `video_generate` 写到 `02-generate/`。
本机已安装 `libtv` 时走画布生成；否则提示安装手册并改用 Remotion。

## 安装与登录

- 安装脚本通常落到 `~/.libtv/libtv`，需在 PATH 中
- `libtv login web --open` 或手机号验证码
- 先 `workspace use` 再 `project use`，否则报 `PROJECT_NOT_BOUND`

## 短视频最小链路

```
libtv workspace create "短视频" && libtv workspace use <id>
libtv project create "成片" && libtv project use <uuid>
libtv node create "脚本" -t text --prompt "..." --set "model=GVLM 3.1" --run
libtv node create "镜头" -t video --prompt "..." --set modeType=text2video --set ratio=9:16 --set duration=5 --run
libtv download ...
```

分镜：`-t script` 生成 rows 后 `libtv script storyboard "剧本"`。
合成：`-t video-clip` 连接多个 video 节点。

## 注意

- `-s/--set` 写生成参数；`-u/--update` 写节点内容，二者不要混用
- `model=` 传展示名（如 `GVLM 3.1`）不要传内部 key
- stdout 是 NDJSON 业务结果，进度在 stderr
- 产物下载到工作区 `02-generate/`
""",
)

_add(
    "wan-gradio",
    "局域网 Gradio WAN 文生视频：/generate_video，成片写入 02-generate/",
    """
# 局域网 WAN / Gradio 文生视频

对话里调用工具 `video_generate`（provider=wan），不要把它当成聊天模型。
云端海螺/Kimi 用 provider=minimax 或 kimi；本机节点图用 provider=comfy。
底层按 Gradio 官方 Python API：`Client(url).predict(..., api_name="/generate_video")`。
该服务 MCP Tools 为 0，不要走 MCP。

## 接入

视频运营页填写 Gradio 地址（常见 `http://192.168.3.23:7860`），点「探测并接入」。
在线时应看到标题（如 WAN-1.3B 文生视频）和 `/generate_video`。

## 参数

- prompt：画面描述，中英文均可
- resolution：`480p` / `720p` / `1080p`（对应 832x480、1280x720、1920x1088）
- num_frames：33–81，默认 60
- num_inference_steps：20–50，默认 50（越高质量越慢）

等价于 Gradio 导出的 Python API：

```python
from gradio_client import Client
client = Client("http://192.168.3.23:7860")
client.predict(prompt=..., resolution="720p (1280x720)",
               num_frames=60, num_inference_steps=50,
               api_name="/generate_video")
```

生成可能要数分钟。完成后文件在 `02-generate/`，并在 `pipeline.md` 记一行。
""",
)

_add(
    "remotion-video",
    "用 Remotion+React 做可反复改的短视频工程并渲染 MP4",
    """
# Remotion 视频

需要代码可控、可改字幕/时长/品牌色时用 Remotion，不要只用文生视频。

## 脚手架

```
npx create-video@latest --yes --blank --no-tailwind <name>
```

默认竖屏 1080x1920、30fps。场景数据、文案、颜色放常量数组，方便改。

## 实现

- 组件：`Composition` `Sequence` `AbsoluteFill` `Audio` `Img`
- 时间用 `useCurrentFrame` + `interpolate` / `spring`，禁止 `setTimeout`
- 字幕高对比、安全边距；TikTok 风格可分页高亮单词
- 预览：`npx remotion studio`
- 抽帧检查：`npx remotion still <id> --scale=0.25 --frame=30`
- 成片：`npx remotion render <id> out/final.mp4`

工程放 `02-generate/remotion-<slug>/`，成片复制到 `03-edit/`。
缺 Node / Chrome / 编解码时报告环境问题，不要假装已渲染。
""",
)

_add(
    "video-edit-zh",
    "中文竖屏混剪：ffmpeg 比例处理、Ken Burns、字幕叠字、帧采样自检",
    """
# 中文视频剪辑

素材文件夹混有照片和视频时：整理 → 方案确认 → 渲染 → 抽帧自检 → 交付。

## 画面

输出 1080x1920。竖屏放大裁剪填满；横屏先 `transpose=1` 再裁；禁止拉伸和黑边。
Apple Silicon 4K 预处理可用 `h264_videotoolbox`。

## 照片动效

zoompan 用帧号 `on`，不要用 `t`。约 5 秒缓慢推镜。

## 字幕

系统 ffmpeg 若无 drawtext：Pillow 生成半透明黑底白字 PNG，ffmpeg overlay，**必须 `-loop 1`**。
中文 ASR（FunASR 等）要校对地名、同音字；同时改 `text` 和 word-level，否则字幕错位。

## 自检

成片后在 10 个时间点截图，确认无拉伸、字可读、比例正确。方案未获用户确认不要开渲。
成片与自检图放 `03-edit/`。
""",
)

_add(
    "ops-analyze",
    "运营数据分析：从 CSV/表格做完播率、选题归因和改稿建议",
    """
# 运营分析（DeepAnalyze 思路）

有播放数据、问卷或后台导出时，自主完成：清洗 → 指标 → 对比 → 图表说明 → 报告。
不要只堆数字。报告写入 `04-analyze/report.md`。

## 短视频常用指标

曝光、完播、3 秒留存、点赞评论分享、涨粉、完播曲线掉点时间。
把掉点对齐到剧本钩子/字幕/封面，给出「改第几秒、改哪句」的动作。

## 数据纪律

- 先列数据源与时间窗，再下结论
- 样本量过小要标明置信不足
- 能复现的计算写清公式或 Python 片段
- 不编造平台后台数字
""",
)

_add(
    "multi-publish",
    "多平台发布草稿：短视频填表+人工确认；图文 Markdown 多平台清单",
    """
# 多平台发布

## 短视频（抖音 / 小红书 / 视频号 / B 站 / YouTube）

在 `05-publish/draft.json` 写：title、description、tags（空格分隔）、video_path、cover_path、platforms。
工作流：本机浏览器先登录各创作者后台 → 用开源工作台或手工粘贴同一套资料 → **每一平台停在发布页由用户点发布**。
禁止：自动点发布、托管账号密码、云端代发、定时代发。

平台差异：B 站侧重标题封面标签；YouTube 标题栏可合并标题+正文+标签。封面以竖版为主。

## 图文（知乎 / CSDN 等）

Markdown 文首：

```
---
title: 标题
tags: tag1, tag2
---
```

导出到 `05-publish/article.md`。登录与排版由用户或自备 Selenium 完成；本技能只保证正文结构稳定、不上传密码。
""",
)

_add(
    "director-desk",
    "导演台：企划→分镜→ComfyUI/WAN 生成→ffmpeg 合成成片，对话与指挥中心之间的创作台",
    """
# 导演台

用户要拍短片、分镜、合成、Comfy 出视频时，打开侧栏「导演台」（在对话和指挥中心之间）。
自己调用工具 `video_studio`（status / save / import_script / add_shot / generate / assemble）。
不要让用户去 Comfy 网页里点 Queue，除非还没有 API Format JSON。

来源：https://docs.comfy.org/zh  ·  https://github.com/Comfy-Org/ComfyUI
Comfy 是节点图，不是聊天模型。自动化协议：Save (API Format) → POST /prompt → GET /history/{id} → GET /view。

## 流程

1. save：片名、一句话故事、画幅、engine（comfy/wan/minimax/kimi）
2. import_script：把「1. 画面」或「## 镜头」剧本拆成镜头
3. Comfy 引擎必须带 workflow_path（API JSON）。MiniMax-H3 用 Unet Loader (GGUF)
4. generate：按镜头出片，写入 `00-desk/shots/`
5. assemble：本机 ffmpeg 拼接成片
6. 发布仍走视频运营草稿，人工点平台发布
""",
)
