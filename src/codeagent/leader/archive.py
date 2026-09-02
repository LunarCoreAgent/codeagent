"""Run archive: every leader command is persisted locally, per project.

All records stay on this machine under ``~/.codeagent/runs/<project>/`` —
progress history survives restarts, and every run is replayable/auditable.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_ARCHIVE_ROOT = Path("~/.codeagent/runs")


def project_key(root: str | Path) -> str:
    """Stable per-project key: readable name + short path hash."""
    path = Path(root).expanduser().resolve()
    digest = hashlib.sha256(str(path).encode()).hexdigest()[:8]
    return f"{path.name}-{digest}"


@dataclass
class RunRecord:
    run_id: str
    project: str
    command: str
    reply: str
    board: dict[str, Any]
    created_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project": self.project,
            "command": self.command,
            "reply": self.reply,
            "board": self.board,
            "created_at": self.created_at,
        }


class RunArchive:
    """JSON-file archive of leader runs, stored locally per project."""

    def __init__(self, base: str | Path = DEFAULT_ARCHIVE_ROOT) -> None:
        self.base = Path(base).expanduser()

    def _project_dir(self, root: str | Path) -> Path:
        folder = self.base / project_key(root)
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def save(
        self,
        project_root: str | Path,
        command: str,
        reply: str,
        board_snapshot: dict[str, Any],
    ) -> Path:
        run_id = (
            time.strftime("%Y%m%d-%H%M%S")
            + f"-{int(time.time() * 1_000_000) % 1_000_000:06d}"
            + f"-{uuid.uuid4().hex[:4]}"
        )
        record = RunRecord(
            run_id=run_id,
            project=str(Path(project_root).expanduser().resolve()),
            command=command,
            reply=reply,
            board=board_snapshot,
            created_at=time.time(),
        )
        path = self._project_dir(project_root) / f"{run_id}.json"
        path.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    def list(self, project_root: str | Path | None = None) -> list[dict[str, Any]]:
        """All archived runs (optionally for one project), newest first."""
        folders = (
            [self._project_dir(project_root)]
            if project_root is not None
            else sorted(self.base.iterdir()) if self.base.is_dir() else []
        )
        records: list[dict[str, Any]] = []
        for folder in folders:
            if not folder.is_dir():
                continue
            for path in folder.glob("*.json"):
                try:
                    records.append(json.loads(path.read_text(encoding="utf-8")))
                except (json.JSONDecodeError, OSError):
                    continue
        records.sort(key=lambda r: r.get("created_at", 0), reverse=True)
        return records
