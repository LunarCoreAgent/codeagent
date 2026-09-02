#!/usr/bin/env python3
"""Package the built macOS binary into a .dmg installer image.

Layout inside the dmg:
    codeagent          — the single-file binary
    安装.command        — double-click installer (copies to /usr/local/bin)
    使用说明.txt        — quick-start guide

Usage:
    python scripts/build_binary.py   # first, produces dist/binary/
    python scripts/build_dmg.py      # then, produces dist/*.dmg
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

INSTALL_COMMAND = """#!/bin/bash
# codeagent 安装器 —— 双击运行
cd "$(dirname "$0")"
echo "正在安装 codeagent 到 /usr/local/bin（需要输入开机密码）..."
if sudo cp codeagent /usr/local/bin/codeagent && sudo chmod +x /usr/local/bin/codeagent; then
    echo ""
    echo "✅ 安装完成！打开「终端」输入 codeagent 即可使用。"
    echo "   首次使用先配置模型：export OPENAI_API_KEY=... 或 ollama pull qwen2.5-coder:7b"
else
    echo "❌ 安装失败，也可以手动复制：把 codeagent 文件拷到任意目录直接运行"
fi
echo ""
read -n 1 -s -r -p "按任意键关闭..."
"""

README_TXT = """codeagent —— 专业代码开发 Agent

【快速开始】
1. 双击「安装.command」装到系统（推荐），或直接把 codeagent 拷到任意目录
2. 打开「终端」：
     codeagent version            验证安装
     codeagent chat               交互对话
     codeagent run "帮我写个脚本"  单任务模式

【模型配置（三选一）】
· 本地免费：  安装 Ollama 后 ollama pull qwen2.5-coder:7b
              然后 codeagent chat --provider ollama
· OpenAI：    export OPENAI_API_KEY="sk-..."
· Claude：    export ANTHROPIC_API_KEY="sk-ant-..."

【个性化】
  codeagent settings set --nickname 你的名字 --language 中文

完整文档：https://github.com/ （见仓库 README.md）
"""


def main() -> int:
    binaries = sorted(DIST.glob("binary/codeagent-macos-*"))
    if not binaries:
        print("先运行 scripts/build_binary.py 构建 macOS 二进制", file=sys.stderr)
        return 1

    made = []
    for binary in binaries:
        target = binary.name.removeprefix("codeagent-")  # e.g. macos-arm64
        dmg = DIST / f"codeagent-{target}.dmg"

        with tempfile.TemporaryDirectory() as staging:
            stage = Path(staging)
            shutil.copy2(binary, stage / "codeagent")
            (stage / "codeagent").chmod(0o755)
            (stage / "安装.command").write_text(INSTALL_COMMAND, encoding="utf-8")
            (stage / "安装.command").chmod(0o755)
            (stage / "使用说明.txt").write_text(README_TXT, encoding="utf-8")

            subprocess.run(
                [
                    "hdiutil", "create",
                    "-volname", "codeagent",
                    "-srcfolder", str(stage),
                    "-ov", "-format", "UDZO",
                    str(dmg),
                ],
                check=True,
                capture_output=True,
            )
        made.append(dmg)
        print(f"OK → {dmg} ({dmg.stat().st_size / 1_000_000:.1f} MB)")

    return 0 if made else 1


if __name__ == "__main__":
    raise SystemExit(main())
