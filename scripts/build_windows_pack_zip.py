#!/usr/bin/env python3
"""Zip the files a Windows machine needs to build the desktop installer."""

from __future__ import annotations

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
OUT_NAME = f"CodeCoreAgent-{VERSION}-Windows打包"
DOC_NAME = f"Windows封装配置说明-{VERSION}.md"

README = f"""# 请先读：Windows 安装包怎么打

这不是已经编好的 `.exe`。macOS 打不出 Windows 安装程序。
把本 zip 拷到 **Windows 10/11 x64**，解压后按下面做。

版本：**{VERSION}**（知识库自动部署/局域网盘、项目导出导入、DBX/Limbas/OpenViking 融合、思考折叠）

## 解压后目录

| 路径 | 作用 |
|------|------|
| `请先读-Windows安装包说明.md` | 本文件 |
| `{DOC_NAME}` | 完整封装说明（配置文件、版本同步、验收） |
| `CHATGPT_WINDOWS_BUILD.md` | 交给 Windows 上 ChatGPT / Cursor 的构建任务 |
| `codeagent/` | 可构建的工程（源码 + packaging + scripts） |

## 在 Windows 上构建

1. 安装 [Python 3.12](https://www.python.org/downloads/)（勾选 Add to PATH）
2. 安装 [Inno Setup 6](https://jrsoftware.org/isinfo.php)，或：
   `choco install innosetup -y --no-progress`
3. 打开「命令提示符」或 PowerShell：

```bat
cd codeagent
python -m venv .venv
.venv\\Scripts\\activate
pip install -U pip
pip install -e ".[anthropic,openai,mcp,voice,desktop,packaging]"
python scripts\\build_desktop.py
```

成功后在 `codeagent\\dist\\` 里会有：

- `codeagent-desktop-windows-amd64-setup.exe` — 安装向导
- `codeagent-desktop-windows-amd64.zip` — 便携包

也可以把 `CHATGPT_WINDOWS_BUILD.md` 整份交给 Windows 上的 AI 助手，让它按文档构建。

## 不要打进安装包的东西

`.venv`、API Key、`%USERPROFILE%\\.codeagent` 用户数据。
"""

COPY_ROOT = [
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "PRIVACY.md",
    "项目说明.md",
]

COPY_TREES = [
    "src",
    "packaging",
    "scripts",
]

SKIP_DIR_NAMES = {
    ".venv",
    ".venv2",
    "venv",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".git",
    ".DS_Store",
}


def ignore(directory: str, names: list[str]) -> list[str]:
    dropped = []
    for n in names:
        if n in SKIP_DIR_NAMES or n.endswith(".pyc") or n.endswith(".egg-info"):
            dropped.append(n)
    return dropped


def main() -> int:
    doc = ROOT / DOC_NAME
    if not doc.is_file():
        raise SystemExit(f"missing {DOC_NAME} — write it before packing")

    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / OUT_NAME
        dest = stage / "codeagent"
        dest.mkdir(parents=True)

        for name in COPY_ROOT:
            src = ROOT / name
            if src.is_file():
                shutil.copy2(src, dest / name)

        for tree in COPY_TREES:
            shutil.copytree(ROOT / tree, dest / tree, ignore=ignore)

        wf = ROOT / ".github" / "workflows" / "binaries.yml"
        if wf.is_file():
            target = dest / ".github" / "workflows"
            target.mkdir(parents=True)
            shutil.copy2(wf, target / "binaries.yml")

        (stage / "请先读-Windows安装包说明.md").write_text(README, encoding="utf-8")
        shutil.copy2(doc, stage / DOC_NAME)
        shutil.copy2(
            ROOT / "packaging" / "CHATGPT_WINDOWS_BUILD.md",
            stage / "CHATGPT_WINDOWS_BUILD.md",
        )

        DESKTOP.mkdir(parents=True, exist_ok=True)
        zip_path = DESKTOP / f"{OUT_NAME}.zip"
        if zip_path.exists():
            zip_path.unlink()
        archive = shutil.make_archive(str(DESKTOP / OUT_NAME), "zip", root_dir=stage.parent, base_dir=OUT_NAME)
        print(f"OK → {archive} ({Path(archive).stat().st_size / 1_000_000:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
