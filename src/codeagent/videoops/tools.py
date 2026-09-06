"""Agent tools for the video ops workspace."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from codeagent.security.policy import RiskLevel
from codeagent.tools.base import Tool
from codeagent.videoops import (
    VideoOpsConfig,
    append_pipeline,
    save_publish_draft,
    workspace_status,
)
from codeagent.videoops.gradio import generate_wan_video, resolve_gradio_base


class VideoOpsStatusTool(Tool):
    name = "video_ops_status"
    description = (
        "Inspect the CodeCoreAgent video ops workspace: stages, toolchain "
        "(libtv/ffmpeg/node), Gradio WAN endpoint, and current publish draft."
    )
    parameters = {"type": "object", "properties": {}}

    async def execute(self, **_: Any) -> str:
        cfg = VideoOpsConfig.load()
        st = workspace_status(cfg.workspace())
        tc = st["toolchain"]
        lines = [
            f"path: {st['path']}",
            f"ready: {st['ready']}",
            f"files: {st.get('counts')}",
            f"gradio: {resolve_gradio_base(cfg) or 'missing'}",
            f"libtv: {tc.get('libtv') or 'missing'}",
            f"ffmpeg: {tc.get('ffmpeg') or 'missing'}",
            f"node: {tc.get('node') or 'missing'}",
        ]
        draft = st.get("draft") or {}
        if draft.get("title"):
            lines.append(f"draft title: {draft['title']}")
        return "\n".join(lines)


class VideoOpsLogTool(Tool):
    name = "video_ops_log"
    description = "Append a pipeline progress line to the video ops workspace."
    parameters = {
        "type": "object",
        "properties": {
            "event": {"type": "string", "description": "What just finished."},
        },
        "required": ["event"],
    }
    risk_level = RiskLevel.WRITE

    async def execute(self, event: str, **_: Any) -> str:
        cfg = VideoOpsConfig.load()
        root = cfg.workspace()
        if not root.exists():
            return "workspace missing — 请先在「视频运营」页一键布置"
        append_pipeline(root, event)
        return f"logged: {event}"


class VideoOpsDraftTool(Tool):
    name = "video_ops_draft"
    description = (
        "Save a multi-platform publish draft (title/description/tags/video). "
        "Does not log in or click publish."
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "tags": {"type": "string"},
            "video_path": {"type": "string"},
            "cover_path": {"type": "string"},
        },
        "required": ["title"],
    }
    risk_level = RiskLevel.WRITE

    async def execute(self, **kwargs: Any) -> str:
        cfg = VideoOpsConfig.load()
        root = cfg.workspace()
        if not root.exists():
            return "workspace missing — 请先一键布置"
        r = save_publish_draft(root, kwargs)
        return f"draft saved: {r['path']} — 请人工在各平台点发布"


class VideoGenerateTool(Tool):
    name = "video_generate"
    description = (
        "Generate a video from a text prompt. Backends: auto / wan (LAN Gradio) / "
        "minimax (Hailuo) / kimi (Moonshot video model) / comfy (ComfyUI workflow). "
        "Saves under video ops 02-generate/. Not a chat model. May take minutes."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "画面描述"},
            "provider": {
                "type": "string",
                "description": "auto | wan | minimax | kimi | comfy",
            },
            "resolution": {
                "type": "string",
                "description": "480p / 720p / 1080p",
            },
            "num_frames": {"type": "integer", "description": "WAN: 33–81. MiniMax: 6 或 10 秒可直接填"},
            "num_inference_steps": {
                "type": "integer",
                "description": "WAN only, 20–50, default 50",
            },
            "duration": {"type": "integer", "description": "云端秒数，默认 6"},
            "workflow_path": {
                "type": "string",
                "description": "ComfyUI API 格式工作流 JSON 路径（provider=comfy 时）",
            },
        },
        "required": ["prompt"],
    }
    risk_level = RiskLevel.WRITE

    async def execute(
        self,
        prompt: str,
        provider: str = "auto",
        resolution: str = "720p",
        num_frames: int = 60,
        num_inference_steps: int = 50,
        duration: int | None = None,
        workflow_path: str = "",
        **_: Any,
    ) -> str:
        from codeagent.videoops.cloud import generate_cloud_video, list_video_credentials
        from codeagent.videoops.comfy import (
            load_workflow_file,
            normalize_comfy_base,
            queue_comfy_workflow,
        )

        cfg = VideoOpsConfig.load()
        dest_dir = cfg.workspace() / "02-generate"
        dest_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        kind = (provider or "auto").strip().lower()
        if kind in {"hailuo", "minimax-hailuo"}:
            kind = "minimax"
        if kind in {"moonshot"}:
            kind = "kimi"
        if kind == "auto":
            creds = {c["backend"] for c in list_video_credentials() if c.get("api_key")}
            if resolve_gradio_base(cfg):
                kind = "wan"
            elif "minimax" in creds:
                kind = "minimax"
            elif "kimi" in creds:
                kind = "kimi"
            elif (cfg.comfy_base or "").strip():
                kind = "comfy"
            else:
                return (
                    "没有可用的文生视频后端。请任选其一："
                    "视频运营页接入 Gradio WAN；模型页添加 MiniMax Hailuo 或 Kimi 视频模型并填密钥；"
                    "或填写 ComfyUI 地址并提供 API 工作流 JSON。"
                )
        if kind == "wan":
            base = resolve_gradio_base(cfg)
            if not base:
                return "未配置 Gradio WAN。请到「视频运营」填写地址并点「探测并接入」。"
            dest = dest_dir / f"wan-{stamp}.mp4"
            result = await generate_wan_video(
                base, prompt,
                resolution=resolution,
                num_frames=int(num_frames),
                num_inference_steps=int(num_inference_steps),
                dest=dest,
            )
        elif kind in {"minimax", "kimi"}:
            dest = dest_dir / f"{kind}-{stamp}.mp4"
            result = await generate_cloud_video(
                prompt, dest, backend=kind,
                resolution=resolution,
                num_frames=int(num_frames),
                duration=duration,
            )
        elif kind == "comfy":
            base = normalize_comfy_base(cfg.comfy_base)
            if not base:
                return "未配置 ComfyUI。请到「视频运营」填写如 http://127.0.0.1:8188"
            if not (workflow_path or "").strip():
                return (
                    "ComfyUI 需要 API 格式工作流 JSON。"
                    "在 ComfyUI 菜单 Save (API Format) 后把路径传给 workflow_path。"
                )
            try:
                wf = load_workflow_file(workflow_path)
            except (OSError, ValueError) as exc:
                return f"读工作流失败：{exc}"
            result = await queue_comfy_workflow(base, wf, dest_dir)
        else:
            return f"未知 provider {provider!r}，请用 auto / wan / minimax / kimi / comfy"
        if not result.get("ok"):
            return f"生成失败：{result.get('error') or 'unknown'}"
        path = result.get("path") or ""
        if cfg.workspace().exists():
            append_pipeline(cfg.workspace(), f"{kind} 生成 {Path(path).name if path else ''}")
        return f"saved: {path}"


def video_ops_tools(cfg: VideoOpsConfig | None = None) -> list[Tool]:
    cfg = cfg or VideoOpsConfig.load()
    if not cfg.enabled:
        return []
    return [
        VideoOpsStatusTool(),
        VideoOpsLogTool(),
        VideoOpsDraftTool(),
        VideoGenerateTool(),
    ]
