# 导演台与 ComfyUI（0.36.0）

侧栏顺序：**对话 → 导演台 → 指挥中心**。  
文档：[docs.comfy.org/zh](https://docs.comfy.org/zh) · 源码：[Comfy-Org/ComfyUI](https://github.com/Comfy-Org/ComfyUI)。

**ComfyUI 是节点图后端，不是聊天模型。** 不要往 `/v1/chat/completions` 上猜。

---

## 1. 台上五步

| 步 | 界面 | 落盘 | 说明 |
|---|---|---|---|
| 1 企划 | 片名、一句话、画幅、时长、引擎、API 工作流路径 | `00-desk/desk.json` | 引擎：comfy / wan / minimax / kimi / auto |
| 2 分镜 | 导入 `1. 画面` 或 `## 镜头名`；每镜可改标题、秒数、引擎、提示词 | 同上 `shots[]` | 最多约 40 镜 |
| 3 生成 | 单镜或「生成未完成」 | `00-desk/shots/` | 后台线程；可停止（含 Comfy `/interrupt`） |
| 4 合成 | ffmpeg concat，失败则重编码 | `00-desk/assembly/cut-*.mp4` | 本机必须有 ffmpeg |
| 5 成片 | 写入发布草稿 | `05-publish/draft.json` | 仍要人工点平台发布 |

对话里对等工具：`video_studio`（status / save / import_script / add_shot / generate / assemble）。

---

## 2. Comfy 自动化协议（官方）

1. 在 Comfy 菜单 **Save (API Format)** 导出 JSON（不是普通工作流保存）。
2. `POST {base}/prompt` 排队。
3. `GET {base}/history/{prompt_id}` 等到完成。
4. `GET {base}/view` 拉回图像/视频。

局域网要被别的电脑访问：启动加 **`--listen 0.0.0.0 --port 8188`**。只写 `127.0.0.1` 时别的机器连不上。  
12GB 卡（如 RTX 3080 Ti）常用 `--lowvram`。

### MiniMax-H3 GGUF

- 权重在 `models/diffusion_models/`、VAE 在 `models/vae/`。
- 内置 UNETLoader **不列 `.gguf`**，须用扩展 **Unet Loader (GGUF)**（ComfyUI-GGUF）。
- CodeCoreAgent 探测会走 UnetLoaderGGUF 对象信息，把 GGUF 列到模型页，**不当聊天模型**。

导演台「Comfy API 工作流 JSON」填该 API Format 文件的本机路径。

---

## 3. 其它生成引擎

| provider | 来源 | 备注 |
|---|---|---|
| `wan` | 局域网 Gradio，如 `:7860` | `Client.predict(/generate_video)` |
| `minimax` | Hailuo 云 API | 模型页保存密钥 |
| `kimi` | Moonshot 视频接口 | 若控制台无视频生成会明确报错 |
| `auto` | 按已接入后端选 | 先 WAN，再 Hailuo / Kimi，再 Comfy |

单段生成也可用对话工具 `video_generate`；导演台按镜头循环调用，并限制写出目录在视频工作区内。

---

## 4. 相关文件

| 路径 | 职责 |
|---|---|
| `src/codeagent/videoops/studio.py` | Desk/Shot、解析剧本、生成一镜、ffmpeg 合成 |
| `src/codeagent/videoops/tools.py` | `video_studio` / `video_generate` |
| `src/codeagent/videoops/comfy.py` | 探测、排队、中断 |
| `src/codeagent/desktop/api.py` | `get_studio`、导入/加删镜、后台生成、合成 |
| `src/codeagent/desktop/ui.py` | `#page-studio`、侧栏夹在 chat 与 lead 之间 |
| `src/codeagent/videoops/bundled.py` | 技能 `director-desk` |
| `tests/test_studio.py` | 解析、持久化、API、UI 位置 |

工作区阶段名：`00-desk`（导演台）→ `01-script` → `02-generate` → `03-edit` → `04-analyze` → `05-publish`。
