"""Microphone OS permission helpers for the desktop voice button.

On macOS, an app only appears under 系统设置 → 隐私与安全性 → 麦克风 after it
calls AVFoundation ``requestAccessForMediaType``. WKWebView getUserMedia alone
is unreliable for registering ``com.codeagent.desktop`` in TCC.

Speech Recognition is a **separate** TCC permission. Both must be authorized
or native listen never fills the input box.

Permission prompts must stay **short / non-blocking** on the UI bridge thread —
waiting 30–90s inside ``ensure_mic_permission`` / ``start_native_listen`` freezes
the whole desktop window.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import threading
import time
from typing import Any, Callable

log = logging.getLogger("codeagent.desktop.mic")

# Real ExtensionKit id on macOS Ventura+ (must be lowercase "settings").
_MAC_MIC_URLS = (
    "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_Microphone",
    "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension/Privacy_Microphone",
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
)
_MAC_SPEECH_URLS = (
    "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_SpeechRecognition",
    "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension/Privacy_SpeechRecognition",
    "x-apple.systempreferences:com.apple.preference.security?Privacy_SpeechRecognition",
)

MIC_SETTINGS_HINT = (
    "请在「麦克风」列表里打开「CodeCoreAgent」。"
    "若只有 LunarCore Agent，那是另一个软件；"
    "请先点「允许并开始语音」，再回来找 CodeCoreAgent。"
)
MIC_SETTINGS_PATH = "系统设置 → 隐私与安全性 → 麦克风 → CodeCoreAgent"
SPEECH_SETTINGS_HINT = (
    "语音听写还需要「语音识别」权限。"
    "请在系统设置里打开 CodeCoreAgent 的语音识别；"
    "只开麦克风、不开语音识别时，说的话进不了输入框。"
)
SPEECH_SETTINGS_PATH = "系统设置 → 隐私与安全性 → 语音识别 → CodeCoreAgent"

_STATUS = {
    0: "not_determined",
    1: "restricted",
    2: "denied",
    3: "authorized",
}
_STATUS_ZH = {
    "authorized": "已允许",
    "denied": "已拒绝",
    "restricted": "受限制",
    "not_determined": "未决定",
    "unknown": "未知",
}

# Keep UI-bridge waits short so the window never freezes on the mic button.
_PROMPT_TIMEOUT = 6.0


def status_label(code: str) -> str:
    return _STATUS_ZH.get(str(code or "unknown"), str(code or "未知"))


def mic_permission_status() -> dict[str, Any]:
    """Instant TCC read — never shows dialogs, never blocks."""
    if sys.platform == "darwin":
        mic = _macos_status()
        speech = _speech_status()
        ready = mic == "authorized" and speech == "authorized"
        return {
            "status": mic,
            "speech_status": speech,
            "status_label": status_label(mic),
            "speech_status_label": status_label(speech),
            "ready": ready,
            "platform": "darwin",
            "mic_path": MIC_SETTINGS_PATH,
            "speech_path": SPEECH_SETTINGS_PATH,
        }
    if sys.platform == "win32":
        return {
            "status": "unknown",
            "speech_status": "unknown",
            "status_label": status_label("unknown"),
            "speech_status_label": status_label("unknown"),
            "ready": False,
            "platform": "win32",
            "mic_path": "设置 → 隐私和安全性 → 麦克风 → CodeCoreAgent",
            "speech_path": "设置 → 隐私和安全性 → 语音 → CodeCoreAgent",
        }
    return {
        "status": "unknown",
        "speech_status": "unknown",
        "status_label": status_label("unknown"),
        "speech_status_label": status_label("unknown"),
        "ready": False,
        "platform": sys.platform,
        "mic_path": MIC_SETTINGS_PATH,
        "speech_path": SPEECH_SETTINGS_PATH,
    }


def permissions_ready() -> dict[str, Any]:
    """Fast gate used by native listen start — no dialogs."""
    info = mic_permission_status()
    if info.get("ready"):
        return {"ok": True, **info}
    mic = info.get("status")
    speech = info.get("speech_status")
    if mic != "authorized":
        message, path = MIC_SETTINGS_HINT, info.get("mic_path") or MIC_SETTINGS_PATH
    else:
        message, path = SPEECH_SETTINGS_HINT, info.get("speech_path") or SPEECH_SETTINGS_PATH
    return {
        "ok": False,
        "error": message,
        "message": message,
        "path": path,
        "open_settings": True,
        **info,
    }


def open_mic_settings() -> dict[str, Any]:
    """Jump straight to OS Privacy → Microphone (not the Settings home page)."""
    return _open_privacy_urls(
        _MAC_MIC_URLS,
        win_url="ms-settings:privacy-microphone",
        hint=MIC_SETTINGS_HINT,
        path=MIC_SETTINGS_PATH,
        win_hint="请打开：设置 → 隐私和安全性 → 麦克风 → 允许 CodeCoreAgent。",
        win_path="设置 → 隐私和安全性 → 麦克风 → CodeCoreAgent",
    )


def open_speech_settings() -> dict[str, Any]:
    """Jump to OS Privacy → Speech Recognition."""
    return _open_privacy_urls(
        _MAC_SPEECH_URLS,
        win_url="ms-settings:privacy-speechtyping",
        hint=SPEECH_SETTINGS_HINT,
        path=SPEECH_SETTINGS_PATH,
        win_hint="请打开：设置 → 隐私和安全性 → 语音 → 允许 CodeCoreAgent。",
        win_path="设置 → 隐私和安全性 → 语音 → CodeCoreAgent",
    )


def _open_privacy_urls(
    mac_urls: tuple[str, ...],
    *,
    win_url: str,
    hint: str,
    path: str,
    win_hint: str,
    win_path: str,
) -> dict[str, Any]:
    try:
        if sys.platform == "darwin":
            last_err = ""
            for url in mac_urls:
                res = subprocess.run(
                    ["open", url], capture_output=True, text=True, timeout=8, check=False,
                )
                if res.returncode == 0:
                    return {"ok": True, "url": url, "hint": hint, "path": path}
                last_err = (res.stderr or "").strip()[:120]
            subprocess.run(
                [
                    "open",
                    "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension",
                ],
                capture_output=True, timeout=8, check=False,
            )
            return {
                "ok": True,
                "url": "PrivacySecurity",
                "hint": hint,
                "path": path,
                "warning": last_err or "deep-link fallback",
            }
        if sys.platform == "win32":
            subprocess.run(
                ["cmd", "/c", "start", "", win_url],
                capture_output=True, timeout=8, check=False, shell=False,
            )
            return {"ok": True, "url": win_url, "hint": win_hint, "path": win_path}
        return {"ok": False, "error": "unsupported platform"}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "error": str(exc)[:180], "hint": hint}


def request_mic_access(timeout: float = _PROMPT_TIMEOUT) -> dict[str, Any]:
    """Ask the OS for microphone (and speech) access so CodeCoreAgent enters TCC.

    ``ok`` requires **both** mic and speech authorized on macOS.
    Timeouts stay short so the desktop UI bridge never freezes.
    """
    if sys.platform != "darwin":
        return {"ok": False, "status": "unknown", "speech_status": "unknown",
                "platform": sys.platform,
                "message": "请在浏览器权限或系统设置中允许麦克风"}

    timeout = max(1.0, min(float(timeout or _PROMPT_TIMEOUT), 12.0))
    before = _macos_status()
    if before == "authorized":
        granted = True
    elif before in {"denied", "restricted"}:
        granted = False
    else:
        granted = _request_av_mic_access(timeout=timeout)

    speech_before = _speech_status()
    if speech_before == "authorized":
        speech = "authorized"
    elif speech_before in {"denied", "restricted"}:
        speech = speech_before
    else:
        speech = _request_speech_access(timeout=timeout)

    after = _macos_status()
    mic_ok = after == "authorized" or bool(granted)
    speech_ok = speech == "authorized"
    ok = mic_ok and speech_ok
    if not mic_ok:
        message, path = MIC_SETTINGS_HINT, MIC_SETTINGS_PATH
    elif not speech_ok:
        message, path = SPEECH_SETTINGS_HINT, SPEECH_SETTINGS_PATH
    else:
        message, path = None, MIC_SETTINGS_PATH
    return {
        "ok": ok,
        "status": after,
        "speech_status": speech,
        "status_label": status_label(after),
        "speech_status_label": status_label(speech),
        "ready": ok,
        "registered": after != "not_determined" or speech != "not_determined",
        "granted": bool(granted),
        "message": message,
        "path": path,
    }


def ensure_mic_permission() -> dict[str, Any]:
    """Gate voice start without freezing the UI for tens of seconds."""
    info = mic_permission_status()
    status = info["status"]
    speech = str(info.get("speech_status") or "unknown")
    ready = bool(info.get("ready")) or (
        status == "authorized" and speech == "authorized"
    )
    if ready:
        return {"ok": True, "need_prompt": False, "open_settings": False, **info}

    # Only prompt when the OS has not decided yet; keep wait short.
    if status in {"not_determined", "unknown"} or speech in {"not_determined", "unknown"}:
        req = request_mic_access(timeout=_PROMPT_TIMEOUT)
        if req.get("ok"):
            return {
                "ok": True,
                "need_prompt": False,
                "open_settings": False,
                "status": req.get("status", "authorized"),
                "speech_status": req.get("speech_status", "authorized"),
                "status_label": req.get("status_label") or status_label("authorized"),
                "speech_status_label": req.get("speech_status_label")
                or status_label("authorized"),
                "ready": True,
                "platform": "darwin",
                "registered": True,
                "mic_path": MIC_SETTINGS_PATH,
                "speech_path": SPEECH_SETTINGS_PATH,
            }
        status = str(req.get("status") or _macos_status())
        speech = str(req.get("speech_status") or _speech_status())
        info = {
            "status": status,
            "speech_status": speech,
            "status_label": status_label(status),
            "speech_status_label": status_label(speech),
            "ready": False,
            "platform": "darwin",
            "registered": req.get("registered"),
            "mic_path": MIC_SETTINGS_PATH,
            "speech_path": SPEECH_SETTINGS_PATH,
        }
        if status == "authorized" and speech != "authorized":
            opened = open_speech_settings()
            return {
                "ok": False,
                "need_prompt": True,
                "open_settings": True,
                "opened_settings": bool(opened.get("ok")),
                "message": req.get("message") or SPEECH_SETTINGS_HINT,
                "path": opened.get("path") or SPEECH_SETTINGS_PATH,
                **{k: v for k, v in info.items() if k != "ok"},
            }

    if status in {"denied", "restricted"}:
        opened = open_mic_settings()
        return {
            "ok": False,
            "need_prompt": True,
            "open_settings": True,
            "opened_settings": bool(opened.get("ok")),
            "message": MIC_SETTINGS_HINT,
            "path": opened.get("path") or MIC_SETTINGS_PATH,
            **{k: v for k, v in info.items() if k != "ok"},
        }

    if speech in {"denied", "restricted"}:
        opened = open_speech_settings()
        return {
            "ok": False,
            "need_prompt": True,
            "open_settings": True,
            "opened_settings": bool(opened.get("ok")),
            "message": SPEECH_SETTINGS_HINT,
            "path": opened.get("path") or SPEECH_SETTINGS_PATH,
            **{k: v for k, v in info.items() if k != "ok"},
        }

    return {
        "ok": False,
        "need_prompt": True,
        "open_settings": False,
        "message": info.get("message") or MIC_SETTINGS_HINT,
        "path": MIC_SETTINGS_PATH,
        **info,
    }


def register_mic_with_tcc_async() -> None:
    """Fire-and-forget TCC registration after the desktop window is up."""
    if sys.platform != "darwin":
        return

    def _run() -> None:
        try:
            # Give WKWebView a moment to finish launching.
            time.sleep(1.0)
            info = mic_permission_status()
            if info.get("ready"):
                return
            status = info.get("status")
            speech = info.get("speech_status")
            if status == "not_determined" or speech in {"not_determined", "unknown"}:
                request_mic_access(timeout=12.0)
            elif status == "unknown":
                request_mic_access(timeout=8.0)
        except Exception:  # noqa: BLE001
            log.exception("mic TCC registration failed")

    threading.Thread(target=_run, daemon=True, name="cca-mic-tcc").start()


def _macos_status() -> str:
    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeAudio

        code = int(AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeAudio))
        return _STATUS.get(code, "unknown")
    except Exception:  # noqa: BLE001
        pass
    # Fallback without the AVFoundation wheel (tests / odd installs).
    try:
        import objc
        from Foundation import NSBundle

        bundle = NSBundle.bundleWithPath_(
            "/System/Library/Frameworks/AVFoundation.framework"
        )
        if bundle is None or not bundle.load():
            return "unknown"
        device = objc.lookUpClass("AVCaptureDevice")
        code = int(device.authorizationStatusForMediaType_("soun"))
        return _STATUS.get(code, "unknown")
    except Exception:  # noqa: BLE001
        return "unknown"


def _speech_status() -> str:
    try:
        from Speech import SFSpeechRecognizer

        code = int(SFSpeechRecognizer.authorizationStatus())
        return _STATUS.get(code, "unknown")
    except Exception:  # noqa: BLE001
        return "unknown"


def _request_av_mic_access(timeout: float) -> bool | None:
    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeAudio
    except Exception:  # noqa: BLE001
        log.exception("AVFoundation unavailable")
        return None

    status = int(AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeAudio))
    if status == 3:
        return True
    if status in {1, 2}:
        return False

    box: dict[str, bool] = {}
    ev = threading.Event()

    def handler(granted: bool) -> None:
        box["g"] = bool(granted)
        ev.set()

    def invoke() -> None:
        AVCaptureDevice.requestAccessForMediaType_completionHandler_(
            AVMediaTypeAudio, handler
        )

    _call_on_main(invoke)
    _wait_for(ev, timeout)
    return box.get("g")


def _request_speech_access(timeout: float = _PROMPT_TIMEOUT) -> str:
    try:
        from Speech import SFSpeechRecognizer
    except Exception:  # noqa: BLE001
        return "unknown"

    try:
        code = int(SFSpeechRecognizer.authorizationStatus())
    except Exception:  # noqa: BLE001
        return "unknown"
    if code == 3:
        return "authorized"
    if code in {1, 2}:
        return "denied"

    box: dict[str, int] = {}
    ev = threading.Event()

    def handler(status: int) -> None:
        box["s"] = int(status)
        ev.set()

    def invoke() -> None:
        SFSpeechRecognizer.requestAuthorization_(handler)

    _call_on_main(invoke)
    _wait_for(ev, timeout)
    if "s" in box:
        return _STATUS.get(box["s"], "unknown")
    # Dialog may still be pending; re-read current TCC state.
    return _speech_status()


def _call_on_main(fn: Callable[[], None]) -> None:
    if threading.current_thread() is threading.main_thread():
        fn()
        return
    try:
        from PyObjCTools import AppHelper

        AppHelper.callAfter(fn)
        return
    except Exception:  # noqa: BLE001
        pass
    try:
        from Foundation import NSOperationQueue

        NSOperationQueue.mainQueue().addOperationWithBlock_(fn)
        return
    except Exception:  # noqa: BLE001
        fn()


def _wait_for(ev: threading.Event, timeout: float) -> None:
    if threading.current_thread() is threading.main_thread():
        try:
            from Foundation import NSDate, NSDefaultRunLoopMode, NSRunLoop
        except Exception:  # noqa: BLE001
            ev.wait(timeout)
            return
        deadline = time.time() + max(0.5, timeout)
        while not ev.is_set() and time.time() < deadline:
            NSRunLoop.currentRunLoop().runMode_beforeDate_(
                NSDefaultRunLoopMode,
                NSDate.dateWithTimeIntervalSinceNow_(0.1),
            )
        return
    ev.wait(timeout)
