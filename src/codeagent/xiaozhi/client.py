"""High-level xiaozhi client: OTA check-in + protocol + conversation events.

Connects codeagent to xiaozhi.me's free server (Qwen realtime model +
official voices) as a virtual device. Push-to-talk instead of wake word;
audio frames flow through callbacks so any front-end (CLI, voice module)
can plug in.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from codeagent.xiaozhi.config import XiaozhiConfig
from codeagent.xiaozhi.ota import ActivationRequiredError, OtaClient
from codeagent.xiaozhi.protocol import XiaozhiMessage, XiaozhiProtocol


@dataclass
class ConversationEvents:
    """Collected during one server turn (listen stop → tts stop)."""

    stt_text: str = ""                       # what the server heard
    emotion: str | None = None               # llm emotion tag
    sentences: list[str] = field(default_factory=list)  # tts sentence texts
    audio_frames: list[bytes] = field(default_factory=list)  # opus frames


class XiaozhiClient:
    def __init__(
        self,
        config: XiaozhiConfig | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        if config is None:
            config = XiaozhiConfig.load(config_path or "~/.codeagent/xiaozhi.json")
        self.config = config
        self.protocol = XiaozhiProtocol()
        self.protocol.on_message = self._on_message
        self.protocol.on_audio = self._on_audio
        self.current = ConversationEvents()
        self._tts_done: asyncio.Event | None = None

    async def connect(self) -> None:
        """OTA check-in (activation handling included), then WS handshake."""
        result = await OtaClient(self.config).check_in()
        if not result.activated:
            raise ActivationRequiredError(result)
        await self.protocol.connect(
            result.websocket_url, result.websocket_token,
            self.config.device_id, self.config.client_id,
        )

    async def say(
        self,
        opus_frames: list[bytes],
        mode: str = "manual",
        timeout: float = 60,
    ) -> ConversationEvents:
        """One conversation turn: stream mic frames, collect the reply.

        Returns when the server finishes its TTS turn (or ``timeout`` hits).
        """
        self.current = ConversationEvents()
        self._tts_done = asyncio.Event()
        await self.protocol.start_listening(mode)
        for frame in opus_frames:
            await self.protocol.send_audio(frame)
        await self.protocol.stop_listening()

        receive_task = asyncio.create_task(self.protocol.receive_loop())
        try:
            await asyncio.wait_for(self._tts_done.wait(), timeout=timeout)
        finally:
            receive_task.cancel()
        return self.current

    async def abort(self) -> None:
        await self.protocol.abort()

    async def close(self) -> None:
        await self.protocol.close()

    # -- protocol callbacks ---------------------------------------------------

    def _on_message(self, message: XiaozhiMessage) -> None:
        if message.type == "stt" and message.text:
            self.current.stt_text = message.text
        elif message.type == "llm" and message.emotion:
            self.current.emotion = message.emotion
        elif message.type == "tts":
            if message.state == "sentence_start" and message.text:
                self.current.sentences.append(message.text)
            elif message.state == "stop" and self._tts_done is not None:
                self._tts_done.set()

    def _on_audio(self, frame: bytes) -> None:
        self.current.audio_frames.append(frame)
