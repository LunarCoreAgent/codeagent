"""Export / import a single CodeCoreAgent project as a portable zip pack.

Pack includes: project metadata, conversations (with thinking + tool events),
workspace files/code, and auto-generated 说明 / 功能详细介绍 docs.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import time
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from codeagent.desktop.projects import (
    Project,
    ProjectStore,
    _unique_folder,
    list_conversations,
    list_files,
    load_conversation,
)

PACK_FORMAT = "codecoreagent-project-v1"
README_NAME = "说明.md"
FEATURE_NAME = "功能详细介绍.md"
MANIFEST_NAME = "manifest.json"
SKIP_ZIP_NAMES = {".DS_Store", "Thumbs.db"}
SKIP_ZIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules"}


def write_project_docs(project: Project) -> tuple[Path, Path]:
    """Refresh human-readable docs inside the project folder."""
    root = Path(project.path)
    root.mkdir(parents=True, exist_ok=True)
    convs = list_conversations(project)
    files = list_files(project)
    think_n = tool_n = 0
    for c in convs:
        for m in load_conversation(project, c["id"]):
            if m.get("role") == "thinking":
                think_n += 1
            elif m.get("role") == "tool":
                tool_n += 1

    readme = (
        f"# {project.name}\n\n"
        f"- 分类：{project.category}\n"
        f"- 创建：{project.created or '—'}\n"
        f"- 最近活动：{project.last_active or '—'}\n"
        f"- 本地路径：`{project.path}`\n\n"
        f"## 内容概览\n\n"
        f"- 对话：{len(convs)} 个\n"
        f"- 文件：{len(files)} 个\n"
        f"- 已记录思考片段：{think_n}\n"
        f"- 已记录工具调用：{tool_n}\n\n"
        f"本包由 CodeCoreAgent 导出，可在另一台机器「导入项目」恢复。\n"
    )
    feature_lines = [
        f"# {project.name} · 功能详细介绍\n",
        "\n## 项目说明\n",
        f"本项目属于「{project.category}」分类，用于在 CodeCoreAgent 中集中保存对话、"
        "思考过程、工具调用痕迹与工程产出。\n",
        "\n## 对话列表\n",
    ]
    if not convs:
        feature_lines.append("\n（暂无对话）\n")
    else:
        for c in convs:
            feature_lines.append(
                f"- `{c['id']}` · {c['title']}（{c['count']} 条 · {c.get('created', '')}）\n"
            )
    feature_lines.append("\n## 工程文件与代码\n")
    if not files:
        feature_lines.append("\n（暂无文件；对话附件会进入 `files/`）\n")
    else:
        for f in files[:200]:
            feature_lines.append(f"- `{f['path']}`（{f['size']}）\n")
        if len(files) > 200:
            feature_lines.append(f"\n… 另有 {len(files) - 200} 个文件未全部列出。\n")
    feature_lines.extend(
        [
            "\n## 思考与工具\n",
            "对话 jsonl 中 `role=thinking` / `role=tool` 记录思考过程与工具调用；"
            "可读版见同名 `.md`。导入后可在对话页展开「思考过程」查看。\n",
            "\n## 目录结构\n",
            "```\n",
            "project.json          # 元数据\n",
            "说明.md / 功能详细介绍.md\n",
            "conversations/        # 对话 + 思考 + 工具事件\n",
            "files/                # 附件与用户文件\n",
            "（其它）              # 代码与工程产出\n",
            "```\n",
        ]
    )
    readme_path = root / README_NAME
    feature_path = root / FEATURE_NAME
    readme_path.write_text(readme, encoding="utf-8")
    feature_path.write_text("".join(feature_lines), encoding="utf-8")
    return readme_path, feature_path


def export_project_zip(project: Project, dest: Path, *, app_version: str = "") -> Path:
    """Zip one project folder (after refreshing docs) to ``dest``."""
    root = Path(project.path).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"项目文件夹不存在：{root}")
    write_project_docs(project)
    dest = Path(dest).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()

    manifest: dict[str, Any] = {
        "format": PACK_FORMAT,
        "app_version": app_version,
        "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "project": asdict(project),
        "includes": [
            "conversations",
            "thinking",
            "tools",
            "files",
            "code",
            "docs",
            README_NAME,
            FEATURE_NAME,
        ],
    }
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            MANIFEST_NAME,
            json.dumps(manifest, ensure_ascii=False, indent=2),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if any(part in SKIP_ZIP_DIRS for part in rel.parts):
                continue
            if path.name in SKIP_ZIP_NAMES:
                continue
            zf.write(path, arcname=str(rel).replace("\\", "/"))
    return dest


def _read_manifest(zf: zipfile.ZipFile) -> dict[str, Any]:
    try:
        raw = zf.read(MANIFEST_NAME)
    except KeyError:
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def import_project_zip(
    store: ProjectStore,
    zip_path: Path,
    *,
    base: str = "",
    name_override: str = "",
) -> Project:
    """Import a project pack into a new folder and register it."""
    zip_path = Path(zip_path).expanduser()
    if not zip_path.is_file():
        raise FileNotFoundError(f"找不到打包文件：{zip_path}")

    with tempfile.TemporaryDirectory(prefix="cca-import-") as tmp:
        stage = Path(tmp) / "pack"
        stage.mkdir()
        with zipfile.ZipFile(zip_path, "r") as zf:
            manifest = _read_manifest(zf)
            for info in zf.infolist():
                name = info.filename.replace("\\", "/")
                if not name or name.endswith("/"):
                    continue
                if name.startswith("__MACOSX/") or "/__MACOSX/" in name:
                    continue
                if Path(name).name in SKIP_ZIP_NAMES:
                    continue
                if name == MANIFEST_NAME:
                    continue
                # Prevent zip-slip
                stage_root = stage.resolve()
                target = (stage / name).resolve()
                try:
                    target.relative_to(stage_root)
                except ValueError as exc:
                    raise ValueError(f"非法压缩路径：{name}") from exc
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)

        meta: dict[str, Any] = {}
        pj = stage / "project.json"
        if pj.is_file():
            try:
                meta = json.loads(pj.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                meta = {}
        if not meta and isinstance(manifest.get("project"), dict):
            meta = dict(manifest["project"])

        name = (name_override or meta.get("name") or zip_path.stem or "导入项目").strip()
        category = meta.get("category") or "其他"
        base_path = Path(base).expanduser() if base.strip() else None
        from codeagent.desktop.projects import DEFAULT_BASE, CATEGORIES

        if category not in CATEGORIES:
            category = "其他"
        folder = _unique_folder(base_path or DEFAULT_BASE.expanduser(), name)
        folder.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(stage, folder)

        now = time.strftime("%Y-%m-%d %H:%M:%S")
        proj = Project(
            name=name,
            path=str(folder),
            created=meta.get("created") or now,
            last_active=now,
            category=category,
        )
        (folder / "conversations").mkdir(exist_ok=True)
        (folder / "files").mkdir(exist_ok=True)
        (folder / "project.json").write_text(
            json.dumps(asdict(proj), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        write_project_docs(proj)
        store.projects.append(proj)
        store.active = proj.id
        store.save()
        return proj
