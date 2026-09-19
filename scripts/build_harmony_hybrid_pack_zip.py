#!/usr/bin/env python3
"""Build CodeCoreAgent HarmonyOS PC+Tablet hybrid scaffold pack (zip → Desktop).

Produces an ArkTS shell project (HarmonyOS NEXT) that embeds CodeCoreAgent's
Web UI via a Web component, with responsive layout for PC and tablet.
Not a signed .hap — open in DevEco Studio to compile and sign.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD_DIR = ROOT / "packaging" / "harmony_hybrid_scaffold"
DESKTOP = Path.home() / "Desktop"


def _version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("version"):
            return line.split("=", 1)[1].strip().strip('"')
    return "0.0.0"


VERSION = _version()
OUT_NAME = f"CodeCoreAgent-{VERSION}-鸿蒙电脑平板混合版"


def _write_skill(stage: Path, name: str) -> None:
    from codeagent.skills.fusion import FUSION_SKILLS

    desc, triggers, source, body = FUSION_SKILLS[name]
    folder = stage / "skills" / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        f"description: {desc}\n"
        f"source: {source}\n"
        f"triggers: {triggers}\n"
        "pack: fusion\n"
        "---\n\n"
        f"{body.strip()}\n",
        encoding="utf-8",
    )


MCP_EXAMPLE = {
    "mcpServers": {
        "deveco-mcp": {
            "command": "npx",
            "args": ["-y", "deveco-mcp-server"],
            "env": {
                "PROJECT_PATH": "/绝对路径/鸿蒙工程",
                "DEVECO_PATH": "/Applications/DevEco-Studio.app/Contents",
            },
        }
    }
}


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

        # mcp
        mcp_dir = stage / "mcp"
        mcp_dir.mkdir()
        (mcp_dir / "deveco-mcp.example.json").write_text(
            json.dumps(MCP_EXAMPLE, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        # skills
        for name in ("harmony-next", "arkts-syntax-assistant", "deveco-mcp"):
            _write_skill(stage, name)

        # arkts shell project
        app_dir = stage / "harmony-hybrid"
        shutil.copytree(SCAFFOLD_DIR / "harmony-hybrid", app_dir, dirs_exist_ok=False)

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
