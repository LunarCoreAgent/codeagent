"""Phone / tablet USB install & smoke-test bridge."""

from __future__ import annotations

from pathlib import Path

import pytest

from codeagent.phone.bridge import (
    Device,
    PhoneBridge,
    list_devices,
    run_action,
    status_text,
)
from codeagent.tools import default_tools
from codeagent.tools.phone import PhoneTool


def test_default_tools_include_phone(tmp_path: Path):
    reg = default_tools(tmp_path)
    assert reg.get("phone") is not None


def test_phone_tool_status_risk_is_read_only():
    tool = PhoneTool()
    assert tool.risk_for({"action": "status"}).name == "READ_ONLY"
    assert tool.risk_for({"action": "install"}).name == "EXECUTE"
    assert tool.risk_for({"action": "uninstall"}).name == "DESTRUCTIVE"


@pytest.mark.asyncio
async def test_phone_status_mentions_actions():
    text = await PhoneTool().execute(action="status")
    assert "hdc" in text.lower() or "adb" in text.lower() or "真机" in text or "未找到" in text
    assert "install" in text


def test_list_devices_parses_hdc(monkeypatch):
    def fake_run(args, timeout=120.0, input_text=None):
        return 0, "ABC123\nDEF456\n"

    monkeypatch.setattr("codeagent.phone.bridge._run", fake_run)
    devices = list_devices("hdc", "/fake/hdc")
    assert [d.serial for d in devices] == ["ABC123", "DEF456"]


def test_list_devices_parses_adb(monkeypatch):
    def fake_run(args, timeout=120.0, input_text=None):
        return 0, (
            "List of devices attached\n"
            "emulator-5554 device product:sdk model:Pixel_6 device:emu\n"
            "dead unauthorized\n"
        )

    monkeypatch.setattr("codeagent.phone.bridge._run", fake_run)
    devices = list_devices("adb", "/fake/adb")
    assert len(devices) == 1
    assert devices[0].serial == "emulator-5554"
    assert "Pixel" in devices[0].label


def test_install_requires_file(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "codeagent.phone.bridge.find_bridge",
        lambda prefer="auto": PhoneBridge("hdc", "/fake/hdc", Device("T1", "hdc")),
    )
    monkeypatch.setattr(
        "codeagent.phone.bridge.list_devices",
        lambda backend, exe: [Device("T1", "hdc")],
    )
    out = run_action("install", path=str(tmp_path / "missing.hap"))
    assert "不存在" in out


def test_install_calls_hdc(monkeypatch, tmp_path: Path):
    hap = tmp_path / "app.hap"
    hap.write_bytes(b"hap")
    calls: list[list[str]] = []

    def fake_run(args, timeout=120.0, input_text=None):
        calls.append(list(args))
        return 0, "install bundle successfully"

    monkeypatch.setattr("codeagent.phone.bridge._run", fake_run)
    monkeypatch.setattr(
        "codeagent.phone.bridge.find_bridge",
        lambda prefer="auto": PhoneBridge("hdc", "/fake/hdc"),
    )
    monkeypatch.setattr(
        "codeagent.phone.bridge.list_devices",
        lambda backend, exe: [Device("T1", "hdc")],
    )
    out = run_action("install", path=str(hap), prefer="hdc")
    assert "install bundle successfully" in out
    assert any("install" in c for c in calls)
    assert any(str(hap) in c for c in calls)


def test_start_harmony_aa(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(args, timeout=120.0, input_text=None):
        calls.append(list(args))
        return 0, "start ability successfully"

    monkeypatch.setattr("codeagent.phone.bridge._run", fake_run)
    monkeypatch.setattr(
        "codeagent.phone.bridge.find_bridge",
        lambda prefer="auto": PhoneBridge("hdc", "/fake/hdc"),
    )
    monkeypatch.setattr(
        "codeagent.phone.bridge.list_devices",
        lambda backend, exe: [Device("T1", "hdc")],
    )
    out = run_action("start", package="com.agent.lunarcore", ability="EntryAbility")
    assert "start ability successfully" in out
    flat = " ".join(calls[-1])
    assert "aa" in flat and "start" in flat and "com.agent.lunarcore" in flat


def test_status_text_lists_actions():
    text = status_text("auto")
    assert "install" in text
