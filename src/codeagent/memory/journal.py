"""Helpers for auto-recorded conversation / progress memories."""

from __future__ import annotations

CONVERSATION_KINDS = ("turn", "thinking", "conversation")
LEARNED_KINDS = (
    "learned_code",
    "learned_design",
    "learned_ui",
    "learned_flow",
    "learned_db",
    "learned_tech",
)


def clip(text: str, limit: int = 400) -> str:
    blob = (text or "").strip()
    if len(blob) <= limit:
        return blob
    return blob[: limit - 1] + "…"


def format_turn(user: str, assistant: str, thinking: str = "") -> str:
    parts = [f"用户：{clip(user, 400)}", f"助手：{clip(assistant, 500)}"]
    thought = clip(thinking, 500)
    if thought:
        parts.append(f"思考：{thought}")
    return "\n".join(parts)


def format_progress(project: str, summary: str) -> str:
    name = (project or "").strip() or "未分项目"
    return f"项目进度「{name}」：{clip(summary, 240)}"


def format_zone_start(project: str) -> str:
    name = (project or "").strip() or "未分项目"
    return f"开始记录项目「{name}」的对话、思考与进度。"
