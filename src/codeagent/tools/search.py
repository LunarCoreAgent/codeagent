"""Codebase search tools: regex content search and glob file matching."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any

from codeagent.tools.base import Tool

MAX_RESULTS = 200
_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache", "dist", "build"}


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir():
                if entry.name not in _SKIP_DIRS and not entry.is_symlink():
                    stack.append(entry)
            else:
                files.append(entry)
    return files


class GrepTool(Tool):
    name = "grep"
    description = (
        "Search file contents for a regex pattern. Returns matching lines as "
        "'path:line_number: content'. Skips common build/dependency directories."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regular expression to search for."},
            "path": {"type": "string", "description": "File or directory to search in.", "default": "."},
            "include": {"type": "string", "description": "Glob filter for file names, e.g. '*.py'."},
        },
        "required": ["pattern"],
    }

    def __init__(self, root_dir: str | Path = ".") -> None:
        self.root_dir = Path(root_dir).resolve()

    async def execute(self, pattern: str, path: str = ".", include: str | None = None, **_: Any) -> str:
        target = (self.root_dir / path).resolve()
        if not target.exists():
            raise FileNotFoundError(f"No such path: {path!r}")
        regex = re.compile(pattern)

        files = [target] if target.is_file() else _iter_files(target)
        matches: list[str] = []
        for file in files:
            if include and not fnmatch.fnmatch(file.name, include):
                continue
            try:
                lines = file.read_text(errors="replace").splitlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, start=1):
                if regex.search(line):
                    matches.append(f"{file.relative_to(self.root_dir)}:{lineno}: {line.strip()}")
                    if len(matches) >= MAX_RESULTS:
                        return "\n".join(matches) + "\n... [truncated]"
        return "\n".join(matches) if matches else "(no matches)"


class GlobTool(Tool):
    name = "glob"
    description = (
        "Find files matching a glob pattern relative to the workspace root, "
        "e.g. '**/*.py'. Returns matching paths sorted by name."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern, e.g. 'src/**/*.ts'."},
        },
        "required": ["pattern"],
    }

    def __init__(self, root_dir: str | Path = ".") -> None:
        self.root_dir = Path(root_dir).resolve()

    async def execute(self, pattern: str, **_: Any) -> str:
        matches = [
            p
            for p in self.root_dir.glob(pattern)
            if not any(part in _SKIP_DIRS for part in p.parts)
        ]
        matches.sort()
        if not matches:
            return "(no matches)"
        lines = [str(p.relative_to(self.root_dir)) for p in matches[:MAX_RESULTS]]
        result = "\n".join(lines)
        if len(matches) > MAX_RESULTS:
            result += f"\n... [{len(matches) - MAX_RESULTS} more]"
        return result
