"""Browser bridge: detect backend, parse session, call bsk without a real browser."""

from __future__ import annotations

from codeagent.tools.browser import (
    BrowserTool,
    INSTALL_HINT,
    detect_browser_backend,
    parse_bsk_session_id,
)


def test_parse_bsk_session_id():
    assert parse_bsk_session_id("Started session: abcd\n") == "abcd"
    assert parse_bsk_session_id("session id wxyz ready") == "wxyz"


def test_detect_prefers_bsk(monkeypatch):
    monkeypatch.setattr(
        "codeagent.tools.browser.shutil.which",
        lambda name: "/usr/bin/bsk" if name == "bsk" else None,
    )
    assert detect_browser_backend() == "bsk"


async def test_status_without_bridge(monkeypatch, tmp_path):
    monkeypatch.setattr("codeagent.tools.browser.shutil.which", lambda _n: None)
    tool = BrowserTool(session_path=tmp_path / "sid")
    text = await tool.execute(action="status")
    assert "BrowserSkill" in text
    assert "ego-lite" in text
    assert "github.com" in text


async def test_navigate_without_bridge_explains_install(monkeypatch, tmp_path):
    monkeypatch.setattr("codeagent.tools.browser.shutil.which", lambda _n: None)
    tool = BrowserTool(session_path=tmp_path / "sid")
    text = await tool.execute(action="navigate", url="https://example.com")
    assert text == INSTALL_HINT


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
