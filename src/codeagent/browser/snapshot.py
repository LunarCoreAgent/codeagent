"""Turn HTML into observe text with @eN refs the agent can click."""

from __future__ import annotations

import html as htmlmod
import re
from typing import Any
from urllib.parse import urljoin, urlparse

_SKIP = re.compile(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>")
_TAG = re.compile(r"(?is)<[^>]+>")
_TITLE = re.compile(r"(?is)<title[^>]*>(.*?)</title>")
_A = re.compile(
    r"(?is)<a\s[^>]*?href\s*=\s*[\"']([^\"']+)[\"'][^>]*>(.*?)</a>"
)
_BUTTON = re.compile(r"(?is)<button\b([^>]*)>(.*?)</button>")
_INPUT = re.compile(r"(?is)<input\b([^>]*)/?>")
_TEXTAREA = re.compile(r"(?is)<textarea\b([^>]*)>(.*?)</textarea>")
_SELECT = re.compile(r"(?is)<select\b([^>]*)>(.*?)</select>")
_ATTR = re.compile(r"""(?is)([^\s=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|(\S+)))?""")
_ENTITIES = {
    "&nbsp;": " ",
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
}

MAX_NODES = 80
MAX_TEXT = 6000


def normalize_url(url: str) -> str:
    """Require http(s). Bare hosts get https://."""
    raw = (url or "").strip()
    if not raw:
        raise ValueError("navigate 需要 url。")
    lowered = raw.lower()
    if lowered.startswith("about:"):
        return raw
    if lowered.startswith(("javascript:", "data:", "file:", "vbscript:")):
        raise ValueError("内置浏览器只打开 http/https 页面。")
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("内置浏览器只打开 http/https 页面。")
    if not parsed.netloc:
        raise ValueError("url 无效。")
    return raw


def _attrs(blob: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for match in _ATTR.finditer(blob or ""):
        key = match.group(1).lower()
        val = match.group(2) or match.group(3) or match.group(4) or ""
        out[key] = htmlmod.unescape(val)
    return out


def _plain(chunk: str) -> str:
    chunk = _SKIP.sub(" ", chunk or "")
    chunk = _TAG.sub(" ", chunk)
    for src, dst in _ENTITIES.items():
        chunk = chunk.replace(src, dst)
    chunk = htmlmod.unescape(chunk)
    return re.sub(r"\s+", " ", chunk).strip()


def snapshot_html(html: str, url: str = "") -> dict[str, Any]:
    """Extract title, readable text, and interactive nodes."""
    title_m = _TITLE.search(html or "")
    title = _plain(title_m.group(1)) if title_m else ""
    nodes: list[dict[str, str]] = []

    def add(tag: str, text: str, **extra: str) -> None:
        if len(nodes) >= MAX_NODES:
            return
        ref = f"@e{len(nodes) + 1}"
        item = {"ref": ref, "tag": tag, "text": (text or "")[:80]}
        for key, val in extra.items():
            if val:
                item[key] = val
        nodes.append(item)

    for href, inner in _A.findall(html or ""):
        abs_href = urljoin(url, htmlmod.unescape(href).strip())
        if abs_href.lower().startswith("javascript:"):
            continue
        add("a", _plain(inner) or abs_href, href=abs_href)

    for attr_blob, inner in _BUTTON.findall(html or ""):
        info = _attrs(attr_blob)
        add("button", _plain(inner) or info.get("aria-label") or info.get("name") or "button",
            type=info.get("type", "submit"))

    for attr_blob in _INPUT.findall(html or ""):
        info = _attrs(attr_blob)
        if info.get("type", "").lower() in {"hidden", "submit", "button", "image"}:
            kind = info.get("type", "text").lower()
            if kind in {"submit", "button", "image"}:
                add("input", info.get("value") or info.get("name") or kind,
                    type=kind, name=info.get("name", ""))
            continue
        label = info.get("placeholder") or info.get("aria-label") or info.get("name") or info.get("type") or "input"
        add("input", label, type=info.get("type", "text"), name=info.get("name", ""),
            value=info.get("value", ""))

    for attr_blob, inner in _TEXTAREA.findall(html or ""):
        info = _attrs(attr_blob)
        add("textarea", info.get("placeholder") or info.get("name") or _plain(inner)[:40] or "textarea",
            name=info.get("name", ""))

    for attr_blob, _inner in _SELECT.findall(html or ""):
        info = _attrs(attr_blob)
        add("select", info.get("name") or info.get("aria-label") or "select",
            name=info.get("name", ""))

    text = _plain(_SKIP.sub(" ", html or ""))[:MAX_TEXT]
    return {"url": url, "title": title, "text": text, "nodes": nodes}


def format_observe(snap: dict[str, Any]) -> str:
    """bsk-like observe dump the model already knows how to read."""
    url = str(snap.get("url") or "")
    title = str(snap.get("title") or "")
    lines = [f"url: {url}", f"title: {title}"]
    for node in snap.get("nodes") or []:
        ref = node.get("ref", "")
        tag = node.get("tag", "")
        text = node.get("text") or ""
        extra = node.get("href") or node.get("name") or node.get("type") or ""
        piece = f"{ref} {tag} \"{text}\""
        if extra:
            piece += f" {extra}"
        lines.append(piece)
    body = str(snap.get("text") or "").strip()
    if body:
        lines.append("")
        lines.append(body)
    return "\n".join(lines).strip()
