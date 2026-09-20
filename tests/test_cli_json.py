"""CLI --json envelope for version / settings / doctor."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from codeagent import __version__
from codeagent.cli.main import app

runner = CliRunner()


def test_version_json_envelope():
    result = runner.invoke(app, ["version", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["version"] == __version__
    assert payload["data"]["version"] == __version__
    assert "highlights" in payload["data"]
    assert "error" not in payload


def test_settings_show_json_empty(monkeypatch):
    from codeagent.settings import Settings

    monkeypatch.setattr("codeagent.cli.main.Settings.load", lambda path=None: Settings())
    result = runner.invoke(app, ["settings", "show", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["settings"] is None
    assert payload["data"]["version"] == __version__


def test_doctor_json_exit_zero_on_workspace(tmp_path):
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"])
    payload = json.loads(result.stdout)
    assert "ok" in payload
    assert payload["version"] == __version__
    assert payload["data"]["checks"]
    names = {c["name"] for c in payload["data"]["checks"]}
    assert "python" in names
    assert "workspace" in names
    if payload["ok"]:
        assert result.exit_code == 0
    else:
        assert result.exit_code == 1
