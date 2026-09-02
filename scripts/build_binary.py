#!/usr/bin/env python3
"""Build the codeagent single-file binary for the current platform.

Usage:
    pip install -e ".[anthropic,openai,mcp,voice]" pyinstaller
    python scripts/build_binary.py

Output: dist/binary/codeagent-<os>-<arch>[.exe] — smoke-tested with
``version`` before reporting success.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "packaging" / "codeagent.spec"


def artifact_name() -> str:
    system = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}.get(
        platform.system(), platform.system().lower()
    )
    machine = platform.machine().lower()
    arch = {
        "x86_64": "amd64", "amd64": "amd64",
        "arm64": "arm64", "aarch64": "arm64",
    }.get(machine, machine)
    suffix = ".exe" if system == "windows" else ""
    return f"codeagent-{system}-{arch}{suffix}"


def main() -> int:
    if not SPEC.is_file():
        print(f"spec not found: {SPEC}", file=sys.stderr)
        return 1

    dist_dir = ROOT / "dist" / "binary"
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--clean", "--noconfirm",
            "--distpath", str(dist_dir),
            "--workpath", str(ROOT / "build" / "pyinstaller"),
            str(SPEC),
        ],
        cwd=ROOT / "packaging",
        check=True,
    )

    name = artifact_name()
    binary = dist_dir / ("codeagent.exe" if name.endswith(".exe") else "codeagent")
    target = dist_dir / name
    shutil.move(str(binary), str(target))
    target.chmod(0o755)

    result = subprocess.run(
        [str(target), "version"], capture_output=True, text=True, timeout=120
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        print("smoke test FAILED", file=sys.stderr)
        return 1
    print(f"OK → {target} ({target.stat().st_size / 1_000_000:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
