"""Agent tools for the video ops workspace."""

from __future__ import annotations

import time
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
        "Generate a video from a text prompt via the LAN Gradio WAN endpoint "
        "(/generate_video). Saves MP4 under the video ops 02-generate folder. "
        "Not a chat model. Generation may take several minutes."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "画面描述"},
            "resolution": {
                "type": "string",
                "description": "480p / 720p / 1080p",
            },
            "num_frames": {"type": "integer", "description": "33–81, default 60"},
            "num_inference_steps": {
                "type": "integer",
                "description": "20–50, default 50",
            },
        },
        "required": ["prompt"],
    }
    risk_level = RiskLevel.WRITE

    async def execute(
        self,
        prompt: str,
        resolution: str = "720p",
        num_frames: int = 60,
        num_inference_steps: int = 50,
        **_: Any,
    ) -> str:
        cfg = VideoOpsConfig.load()
        base = resolve_gradio_base(cfg)
        if not base:
            return (
                "未配置 Gradio 文生视频地址。"
                "请到「视频运营」填写并点「探测并接入」，例如 http://192.168.3.23:7860"
            )
        dest_dir = cfg.workspace() / "02-generate"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"wan-{time.strftime('%Y%m%d-%H%M%S')}.mp4"
        result = await generate_wan_video(
            base,
            prompt,
            resolution=resolution,
            num_frames=int(num_frames),
            num_inference_steps=int(num_inference_steps),
            dest=dest,
        )
        if not result.get("ok"):
            return f"生成失败：{result.get('error') or 'unknown'}"
        if cfg.workspace().exists():
            append_pipeline(cfg.workspace(), f"WAN 生成 {dest.name}")
        return f"saved: {result['path']}"


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
