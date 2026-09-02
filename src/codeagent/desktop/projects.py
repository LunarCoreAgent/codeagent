"""Project workspaces for the desktop app.

每个项目对应一个本地文件夹，agent 的工作根目录即项目文件夹——
所有产出文件、对话记录都在文件夹里：

    <项目文件夹>/
    ├── project.json            # 元数据
    ├── files/                  # 上传附件与用户放入的文件
    └── conversations/
        ├── <id>.jsonl          # 对话事件流（程序用）
        └── <id>.md             # 可读对话记录（人看）

项目按分类（工作 / 个人 / 学习 / 其他）组织。
项目索引存于 ~/.codeagent/projects.json。
"""

from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

PROJECTS_INDEX = Path("~/.codeagent/projects.json")
DEFAULT_BASE = Path("~/codeagent-projects")
CATEGORIES = ("工作", "个人", "学习", "其他")


@dataclass
class Project:
    name: str
    path: str
    created: str = ""
    last_active: str = ""
    category: str = "其他"
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


@dataclass
class ProjectStore:
    projects: list[Project] = field(default_factory=list)
    active: str = ""

    @classmethod
    def load(cls, path: Path | None = None) -> "ProjectStore":
        path = Path(path or PROJECTS_INDEX).expanduser()
        if not path.is_file():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        known = set(Project.__dataclass_fields__)
        return cls(
            projects=[Project(**{k: v for k, v in p.items() if k in known})
                      for p in data.get("projects", [])],
            active=data.get("active", ""),
        )

    def save(self, path: Path | None = None) -> None:
        path = Path(path or PROJECTS_INDEX).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2),
                        encoding="utf-8")

    def get(self, pid: str) -> Project | None:
        return next((p for p in self.projects if p.id == pid), None)

    def create(self, name: str, base: str = "", category: str = "其他") -> Project:
        """建立项目：同时在本地创建项目文件夹（含 conversations/ 与 files/）。"""
        name = name.strip() or "未命名项目"
        category = category if category in CATEGORIES else "其他"
        folder = _unique_folder(Path(base).expanduser() if base.strip()
                                else DEFAULT_BASE.expanduser(), name)
        folder.mkdir(parents=True, exist_ok=False)
        (folder / "conversations").mkdir()
        (folder / "files").mkdir()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        proj = Project(name=name, path=str(folder), created=now,
                       last_active=now, category=category)
        (folder / "project.json").write_text(json.dumps(
            asdict(proj), ensure_ascii=False, indent=2), encoding="utf-8")
        self.projects.append(proj)
        self.active = proj.id
        self.save()
        return proj

    def ensure_default(self) -> Project:
        """没有项目时自动建立一个默认项目，保证对话不会丢。"""
        if self.projects:
            if not self.active:
                self.active = self.projects[0].id
                self.save()
            return self.get(self.active) or self.projects[0]
        return self.create("默认项目", category="其他")

    def remove(self, pid: str) -> bool:
        """仅从索引移除（本地文件夹与对话记录保留）。"""
        proj = self.get(pid)
        if proj is None:
            return False
        self.projects.remove(proj)
        if self.active == pid:
            self.active = self.projects[-1].id if self.projects else ""
        self.save()
        return True

    def touch(self, pid: str) -> None:
        proj = self.get(pid)
        if proj:
            proj.last_active = time.strftime("%Y-%m-%d %H:%M:%S")
            self.active = pid
            self.save()


def _unique_folder(base: Path, name: str) -> Path:
    slug = re.sub(r'[\\/:*?"<>|]+', "-", name).strip() or "project"
    folder = base / slug
    n = 2
    while folder.exists():
        folder = base / f"{slug}-{n}"
        n += 1
    return folder


# ---------------------------------------------------------------------------
# conversations（每个项目文件夹内的对话记录）
# ---------------------------------------------------------------------------

def conversation_dir(project: Project) -> Path:
    d = Path(project.path) / "conversations"
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_conversation_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]


def append_message(project: Project, conv_id: str, role: str, text: str) -> None:
    """追加一条消息到对话（jsonl 事件流 + 同步重写 md 可读版）。"""
    d = conversation_dir(project)
    line = {"role": role, "text": text, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    with (d / f"{conv_id}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    _rewrite_md(d, conv_id)


def load_conversation(project: Project, conv_id: str) -> list[dict[str, Any]]:
    f = conversation_dir(project) / f"{conv_id}.jsonl"
    if not f.is_file():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def list_conversations(project: Project) -> list[dict[str, Any]]:
    """按时间倒序列出项目全部对话（含首条用户消息作标题）。"""
    d = conversation_dir(project)
    out = []
    for f in sorted(d.glob("*.jsonl"), reverse=True):
        msgs = load_conversation(project, f.stem)
        if not msgs:
            continue
        first_user = next((m for m in msgs if m.get("role") == "user"), None)
        title = (first_user["text"][:30] if first_user else msgs[0]["text"][:30])
        out.append({
            "id": f.stem,
            "title": title.replace("\n", " "),
            "created": msgs[0].get("ts", ""),
            "count": len(msgs),
        })
    return out


def _rewrite_md(d: Path, conv_id: str) -> None:
    msgs = [
        json.loads(line)
        for line in (d / f"{conv_id}.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    parts = [f"# 对话记录 {conv_id}\n"]
    for m in msgs:
        who = "🧑 用户" if m["role"] == "user" else "🤖 助手"
        parts.append(f"\n## {who} · {m.get('ts', '')}\n\n{m['text']}\n")
    (d / f"{conv_id}.md").write_text("".join(parts), encoding="utf-8")


def files_dir(project: Project) -> Path:
    d = Path(project.path) / "files"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ingest_file(project: Project, src: Path) -> Path:
    """把外部文件复制进项目 files/，重名自动加序号。"""
    src = Path(src).expanduser()
    dest = files_dir(project) / src.name
    n = 2
    while dest.exists():
        dest = files_dir(project) / f"{src.stem}-{n}{src.suffix}"
        n += 1
    shutil.copy2(src, dest)
    return dest


def list_files(project: Project) -> list[dict[str, Any]]:
    """列出项目文件夹内的用户文件（不含对话记录与元数据）。"""
    root = Path(project.path)
    if not root.is_dir():
        return []
    skip_dirs = {"conversations"}
    skip_names = {"project.json", ".DS_Store"}
    out: list[dict[str, Any]] = []
    for p in sorted(root.rglob("*")):
        if p.is_dir() or p.name in skip_names:
            continue
        rel = p.relative_to(root)
        if rel.parts[0] in skip_dirs:
            continue
        stat = p.stat()
        out.append({
            "name": p.name,
            "path": str(rel),
            "size": _size_label(stat.st_size),
            "mtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
        })
    return out


def _size_label(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"
