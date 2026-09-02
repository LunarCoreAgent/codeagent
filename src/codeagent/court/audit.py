"""Audit trail: every state transition and decision, persisted as JSONL.

The 奏折存档 (memorial archive) equivalent — full traceability of who did
what, when, and why, so any edict's handling can be replayed and audited.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AuditEvent:
    kind: str            # transition / plan / review / dispatch / result / report
    detail: dict[str, Any]
    ts: float = field(default_factory=time.time)


class AuditLog:
    """In-memory event list, optionally mirrored to a JSONL file."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else None
        self.events: list[AuditEvent] = []
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, kind: str, **detail: Any) -> AuditEvent:
        event = AuditEvent(kind=kind, detail=detail)
        self.events.append(event)
        if self.path:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        return event

    def of_kind(self, kind: str) -> list[AuditEvent]:
        return [e for e in self.events if e.kind == kind]
