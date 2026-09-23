"""Local learned-knowledge library in the bundled SQLite file."""

from __future__ import annotations

import hashlib
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codeagent.memory.store import _tokenize
from codeagent.sqlite_store import connect, db_path

KINDS = ("code", "design", "ui", "flow", "database", "tech")
KIND_LABELS = {
    "code": "代码",
    "design": "设计",
    "ui": "UI 设计",
    "flow": "流程设计",
    "database": "数据库设计",
    "tech": "技术",
}
MEMORY_KIND = {
    "code": "learned_code",
    "design": "learned_design",
    "ui": "learned_ui",
    "flow": "learned_flow",
    "database": "learned_db",
    "tech": "learned_tech",
}
LEARNED_MEMORY_KINDS = tuple(MEMORY_KIND.values())

_SCHEMA = """
CREATE TABLE IF NOT EXISTS learned_knowledge (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    project_name TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    query TEXT NOT NULL DEFAULT '',
    fingerprint TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_learned_proj ON learned_knowledge(project_id);
CREATE INDEX IF NOT EXISTS idx_learned_kind ON learned_knowledge(kind);
CREATE INDEX IF NOT EXISTS idx_learned_fp ON learned_knowledge(fingerprint);
"""


def _norm_kind(kind: str) -> str:
    key = (kind or "").strip().lower()
    aliases = {
        "ui设计": "ui",
        "ui_design": "ui",
        "视觉设计": "design",
        "流程": "flow",
        "流程设计": "flow",
        "数据库": "database",
        "数据库设计": "database",
        "代码": "code",
        "技术": "tech",
    }
    key = aliases.get(key, key)
    return key if key in KINDS else "tech"


def fingerprint(project_id: str, kind: str, title: str, content: str) -> str:
    raw = f"{project_id}\n{kind}\n{title.strip()}\n{content.strip()[:800]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


@dataclass
class LearnedNote:
    id: str
    project_id: str
    project_name: str
    kind: str
    title: str
    content: str
    source_url: str = ""
    query: str = ""
    fingerprint: str = ""
    created_at: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "kind": self.kind,
            "kind_label": KIND_LABELS.get(self.kind, self.kind),
            "title": self.title,
            "content": self.content,
            "source_url": self.source_url,
            "query": self.query,
            "created_at": self.created_at,
            "memory_kind": MEMORY_KIND.get(self.kind, "learned_tech"),
        }

    def memory_text(self) -> str:
        label = KIND_LABELS.get(self.kind, self.kind)
        src = f"\n来源：{self.source_url}" if self.source_url else ""
        return f"【{label}】{self.title}\n{self.content}{src}"


class LearnedStore:
    """Keyword retrieval over codecore.sqlite learned_knowledge."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else db_path()

    def _connect(self) -> sqlite3.Connection:
        conn = connect(self.path)
        conn.executescript(_SCHEMA)
        conn.commit()
        return conn

    def add(self, note: LearnedNote) -> LearnedNote | None:
        kind = _norm_kind(note.kind)
        title = (note.title or "").strip()[:160]
        content = (note.content or "").strip()
        if not title or not content:
            return None
        fp = note.fingerprint or fingerprint(note.project_id, kind, title, content)
        now = note.created_at or time.time()
        nid = note.id or uuid.uuid4().hex[:12]
        conn = self._connect()
        try:
            exists = conn.execute(
                "SELECT id FROM learned_knowledge WHERE fingerprint=?",
                (fp,),
            ).fetchone()
            if exists:
                return None
            conn.execute(
                "INSERT INTO learned_knowledge"
                "(id, project_id, project_name, kind, title, content,"
                " source_url, query, fingerprint, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    nid,
                    note.project_id,
                    note.project_name,
                    kind,
                    title,
                    content,
                    note.source_url or "",
                    note.query or "",
                    fp,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        note.id = nid
        note.kind = kind
        note.title = title
        note.content = content
        note.fingerprint = fp
        note.created_at = now
        return note

    def search(
        self,
        query: str,
        *,
        project_id: str = "",
        kinds: tuple[str, ...] | None = None,
        limit: int = 8,
    ) -> list[LearnedNote]:
        query_tokens = set(_tokenize(query or ""))
        rows = self._load(project_id=project_id, kinds=kinds)
        if not query_tokens:
            return rows[:limit]
        scored: list[tuple[float, LearnedNote]] = []
        for note in rows:
            hay = set(_tokenize(f"{note.title} {note.content} {note.kind} {note.query}"))
            overlap = len(query_tokens & hay)
            if not overlap:
                continue
            score = overlap / (len(query_tokens) ** 0.5 * max(len(hay), 1) ** 0.5)
            scored.append((score, note))
        scored.sort(key=lambda pair: (-pair[0], -pair[1].created_at))
        return [note for _, note in scored[:limit]]

    def recent(self, limit: int = 30, project_id: str = "") -> list[LearnedNote]:
        return self._load(project_id=project_id)[:limit]

    def count(self, project_id: str = "") -> int:
        conn = self._connect()
        try:
            if project_id:
                row = conn.execute(
                    "SELECT COUNT(*) FROM learned_knowledge WHERE project_id=?",
                    (project_id,),
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM learned_knowledge").fetchone()
        finally:
            conn.close()
        return int(row[0]) if row else 0

    def _load(
        self,
        *,
        project_id: str = "",
        kinds: tuple[str, ...] | None = None,
    ) -> list[LearnedNote]:
        conn = self._connect()
        try:
            sql = (
                "SELECT id, project_id, project_name, kind, title, content,"
                " source_url, query, fingerprint, created_at"
                " FROM learned_knowledge"
            )
            args: list[Any] = []
            clauses: list[str] = []
            if project_id:
                clauses.append("project_id=?")
                args.append(project_id)
            if kinds:
                allowed = [_norm_kind(k) for k in kinds]
                clauses.append(f"kind IN ({','.join('?' * len(allowed))})")
                args.extend(allowed)
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            sql += " ORDER BY created_at DESC"
            rows = conn.execute(sql, args).fetchall()
        finally:
            conn.close()
        return [
            LearnedNote(
                id=row[0],
                project_id=row[1],
                project_name=row[2],
                kind=row[3],
                title=row[4],
                content=row[5],
                source_url=row[6],
                query=row[7],
                fingerprint=row[8],
                created_at=row[9],
            )
            for row in rows
        ]


def recall_learned(
    query: str,
    *,
    project_id: str = "",
    limit: int = 8,
    path: Path | None = None,
) -> list[str]:
    """Plain-text notes for the current task."""
    notes = LearnedStore(path).search(query, project_id=project_id, limit=limit)
    return [n.memory_text() for n in notes]
