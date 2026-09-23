"""Embedded SQLite shipped inside the desktop app.

The engine is the sqlite3 module from the bundled Python, so the installer
does not need a separate database server. Existing memory.json and knowledge
files stay as they are. Night study writes learned_knowledge rows here,
and tasks retrieve them from this same file.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ENGINE = f"SQLite {sqlite3.sqlite_version}"
SCOPES = ("local", "lan", "wan")


def db_path() -> Path:
    return Path.home() / ".codeagent" / "codecore.sqlite"


def default_dir() -> Path:
    return Path.home() / ".codeagent"


def _unc(path: str) -> bool:
    raw = (path or "").strip()
    folded = raw.replace("\\", "/")
    return raw.startswith("\\\\") or folded.startswith("//") or folded.lower().startswith("smb://")


def _host(path: str) -> str:
    folded = (path or "").strip().replace("\\", "/")
    if folded.lower().startswith("smb://"):
        folded = folded[6:]
    folded = folded.lstrip("/")
    return folded.split("/", 1)[0]


def _private_host(host: str) -> bool:
    name = (host or "").strip().lower().strip("[]")
    if not name or name in {"localhost"} or name.endswith(".local"):
        return True
    parts = name.split(".")
    if len(parts) == 4 and all(part.isdigit() for part in parts):
        first, second = int(parts[0]), int(parts[1])
        if first in {10, 127} or (first == 192 and second == 168):
            return True
        if first == 172 and 16 <= second <= 31:
            return True
        return False
    return "." not in name


def suggest_scope(path: str) -> str:
    """Guess local / lan / wan from a path. The user's choice still wins."""
    if not _unc(path):
        return "local"
    return "lan" if _private_host(_host(path)) else "wan"


def _check_scope(scope: str, path: str) -> str | None:
    if scope not in SCOPES:
        return "请选择本地、局域网或广域网"
    if scope == "local" and _unc(path):
        return "本地请选择本机文件夹。网络路径请改选局域网或广域网。"
    if scope == "lan" and _unc(path) and not _private_host(_host(path)):
        return "这个地址像广域网主机，请改选广域网，或填写局域网服务器。"
    if scope == "lan" and not _unc(path):
        from codeagent.desktop.projects import is_network_storage_path

        if not is_network_storage_path(path):
            return "局域网请选择已挂载的网络盘，或填写 \\\\服务器\\共享。"
    if scope == "wan" and _unc(path) and _private_host(_host(path)):
        return "这个地址在局域网里。请改选局域网，或填写公网主机 / 网盘目录。"
    return None


def connect(path: Path | None = None) -> sqlite3.Connection:
    dest = Path(path) if path is not None else db_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(dest)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('engine', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (ENGINE,),
    )
    conn.commit()
    return conn


def ensure(path: Path | None = None) -> dict[str, str]:
    """Create the embedded database if it is missing and return its status."""
    dest = Path(path) if path is not None else db_path()
    conn = connect(dest)
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='engine'").fetchone()
    finally:
        conn.close()
    return {
        "ok": "1",
        "engine": row[0] if row else ENGINE,
        "path": str(dest),
    }


def install_database(directory: str, scope: str) -> dict[str, str]:
    """Create codecore.sqlite in a folder the user picked before install."""
    chosen = (directory or "").strip()
    place = (scope or "").strip().lower()
    if not chosen:
        return {"ok": "0", "error": "请先填写数据库安装位置"}
    problem = _check_scope(place, chosen)
    if problem:
        return {"ok": "0", "error": problem}
    dest = Path(chosen).expanduser()
    if dest.suffix.lower() == ".sqlite":
        folder, dbfile = dest.parent, dest
    else:
        folder, dbfile = dest, dest / "codecore.sqlite"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".cca-db-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return {"ok": "0", "error": f"该位置不可写：{exc}"}
    info = ensure(dbfile)
    info["scope"] = place
    info["path"] = str(dbfile)
    return info
