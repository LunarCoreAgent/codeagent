"""Doctor health check: local, no secrets, fail only on hard errors."""

from __future__ import annotations

from pathlib import Path

from codeagent.doctor import run_doctor


def test_doctor_passes_on_existing_workspace(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEAGENT_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    monkeypatch.delenv("AIHUBMIX_API_KEY", raising=False)
    monkeypatch.delenv("ONEAPI_API_KEY", raising=False)
    report = run_doctor(tmp_path, probe=False, settings_path=tmp_path / "missing.json")
    by_name = {c.name: c for c in report.checks}
    assert by_name["python"].status == "ok"
    assert by_name["workspace"].status == "ok"
    assert by_name["tools"].status == "ok"
    assert by_name["credentials"].status == "warn"
    assert report.ok is True
    assert report.exit_code == 0
    payload = report.to_dict()
    assert payload["ok"] is True
    assert "version" in payload
    assert all("status" in c for c in payload["checks"])


def test_doctor_fails_on_missing_workspace(tmp_path):
    missing = tmp_path / "no-such-dir"
    report = run_doctor(missing, probe=False, settings_path=tmp_path / "s.json")
    by_name = {c.name: c for c in report.checks}
    assert by_name["workspace"].status == "fail"
    assert report.ok is False
    assert report.exit_code == 1


def test_doctor_reports_configured_keys_without_values(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-should-never-appear")
    report = run_doctor(tmp_path, probe=False, settings_path=tmp_path / "s.json")
    cred = next(c for c in report.checks if c.name == "credentials")
    assert cred.status == "ok"
    assert "openai" in cred.message
    blob = str(report.to_dict())
    assert "sk-secret" not in blob


def test_doctor_does_not_probe_by_default(tmp_path, monkeypatch):
    called = []

    def boom(*_a, **_k):
        called.append(True)
        raise AssertionError("network must not run without --probe")

    monkeypatch.setattr("codeagent.doctor.socket.create_connection", boom)
    report = run_doctor(tmp_path, probe=False)
    assert called == []
    assert all(c.name != "endpoints" for c in report.checks)


def test_doctor_probe_records_local_endpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "codeagent.doctor.socket.create_connection",
        lambda *a, **k: __import__("contextlib").nullcontext(),
    )
    report = run_doctor(tmp_path, probe=True)
    endpoints = next(c for c in report.checks if c.name == "endpoints")
    assert endpoints.status == "ok"
    assert "Ollama" in endpoints.detail["reachable"]
