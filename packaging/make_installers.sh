#!/bin/bash
# 打当前平台的桌面安装包。
# macOS → dist/codeagent-desktop-macos-<arch>.dmg
# Windows（需 Inno Setup）→ dist/codeagent-desktop-windows-amd64-setup.exe
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python scripts/build_desktop.py "$@"
