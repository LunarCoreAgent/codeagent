"""Voice & emotion: emotional dialogue mode, continuous chat, free TTS."""

from codeagent.voice.asr import ASRProvider, WhisperASRProvider
from codeagent.voice.chat import ChatTurn, VoiceChatLoop
from codeagent.voice.emotion import (
    EMOTION_PROMPT_SUFFIX,
    EMOTION_VOICE_MAP,
    Emotion,
    VoiceStyle,
    parse_emotion,
    style_for,
)
from codeagent.voice.recorder import record_until_enter
from codeagent.voice.tts import (
    DEFAULT_VOICE,
    VOICE_PRESETS,
    EdgeTTSProvider,
    TTSProvider,
    play_audio,
    resolve_voice,
)

__all__ = [
    "ASRProvider",
    "ChatTurn",
    "DEFAULT_VOICE",
    "EMOTION_PROMPT_SUFFIX",
    "EMOTION_VOICE_MAP",
    "EdgeTTSProvider",
    "Emotion",
    "TTSProvider",
    "VOICE_PRESETS",
    "VoiceChatLoop",
    "VoiceStyle",
    "WhisperASRProvider",
    "parse_emotion",
    "play_audio",
    "record_until_enter",
    "resolve_voice",
    "style_for",
]
