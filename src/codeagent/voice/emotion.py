"""Emotion mode: xiaozhi-style out-of-band emotion tags.

Inspired by xiaozhi-esp32's `{"type":"llm","emotion":"happy"}` channel:
the model prefixes every reply with ``[emotion:happy]``; the tag is parsed
off the text and mapped to a voice style (voice / rate / pitch) for TTS,
so the agent speaks with emotional prosody.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Emotion(str, Enum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISED = "surprised"
    THINKING = "thinking"
    LOVING = "loving"
    SLEEPY = "sleepy"


EMOTION_PROMPT_SUFFIX = """\

## Emotion mode

You are in emotional-companion mode. Start EVERY reply with exactly one \
emotion tag on its own line, chosen from:
[emotion:neutral] [emotion:happy] [emotion:sad] [emotion:angry] \
[emotion:surprised] [emotion:thinking] [emotion:loving] [emotion:sleepy]

Pick the emotion that matches the tone of your reply, then write the \
reply itself after the tag. Be warm and personable; keep spoken replies \
conversational and reasonably short.
"""

_TAG_RE = re.compile(r"^\s*\[emotion:([A-Za-z一-鿿]+)\]\s*")

_ALIASES = {
    "neutral": Emotion.NEUTRAL, "平静": Emotion.NEUTRAL,
    "happy": Emotion.HAPPY, "开心": Emotion.HAPPY, "高兴": Emotion.HAPPY, "快乐": Emotion.HAPPY,
    "sad": Emotion.SAD, "难过": Emotion.SAD, "伤心": Emotion.SAD, "悲伤": Emotion.SAD,
    "angry": Emotion.ANGRY, "生气": Emotion.ANGRY, "愤怒": Emotion.ANGRY,
    "surprised": Emotion.SURPRISED, "惊讶": Emotion.SURPRISED, "吃惊": Emotion.SURPRISED,
    "thinking": Emotion.THINKING, "思考": Emotion.THINKING, "想": Emotion.THINKING,
    "loving": Emotion.LOVING, "温柔": Emotion.LOVING, "爱": Emotion.LOVING, "亲密": Emotion.LOVING,
    "sleepy": Emotion.SLEEPY, "困": Emotion.SLEEPY, "困倦": Emotion.SLEEPY,
}


def parse_emotion(text: str) -> tuple[Emotion, str]:
    """Split a leading ``[emotion:xxx]`` tag off the reply.

    Returns ``(emotion, clean_text)``; unknown or missing tags yield
    ``Emotion.NEUTRAL`` with the tag (if any) stripped.
    """
    match = _TAG_RE.match(text)
    if not match:
        return Emotion.NEUTRAL, text
    emotion = _ALIASES.get(match.group(1).lower(), Emotion.NEUTRAL)
    return emotion, text[match.end():]


@dataclass(frozen=True)
class VoiceStyle:
    """Prosody for one emotion. ``voice=None`` keeps the TTS default."""

    voice: str | None = None
    rate: str = "+0%"
    pitch: str = "+0Hz"


# Free Chinese neural voices (edge-tts voice pack) tuned per emotion.
EMOTION_VOICE_MAP: dict[Emotion, VoiceStyle] = {
    Emotion.NEUTRAL: VoiceStyle("zh-CN-XiaoxiaoNeural", "+0%", "+0Hz"),
    Emotion.HAPPY: VoiceStyle("zh-CN-XiaoxiaoNeural", "+12%", "+25Hz"),
    Emotion.SAD: VoiceStyle("zh-CN-XiaoxiaoNeural", "-15%", "-15Hz"),
    Emotion.ANGRY: VoiceStyle("zh-CN-YunxiNeural", "+15%", "-5Hz"),
    Emotion.SURPRISED: VoiceStyle("zh-CN-XiaoxiaoNeural", "+20%", "+40Hz"),
    Emotion.THINKING: VoiceStyle("zh-CN-YunjianNeural", "-8%", "+0Hz"),
    Emotion.LOVING: VoiceStyle("zh-CN-XiaoyiNeural", "-5%", "+10Hz"),
    Emotion.SLEEPY: VoiceStyle("zh-CN-XiaoxiaoNeural", "-20%", "-20Hz"),
}


def style_for(emotion: Emotion) -> VoiceStyle:
    return EMOTION_VOICE_MAP.get(emotion, EMOTION_VOICE_MAP[Emotion.NEUTRAL])
