"""Project workspaces for the desktop app.

每个项目对应一个本地文件夹，agent 的工作根目录即项目文件夹——
所有产出文件、对话记录都在文件夹里：

    <项目文件夹>/
    ├── project.json            # 元数据
    ├── memory.json             # 本项目长期记忆（对话/思考/进度）
    ├── files/                  # 上传附件与用户放入的文件
    └── conversations/
        ├── <id>.jsonl          # 对话事件流（程序用）
        └── <id>.md             # 可读对话记录（人看）

项目按分类（工作 / 个人 / 学习 / 其他）组织。
项目索引存于 ~/.codeagent/projects.json。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
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
    parent_id: str = ""
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

    def create(
        self,
        name: str,
        base: str = "",
        category: str = "其他",
        parent_id: str = "",
    ) -> Project:
        """建立项目：同时在本地创建项目文件夹（含 conversations/ 与 files/）。"""
        name = name.strip() or "未命名项目"
        category = category if category in CATEGORIES else "其他"
        parent_id = (parent_id or "").strip()
        parent = self.get(parent_id) if parent_id else None
        if parent_id and parent is None:
            raise ValueError("父项目不存在")
        dest = (base or "").strip()
        if not dest and parent is not None:
            dest = parent.path
        folder = _unique_folder(
            Path(dest).expanduser() if dest else DEFAULT_BASE.expanduser(),
            name,
        )
        folder.mkdir(parents=True, exist_ok=False)
        (folder / "conversations").mkdir()
        (folder / "files").mkdir()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        proj = Project(
            name=name,
            path=str(folder),
            created=now,
            last_active=now,
            category=parent.category if parent is not None else category,
            parent_id=parent.id if parent is not None else "",
        )
        _write_meta(proj)
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

    def children(self, pid: str) -> list[Project]:
        return [p for p in self.projects if p.parent_id == pid]

    def descendants(self, pid: str) -> list[Project]:
        found: list[Project] = []
        pending = [pid]
        seen = {pid}
        while pending:
            current = pending.pop()
            for child in self.children(current):
                if child.id in seen:
                    continue
                seen.add(child.id)
                found.append(child)
                pending.append(child.id)
        return found

    def walk(self) -> list[tuple[Project, int]]:
        """Top-level projects first, children nested; preserves sibling order."""
        by_parent: dict[str, list[Project]] = {}
        for proj in self.projects:
            by_parent.setdefault(proj.parent_id or "", []).append(proj)
        rows: list[tuple[Project, int]] = []

        def visit(parent: str, depth: int, stack: frozenset[str]) -> None:
            for proj in by_parent.get(parent, []):
                rows.append((proj, depth))
                if proj.id in stack:
                    continue
                visit(proj.id, depth + 1, stack | {proj.id})

        visit("", 0, frozenset())
        listed = {proj.id for proj, _ in rows}
        for proj in self.projects:
            if proj.id not in listed:
                rows.append((proj, 0))
        return rows

    def set_path(self, pid: str, path: str) -> Project:
        """Point the index at another existing folder. Does not move files."""
        proj = self.get(pid)
        if proj is None:
            raise ValueError("项目不存在")
        folder = Path(path).expanduser()
        if not folder.is_dir():
            raise ValueError("该路径不是可用的文件夹")
        occupied = next(
            (p for p in self.projects if p.id != pid and _same_path(p.path, str(folder))),
            None,
        )
        if occupied is not None:
            raise ValueError(f"该路径已被项目「{occupied.name}」使用")
        proj.path = str(folder)
        _write_meta(proj)
        self.save()
        return proj

    def remove(self, pid: str, delete_files: bool = False) -> bool:
        """Remove from the index. Optionally delete the folder on disk."""
        proj = self.get(pid)
        if proj is None:
            return False
        nested = [
            child for child in self.descendants(pid)
            if _is_under(child.path, proj.path)
        ]
        outsiders = [
            child for child in self.descendants(pid)
            if child not in nested
        ]
        if delete_files:
            folder = Path(proj.path).expanduser()
            if folder.is_dir():
                try:
                    shutil.rmtree(folder)
                except OSError:
                    return False
            drop = {proj.id, *(child.id for child in nested)}
            self.projects = [p for p in self.projects if p.id not in drop]
            for child in outsiders:
                child.parent_id = proj.parent_id
        else:
            for child in self.children(pid):
                child.parent_id = proj.parent_id
            self.projects = [p for p in self.projects if p.id != pid]
        if self.active == pid or self.get(self.active) is None:
            self.active = self.projects[-1].id if self.projects else ""
        self.save()
        return True

    def touch(self, pid: str) -> None:
        proj = self.get(pid)
        if proj:
            proj.last_active = time.strftime("%Y-%m-%d %H:%M:%S")
            self.active = pid
            self.save()


def _write_meta(proj: Project) -> None:
    folder = Path(proj.path).expanduser()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "project.json").write_text(
            json.dumps(asdict(proj), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def _norm_path(path: str) -> str:
    text = os.path.normpath(os.path.expanduser(str(path)))
    if len(text) > 1:
        text = text.rstrip("/\\")
    return text


def _same_path(a: str, b: str) -> bool:
    left, right = _norm_path(a), _norm_path(b)
    if sys.platform == "win32":
        return left.casefold() == right.casefold()
    return left == right


def _is_under(path: str, root: str) -> bool:
    child, parent = _norm_path(path), _norm_path(root)
    if not parent:
        return False
    try:
        common = os.path.commonpath([child, parent])
    except ValueError:
        return False
    if sys.platform == "win32":
        return common.casefold() == parent.casefold() and child.casefold() != parent.casefold()
    return common == parent and child != parent


def _unique_folder(base: Path, name: str) -> Path:
    slug = re.sub(r'[\\/:*?"<>|]+', "-", name).strip() or "project"
    folder = base / slug
    n = 2
    while folder.exists():
        folder = base / f"{slug}-{n}"
        n += 1
    return folder


_DISK_ROOTS_TTL = 45.0
_DISK_ROOTS_CACHE: tuple[float, list[dict[str, str]]] | None = None
_MOUNT_CACHE: tuple[float, set[str]] | None = None
_MOUNT_TTL = 60.0


def list_disk_roots(*, force: bool = False) -> list[dict[str, str]]:
    """列出本机与已挂载局域网卷，供项目/知识库选存放位置。

    Each item: ``{path, label, kind}`` where kind is ``local`` | ``network`` | ``other``.
    Results are cached briefly to avoid UI stalls on every settings/knowledge load.
    """
    import sys
    import time

    global _DISK_ROOTS_CACHE, _MOUNT_CACHE
    now = time.monotonic()
    if (
        not force
        and _DISK_ROOTS_CACHE is not None
        and now - _DISK_ROOTS_CACHE[0] < _DISK_ROOTS_TTL
    ):
        return [dict(x) for x in _DISK_ROOTS_CACHE[1]]

    roots: list[dict[str, str]] = []
    seen: set[str] = set()
    net_mounts = _network_mount_paths()

    def _add(
        path: Path,
        label: str,
        kind: str = "",
        *,
        trust_exists: bool = False,
    ) -> None:
        raw = str(path.expanduser())
        if not kind:
            kind = "network" if _path_looks_network(raw, net_mounts) else "local"
        # 网络卷禁止 resolve()/二次 exists：慢盘或掉线会卡死 UI 线程
        if kind == "network":
            display = raw
            if not trust_exists:
                try:
                    if not path.expanduser().is_dir():
                        return
                except OSError:
                    return
        else:
            try:
                display = str(path.expanduser().resolve(strict=False))
            except OSError:
                display = raw
            if not trust_exists:
                try:
                    if not path.expanduser().exists():
                        return
                except OSError:
                    return
        if display in seen:
            return
        seen.add(display)
        if kind == "network" and "局域网" not in label and "网络" not in label:
            label = f"{label} · 局域网"
        roots.append({"path": display, "label": label, "kind": kind})

    home = Path.home()
    _add(home, "用户目录", "local")
    _add(DEFAULT_BASE.expanduser().parent, "默认项目父目录", "local")

    if sys.platform == "darwin":
        vols = Path("/Volumes")
        if vols.is_dir():
            try:
                entries = sorted(vols.iterdir(), key=lambda p: p.name.lower())
            except OSError:
                entries = []
            for v in entries:
                try:
                    if not v.is_dir() or v.name.startswith("."):
                        continue
                except OSError:
                    continue
                kind = "network" if _path_looks_network(str(v), net_mounts) else "local"
                _add(v, v.name, kind, trust_exists=True)
    elif sys.platform == "win32":
        import string

        for letter in string.ascii_uppercase:
            drive = Path(f"{letter}:\\")
            try:
                if not drive.exists():
                    continue
            except OSError:
                continue
            kind = "network" if _win_drive_is_remote(letter) else "local"
            tag = "网络盘" if kind == "network" else "盘"
            _add(drive, f"{letter}: {tag}", kind, trust_exists=True)
    else:
        _add(Path("/"), "系统根目录", "local")
        for media in (Path("/media"), Path("/mnt"), Path("/run/media")):
            if not media.is_dir():
                continue
            try:
                for child in sorted(media.iterdir()):
                    if child.is_dir() and not child.name.startswith("."):
                        kind = (
                            "network"
                            if _path_looks_network(str(child), net_mounts)
                            else "local"
                        )
                        _add(child, child.name, kind, trust_exists=True)
            except OSError:
                continue

    roots.sort(key=lambda r: (0 if r.get("kind") == "network" else 1, r["label"].lower()))
    _DISK_ROOTS_CACHE = (now, [dict(x) for x in roots])
    return [dict(x) for x in roots]


def _network_mount_paths() -> set[str]:
    """Best-effort set of mount points that are SMB/NFS/AFP/WebDAV/etc."""
    import subprocess
    import sys
    import time

    global _MOUNT_CACHE
    now = time.monotonic()
    if _MOUNT_CACHE is not None and now - _MOUNT_CACHE[0] < _MOUNT_TTL:
        return set(_MOUNT_CACHE[1])

    out: set[str] = set()
    try:
        raw = subprocess.check_output(
            ["mount"], stderr=subprocess.DEVNULL, text=True, timeout=1.5,
        )
    except (OSError, subprocess.SubprocessError):
        _MOUNT_CACHE = (now, out)
        return out
    net_markers = (
        "smbfs", "afpfs", "nfs", "webdav", "cifs", "fuse.sshfs",
        "fuse.rclone", "osxfs", "//",
    )
    for line in raw.splitlines():
        lower = line.lower()
        if not any(m in lower for m in net_markers):
            continue
        if " on " in line:
            try:
                mid = line.split(" on ", 1)[1]
                mp = mid.split(" (", 1)[0].split(" type ", 1)[0].strip()
                if mp:
                    out.add(str(Path(mp)))
            except (IndexError, ValueError):
                continue
    if sys.platform == "darwin":
        for line in raw.splitlines():
            if "/volumes/" not in line.lower():
                continue
            if "//" in line or "smbfs" in line.lower() or "afpfs" in line.lower() or "nfs" in line.lower():
                if " on " in line:
                    mid = line.split(" on ", 1)[1]
                    mp = mid.split(" (", 1)[0].strip()
                    if mp:
                        out.add(str(Path(mp)))
    _MOUNT_CACHE = (now, set(out))
    return out


def _path_looks_network(path: str, net_mounts: set[str] | None = None) -> bool:
    raw = str(path)
    p = raw.replace("\\", "/")
    if p.startswith("//") or raw.startswith("\\\\"):
        return True
    mounts = net_mounts if net_mounts is not None else _network_mount_paths()
    # 不用 Path.resolve()：慢盘 / 掉线 NAS 会卡死 UI
    try:
        expanded = str(Path(path).expanduser()).replace("\\", "/")
    except OSError:
        expanded = p
    candidates = {p, expanded}
    for m in mounts:
        mp = str(m).replace("\\", "/")
        for c in candidates:
            if c == mp or c.startswith(mp.rstrip("/") + "/"):
                return True
    return False


def _win_drive_is_remote(letter: str) -> bool:
    try:
        import ctypes

        root = f"{letter}:\\"
        # DRIVE_REMOTE = 4
        return int(ctypes.windll.kernel32.GetDriveTypeW(root)) == 4
    except Exception:  # noqa: BLE001
        return False


def is_network_storage_path(path: str | Path) -> bool:
    """True if path is UNC or on a mounted LAN/NAS volume."""
    return _path_looks_network(str(Path(path).expanduser()))


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
    """追加一条用户/助手消息到对话（jsonl 事件流 + 同步重写 md 可读版）。"""
    append_event(project, conv_id, role, text=text)


def append_event(
    project: Project,
    conv_id: str,
    role: str,
    *,
    text: str = "",
    name: str = "",
) -> None:
    """追加一条对话事件：user / assistant / thinking / tool。"""
    d = conversation_dir(project)
    line: dict[str, Any] = {
        "role": role,
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if text:
        line["text"] = text
    if name:
        line["name"] = name
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
        chat = [m for m in msgs if m.get("role") in ("user", "assistant")]
        first_user = next((m for m in chat if m.get("role") == "user"), None)
        title_src = first_user or (chat[0] if chat else msgs[0])
        title = (title_src.get("text") or title_src.get("name") or "")[:30]
        out.append({
            "id": f.stem,
            "title": title.replace("\n", " "),
            "created": msgs[0].get("ts", ""),
            "count": len(chat),
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
        role = m.get("role")
        ts = m.get("ts", "")
        if role == "user":
            parts.append(f"\n## 🧑 用户 · {ts}\n\n{m.get('text', '')}\n")
        elif role == "assistant":
            parts.append(f"\n## 🤖 助手 · {ts}\n\n{m.get('text', '')}\n")
        elif role == "thinking":
            parts.append(f"\n### 💭 思考 · {ts}\n\n{m.get('text', '')}\n")
        elif role == "tool":
            parts.append(f"\n- 🔧 `{m.get('name') or m.get('text', '')}` · {ts}\n")
        else:
            parts.append(f"\n## {role} · {ts}\n\n{m.get('text', '')}\n")
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
