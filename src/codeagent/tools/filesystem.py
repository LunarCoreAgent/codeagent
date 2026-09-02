"""Filesystem tools: read, write, edit and list files within a root directory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codeagent.security.policy import RiskLevel
from codeagent.tools.base import Tool

MAX_READ_CHARS = 100_000


class _FilesystemTool(Tool):
    def __init__(self, root_dir: str | Path = ".", restrict_to_root: bool = True) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.restrict_to_root = restrict_to_root

    def _resolve(self, path: str) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root_dir / candidate
        resolved = candidate.resolve()
        if self.restrict_to_root and not (
            resolved == self.root_dir or self.root_dir in resolved.parents
        ):
            raise PermissionError(
                f"Path {path!r} escapes the workspace root {str(self.root_dir)!r}"
            )
        return resolved


class ReadFileTool(_FilesystemTool):
    name = "read_file"
    description = (
        "Read the contents of a file. Returns numbered lines. "
        "Use offset/limit to page through large files."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file, relative to the workspace root or absolute."},
            "offset": {"type": "integer", "description": "1-based line number to start reading from.", "minimum": 1},
            "limit": {"type": "integer", "description": "Maximum number of lines to read.", "minimum": 1},
        },
        "required": ["path"],
    }

    async def execute(self, path: str, offset: int = 1, limit: int | None = None, **_: Any) -> str:
        resolved = self._resolve(path)
        if not resolved.is_file():
            raise FileNotFoundError(f"No such file: {path!r}")
        text = resolved.read_text(errors="replace")
        if len(text) > MAX_READ_CHARS:
            text = text[:MAX_READ_CHARS] + "\n... [truncated]"
        lines = text.splitlines()
        start = max(offset - 1, 0)
        end = None if limit is None else start + limit
        selected = lines[start:end]
        if not selected:
            return "(empty)"
        width = len(str(start + len(selected)))
        return "\n".join(
            f"{i:>{width}}|{line}" for i, line in enumerate(selected, start=start + 1)
        )


class WriteFileTool(_FilesystemTool):
    name = "write_file"
    risk_level = RiskLevel.WRITE
    description = (
        "Write content to a file, creating it (and parent directories) if needed. "
        "Overwrites any existing content."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to write."},
            "content": {"type": "string", "description": "Full content to write to the file."},
        },
        "required": ["path", "content"],
    }

    async def execute(self, path: str, content: str, **_: Any) -> str:
        resolved = self._resolve(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content)
        return f"Wrote {len(content)} characters to {path}"


class EditFileTool(_FilesystemTool):
    name = "edit_file"
    risk_level = RiskLevel.WRITE
    description = (
        "Replace an exact substring of a file with new content. "
        "The old_string must match exactly once unless replace_all is set."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to edit."},
            "old_string": {"type": "string", "description": "Exact text to replace."},
            "new_string": {"type": "string", "description": "Replacement text."},
            "replace_all": {"type": "boolean", "description": "Replace every occurrence.", "default": False},
        },
        "required": ["path", "old_string", "new_string"],
    }

    async def execute(
        self,
        path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
        **_: Any,
    ) -> str:
        resolved = self._resolve(path)
        if not resolved.is_file():
            raise FileNotFoundError(f"No such file: {path!r}")
        text = resolved.read_text()
        occurrences = text.count(old_string)
        if occurrences == 0:
            raise ValueError(f"old_string not found in {path!r}")
        if occurrences > 1 and not replace_all:
            raise ValueError(
                f"old_string occurs {occurrences} times in {path!r}; "
                "provide more context or set replace_all=true"
            )
        updated = text.replace(old_string, new_string) if replace_all else text.replace(old_string, new_string, 1)
        resolved.write_text(updated)
        return f"Edited {path}: replaced {occurrences if replace_all else 1} occurrence(s)"


class ListDirTool(_FilesystemTool):
    name = "list_dir"
    description = "List files and directories at a path (non-recursive). Directories end with '/'."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path.", "default": "."},
        },
    }

    async def execute(self, path: str = ".", **_: Any) -> str:
        resolved = self._resolve(path)
        if not resolved.is_dir():
            raise NotADirectoryError(f"No such directory: {path!r}")
        entries = sorted(resolved.iterdir(), key=lambda p: (p.is_file(), p.name))
        if not entries:
            return "(empty directory)"
        return "\n".join(f"{p.name}/" if p.is_dir() else p.name for p in entries)
