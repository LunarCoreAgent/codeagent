"""Always-on internal browser: live window on desktop, HTML fetch elsewhere."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable
from urllib.parse import urlparse

from codeagent.browser.js import SNAPSHOT_JS, click_js, fill_js, press_js, select_js
from codeagent.browser.snapshot import format_observe, normalize_url, snapshot_html

FetchFn = Callable[[str, int], tuple[str, str]]

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 "
    "CodeCoreAgent/0.40"
)


class _HttpOnlyRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects that leave http(s)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        parsed = urlparse(newurl)
        if parsed.scheme not in ("http", "https"):
            raise urllib.error.HTTPError(
                newurl, code, "redirect blocked", headers, fp,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_HttpOnlyRedirect)


def fetch_html(url: str, timeout: int = 30) -> tuple[str, str]:
    """GET ``url`` and return ``(final_url, html)``."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
        method="GET",
    )
    with _OPENER.open(req, timeout=timeout) as resp:
        raw = resp.read(2_000_000)
        final = resp.geturl()
        charset = resp.headers.get_content_charset() or "utf-8"
    return final, raw.decode(charset, errors="replace")


def _parse_snap(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    text = str(raw).strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"text": text[:4000], "nodes": []}
    return data if isinstance(data, dict) else {}


class InternalBrowser:
    """Session the ``browser`` tool drives.

    Desktop attaches a ``WebviewHost`` so the user sees a real in-app window.
    CLI / tests without a host use HTTP fetch (open page + click links).
    """

    def __init__(
        self,
        host: Any | None = None,
        fetcher: FetchFn | None = None,
    ) -> None:
        self.host = host
        self._fetch = fetcher or fetch_html
        self.url = ""
        self.title = ""
        self.text = ""
        self.nodes: list[dict[str, str]] = []
        self.backend = "idle"

    @property
    def has_gui(self) -> bool:
        return bool(self.host is not None and getattr(self.host, "has_gui", False))

    def status_text(self) -> str:
        if self.has_gui:
            where = "软件内浏览窗口（对话里调用 browser 即可开页/点击/填表，你能看见）"
        else:
            where = "内置抓取模式（开页、读内容、点链接；复杂点击请用桌面版窗口）"
        loc = f" 当前 {self.url}" if self.url else " 尚未打开页面"
        return f"内置浏览器已就绪：{where}。{loc}"

    def ui_state(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "excerpt": self.text[:1200],
            "nodes": self.nodes[:40],
            "backend": self.backend,
            "ready_text": self.status_text(),
        }

    def _apply(self, snap: dict[str, Any]) -> None:
        self.url = str(snap.get("url") or self.url)
        self.title = str(snap.get("title") or "")
        self.text = str(snap.get("text") or "")
        raw_nodes = snap.get("nodes") or []
        self.nodes = [n for n in raw_nodes if isinstance(n, dict)]

    def _observe_text(self) -> str:
        return format_observe({
            "url": self.url,
            "title": self.title,
            "text": self.text,
            "nodes": self.nodes,
        })

    def _find(self, target: str | None) -> dict[str, str] | None:
        if not target:
            return None
        key = target.strip()
        for node in self.nodes:
            if node.get("ref") == key or node.get("ref") == f"@{key.lstrip('@')}":
                return node
        if key.startswith("@"):
            return None
        for node in self.nodes:
            if key.lower() in (node.get("text") or "").lower():
                return node
        return None

    def _live_snapshot(self, timeout: int) -> bool:
        if not self.has_gui:
            return False
        wait = min(max(timeout, 3), 25)
        self.host.loaded.wait(timeout=wait)
        time.sleep(0.35)
        try:
            raw = self.host.eval_js(SNAPSHOT_JS, timeout=min(timeout, 20))
        except Exception:  # noqa: BLE001 — window may not be ready
            return False
        snap = _parse_snap(raw)
        if not snap:
            return False
        self._apply(snap)
        self.backend = "webview"
        return True

    def navigate_sync(self, url: str | None, timeout: int = 30) -> str:
        if not url:
            return "navigate 需要 url。"
        try:
            target = normalize_url(url)
        except ValueError as exc:
            return str(exc)

        from codeagent.browser.showcase import (
            discover_local_preview,
            preview_unavailable_html,
            probe_http,
        )

        # Dead localhost → white WKWebView. Probe first; fall back to a live port.
        from urllib.parse import urlparse

        host = (urlparse(target).hostname or "").lower()
        if host in ("127.0.0.1", "localhost", "0.0.0.0") and not probe_http(target):
            alt = discover_local_preview()
            if alt and alt.rstrip("/") != target.rstrip("/"):
                target = alt
            elif self.has_gui:
                try:
                    self.host.load_html(preview_unavailable_html(target), queued=True)
                    self.url = target
                    self.title = "预览未就绪"
                    self.text = f"无法连接 {target}"
                    self.nodes = []
                    self.backend = "webview"
                    try:
                        self.host.notify(**self.ui_state(), error=f"无法连接 {target}")
                    except Exception:  # noqa: BLE001
                        pass
                    return (
                        f"预览地址不可达：{target}（已显示说明页，避免白屏）。"
                        "请先启动 npm run dev / vite preview，或改用当前仍在监听的端口。"
                    )
                except Exception as exc:  # noqa: BLE001
                    return f"预览地址不可达：{target}（{exc}）"
            else:
                return f"预览地址不可达：{target}。请先启动本地开发服务器。"

        if self.has_gui:
            try:
                self.host.ensure_window(target, queued=True)
                if self._live_snapshot(timeout):
                    try:
                        self.host.notify(**self.ui_state())
                    except Exception:  # noqa: BLE001
                        pass
                    return self._observe_text()
            except Exception as exc:  # noqa: BLE001 — fall through to fetch
                live_err = str(exc)[:200]
            else:
                live_err = "浏览窗口尚未给出页面快照，改用抓取。"
        else:
            live_err = ""
        try:
            final, html = self._fetch(target, timeout)
        except urllib.error.HTTPError as exc:
            return f"打开失败 HTTP {exc.code}：{target}"
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            extra = f"（{live_err}）" if live_err else ""
            if self.has_gui:
                try:
                    self.host.load_html(preview_unavailable_html(target), queued=True)
                except Exception:  # noqa: BLE001
                    pass
            return f"打开失败：{reason}{extra}"
        except OSError as exc:
            return f"打开失败：{exc}"
        snap = snapshot_html(html, final)
        self._apply(snap)
        self.backend = "fetch"
        if self.has_gui:
            try:
                self.host.notify(**self.ui_state())
            except Exception:  # noqa: BLE001
                pass
        return self._observe_text()

    def observe_sync(self, timeout: int = 30) -> str:
        if self.has_gui and self.host.win is not None:
            if self._live_snapshot(timeout):
                return self._observe_text()
        if self.url:
            return self._observe_text()
        return "还没有打开页面。先 navigate。"

    def click_sync(self, target: str | None, timeout: int = 30) -> str:
        if self.has_gui:
            node = self._find(target)
            ref = (node or {}).get("ref") or (target or "").strip()
            if not ref:
                return "click 需要 target（observe 得到的 @eN）。"
            try:
                result = self.host.eval_js(click_js(ref), timeout=min(timeout, 20))
            except Exception as exc:  # noqa: BLE001
                return f"点击失败：{exc}"
            if str(result) == "missing":
                return f"页面上没有 {ref}。先 observe。"
            time.sleep(0.4)
            self._live_snapshot(timeout)
            try:
                self.host.notify(**self.ui_state())
            except Exception:  # noqa: BLE001
                pass
            return self._observe_text()
        node = self._find(target)
        if not node:
            return "click 需要 target（observe 得到的 @eN）。"
        href = node.get("href") or ""
        parsed = urlparse(href)
        if parsed.scheme in ("http", "https"):
            return self.navigate_sync(href, timeout=timeout)
        return (
            f"{node.get('ref')} 没有可跟随的链接。"
            "桌面版会打开内置浏览窗口，才能点按钮、填表。"
        )

    def fill_sync(self, target: str | None, value: str | None, timeout: int = 30) -> str:
        if value is None:
            return "fill 需要 target 和 value。"
        if not self.has_gui:
            return "填表需要桌面内置浏览窗口（或外接已登录浏览器）。"
        node = self._find(target)
        ref = (node or {}).get("ref") or (target or "").strip()
        if not ref:
            return "fill 需要 target（observe 得到的 @eN）。"
        try:
            result = self.host.eval_js(fill_js(ref, value), timeout=min(timeout, 20))
        except Exception as exc:  # noqa: BLE001
            return f"填表失败：{exc}"
        if str(result) == "missing":
            return f"页面上没有 {ref}。先 observe。"
        self._live_snapshot(timeout)
        return f"已填 {ref}\n\n{self._observe_text()}"

    def press_sync(self, value: str | None, timeout: int = 30) -> str:
        key = (value or "").strip() or "Enter"
        if not self.has_gui:
            return "按键需要桌面内置浏览窗口。"
        try:
            self.host.eval_js(press_js(key), timeout=min(timeout, 15))
        except Exception as exc:  # noqa: BLE001
            return f"按键失败：{exc}"
        time.sleep(0.3)
        self._live_snapshot(timeout)
        return self._observe_text()

    def select_sync(self, target: str | None, value: str | None, timeout: int = 30) -> str:
        if not target or value is None:
            return "select 需要 target 和 value。"
        if not self.has_gui:
            return "选择菜单需要桌面内置浏览窗口。"
        node = self._find(target)
        ref = (node or {}).get("ref") or target.strip()
        try:
            result = self.host.eval_js(select_js(ref, value), timeout=min(timeout, 15))
        except Exception as exc:  # noqa: BLE001
            return f"选择失败：{exc}"
        if str(result) == "missing":
            return f"页面上没有 {ref}。先 observe。"
        self._live_snapshot(timeout)
        return self._observe_text()

    def evaluate_sync(self, script: str | None, timeout: int = 30) -> str:
        if not script:
            return "evaluate 需要 script。"
        if not self.has_gui:
            return "执行页面脚本需要桌面内置浏览窗口。"
        try:
            raw = self.host.eval_js(script, timeout=min(timeout, 20))
        except Exception as exc:  # noqa: BLE001
            return f"evaluate 失败：{exc}"
        return str(raw)[:40_000]

    def stop_sync(self) -> str:
        if self.has_gui:
            try:
                self.host.close()
            except Exception:  # noqa: BLE001
                pass
        self.url = ""
        self.title = ""
        self.text = ""
        self.nodes = []
        self.backend = "idle"
        return "已关闭内置浏览窗口。"

    async def run(
        self,
        action: str,
        url: str | None = None,
        target: str | None = None,
        value: str | None = None,
        script: str | None = None,
        timeout: int = 30,
        **_: Any,
    ) -> str:
        import asyncio

        action = (action or "").strip().lower()
        wait = int(timeout or 30)
        if action == "status":
            return self.status_text()
        if action == "navigate":
            return await asyncio.to_thread(self.navigate_sync, url, wait)
        if action == "observe":
            return await asyncio.to_thread(self.observe_sync, wait)
        if action == "click":
            return await asyncio.to_thread(self.click_sync, target, wait)
        if action == "fill":
            return await asyncio.to_thread(self.fill_sync, target, value, wait)
        if action == "press":
            return await asyncio.to_thread(self.press_sync, value or target, wait)
        if action == "select":
            return await asyncio.to_thread(self.select_sync, target, value, wait)
        if action in ("evaluate", "script"):
            return await asyncio.to_thread(self.evaluate_sync, script, wait)
        if action == "screenshot":
            return "内置浏览窗口可直接看页面。截图请用外接 bsk，或描述 observe 摘要。"
        if action == "stop":
            return await asyncio.to_thread(self.stop_sync)
        return (
            f"未知 action：{action}。"
            "可用：status navigate observe click fill press select screenshot evaluate script stop"
        )
