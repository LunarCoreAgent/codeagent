"""Voice Surface helpers distilled from LunarCore v3.3.17 (not a source dump)."""

from __future__ import annotations

import re

from codeagent.voice.emotion import VoiceStyle

_CODE_FENCE = re.compile(r"```[\s\S]*?```")
_INLINE_CODE = re.compile(r"`[^`]*`")
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MD_MARK = re.compile(r"[#*>|-]{1,}\s?")


def to_speech_text(text: str, max_len: int = 220) -> str:
    """Strip markdown/code so TTS only speaks the conclusion and numbers."""
    cleaned = _CODE_FENCE.sub("（略去代码）", text or "")
    cleaned = _INLINE_CODE.sub("", cleaned)
    cleaned = _MD_LINK.sub(r"\1", cleaned)
    cleaned = _MD_MARK.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len] + "。"
    return cleaned


def cute_style(
    pitch_hz: int = -10,
    rate_pct: int = -5,
    enabled: bool = True,
) -> VoiceStyle:
    """LunarCore 嗲音：pitch in Hz, rate in percent (Edge TTS format)."""
    if not enabled:
        return VoiceStyle()
    pitch = max(-50, min(50, int(pitch_hz)))
    rate = max(-20, min(20, int(rate_pct)))
    return VoiceStyle(rate=f"{rate:+d}%", pitch=f"{pitch:+d}Hz")


def _num(token: str, suffix: str) -> int:
    raw = (token or "").replace(suffix, "").replace("+", "").strip() or "0"
    try:
        return int(float(raw))
    except ValueError:
        return 0


def overlay_style(emotion: VoiceStyle, cute: VoiceStyle) -> VoiceStyle:
    """Stack 嗲音 on emotion prosody; keep the emotion voice if set."""
    rate = max(-50, min(50, _num(emotion.rate, "%") + _num(cute.rate, "%")))
    pitch = max(-50, min(50, _num(emotion.pitch, "Hz") + _num(cute.pitch, "Hz")))
    return VoiceStyle(
        voice=emotion.voice,
        rate=f"{rate:+d}%",
        pitch=f"{pitch:+d}Hz",
    )
