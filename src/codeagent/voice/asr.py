"""Speech recognition: provider abstraction plus free offline ASR.

``WhisperASRProvider`` runs faster-whisper locally — free, offline, no API
key, good Chinese accuracy. This completes the voice loop
(mic → ASR → agent → emotion TTS) without any cloud dependency.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path


class ASRProvider(ABC):
    """Transcribe an audio file into text."""

    @abstractmethod
    async def transcribe(self, audio_path: str | Path) -> str:
        """Return the recognized text (empty string if nothing heard)."""


class WhisperASRProvider(ASRProvider):
    """Local faster-whisper ASR (``pip install codeagent[voice-full]``).

    ``model_size``: tiny / base / small / medium / large-v3 — larger is
    more accurate but slower; ``base`` is a sensible laptop default.
    """

    def __init__(self, model_size: str = "base", language: str | None = "zh") -> None:
        self.model_size = model_size
        self.language = language
        self._model = None  # lazy: model load is heavy, defer until first use

    def _load(self):
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is required for voice input: "
                "pip install codeagent[voice-full]"
            ) from exc
        if self._model is None:
            self._model = WhisperModel(self.model_size)
        return self._model

    def _transcribe_sync(self, audio_path: str | Path) -> str:
        model = self._load()
        segments, _ = model.transcribe(str(audio_path), language=self.language)
        return "".join(seg.text for seg in segments).strip()

    async def transcribe(self, audio_path: str | Path) -> str:
        # faster-whisper is synchronous; keep the event loop responsive
        return await asyncio.to_thread(self._transcribe_sync, audio_path)
