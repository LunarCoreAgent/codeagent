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
from typing import Any

from codeagent.voice.emotion import VoiceStyle

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"

# Friendly aliases for the free edge-tts voice pack. Values are full
# edge-tts voice IDs; any other valid edge-tts voice ID also works.
VOICE_PRESETS: dict[str, str] = {
    # LunarCore 语音面别名（豆包未配置时小智回退晓晨）
    "xiaozhi": "zh-TW-HsiaoChenNeural",
    "edge-tw": "zh-TW-HsiaoChenNeural",
    "zh-tw": "zh-TW-HsiaoChenNeural",
    "zh-cn": "zh-CN-XiaoxiaoNeural",
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

VOICE_LABELS: dict[str, str] = {
    "xiaozhi": "小智·湾湾小何（无豆包时回退晓晨）",
    "edge-tw": "台湾女声·晓晨（Edge TTS·免费）",
    "zh-tw": "台湾女声（系统/Edge）",
    "zh-cn": "大陆女声（系统/Edge）",
    "xiaoxiao": "晓晓 · 温暖女声",
    "xiaoyi": "小艺 · 活泼女声",
    "yunxi": "云希 · 阳光男声",
    "yunjian": "云健 · 沉稳男声",
    "xiaochen": "晓晨 · 大陆女声",
    "hsiaochen": "晓晨 · 台湾女声",
    "hsiaoyu": "晓宇 · 台湾女声",
    "yunjhe": "云哲 · 台湾男声",
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

_play_proc: asyncio.subprocess.Process | None = None
_say_proc: Any = None  # subprocess.Popen | None
_stop_gen: int = 0


class PlaybackCancelled(Exception):
    """User (or a newer utterance) stopped playback — do not fall back to another engine."""


def playback_generation() -> int:
    return _stop_gen


def begin_utterance() -> int:
    """Cancel any prior playback and return the generation id for a new utterance."""
    stop_audio()
    return _stop_gen


def _which(name: str) -> str | None:
    """Resolve a player/binary; GUI-launched apps often have a thin PATH."""
    found = shutil.which(name)
    if found:
        return found
    if sys.platform == "darwin" and name in {"afplay", "say"}:
        fallback = f"/usr/bin/{name}"
        if Path(fallback).is_file():
            return fallback
    return None


def _win_player(path: str) -> list[str]:
    safe = path.replace("'", "''")
    ps = (
        "Add-Type -AssemblyName presentationCore; "
        "$m = New-Object System.Windows.Media.MediaPlayer; "
        f"$m.Open([uri]'{safe}'); $m.Play(); "
        "while(-not $m.NaturalDuration.HasTimeSpan){ Start-Sleep -Milliseconds 40 }; "
        "Start-Sleep -Milliseconds ([int]$m.NaturalDuration.TimeSpan.TotalMilliseconds + 180)"
    )
    return ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps]


def _macos_say_voice(hint: str) -> str:
    low = (hint or "").lower()
    if any(tok in low for tok in ("tw", "hsiao", "meijia", "edge-tw", "yunjhe")):
        return "Meijia"
    return "Tingting"


def _run_say(argv: list[str], gen: int) -> None:
    """Run OS TTS as a killable process; respect stop_audio() mid-flight."""
    import subprocess
    import time

    global _say_proc
    if _stop_gen != gen:
        raise PlaybackCancelled()
    proc = subprocess.Popen(
        argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    _say_proc = proc
    try:
        while proc.poll() is None:
            if _stop_gen != gen:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                raise PlaybackCancelled()
            time.sleep(0.05)
        if _stop_gen != gen:
            raise PlaybackCancelled()
        if proc.returncode not in (0, None):
            # Killed by stop_audio → treat as cancel; other failures bubble.
            if _stop_gen != gen:
                raise PlaybackCancelled()
            raise subprocess.CalledProcessError(proc.returncode or 1, argv)
    finally:
        if _say_proc is proc:
            _say_proc = None


def system_say(text: str, voice_hint: str = "") -> None:
    """Offline OS TTS when edge-tts / afplay is unavailable."""
    import subprocess

    spoken = (text or "").strip()
    if not spoken:
        raise RuntimeError("没有可朗读的文字")
    gen = _stop_gen
    if sys.platform == "darwin":
        say = _which("say") or "say"
        voice = _macos_say_voice(voice_hint)
        try:
            _run_say([say, "-v", voice, spoken], gen)
            return
        except PlaybackCancelled:
            raise
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            if _stop_gen != gen:
                raise PlaybackCancelled()
            _run_say([say, spoken], gen)
            return
    if sys.platform == "win32":
        safe = spoken.replace("'", "''")[:800]
        ps = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Speak('{safe}')"
        )
        _run_say(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            gen,
        )
        return
    raise RuntimeError("当前系统没有可用的朗读引擎")


async def play_audio(path: str | Path) -> None:
    """Play an audio file with whatever player the OS offers."""
    global _play_proc
    target = str(path)
    gen = _stop_gen
    if sys.platform == "win32":
        candidates = [_win_player(target)]
    else:
        candidates = _PLAYERS.get(sys.platform, _PLAYERS["linux"])
    tried = False
    for player in candidates:
        if _stop_gen != gen:
            raise PlaybackCancelled()
        if player[0] == "powershell":
            argv = list(player)
        else:
            binary = _which(player[0])
            if binary is None:
                continue
            argv = [binary, *player[1:], target]
        tried = True
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        _play_proc = process
        try:
            rc = await process.wait()
        finally:
            if _play_proc is process:
                _play_proc = None
        if _stop_gen != gen:
            raise PlaybackCancelled()
        if rc == 0:
            return
        # Non-zero after an explicit stop is cancel, not "try next engine".
        if _stop_gen != gen:
            raise PlaybackCancelled()
    if _stop_gen != gen:
        raise PlaybackCancelled()
    raise RuntimeError(
        "No audio player found (tried afplay/ffplay/mpg123/MediaPlayer); "
        f"audio file saved at {path}"
        if tried else
        f"No audio player binary available; audio file saved at {path}"
    )


def stop_audio() -> None:
    """Interrupt in-flight playback (file player and OS say)."""
    global _play_proc, _say_proc, _stop_gen
    _stop_gen += 1
    proc = _play_proc
    _play_proc = None
    if proc is not None:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        except Exception:  # noqa: BLE001
            pass
    say = _say_proc
    _say_proc = None
    if say is not None:
        try:
            say.kill()
        except ProcessLookupError:
            pass
        except Exception:  # noqa: BLE001
            pass
