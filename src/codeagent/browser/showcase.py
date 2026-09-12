"""Detect finished website work and open a local preview in the internal browser.

``file://`` is blocked by the browser engine — local sites must be served over HTTP.
"""

from __future__ import annotations

import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

_WEB_TASK = re.compile(
    r"网站|网页|官网|落地页|首页|前端|界面|改版|站点|页面|展示成品|预览|"
    r"website|landing|frontend|\bui\b|\bux\b|\bvite\b|\breact\b|\bvue\b|"
    r"next\.?js|nuxt|astro|svelte|\.html\b|css|tailwind",
    re.I,
)
_DONEISH = re.compile(
    r"完成|做完|已改|已写|建好|交付|成品|可以打开|预览地址|本地预览|"
    r"done|finished|shipped|ready|preview",
    re.I,
)
_LOCAL_URL = re.compile(
    r"https?://(?:127\.0\.0\.1|localhost|0\.0\.0\.0)(?::\d+)?(?:/[^\s\"'<>]*)?",
    re.I,
)
_DIST_CANDIDATES = (
    "dist",
    "build",
    "out",
    "public",
    ".output/public",
)

# port -> (site_root, Popen) — keep servers alive for the desktop session
_SERVERS: dict[int, tuple[Path, subprocess.Popen[Any]]] = {}


def looks_like_website_task(*parts: str) -> bool:
    """True when the user task / workspace smells like web UI work."""
    blob = " ".join(p for p in parts if p)
    return bool(blob and _WEB_TASK.search(blob))


def looks_like_website_finished(task: str, answer: str, *extra: str) -> bool:
    """Website-shaped work that also reads as finished / ready to show."""
    if not looks_like_website_task(task, answer, *extra):
        return False
    blob = f"{task}\n{answer}\n" + "\n".join(extra)
    return bool(_DONEISH.search(blob) or looks_like_website_task(task))


def extract_preview_urls(*texts: str) -> list[str]:
    """Collect localhost/127.0.0.1 http(s) URLs, newest last, unique."""
    found: list[str] = []
    seen: set[str] = set()
    for text in texts:
        if not text:
            continue
        for m in _LOCAL_URL.finditer(text):
            url = m.group(0).rstrip(").,;]")
            key = url.rstrip("/")
            if key in seen:
                continue
            seen.add(key)
            found.append(url)
    return found


def find_static_site_root(workspace: str | Path) -> Path | None:
    """Prefer built ``dist``/``build``/``out``, else a root ``index.html``."""
    root = Path(workspace).expanduser().resolve()
    if not root.is_dir():
        return None
    for name in _DIST_CANDIDATES:
        cand = root / name
        if (cand / "index.html").is_file():
            return cand
    # Nested one level (e.g. fujitennka-site/dist)
    try:
        for child in root.iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue
            for name in _DIST_CANDIDATES:
                cand = child / name
                if (cand / "index.html").is_file():
                    return cand
            if (child / "index.html").is_file():
                return child
    except OSError:
        pass
    if (root / "index.html").is_file():
        return root
    return None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


_COMMON_PORTS = (5173, 5174, 4173, 3000, 3001, 8080, 8000, 7100, 4174, 24678)


def probe_http(url: str, timeout: float = 1.5) -> bool:
    """True when ``url`` answers with an HTTP response (any status < 500)."""
    try:
        from urllib.parse import urlparse
        from urllib.request import Request, urlopen

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        req = Request(
            url,
            method="GET",
            headers={"User-Agent": "CodeCoreAgent-preview-probe/1.0"},
        )
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — local preview only
            code = getattr(resp, "status", None) or resp.getcode()
            return int(code) < 500
    except Exception:  # noqa: BLE001 — unreachable / TLS / timeout
        return False


def wait_http_ready(url: str, attempts: int = 12, delay: float = 0.15) -> bool:
    """Poll until the local preview answers."""
    import time

    for _ in range(max(1, attempts)):
        if probe_http(url):
            return True
        time.sleep(delay)
    return False


def discover_local_preview() -> str | None:
    """Find an already-running Vite/dev/static server on common ports."""
    for port in _COMMON_PORTS:
        for host in ("127.0.0.1", "localhost"):
            url = f"http://{host}:{port}/"
            if probe_http(url):
                return f"http://127.0.0.1:{port}/"
    return None


def pick_preview_url(
    *candidate_texts: str,
    workspace: str | Path | None = None,
) -> str | None:
    """Prefer a *reachable* preview URL; never open a dead localhost address.

    Order: extracted candidates (newest first) → common ports → static dist server.
    """
    candidates = list(reversed(extract_preview_urls(*candidate_texts)))
    for url in candidates:
        if probe_http(url):
            return url
    live = discover_local_preview()
    if live:
        return live
    if workspace is not None:
        served = ensure_local_preview(workspace)
        if served and wait_http_ready(served):
            return served
        return served
    return None


def preview_unavailable_html(url: str) -> str:
    """Friendly page shown instead of a blank white WKWebView."""
    safe = (
        url.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>预览未就绪</title>
<style>
  body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    background:linear-gradient(160deg,#f4f6f8,#e8eef5);color:#1c2430;min-height:100vh;
    display:flex;align-items:center;justify-content:center;padding:32px;box-sizing:border-box}}
  .card{{max-width:520px;background:#fff;border-radius:16px;padding:28px 32px;
    box-shadow:0 12px 40px rgba(28,36,48,.08)}}
  h1{{font-size:22px;margin:0 0 12px}}
  p{{line-height:1.65;margin:0 0 10px;color:#3a4656}}
  code{{background:#f0f3f7;padding:2px 7px;border-radius:6px;font-size:13px}}
  .hint{{font-size:13px;color:#6b7785;margin-top:16px}}
</style></head><body><div class="card">
<h1>预览地址打不开</h1>
<p>无法连接 <code>{safe}</code>，所以窗口是空白的。</p>
<p>请先在本机启动开发服务器（例如 <code>npm run dev -- --host 127.0.0.1</code>
或 <code>npx vite preview --host 127.0.0.1</code>），确认浏览器能打开后再展示。</p>
<p class="hint">CodeCoreAgent 会自动探测 5173 / 4173 / 3000 等常见端口；也可以让我重新 serve dist。</p>
</div></body></html>
"""


def ensure_local_preview(workspace: str | Path) -> str | None:
    """Serve a static site root over HTTP; return ``http://127.0.0.1:port/``."""
    site = find_static_site_root(workspace)
    if site is None:
        return None
    site = site.resolve()
    for port, (root, proc) in list(_SERVERS.items()):
        if proc.poll() is not None:
            _SERVERS.pop(port, None)
            continue
        if root == site:
            url = f"http://127.0.0.1:{port}/"
            if probe_http(url) or wait_http_ready(url, attempts=8):
                return url
            _SERVERS.pop(port, None)
            try:
                proc.terminate()
            except Exception:  # noqa: BLE001
                pass
    port = _free_port()
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
            cwd=str(site),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return None
    _SERVERS[port] = (site, proc)
    url = f"http://127.0.0.1:{port}/"
    wait_http_ready(url)
    return url


SHOWCASE_NUDGE = (
    "网站/前端成品需要展示给用户看。请立刻：\n"
    "1) 若本地预览未开，用 bash 后台启动（例：`npx --yes serve dist -l 5173`、"
    "`npm run preview -- --host 127.0.0.1 --port 5173`、"
    "或 `python -m http.server 8765 --bind 127.0.0.1`，命令末尾加 `&` 或用短超时）；\n"
    "2) 用 curl/bash 确认 http://127.0.0.1:端口/ 能打开，再调用 browser "
    "action=navigate（禁止 file://，禁止打开已退出的端口，否则用户只看到白屏）；\n"
    "3) 再简短总结。不要只文字描述，必须先打开内置浏览器展示成品。"
)
