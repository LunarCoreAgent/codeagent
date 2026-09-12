"""Voice & emotion: emotional dialogue mode, continuous chat, free TTS."""

from codeagent.voice.asr import ASRProvider, WhisperASRProvider
from codeagent.voice.chat import ChatTurn, VoiceChatLoop
from codeagent.voice.emotion import (
    EMOTION_LABELS,
    EMOTION_PROMPT_SUFFIX,
    EMOTION_VOICE_MAP,
    VOICE_CHAT_HINT,
    Emotion,
    VoiceStyle,
    parse_emotion,
    style_for,
)
from codeagent.voice.recorder import record_until_enter
from codeagent.voice.speech import cute_style, overlay_style, to_speech_text
from codeagent.voice.tts import (
    DEFAULT_VOICE,
    VOICE_LABELS,
    VOICE_PRESETS,
    EdgeTTSProvider,
    PlaybackCancelled,
    TTSProvider,
    begin_utterance,
    play_audio,
    playback_generation,
    resolve_voice,
    stop_audio,
)

__all__ = [
    "ASRProvider",
    "ChatTurn",
    "DEFAULT_VOICE",
    "EMOTION_LABELS",
    "EMOTION_PROMPT_SUFFIX",
    "EMOTION_VOICE_MAP",
    "EdgeTTSProvider",
    "Emotion",
    "PlaybackCancelled",
    "TTSProvider",
    "VOICE_CHAT_HINT",
    "VOICE_LABELS",
    "VOICE_PRESETS",
    "VoiceChatLoop",
    "VoiceStyle",
    "WhisperASRProvider",
    "begin_utterance",
    "cute_style",
    "overlay_style",
    "parse_emotion",
    "play_audio",
    "playback_generation",
    "record_until_enter",
    "resolve_voice",
    "stop_audio",
    "style_for",
    "to_speech_text",
]
