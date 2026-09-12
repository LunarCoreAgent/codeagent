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
            return f"http://127.0.0.1:{port}/"
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
    return f"http://127.0.0.1:{port}/"


SHOWCASE_NUDGE = (
    "网站/前端成品需要展示给用户看。请立刻：\n"
    "1) 若本地预览未开，用 bash 后台启动（例：`npx --yes serve dist -l 5173`、"
    "`npm run preview -- --host 127.0.0.1 --port 5173`、"
    "或 `python -m http.server 8765 --bind 127.0.0.1`，命令末尾加 `&` 或用短超时）；\n"
    "2) 调用 browser，action=navigate，url 填 http://127.0.0.1:端口/ "
    "（禁止 file://）；\n"
    "3) 再简短总结。不要只文字描述，必须先打开内置浏览器展示成品。"
)
