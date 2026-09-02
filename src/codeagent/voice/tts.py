"""Text-to-speech: provider abstraction plus a free voice pack.

``EdgeTTSProvider`` uses Microsoft Edge's neural voices via ``edge-tts`` —
completely free, no API key, with high-quality Chinese voices
(Xiaoxiao / Xiaoyi / Yunxi / Yunjian). This is the default "voice pack";
production deployments can subclass :class:`TTSProvider` for Volcano
Engine (what xiaozhi.me uses), CosyVoice, or ElevenLabs.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from codeagent.voice.emotion import VoiceStyle

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"

# Friendly aliases for the free edge-tts voice pack. Values are full
# edge-tts voice IDs; any other valid edge-tts voice ID also works.
VOICE_PRESETS: dict[str, str] = {
    # 大陆普通话
    "xiaoxiao": "zh-CN-XiaoxiaoNeural",   # 晓晓：温暖亲切女声
    "xiaoyi": "zh-CN-XiaoyiNeural",       # 小艺：活泼女声
    "yunxi": "zh-CN-YunxiNeural",         # 云希：阳光男声
    "yunjian": "zh-CN-YunjianNeural",     # 云健：沉稳男声
    "xiaochen": "zh-CN-XiaochenNeural",   # 晓晨：温柔治愈女声
    # 台湾国语
    "hsiaochen": "zh-TW-HsiaoChenNeural", # 晓晨：台湾女声，温柔细腻
    "hsiaoyu": "zh-TW-HsiaoYuNeural",     # 晓宇：台湾女声，语调柔和
    "yunjhe": "zh-TW-YunJheNeural",       # 云哲：台湾男声
}


def resolve_voice(name_or_id: str) -> str:
    """Accept a preset alias (``hsiaochen``) or a full edge-tts voice ID."""
    return VOICE_PRESETS.get(name_or_id.lower(), name_or_id)


class TTSProvider(ABC):
    """Synthesize text into an audio file."""

    @abstractmethod
    async def synthesize(self, text: str, style: VoiceStyle | None = None) -> Path:
        """Return the path of a synthesized audio file."""


class EdgeTTSProvider(TTSProvider):
    """Free neural-voice pack (requires ``pip install codeagent[voice]``).

    With ``emotion_voices=True`` (default), per-emotion styles may switch
    voices. Pass ``emotion_voices=False`` to pin one voice (e.g. the
    Taiwanese HsiaoChen) and let emotions only adjust rate/pitch.
    """

    def __init__(
        self,
        voice: str = DEFAULT_VOICE,
        output_dir: str | Path | None = None,
        emotion_voices: bool = True,
    ) -> None:
        self.voice = resolve_voice(voice)
        self.emotion_voices = emotion_voices
        self.output_dir = Path(output_dir) if output_dir else Path(tempfile.gettempdir()) / "codeagent-voice"

    async def synthesize(self, text: str, style: VoiceStyle | None = None) -> Path:
        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError(
                "edge-tts is required for voice output: pip install codeagent[voice]"
            ) from exc
        if style and style.voice and self.emotion_voices:
            voice = style.voice
        else:
            voice = self.voice
        rate = style.rate if style else "+0%"
        pitch = style.pitch if style else "+0Hz"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{uuid.uuid4().hex[:12]}.mp3"
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await communicate.save(str(path))
        return path


_PLAYERS: dict[str, list[list[str]]] = {
    "darwin": [["afplay"]],
    "linux": [
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
        ["mpg123", "-q"],
    ],
}


async def play_audio(path: str | Path) -> None:
    """Play an audio file with whatever player the OS offers."""
    candidates = _PLAYERS.get(sys.platform, _PLAYERS["linux"])
    for player in candidates:
        if shutil.which(player[0]):
            process = await asyncio.create_subprocess_exec(
                *player, str(path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await process.wait()
            return
    raise RuntimeError(
        "No audio player found (tried afplay/ffplay/mpg123); "
        f"audio file saved at {path}"
    )
