"""Native macOS speech listening for the desktop mic button.

WKWebView's ``webkitSpeechRecognition`` is often missing or always
``not-allowed`` even when System Settings shows the mic toggle on.
``SFSpeechRecognizer`` + ``AVAudioEngine`` is the reliable path.

Critical UX: buffer recognition often delivers **partial** transcripts but
never sets ``isFinal`` until ``endAudio()`` is called. Without a silence
timeout the UI shows text in the input box and never auto-sends — so the
agent never replies (and never speaks). We end the utterance after a short
pause and commit ``heard`` ourselves.
"""

from __future__ import annotations

import logging
import sys
import threading
from typing import Any, Callable

log = logging.getLogger("codeagent.desktop.voice_listen")

_OnText = Callable[[str, bool], None]
_OnError = Callable[[str], None]

# After the user stops talking, wait this long then finalize the utterance.
_SILENCE_SEC = 1.15
# Brief grace after endAudio() before we force-commit if isFinal never arrives.
_FINAL_GRACE_SEC = 0.4


class NativeSpeechSession:
    """One-shot utterance listener (macOS only) with silence auto-commit."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._engine = None
        self._request = None
        self._task = None
        self._node = None
        self._recognizer = None
        self._on_tap = None
        self._on_result = None
        self._active = False
        self._committed = False
        self._last_partial = ""
        self._silence_timer: threading.Timer | None = None
        self._grace_timer: threading.Timer | None = None
        self._on_text: _OnText | None = None

    @property
    def active(self) -> bool:
        return self._active

    def start(
        self,
        on_text: _OnText,
        on_error: _OnError | None = None,
        locale: str = "zh-CN",
    ) -> dict[str, Any]:
        if sys.platform != "darwin":
            return {"ok": False, "error": "仅 macOS 支持系统听写"}

        from codeagent.desktop.mic import permissions_ready

        gate = permissions_ready()
        if not gate.get("ok"):
            return {
                "ok": False,
                "error": gate.get("error") or gate.get("message")
                or "系统未授予麦克风/语音识别权限",
                "status": gate.get("status"),
                "speech_status": gate.get("speech_status"),
                "path": gate.get("path"),
                "open_settings": True,
            }

        with self._lock:
            self.stop_unlocked()
            try:
                return self._start_unlocked(on_text, on_error, locale)
            except Exception as exc:  # noqa: BLE001
                log.exception("native listen start failed")
                self.stop_unlocked()
                return {"ok": False, "error": str(exc)[:180]}

    def stop(self) -> None:
        with self._lock:
            self.stop_unlocked()

    def _cancel_timers(self) -> None:
        for attr in ("_silence_timer", "_grace_timer"):
            t = getattr(self, attr)
            if t is not None:
                try:
                    t.cancel()
                except Exception:  # noqa: BLE001
                    pass
                setattr(self, attr, None)

    def stop_unlocked(self) -> None:
        self._active = False
        self._cancel_timers()
        task = self._task
        request = self._request
        engine = self._engine
        node = self._node
        self._task = None
        self._request = None
        self._engine = None
        self._node = None
        self._recognizer = None
        self._on_tap = None
        self._on_result = None
        self._on_text = None
        try:
            if task is not None:
                task.cancel()
        except Exception:  # noqa: BLE001
            pass
        try:
            if request is not None:
                request.endAudio()
        except Exception:  # noqa: BLE001
            pass
        try:
            if engine is not None:
                engine.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            if node is not None:
                node.removeTapOnBus_(0)
        except Exception:  # noqa: BLE001
            pass

    def _finish_utterance(self) -> None:
        """Tear down engine off the recognition callback thread."""
        self._active = False
        self._cancel_timers()

        def _stop() -> None:
            try:
                self.stop()
            except Exception:  # noqa: BLE001
                log.exception("native listen stop after final failed")

        threading.Thread(target=_stop, daemon=True, name="cca-listen-end").start()

    def _commit(self, text: str) -> None:
        """Send one final transcript to the UI (at most once per start)."""
        text = (text or "").strip()
        with self._lock:
            if self._committed or not text:
                return
            self._committed = True
            on_text = self._on_text
        if on_text is not None:
            try:
                on_text(text, True)
            except Exception:  # noqa: BLE001
                log.exception("on_text(final) failed")
        self._finish_utterance()

    def _arm_silence(self) -> None:
        """Restart silence timer whenever a partial arrives."""
        self._cancel_timers()
        if not self._active or self._committed:
            return

        def _on_silence() -> None:
            if not self._active or self._committed:
                return
            # Tell Speech the user paused — may deliver isFinal.
            try:
                req = self._request
                if req is not None:
                    req.endAudio()
            except Exception:  # noqa: BLE001
                pass

            def _force() -> None:
                if self._committed:
                    return
                self._commit(self._last_partial)

            grace = threading.Timer(_FINAL_GRACE_SEC, _force)
            grace.daemon = True
            self._grace_timer = grace
            grace.start()

        timer = threading.Timer(_SILENCE_SEC, _on_silence)
        timer.daemon = True
        self._silence_timer = timer
        timer.start()

    def _start_unlocked(
        self,
        on_text: _OnText,
        on_error: _OnError | None,
        locale: str,
    ) -> dict[str, Any]:
        from Foundation import NSLocale
        from AVFoundation import AVAudioEngine
        from Speech import (
            SFSpeechAudioBufferRecognitionRequest,
            SFSpeechRecognizer,
        )

        speech_code = int(SFSpeechRecognizer.authorizationStatus())
        if speech_code != 3:
            from codeagent.desktop.mic import SPEECH_SETTINGS_HINT, SPEECH_SETTINGS_PATH

            return {
                "ok": False,
                "error": SPEECH_SETTINGS_HINT,
                "speech_status": {0: "not_determined", 1: "restricted",
                                  2: "denied"}.get(speech_code, "unknown"),
                "path": SPEECH_SETTINGS_PATH,
                "open_settings": True,
            }

        recognizer = SFSpeechRecognizer.alloc().initWithLocale_(
            NSLocale.alloc().initWithLocaleIdentifier_(locale or "zh-CN")
        )
        if recognizer is None or not recognizer.isAvailable():
            recognizer = SFSpeechRecognizer.alloc().init()
        if recognizer is None or not recognizer.isAvailable():
            return {"ok": False, "error": "本机语音识别不可用"}

        engine = AVAudioEngine.alloc().init()
        request = SFSpeechAudioBufferRecognitionRequest.alloc().init()
        request.setShouldReportPartialResults_(True)
        try:
            request.setRequiresOnDeviceRecognition_(False)
        except Exception:  # noqa: BLE001
            pass
        try:
            request.setTaskHint_(1)  # SFSpeechRecognitionTaskHintDictation
        except Exception:  # noqa: BLE001
            pass

        node = engine.inputNode()
        try:
            engine.prepare()
        except Exception:  # noqa: BLE001
            pass
        fmt = node.outputFormatForBus_(0)
        if fmt is None or float(fmt.sampleRate() or 0) <= 0:
            try:
                fmt = node.inputFormatForBus_(0)
            except Exception:  # noqa: BLE001
                fmt = None
        if fmt is None or float(fmt.sampleRate() or 0) <= 0:
            return {"ok": False, "error": "无法打开麦克风输入"}

        self._committed = False
        self._last_partial = ""
        self._on_text = on_text

        def on_tap(buffer, when) -> None:  # noqa: ANN001
            req = self._request
            if not self._active or req is None or self._committed:
                return
            try:
                req.appendAudioPCMBuffer_(buffer)
            except Exception:  # noqa: BLE001
                pass

        def on_result(result, error) -> None:  # noqa: ANN001
            if error is not None:
                msg = str(error)
                if self._active and not self._committed and on_error \
                        and "cancel" not in msg.lower():
                    # If we already have text, prefer committing over erroring out.
                    if self._last_partial.strip():
                        self._commit(self._last_partial)
                    else:
                        on_error(msg[:180])
                return
            if result is None or not self._active or self._committed:
                return
            try:
                text = str(result.bestTranscription().formattedString() or "").strip()
                final = bool(result.isFinal())
            except Exception as exc:  # noqa: BLE001
                if on_error:
                    on_error(str(exc)[:180])
                return
            if not text:
                return
            self._last_partial = text
            if final:
                self._commit(text)
                return
            on_text(text, False)
            self._arm_silence()

        self._on_tap = on_tap
        self._on_result = on_result
        self._recognizer = recognizer

        node.installTapOnBus_bufferSize_format_block_(0, 4096, fmt, on_tap)
        task = recognizer.recognitionTaskWithRequest_resultHandler_(request, on_result)
        ok, err = engine.startAndReturnError_(None)
        if not ok:
            try:
                node.removeTapOnBus_(0)
            except Exception:  # noqa: BLE001
                pass
            detail = str(err) if err is not None else "麦克风启动失败"
            return {"ok": False, "error": detail[:180], "open_settings": True}

        self._engine = engine
        self._request = request
        self._task = task
        self._node = node
        self._active = True
        log.info("native listen started locale=%s silence=%.2fs", locale, _SILENCE_SEC)
        return {"ok": True, "engine": "speech.framework", "locale": locale}
