#!/bin/bash
# 生成 codeagent 桌面版 DMG 安装包
# 用法: packaging/make_dmg.sh [版本号]   （默认从 pyproject.toml 读取）
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="${1:-$(grep -m1 '^version' pyproject.toml | sed 's/.*"\(.*\)"/\1/')}"
APP="dist/desktop/CodeCoreAgent.app"
DMG="dist/desktop/codeagent-${VERSION}.dmg"
STAGE="dist/desktop/dmg-stage"

[ -d "$APP" ] || { echo "缺少 $APP — 先运行 PyInstaller 构建"; exit 1; }

rm -rf "$STAGE" "$DMG"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"   # 拖拽安装

hdiutil create -volname "codeagent ${VERSION}" \
  -srcfolder "$STAGE" -ov -format UDZO "$DMG"
rm -rf "$STAGE"
echo "✓ $DMG ($(du -h "$DMG" | cut -f1))"
