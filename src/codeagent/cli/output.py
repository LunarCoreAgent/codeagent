"""Machine-readable CLI output: a stable JSON envelope.

Inspired by Claw Code's --json contract. Human text stays the default;
``--json`` prints one object so scripts never scrape Rich markup.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from codeagent import __version__


def envelope(
    *,
    ok: bool,
    data: Any = None,
    error: dict[str, str] | None = None,
) -> dict[str, Any]:
    """``{ok, version, data}`` plus optional ``error: {code, message}``."""
    payload: dict[str, Any] = {
        "ok": ok,
        "version": __version__,
        "data": {} if data is None else data,
    }
    if error is not None:
        payload["error"] = error
    return payload


def emit_json(payload: dict[str, Any], *, file=None) -> None:
    json.dump(payload, file or sys.stdout, ensure_ascii=False, indent=2)
    print(file=file or sys.stdout)
