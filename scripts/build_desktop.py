#!/usr/bin/env python3
"""Build the codeagent desktop app and package it for the current platform.

macOS:  dist/desktop/CodeCoreAgent.app  →  dist/codeagent-desktop-macos-<arch>.dmg
        (dmg contains the .app + an Applications shortcut for drag-install)
Windows: dist/desktop/codeagent.exe →  dist/codeagent-desktop-windows-<arch>.zip

Usage:
    pip install -e ".[anthropic,openai,mcp,voice,desktop,packaging]"
    python scripts/build_desktop.py
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "packaging" / "codeagent-desktop.spec"
DIST = ROOT / "dist"

README_TXT = """CodeCoreAgent 桌面版

【macOS 安装】把 CodeCoreAgent.app 拖到「应用程序」(Applications) 文件夹，
首次打开如提示"无法验证开发者"：右键 App → 打开 → 打开。

【Windows 安装】运行 codeagent-desktop-windows-amd64-setup.exe，
按向导安装；也可解压 zip 便携使用。

【模型配置】App 内点「设置」：选 provider、填 API Key；
本地免费模型：装 Ollama 后 ollama pull qwen2.5-coder:7b，provider 选 ollama。

【Node.js】安装包内置 Node.js 24.21.0 LTS（官方 nodejs/node 发布包），
供 npx MCP 与 Remotion 使用，无需再单独安装 Node.js。

【数据库】首次启动在隐私说明后选择 SQLite 位置：本地、局域网或广域网。
确认后才创建 codecore.sqlite。记忆仍写在 memory.json。
"""


def _version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("version"):
            return line.split("=", 1)[1].strip().strip('"')
    return "0.0.0"


def target_name() -> str:
    system = {"Darwin": "macos", "Windows": "windows"}.get(
        platform.system(), platform.system().lower()
    )
    arch = {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64"}.get(
        platform.machine().lower(), platform.machine().lower()
    )
    return f"{system}-{arch}"


def smoke_test(app_binary: Path) -> bool:
    result = subprocess.run(
        [str(app_binary), "--version"], capture_output=True, text=True, timeout=120
    )
    print(result.stdout.strip())
    out = (result.stdout or "").lower()
    return result.returncode == 0 and ("codecoreagent" in out or "codeagent" in out)


def build_dmg(app_path: Path, target: str) -> Path:
    dmg = DIST / f"codeagent-desktop-{target}.dmg"
    with tempfile.TemporaryDirectory() as staging:
        stage = Path(staging)
        # symlinks=True: preserve framework symlink structure (signature seals it)
        shutil.copytree(app_path, stage / "CodeCoreAgent.app", symlinks=True)
        os.symlink("/Applications", stage / "Applications")
        (stage / "使用说明.txt").write_text(README_TXT, encoding="utf-8")
        subprocess.run(
            ["hdiutil", "create", "-volname", "CodeCoreAgent",
             "-srcfolder", str(stage), "-ov", "-format", "UDZO", str(dmg)],
            check=True, capture_output=True,
        )
    return dmg


def build_zip(exe_path: Path, target: str, node_dir: Path | None = None) -> Path:
    out = DIST / f"codeagent-desktop-{target}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe_path, "codeagent.exe")
        zf.writestr("README.txt", README_TXT)
        if node_dir and node_dir.is_dir():
            for path in node_dir.rglob("*"):
                if path.is_file():
                    zf.write(path, Path("node") / path.relative_to(node_dir))
    return out


def stage_node(dest: Path) -> Path:
    """Download the official Node.js LTS tree into the installer layout."""
    sys.path.insert(0, str(ROOT / "src"))
    from codeagent.node_runtime import NODE_VERSION, ensure_installed

    print(f"staging Node.js {NODE_VERSION} → {dest}")
    return ensure_installed(dest)


def build_inno(target: str, version: str) -> Path | None:
    """Compile a Windows Setup.exe with Inno Setup when `iscc` is on PATH."""
    iscc = shutil.which("iscc") or shutil.which("ISCC")
    if iscc is None:
        # Chocolatey default install path
        candidate = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe"
        iscc = str(candidate) if candidate.is_file() else None
    if not iscc:
        print("Inno Setup (iscc) not found — skip Setup.exe; zip only", file=sys.stderr)
        return None
    iss = ROOT / "packaging" / "windows-setup.iss"
    out_name = f"codeagent-desktop-{target}-setup"
    subprocess.run(
        [iscc, f"/DMyAppVersion={version}", f"/F{out_name}", str(iss)],
        cwd=ROOT,
        check=True,
    )
    out = DIST / f"{out_name}.exe"
    return out if out.is_file() else None


def main() -> int:
    if not SPEC.is_file():
        print(f"spec not found: {SPEC}", file=sys.stderr)
        return 1

    dist_dir = DIST / "desktop"
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--clean", "--noconfirm",
            "--distpath", str(dist_dir),
            "--workpath", str(ROOT / "build" / "pyinstaller-desktop"),
            str(SPEC),
        ],
        cwd=ROOT / "packaging",
        check=True,
    )

    target = target_name()
    if sys.platform == "darwin":
        app = dist_dir / "CodeCoreAgent.app"
        if not smoke_test(app / "Contents" / "MacOS" / "codeagent"):
            print("smoke test FAILED", file=sys.stderr)
            return 1
        stage_node(app / "Contents" / "Resources" / "node")
        out = build_dmg(app, target)
        print(f"OK → {out} ({out.stat().st_size / 1_000_000:.1f} MB)")
    else:
        exe = dist_dir / "codeagent.exe"
        if not smoke_test(exe):
            print("smoke test FAILED", file=sys.stderr)
            return 1
        node_dir = stage_node(dist_dir / "node")
        zipped = build_zip(exe, target, node_dir)
        print(f"OK → {zipped} ({zipped.stat().st_size / 1_000_000:.1f} MB)")
        installer = build_inno(target, _version())
        if installer:
            print(f"OK → {installer} ({installer.stat().st_size / 1_000_000:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
