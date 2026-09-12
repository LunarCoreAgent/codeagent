"""Desktop window launcher (pywebview). Import webview lazily so the package
works without the ``desktop`` extra installed."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from codeagent.desktop.api import DesktopAPI, DesktopConfig
from codeagent.desktop.brand import APP_NAME
from codeagent.desktop.brand_mark import MARK_URI
from codeagent.desktop.ui import HTML


def _ensure_os_path() -> None:
    """Finder/PyInstaller apps often ship a PATH without pbcopy/clip."""
    if sys.platform == "win32":
        root = os.environ.get("SystemRoot", r"C:\Windows")
        extras = [rf"{root}\System32", rf"{root}\System32\WindowsPowerShell\v1.0"]
        path = os.environ.get("PATH", "")
        bits = path.split(os.pathsep) if path else []
        lower = {b.lower() for b in bits}
        prefix = [e for e in extras if e.lower() not in lower]
        os.environ["PATH"] = os.pathsep.join(prefix + bits)
        return
    extras = "/usr/bin:/bin:/usr/sbin:/sbin"
    path = os.environ.get("PATH") or ""
    os.environ["PATH"] = extras + (":" + path if path else "")


def apply_webkit_clipboard_prefs(browser_view) -> None:
    """WKWebView.paste: is a no-op unless DOMPasteAllowed is on."""
    try:
        prefs = browser_view.webview.configuration().preferences()
    except Exception:  # noqa: BLE001
        return
    for key in (
        "javaScriptCanAccessClipboard",
        "DOMPasteAllowed",
        "mediaDevicesEnabled",
        "mediaStreamEnabled",
    ):
        try:
            prefs.setValue_forKey_(True, key)
        except Exception:  # noqa: BLE001
            pass
    setter = getattr(prefs, "setJavaScriptCanAccessClipboard_", None)
    if setter is not None:
        try:
            setter(True)
        except Exception:  # noqa: BLE001
            pass


def _patch_media_capture_delegate(browser_view_cls) -> None:
    """Auto-grant getUserMedia so WKWebView does not fake a mic denial."""
    delegate_cls = getattr(browser_view_cls, "BrowserDelegate", None)
    if delegate_cls is None or getattr(delegate_cls, "_cca_media_capture", False):
        return

    def webView_requestMediaCapturePermissionForOrigin_initiatedByFrame_type_decisionHandler_(  # noqa: N802
        self, webview, origin, frame, capture_type, decision_handler,
    ):
        # WKPermissionDecisionGrant == 1
        try:
            decision_handler(1)
        except Exception:  # noqa: BLE001
            try:
                decision_handler(True)
            except Exception:  # noqa: BLE001
                pass

    delegate_cls.webView_requestMediaCapturePermissionForOrigin_initiatedByFrame_type_decisionHandler_ = (  # type: ignore[attr-defined]
        webView_requestMediaCapturePermissionForOrigin_initiatedByFrame_type_decisionHandler_
    )
    delegate_cls._cca_media_capture = True  # type: ignore[attr-defined]


def patch_webkit_clipboard() -> bool:
    """pywebview cocoa intercepts ⌘C/⌘V but never enables WebKit paste."""
    if sys.platform != "darwin":
        return False
    try:
        from webview.platforms.cocoa import BrowserView
    except Exception:  # noqa: BLE001
        return False
    original = BrowserView.__init__
    if getattr(original, "_cca_clipboard", False):
        return True

    def wrapped(self, window):
        original(self, window)
        apply_webkit_clipboard_prefs(self)

    wrapped._cca_clipboard = True  # type: ignore[attr-defined]
    BrowserView.__init__ = wrapped  # type: ignore[method-assign]
    try:
        _patch_media_capture_delegate(BrowserView)
    except Exception:  # noqa: BLE001
        pass
    return True


def _system_light() -> bool:
    """macOS 系统外观检测（auto 主题用）：无 AppleInterfaceStyle 键 = 浅色。"""
    if sys.platform != "darwin":
        return False
    import subprocess

    try:
        subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                       capture_output=True, check=True, timeout=2)
        return False  # 键存在 → 深色
    except (subprocess.CalledProcessError, FileNotFoundError,
            subprocess.TimeoutExpired):
        return True


def _themed_html() -> str:
    """把已保存主题直接渲染进 HTML——webview 隐私模式下 localStorage
    重启即清（甚至抛异常），服务端注入是唯一可靠的启动主题来源。"""
    theme = DesktopConfig.load().theme
    light = theme == "light" or (theme == "auto" and _system_light())
    html = HTML.replace("__BRAND_MARK_SRC__", MARK_URI)
    if light:
        return html.replace("<body>", '<body class="light">', 1)
    return html


def run_desktop(root: Path | None = None) -> int:
    """Open the codeagent desktop window. Blocks until the window closes."""
    if "--version" in sys.argv:  # CI smoke test for the frozen app
        from codeagent.releases import latest

        rel = latest()
        print(f"{APP_NAME} v{rel.version}")
        return 0

    try:
        import webview
    except ImportError:
        print(
            "桌面版需要 pywebview：pip install codeagent[desktop]\n"
            "或下载预编译桌面安装包。",
            file=sys.stderr,
        )
        return 1

    _ensure_os_path()
    patch_webkit_clipboard()
    api = DesktopAPI(root=root)
    window = webview.create_window(
        APP_NAME,
        html=_themed_html(),
        js_api=api,
        width=1440,
        height=900,
        min_size=(1040, 700),
        text_select=True,
    )
    api._window = window

    def _on_shown() -> None:
        # Register with macOS TCC so CodeCoreAgent appears under 麦克风.
        from codeagent.desktop.mic import register_mic_with_tcc_async

        register_mic_with_tcc_async()

    try:
        window.events.shown += _on_shown
    except Exception:  # noqa: BLE001
        pass

    storage = Path.home() / ".codeagent" / "webview"
    storage.mkdir(parents=True, exist_ok=True)
    webview.start(private_mode=False, storage_path=str(storage))
    return 0
