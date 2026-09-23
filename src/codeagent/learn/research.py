"""Night-window web research: search then fetch readable pages."""

from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

USER_AGENT = "CodeCoreAgent-NightLearn/0.90 (+local desktop study)"
FETCH_LIMIT = 6000
SEARCH_LIMIT = 4
TIMEOUT = 12

_TAG_RE = re.compile(r"<[^>]+>")
_HREF_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)
_LITE_RE = re.compile(
    r'<a[^>]+rel="nofollow"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)


@dataclass
class WebHit:
    kind: str
    query: str
    title: str
    url: str
    snippet: str = ""


def _http_get(url: str, timeout: int = TIMEOUT) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(180_000)
        charset = "utf-8"
        ctype = resp.headers.get_content_charset() if hasattr(resp.headers, "get_content_charset") else None
        if ctype:
            charset = ctype
        return raw.decode(charset, errors="replace")


def _plain(blob: str, limit: int = FETCH_LIMIT) -> str:
    text = html.unescape(_TAG_RE.sub(" ", blob or ""))
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)[:limit]


def _safe_url(url: str) -> str:
    url = html.unescape((url or "").strip())
    if url.startswith("//duckduckgo.com/l/?"):
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse("https:" + url).query)
        url = (parsed.get("uddg") or [""])[0]
    if url.startswith("//"):
        url = "https:" + url
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return ""
    host = (parsed.hostname or "").lower().strip("[]")
    if not host or host in {"localhost", "127.0.0.1", "::1"}:
        return ""
    parts = host.split(".")
    if len(parts) == 4 and all(part.isdigit() for part in parts):
        first, second = int(parts[0]), int(parts[1])
        if first in {10, 127} or (first == 192 and second == 168):
            return ""
        if first == 172 and 16 <= second <= 31:
            return ""
        if first == 169 and second == 254:
            return ""
    return url


def _parse_ddg(markup: str) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for regex in (_HREF_RE, _LITE_RE):
        for href, title in regex.findall(markup or ""):
            url = _safe_url(href)
            name = _plain(title, 120)
            if url and name and (url, name) not in hits:
                hits.append((url, name))
            if len(hits) >= SEARCH_LIMIT:
                return hits
    return hits


def search_web(query: str, fetch: Callable[[str], str] | None = None) -> list[tuple[str, str]]:
    """Return (url, title) pairs. ``fetch`` is injectable for tests."""
    getter = fetch or _http_get
    q = urllib.parse.quote_plus((query or "").strip())
    if not q:
        return []
    urls = (
        f"https://html.duckduckgo.com/html/?q={q}",
        f"https://lite.duckduckgo.com/lite/?q={q}",
    )
    for target in urls:
        try:
            hits = _parse_ddg(getter(target))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            hits = []
        if hits:
            return hits
    try:
        wiki = (
            "https://zh.wikipedia.org/w/api.php?action=opensearch"
            f"&search={q}&limit=3&namespace=0&format=json"
        )
        data = json.loads(getter(wiki))
        titles = data[1] if isinstance(data, list) and len(data) > 1 else []
        links = data[3] if isinstance(data, list) and len(data) > 3 else []
        out: list[tuple[str, str]] = []
        for title, link in zip(titles, links):
            url = _safe_url(str(link))
            if url:
                out.append((url, str(title)))
        return out[:SEARCH_LIMIT]
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return []


def fetch_page(url: str, fetch: Callable[[str], str] | None = None) -> str:
    getter = fetch or _http_get
    safe = _safe_url(url)
    if not safe:
        return ""
    try:
        return _plain(getter(safe))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return ""


def research_query(
    kind: str,
    query: str,
    *,
    fetch: Callable[[str], str] | None = None,
    max_pages: int = 2,
) -> list[WebHit]:
    hits: list[WebHit] = []
    for url, title in search_web(query, fetch=fetch)[:max_pages]:
        body = fetch_page(url, fetch=fetch)
        if not body:
            continue
        hits.append(WebHit(
            kind=kind,
            query=query,
            title=title[:160],
            url=url,
            snippet=body[:FETCH_LIMIT],
        ))
    return hits
