"""GUI-thread host for the software's own pywebview browser window.

Agent tools run on a worker thread. Window create / load_url / evaluate_js
must happen on the GUI thread, so jobs are queued and drained by
``pump()`` (called from a short JS interval in the main window).
"""

from __future__ import annotations

import queue
import threading
from concurrent.futures import Future
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class WebviewHost:
    """Own a CodeCoreAgent browser window and marshal work onto the GUI thread."""

    def __init__(self, push: Callable[..., None], title: str = "CodeCoreAgent 浏览器") -> None:
        self._push = push
        self.title = title
        self.win: Any = None
        self.loaded = threading.Event()
        self._q: queue.Queue[tuple[Callable[[], Any], Future[Any]]] = queue.Queue()
        # Desktop always has a GUI thread (main pywebview window + browser_pump).
        # Do not wait for the first pump — otherwise chat-page navigate falls back
        # to HTTP-only mode and never opens the live window.
        self._gui_ready = True

    @property
    def has_gui(self) -> bool:
        return True

    def notify(self, **data: Any) -> None:
        self._push("browser", **data)

    def pump(self) -> int:
        """Run queued GUI jobs. Call from the pywebview JS bridge (GUI thread)."""
        n = 0
        self._gui_ready = True
        while True:
            try:
                fn, fut = self._q.get_nowait()
            except queue.Empty:
                return n
            try:
                fut.set_result(fn())
            except Exception as exc:  # noqa: BLE001 — surface to the waiting worker
                fut.set_exception(exc)
            n += 1

    def call(self, fn: Callable[[], T], timeout: float = 60) -> T:
        fut: Future[T] = Future()
        self._q.put((fn, fut))
        return fut.result(timeout=timeout)

    def _on_closed(self) -> None:
        self.win = None

    def ensure_window(self, url: str, queued: bool = True) -> None:
        """Create or reuse the live browser window and load ``url``."""

        def job() -> None:
            import webview

            target = url or "about:blank"
            if self.win is None:
                self.loaded.clear()
                self.win = webview.create_window(
                    self.title, target, width=1100, height=800,
                )
                try:
                    self.win.events.loaded += lambda: self.loaded.set()
                    self.win.events.closed += self._on_closed
                except Exception:  # noqa: BLE001 — event API varies by backend
                    pass
            else:
                self.loaded.clear()
                self.win.load_url(target)
                try:
                    self.win.show()
                except Exception:  # noqa: BLE001
                    pass

        if queued:
            self.call(job)
        else:
            job()
            self._gui_ready = True

    def load_html(self, html: str, queued: bool = True) -> None:
        """Show inline HTML (used for unreachable-preview error pages)."""

        def job() -> None:
            import webview

            if self.win is None:
                self.loaded.clear()
                self.win = webview.create_window(
                    self.title, html=html, width=1100, height=800,
                )
                try:
                    self.win.events.loaded += lambda: self.loaded.set()
                    self.win.events.closed += self._on_closed
                except Exception:  # noqa: BLE001
                    pass
                self.loaded.set()
                return
            self.loaded.clear()
            try:
                self.win.load_html(html)
            except Exception:  # noqa: BLE001 — some backends only have load_url
                import tempfile
                from pathlib import Path

                path = Path(tempfile.gettempdir()) / "codeagent-preview-error.html"
                path.write_text(html, encoding="utf-8")
                # file:// is blocked in agent navigate; GUI host may still load it
                self.win.load_url(path.as_uri())
            try:
                self.win.show()
            except Exception:  # noqa: BLE001
                pass
            self.loaded.set()

        if queued:
            self.call(job)
        else:
            job()
            self._gui_ready = True

    def eval_js(self, script: str, timeout: float = 30) -> Any:
        def job() -> Any:
            if self.win is None:
                return None
            return self.win.evaluate_js(script)

        return self.call(job, timeout=timeout)

    def close(self) -> None:
        def job() -> None:
            win = self.win
            self.win = None
            if win is None:
                return
            try:
                win.destroy()
            except Exception:  # noqa: BLE001
                try:
                    win.hide()
                except Exception:  # noqa: BLE001
                    pass

        try:
            self.call(job, timeout=8)
        except Exception:  # noqa: BLE001
            self.win = None
