"""Xiaozhi WebSocket protocol (client side).

Implements the device-side protocol from xiaozhi-esp32's docs/websocket.md:
hello handshake → typed JSON control messages + binary Opus audio frames.

    client → hello → server hello
    client → listen(start) → binary opus frames → listen(stop)
    server → stt / tts(start|sentence_start|stop) / llm(emotion) / binary opus

The layer is transport-pure: it parses and builds messages, dispatches via
callbacks, and never touches audio hardware — so it is fully testable
against a mock WebSocket server.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

PROTOCOL_VERSION = 1
HELLO_TIMEOUT_S = 10


@dataclass
class XiaozhiMessage:
    """A parsed server→client JSON message."""

    type: str                       # stt / tts / llm / iot / hello / ...
    state: str | None = None        # tts: start / stop / sentence_start
    text: str | None = None         # stt text / tts sentence / llm emoji
    emotion: str | None = None      # llm emotion
    raw: dict[str, Any] | None = None


MessageHandler = Callable[[XiaozhiMessage], None | Awaitable[None]]
AudioHandler = Callable[[bytes], None | Awaitable[None]]


class XiaozhiProtocol:
    def __init__(
        self,
        on_message: MessageHandler | None = None,
        on_audio: AudioHandler | None = None,
    ) -> None:
        self.on_message = on_message
        self.on_audio = on_audio
        self.session_id = ""
        self._ws = None

    # -- message builders ----------------------------------------------------

    @staticmethod
    def hello_message() -> dict:
        return {
            "type": "hello",
            "version": PROTOCOL_VERSION,
            "transport": "websocket",
            "audio_params": {
                "format": "opus",
                "sample_rate": 16000,
                "channels": 1,
                "frame_duration": 60,
            },
        }

    def listen_message(self, state: str, mode: str = "manual", text: str | None = None) -> dict:
        msg: dict[str, Any] = {
            "session_id": self.session_id,
            "type": "listen",
            "state": state,
            "mode": mode,
        }
        if text is not None:
            msg["text"] = text
        return msg

    def abort_message(self, reason: str = "wake_word_detected") -> dict:
        return {"session_id": self.session_id, "type": "abort", "reason": reason}

    # -- connection ------------------------------------------------------------

    async def connect(
        self,
        url: str,
        token: str,
        device_id: str,
        client_id: str,
        proxy: "str | None | bool" = True,
    ) -> None:
        try:
            import websockets
        except ImportError as exc:
            raise RuntimeError(
                "websockets is required: pip install codeagent[xiaozhi]"
            ) from exc

        headers = {
            "Authorization": f"Bearer {token}",
            "Protocol-Version": str(PROTOCOL_VERSION),
            "Device-Id": device_id,
            "Client-Id": client_id,
        }
        self._ws = await websockets.connect(
            url, additional_headers=headers, proxy=proxy,
        )
        await self._ws.send(json.dumps(self.hello_message()))

        raw = await asyncio.wait_for(self._ws.recv(), timeout=HELLO_TIMEOUT_S)
        message = json.loads(raw)
        if message.get("type") != "hello":
            await self._ws.close()
            raise RuntimeError(f"Server handshake failed, expected hello: {raw!r}")
        self.session_id = message.get("session_id", "")
        await self._emit(XiaozhiMessage(type="hello", raw=message))

    async def send_json(self, message: dict) -> None:
        self._require_ws()
        await self._ws.send(json.dumps(message, ensure_ascii=False))

    async def send_audio(self, opus_frame: bytes) -> None:
        self._require_ws()
        await self._ws.send(opus_frame)

    async def start_listening(self, mode: str = "manual") -> None:
        await self.send_json(self.listen_message("start", mode))

    async def stop_listening(self) -> None:
        await self.send_json(self.listen_message("stop"))

    async def abort(self, reason: str = "wake_word_detected") -> None:
        await self.send_json(self.abort_message(reason))

    async def receive_loop(self) -> None:
        """Dispatch incoming messages until the server disconnects."""
        self._require_ws()
        async for raw in self._ws:
            if isinstance(raw, (bytes, bytearray)):
                if self.on_audio:
                    await _maybe_await(self.on_audio(bytes(raw)))
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            message = XiaozhiMessage(
                type=data.get("type", ""),
                state=data.get("state"),
                text=data.get("text"),
                emotion=data.get("emotion"),
                raw=data,
            )
            await self._emit(message)

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    # -- internals --------------------------------------------------------------

    def _require_ws(self) -> None:
        if self._ws is None:
            raise RuntimeError("Not connected; call connect() first.")

    async def _emit(self, message: XiaozhiMessage) -> None:
        if self.on_message:
            await _maybe_await(self.on_message(message))


async def _maybe_await(result):
    if result is not None and hasattr(result, "__await__"):
        await result
