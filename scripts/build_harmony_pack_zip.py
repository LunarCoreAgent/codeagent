#!/usr/bin/env python3
"""Build CodeCoreAgent HarmonyOS 7.0 developer pack (zip → Desktop).

CodeCoreAgent itself is a Mac/Windows desktop agent. HarmonyOS apps are built
with DevEco; this pack ships distilled skills, MCP config, and a setup guide so
the agent can drive HarmonyOS 7.0 / NEXT development via DevEco MCP.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = Path.home() / "Desktop"


def _version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("version"):
            return line.split("=", 1)[1].strip().strip('"')
    return "0.0.0"


VERSION = _version()
OUT_NAME = f"CodeCoreAgent-{VERSION}-鸿蒙7.0开发包"

README = f"""# CodeCoreAgent × 鸿蒙 7.0 开发包（v{VERSION}）

## 这是什么

**不是** 可在手机/平板上直接安装的 HAP。

本包配合 **CodeCoreAgent 桌面版（macOS / Windows）** + 本机 **DevEco Studio**，
用融合技能与 DevEco MCP 完成鸿蒙 7.0 / HarmonyOS NEXT 的「写码 → 编译 → 装机 → 调试」闭环。

## 目录

| 路径 | 作用 |
|------|------|
| `请先读-鸿蒙7.0开发包说明.md` | 本文件 |
| `mcp/deveco-mcp.example.json` | 粘贴到 MCP 配置的示例 |
| `skills/harmony-next/SKILL.md` | 鸿蒙 API / Kit 路由技能 |
| `skills/arkts-syntax-assistant/SKILL.md` | ArkTS / .ets 语法技能 |
| `skills/deveco-mcp/SKILL.md` | DevEco MCP 闭环指引 |
| `presets/deveco_mcp.py` | Python 预设片段（可选拷入工程） |

## 使用步骤

1. 安装并打开 **CodeCoreAgent {VERSION}**（macOS DMG 或 Windows 安装包）。
2. 安装 **DevEco Studio**，用它新建/打开鸿蒙工程，确认本机能编译、装到模拟器或真机。
3. 在 AI IDE / CodeCoreAgent 的 MCP 配置中加入 `mcp/deveco-mcp.example.json` 内容，
   把 `DEVECO_PATH`、`PROJECT_PATH` 改成你的本机绝对路径。
4. 对话中说明「鸿蒙 / ArkTS / 编译装机」任务；Agent 会启用 `harmony-next`、
   `arkts-syntax-assistant`、`deveco-mcp` 技能，并调用 MCP 工具。

## Python 预设（开发者）

```python
from codeagent.mcp import deveco_mcp

cfg = deveco_mcp(
    project_path=r"/绝对路径/你的鸿蒙工程",
    # macOS 示例：
    # deveco_path="/Applications/DevEco-Studio.app/Contents",
    # Windows 示例：
    # deveco_path=r"C:\\Program Files\\Huawei\\DevEco Studio",
)
```

## 注意

- 需要本机 Node.js（`npx -y deveco-mcp-server`）。
- 上游工具箱：https://github.com/open-deveco/deveco-toolbox
- 知识库技能原文参考：https://github.com/linhay/harmony-next.skills
- ArkTS 助手参考：https://github.com/SummerKaze/skill-arkts-syntax-assistant
"""

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

PRESET_SNIPPET = '''\
"""Copy of codeagent.mcp.presets.deveco_mcp for offline reference."""

# Prefer: from codeagent.mcp import deveco_mcp
#
# def example():
#     return deveco_mcp(
#         project_path="/path/to/harmony/project",
#         deveco_path="/Applications/DevEco-Studio.app/Contents",
#     )
'''


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


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / OUT_NAME
        stage.mkdir(parents=True)

        (stage / "请先读-鸿蒙7.0开发包说明.md").write_text(README, encoding="utf-8")
        mcp_dir = stage / "mcp"
        mcp_dir.mkdir()
        (mcp_dir / "deveco-mcp.example.json").write_text(
            json.dumps(MCP_EXAMPLE, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        presets = stage / "presets"
        presets.mkdir()
        (presets / "deveco_mcp.py").write_text(PRESET_SNIPPET, encoding="utf-8")

        for name in ("harmony-next", "arkts-syntax-assistant", "deveco-mcp"):
            _write_skill(stage, name)

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
