"""Fused official Node.js runtime resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from codeagent.node_runtime import (
    NODE_VERSION,
    archive_name,
    augment_env,
    bindir,
    ensure_installed,
    resolve_launcher,
)


def test_archive_name_matches_official_layout():
    assert archive_name("darwin", "arm64") == f"node-v{NODE_VERSION}-darwin-arm64.tar.gz"
    assert archive_name("darwin", "x86_64") == f"node-v{NODE_VERSION}-darwin-x64.tar.gz"
    assert archive_name("win32", "amd64") == f"node-v{NODE_VERSION}-win-x64.zip"
    assert archive_name("linux", "aarch64") == f"node-v{NODE_VERSION}-linux-arm64.tar.xz"


def test_resolve_launcher_prefers_fused_tree(monkeypatch, tmp_path: Path):
    folder = tmp_path / "bin"
    folder.mkdir()
    node = folder / "node"
    node.write_text("#!/bin/sh\n", encoding="utf-8")
    node.chmod(0o755)
    npx = folder / "npx"
    npx.write_text("#!/bin/sh\n", encoding="utf-8")
    npx.chmod(0o755)
    monkeypatch.setattr("codeagent.node_runtime.locate", lambda: tmp_path)

    assert resolve_launcher("npx") == str(npx)
    assert resolve_launcher("node") == str(node)
    assert resolve_launcher("/usr/bin/git") == "/usr/bin/git"
    assert bindir(tmp_path) == folder
    env = augment_env({"PATH": "/usr/bin"})
    assert env["PATH"].startswith(str(folder))


def test_ensure_installed_reuses_ready_dest(tmp_path: Path):
    folder = tmp_path / "bin"
    folder.mkdir()
    node = folder / "node"
    node.write_text("#!/bin/sh\n", encoding="utf-8")
    node.chmod(0o755)
    assert ensure_installed(tmp_path) == tmp_path


def test_checksum_mismatch_raises(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("codeagent.node_runtime.archive_name", lambda: "node.tgz")
    monkeypatch.setattr("codeagent.node_runtime._expected_sha", lambda name, timeout: "abc")

    def _fake_download(url, timeout=None, context=None):
        class _Resp:
            def __init__(self) -> None:
                self._sent = False

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self, n=-1):
                if self._sent:
                    return b""
                self._sent = True
                return b"not-node"

        return _Resp()

    monkeypatch.setattr("codeagent.node_runtime.urllib.request.urlopen", _fake_download)
    with pytest.raises(RuntimeError, match="checksum"):
        ensure_installed(tmp_path / "missing")
