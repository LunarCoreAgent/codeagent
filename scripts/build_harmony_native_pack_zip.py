#!/usr/bin/env python3
"""Build CodeCoreAgent pure HarmonyOS native app scaffold pack (zip → Desktop)."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD_DIR = ROOT / "packaging" / "harmony_native_scaffold"
DESKTOP = Path.home() / "Desktop"


def _version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("version"):
            return line.split("=", 1)[1].strip().strip('"')
    return "0.0.0"


VERSION = _version()
OUT_NAME = f"CodeCoreAgent-{VERSION}-纯鸿蒙版"


def main() -> int:
    if not SCAFFOLD_DIR.is_dir():
        raise SystemExit(f"missing scaffold dir: {SCAFFOLD_DIR}")

    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / OUT_NAME
        stage.mkdir(parents=True)

        # docs
        (stage / "请先读.md").write_text(
            (SCAFFOLD_DIR / "请先读.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (stage / "构建说明.md").write_text(
            (SCAFFOLD_DIR / "构建说明.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        # arkts native project
        shutil.copytree(SCAFFOLD_DIR / "harmony-native", stage / "harmony-native")

        DESKTOP.mkdir(parents=True, exist_ok=True)
        zip_path = DESKTOP / f"{OUT_NAME}.zip"
        if zip_path.exists():
            zip_path.unlink()
        archive = shutil.make_archive(
            str(DESKTOP / OUT_NAME), "zip", root_dir=stage.parent, base_dir=OUT_NAME
        )
        print(f"OK → {archive} ({Path(archive).stat().st_size / 1_000_000:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
