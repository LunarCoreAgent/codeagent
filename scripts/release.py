#!/usr/bin/env python3
"""一键发版：每次更新统一带上版本号与版本信息记录。

用法：
    python scripts/release.py 0.37.0 --date 2026-09-09 \
        --note "第二对话窗口：主窗口可开独立 B 对话窗口，同一项目并行"
    python scripts/release.py 0.37.0 --note "..." --note "..."

流程（自动完成）：
    1. 校验新版本号比当前 pyproject.toml 版本更新；
    2. 把 pyproject.toml 的 version 升到新版本；
    3. 在 src/codeagent/releases.py 追加一条 Release(version, date, notes)；
    4. 依据 releases.py 重新生成 CHANGELOG.md（单一数据源）。
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
RELEASES = ROOT / "src" / "codeagent" / "releases.py"
INIT = ROOT / "src" / "codeagent" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"


def current_version() -> str:
    m = re.search(r'^version\s*=\s*"([^"]+)"', PYPROJECT.read_text(), re.M)
    if not m:
        sys.exit("pyproject.toml 里找不到 version 字段")
    return m.group(1)


def bump_pyproject(new: str) -> None:
    text = PYPROJECT.read_text()
    new_text, n = re.subn(
        r'^version\s*=\s*"[^"]+"', f'version = "{new}"', text, count=1, flags=re.M
    )
    if n != 1:
        sys.exit("pyproject.toml 版本号替换失败")
    PYPROJECT.write_text(new_text)


def bump_init(new: str) -> None:
    """同步 src/codeagent/__init__.py 里的 __version__（测试/API 读取来源）。"""
    text = INIT.read_text()
    new_text, n = re.subn(
        r'^__version__\s*=\s*"[^"]+"', f'__version__ = "{new}"', text, count=1, flags=re.M
    )
    if n != 1:
        sys.exit("src/codeagent/__init__.py 的 __version__ 替换失败")
    INIT.write_text(new_text)


def insert_release(new: str, date: str, notes: list[str]) -> None:
    text = RELEASES.read_text()
    # 追加到 RELEASES 元组末尾（最后一条 Release 的收尾 "    ))," 之后）
    ends = [m for m in re.finditer(r"^    \)\),$", text, re.M)]
    if not ends:
        sys.exit("releases.py 里找不到 Release 记录末尾")
    idx = ends[-1].end()
    block = '    Release("%s", "%s", (\n' % (new, date)
    block += "".join('        "%s",\n' % n for n in notes)
    block += "    )),\n"
    RELEASES.write_text(text[:idx] + "\n" + block + text[idx:])


def regenerate_changelog() -> None:
    # 直接从源码路径导入，不依赖已安装包
    import sys as _sys

    sys.path.insert(0, str(ROOT / "src"))
    from codeagent.releases import changelog_text

    body = changelog_text()
    header = (
        "# Changelog\n\n"
        "所有版本更新记录。数据源：`src/codeagent/releases.py`（CLI 里 `codeagent changelog` 可查）。\n"
    )
    CHANGELOG.write_text(header + "\n" + body + "\n")


def parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def main() -> int:
    ap = argparse.ArgumentParser(description="CodeCoreAgent 发版工具")
    ap.add_argument("version", help="新版本号，例如 0.37.0")
    ap.add_argument("--date", default=None, help="发布日期 YYYY-MM-DD，默认今天")
    ap.add_argument("--note", action="append", default=[], help="本次更新说明，可重复")
    args = ap.parse_args()

    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        sys.exit("版本号需为 X.Y.Z 格式")
    cur = current_version()
    if parse_version(args.version) <= parse_version(cur):
        sys.exit(f"新版本 {args.version} 不高于当前 {cur}")
    date = args.date or datetime.date.today().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        sys.exit("--date 需为 YYYY-MM-DD")
    notes = [n.strip() for n in args.note if n.strip()]
    if not notes:
        notes = ["版本更新：见 CHANGELOG 与 releases.py"]

    bump_pyproject(args.version)
    bump_init(args.version)
    insert_release(args.version, date, notes)
    regenerate_changelog()

    print(f"OK → {args.version}（{date}）")
    print(f"  pyproject.toml   version = \"{args.version}\"")
    print(f"  __init__.py      __version__ = \"{args.version}\"")
    print(f"  releases.py      Release(\"{args.version}\", \"{date}\", {len(notes)} 条说明)")
    print(f"  CHANGELOG.md     已按 releases.py 重新生成")
    print("说明：")
    for n in notes:
        print(f"  - {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
