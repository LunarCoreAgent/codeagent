"""Microphone recording for voice input.

Push-to-talk style: recording runs until the caller signals stop (the CLI
binds this to the Enter key), producing a 16 kHz mono WAV — the format
Whisper expects.
"""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from pathlib import Path

SAMPLE_RATE = 16000


async def record_until_enter(
    path: str | Path | None = None,
    sample_rate: int = SAMPLE_RATE,
) -> Path:
    """Record from the default microphone until Enter is pressed.

    Requires ``sounddevice`` + ``soundfile`` (``pip install
    codeagent[voice-full]``). Returns the WAV file path.
    """
    try:
        import numpy as np
        import sounddevice as sd
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError(
            "sounddevice/soundfile are required for microphone input: "
            "pip install codeagent[voice-full]"
        ) from exc

    out = Path(path) if path else Path(tempfile.gettempdir()) / "codeagent-voice" / f"rec-{uuid.uuid4().hex[:12]}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)

    frames: list = []
    stream = sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
        callback=lambda indata, n, time_info, status: frames.append(indata.copy()),
    )
    with stream:
        await asyncio.to_thread(input)  # block until Enter, without freezing the loop
    if not frames:
        raise RuntimeError("No audio captured from the microphone.")
    sf.write(str(out), np.concatenate(frames), sample_rate)
    return out
