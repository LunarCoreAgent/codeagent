"""Embedded SQLite is created as a local file."""

from pathlib import Path

from codeagent.sqlite_store import ENGINE, ensure


def test_ensure_creates_database(tmp_path: Path):
    dest = tmp_path / "codecore.sqlite"
    info = ensure(dest)
    assert dest.is_file()
    assert info["engine"] == ENGINE
    assert ENGINE.startswith("SQLite ")
    again = ensure(dest)
    assert again["path"] == str(dest)


def test_install_requires_a_location(tmp_path: Path):
    from codeagent.sqlite_store import install_database, suggest_scope

    missing = install_database("", "local")
    assert missing["ok"] == "0"
    local = install_database(str(tmp_path / "db"), "local")
    assert local["ok"] == "1"
    assert local["scope"] == "local"
    assert local["path"].endswith("codecore.sqlite")
    refused = install_database(r"\\nas\share\db", "local")
    assert refused["ok"] == "0"
    assert suggest_scope(r"\\192.168.1.8\share") == "lan"
    assert suggest_scope(r"\\files.example.com\share") == "wan"
