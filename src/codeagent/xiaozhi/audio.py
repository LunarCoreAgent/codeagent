"""Opus codec for xiaozhi audio frames (16 kHz mono, 60 ms frames).

Thin wrapper over opuslib. System dependency: libopus
(macOS: ``brew install opus``; Debian: ``apt install libopus0``).
Kept optional so the protocol layer works without audio hardware.
"""

from __future__ import annotations

SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_MS = 60
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000  # 960 samples per frame


class OpusCodec:
    def __init__(self) -> None:
        try:
            import opuslib
        except ImportError as exc:
            raise RuntimeError(
                "opuslib is required for xiaozhi audio: "
                "pip install opuslib && brew install opus"
            ) from exc
        self._encoder = opuslib.Encoder(SAMPLE_RATE, CHANNELS, opuslib.APPLICATION_VOIP)
        self._decoder = opuslib.Decoder(SAMPLE_RATE, CHANNELS)

    def encode(self, pcm: bytes) -> bytes:
        """PCM s16le (1920 bytes = 60 ms) → Opus frame."""
        return self._encoder.encode(pcm, FRAME_SAMPLES)

    def decode(self, opus_frame: bytes) -> bytes:
        """Opus frame → PCM s16le."""
        return self._decoder.decode(opus_frame, FRAME_SAMPLES)
