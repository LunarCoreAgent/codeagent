"""Desktop window launcher (pywebview). Import webview lazily so the package
works without the ``desktop`` extra installed."""

from __future__ import annotations

import sys
from pathlib import Path

from codeagent.desktop.api import DesktopAPI, DesktopConfig
from codeagent.desktop.brand import APP_NAME
from codeagent.desktop.brand_mark import MARK_URI
from codeagent.desktop.ui import HTML


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

    api = DesktopAPI(root=root)
    window = webview.create_window(
        APP_NAME,
        html=_themed_html(),
        js_api=api,
        width=1280,
        height=840,
        min_size=(960, 640),
        text_select=True,
    )
    api._window = window
    webview.start()
    return 0
