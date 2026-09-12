"""Browser bridge: internal engine, optional bsk, parse session."""

from __future__ import annotations

import pytest

from codeagent.browser.snapshot import format_observe, normalize_url, snapshot_html
from codeagent.tools.browser import (
    BrowserTool,
    INSTALL_HINT,
    detect_browser_backend,
    parse_bsk_session_id,
)


EXAMPLE_HTML = """
<html><head><title>Example Domain</title></head>
<body>
<h1>Example Domain</h1>
<p>This domain is for use in documentation examples.</p>
<a href="https://www.iana.org/domains/example">More information</a>
<input type="text" name="q" placeholder="search">
<button type="submit">Go</button>
</body></html>
"""


def test_parse_bsk_session_id():
    assert parse_bsk_session_id("Started session: abcd\n") == "abcd"
    assert parse_bsk_session_id("session id wxyz ready") == "wxyz"


def test_detect_prefers_bsk(monkeypatch):
    monkeypatch.setattr(
        "codeagent.tools.browser.shutil.which",
        lambda name: "/usr/bin/bsk" if name == "bsk" else None,
    )
    assert detect_browser_backend() == "bsk"


def test_normalize_url():
    assert normalize_url("example.com") == "https://example.com"
    with pytest.raises(ValueError):
        normalize_url("file:///etc/passwd")
    with pytest.raises(ValueError):
        normalize_url("javascript:alert(1)")


def test_snapshot_html_assigns_refs():
    snap = snapshot_html(EXAMPLE_HTML, "https://example.com")
    assert snap["title"] == "Example Domain"
    assert snap["nodes"][0]["ref"] == "@e1"
    assert snap["nodes"][0]["href"] == "https://www.iana.org/domains/example"
    text = format_observe(snap)
    assert "@e1" in text
    assert "Example Domain" in text


async def test_status_without_bridge(monkeypatch, tmp_path):
    monkeypatch.setattr("codeagent.tools.browser.shutil.which", lambda _n: None)
    tool = BrowserTool(session_path=tmp_path / "sid")
    text = await tool.execute(action="status")
    assert "内置浏览器" in text
    assert "BrowserSkill" in text
    assert "ego-lite" in text
    assert "github.com" in text
    assert INSTALL_HINT.split("\n")[0] in text


async def test_navigate_without_bridge_uses_internal(monkeypatch, tmp_path):
    monkeypatch.setattr("codeagent.tools.browser.shutil.which", lambda _n: None)
    monkeypatch.setattr(
        "codeagent.browser.engine.fetch_html",
        lambda url, timeout=30: (url, EXAMPLE_HTML),
    )
    tool = BrowserTool(session_path=tmp_path / "sid")
    text = await tool.execute(action="navigate", url="https://example.com")
    assert "Example Domain" in text
    assert "@e1" in text
    assert "iana.org" in text


async def test_click_link_in_fetch_mode(monkeypatch, tmp_path):
    monkeypatch.setattr("codeagent.tools.browser.shutil.which", lambda _n: None)
    pages = {
        "https://example.com": EXAMPLE_HTML,
        "https://www.iana.org/domains/example": (
            "<html><head><title>IANA</title></head><body><p>IANA page</p></body></html>"
        ),
    }
    monkeypatch.setattr(
        "codeagent.browser.engine.fetch_html",
        lambda url, timeout=30: (url, pages[url]),
    )
    tool = BrowserTool(session_path=tmp_path / "sid")
    await tool.execute(action="navigate", url="https://example.com")
    text = await tool.execute(action="click", target="@e1")
    assert "IANA" in text


async def test_bsk_navigate_starts_session(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "codeagent.tools.browser.shutil.which",
        lambda name: "/usr/bin/bsk" if name == "bsk" else None,
    )
    calls: list[list[str]] = []

    async def fake_run(self, args, stdin=None, timeout=90):
        calls.append(args)
        if args[:3] == ["bsk", "session", "start"]:
            return "session id abcd\n"
        if args[:2] == ["bsk", "navigate"]:
            return "opened"
        if args[:2] == ["bsk", "observe"]:
            return '@e1 link "Example"'
        return "ok"

    monkeypatch.setattr(BrowserTool, "_run", fake_run)
    tool = BrowserTool(session_path=tmp_path / "sid")
    text = await tool.execute(action="navigate", url="https://example.com")
    assert "abcd" in (tmp_path / "sid").read_text()
    assert any(c[:2] == ["bsk", "navigate"] for c in calls)
    assert "@e1" in text


def test_default_tools_include_browser():
    from codeagent.tools import default_tools

    registry = default_tools()
    assert registry.get("browser") is not None
