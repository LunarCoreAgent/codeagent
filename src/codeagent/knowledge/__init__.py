"""CodeCoreAgent knowledge base — Obsidian / LLM-Wiki vault.

Layout (Karpathy LLM Wiki pattern, Obsidian-compatible)::

    <vault>/
      AGENTS.md              # schema for CodeCoreAgent / any agent
      .obsidian/             # minimal so Obsidian opens the folder as a vault
      raw/                   # Layer 1 — immutable sources
        inbox/
        projects/
        conversations/
      wiki/                  # Layer 2 — LLM-maintained pages
        index.md
        log.md
        overview.md
        concepts/
        entities/
        projects/
        syntheses/

Connection modes:
- **local** — path on this machine (default ``~/Documents/CodeCoreAgent-Wiki``)
- **shared** — network / synced folder (NAS mount, SMB, Syncthing, iCloud,
  Dropbox, OneDrive, etc.). Same vault layout; any computer pointing at the
  same path shares the knowledge base.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

CONFIG_PATH = Path("~/.codeagent/knowledge.json")
DEFAULT_LOCAL_PATH = Path("~/Documents/CodeCoreAgent-Wiki")

VAULT_DIRS = (
    "raw/inbox",
    "raw/projects",
    "raw/conversations",
    "wiki/concepts",
    "wiki/entities",
    "wiki/projects",
    "wiki/syntheses",
    "templates",
    ".obsidian",
)


AGENTS_MD = """# CodeCoreAgent 知识库 Schema（LLM Wiki）

本目录是 CodeCoreAgent 的知识库，兼容 **Obsidian** 与 **LLM Wiki** 约定。
Agent 读写本库时请遵守下列规则。

## 三层结构

1. `raw/` — 原始资料，只增不改（对话摘录、文档、链接笔记）。
2. `wiki/` — 由 LLM 维护的维基页（概念、实体、项目、综合）。
3. 本文件 `AGENTS.md` — 操作约定（Schema）。

## 写入约定

- 新建概念 → `wiki/concepts/<slug>.md`
- 新建实体（人/库/服务）→ `wiki/entities/<slug>.md`
- 项目纪要 → `wiki/projects/<slug>.md`
- 综合对比 → `wiki/syntheses/<slug>.md`
- 每次 ingest / 重要更新后：更新 `wiki/index.md`，并在 `wiki/log.md` **追加**一行。
- 使用 `[[wikilinks]]` 互相引用；YAML frontmatter 可选：`tags`, `updated`, `status`。

## 查询约定

1. 先读 `wiki/overview.md` 与 `wiki/index.md`。
2. 再按关键词打开相关 `concepts/` / `entities/` / `projects/` 页。
3. 原始出处在 `raw/`；不要修改 `raw/` 已有文件。

## CodeCoreAgent 领域

- 本地 / API / 聚合模型配置
- 项目工作区与对话记录
- 工具权限与自动化 / 进化
- 用户偏好与可复用决策

更新本 Schema 时保持简洁，优先可执行规则。
"""

INDEX_MD = """# Wiki Index

| 页面 | 类型 | 说明 |
|------|------|------|
| [[overview]] | 总览 | 知识库导航入口 |
| [[log]] | 日志 | 追加式变更记录 |

> 一键布置后由 Agent / 你持续补充。使用 Obsidian 打开本库可查看图谱与反向链接。
"""

OVERVIEW_MD = """# Overview

CodeCoreAgent 知识库已就绪。

## 快速入口

- [[index]] — 页面目录
- [[log]] — 变更日志
- `raw/inbox/` — 投放待整理的原始材料
- `wiki/concepts/` — 概念页
- `wiki/projects/` — 项目纪要

## 跨电脑

将本库放在 NAS / 网盘同步目录，并在各台电脑的「知识库」设置中指向同一路径即可共享。
"""

LOG_MD = """# Wiki Log

| 时间 | 事件 |
|------|------|
| {ts} | 一键布置：创建 CodeCoreAgent LLM Wiki 结构 |
"""

INBOX_README = """# Inbox

把待整理的原始材料放在这里（PDF 摘录、链接、对话粘贴等）。
Agent ingest 后写入 `wiki/`，请勿手改已归档的 `raw/` 文件。
"""

OBSIDIAN_APP = """{
  "newFileLocation": "folder",
  "newFileFolderPath": "wiki",
  "attachmentFolderPath": "raw/inbox",
  "useMarkdownLinks": false,
  "showUnsupportedFiles": true
}
"""

OBSIDIAN_APPEARANCE = """{
  "cssTheme": ""
}
"""

CONCEPT_TEMPLATE = """---
tags: [concept]
updated: {{date}}
status: draft
---

# {{title}}

## 摘要

## 关联

-

## 来源

- [[]]
"""


@dataclass
class KnowledgeConfig:
    """Persisted connection settings for the knowledge vault."""

    enabled: bool = True
    # local = this machine; shared = network / synced folder (same layout)
    mode: str = "local"
    # obsidian | llmwiki — same on-disk layout; label for UI only
    backend: str = "obsidian"
    path: str = ""
    bootstrapped: bool = False

    def __post_init__(self) -> None:
        if self.mode not in ("local", "shared"):
            self.mode = "local"
        if self.backend not in ("obsidian", "llmwiki"):
            self.backend = "obsidian"
        if not self.path.strip():
            self.path = str(DEFAULT_LOCAL_PATH.expanduser())

    @classmethod
    def load(cls, path: Path | None = None) -> "KnowledgeConfig":
        path = Path(path or CONFIG_PATH).expanduser()
        if not path.is_file():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: Path | None = None) -> None:
        path = Path(path or CONFIG_PATH).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def vault_path(self) -> Path:
        return Path(self.path).expanduser()


@dataclass
class WikiPage:
    rel: str
    title: str
    preview: str = ""
    mtime: float = 0.0
    size: int = 0


def _title_from_md(text: str, fallback: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip() or fallback
    return fallback


def is_vault_ready(root: Path) -> bool:
    return (root / "AGENTS.md").is_file() and (root / "wiki").is_dir()


def bootstrap_vault(root: Path) -> dict[str, Any]:
    """Create the CodeCoreAgent LLM Wiki / Obsidian layout. Idempotent."""
    root = Path(root).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for rel in VAULT_DIRS:
        d = root / rel
        if not d.is_dir():
            d.mkdir(parents=True, exist_ok=True)
            created.append(rel + "/")

    files: dict[str, str] = {
        "AGENTS.md": AGENTS_MD,
        "wiki/index.md": INDEX_MD,
        "wiki/overview.md": OVERVIEW_MD,
        "wiki/log.md": LOG_MD.format(
            ts=time.strftime("%Y-%m-%d %H:%M"),
        ),
        "raw/inbox/README.md": INBOX_README,
        ".obsidian/app.json": OBSIDIAN_APP,
        ".obsidian/appearance.json": OBSIDIAN_APPEARANCE,
        "templates/concept.md": CONCEPT_TEMPLATE,
    }
    for rel, body in files.items():
        p = root / rel
        if not p.is_file():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
            created.append(rel)

    return {
        "ok": True,
        "path": str(root),
        "created": created,
        "ready": is_vault_ready(root),
    }


def vault_status(root: Path) -> dict[str, Any]:
    root = Path(root).expanduser()
    exists = root.exists()
    ready = is_vault_ready(root) if exists else False
    writable = False
    if exists:
        try:
            writable = os.access(root, os.W_OK)
        except OSError:
            writable = False
    pages = 0
    if ready:
        pages = sum(1 for _ in (root / "wiki").rglob("*.md"))
    return {
        "path": str(root),
        "exists": exists,
        "ready": ready,
        "writable": writable,
        "page_count": pages,
        "has_obsidian": (root / ".obsidian").is_dir() if exists else False,
        "agents_md": (root / "AGENTS.md").is_file() if exists else False,
    }


def list_pages(root: Path, query: str = "", limit: int = 80) -> list[WikiPage]:
    root = Path(root).expanduser()
    if not root.is_dir():
        return []
    q = query.strip().lower()
    tokens = [t for t in re.split(r"\s+", q) if t] if q else []
    out: list[WikiPage] = []
    # Prefer wiki/, then raw/ sources
    paths: list[Path] = []
    wiki = root / "wiki"
    raw = root / "raw"
    if wiki.is_dir():
        paths.extend(wiki.rglob("*.md"))
    if raw.is_dir():
        paths.extend(raw.rglob("*.md"))
    paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            st = path.stat()
        except OSError:
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        title = _title_from_md(text, path.stem)
        hay = f"{rel}\n{title}\n{text[:2000]}".lower()
        if tokens and not all(t in hay for t in tokens):
            continue
        preview = " ".join(text.split())[:160]
        out.append(
            WikiPage(
                rel=rel,
                title=title,
                preview=preview,
                mtime=st.st_mtime,
                size=st.st_size,
            )
        )
        if len(out) >= limit:
            break
    return out


def read_page(root: Path, rel: str) -> dict[str, Any] | None:
    root = Path(root).expanduser()
    rel = rel.replace("\\", "/").lstrip("/")
    if ".." in rel.split("/"):
        return None
    path = (root / rel).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "rel": rel,
        "title": _title_from_md(text, path.stem),
        "content": text,
        "mtime": path.stat().st_mtime,
    }


def append_log(root: Path, event: str) -> None:
    root = Path(root).expanduser()
    log = root / "wiki" / "log.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    if not log.is_file():
        log.write_text(LOG_MD.format(ts=time.strftime("%Y-%m-%d %H:%M")), encoding="utf-8")
    line = f"| {time.strftime('%Y-%m-%d %H:%M')} | {event.strip()} |\n"
    with log.open("a", encoding="utf-8") as f:
        f.write(line)


def ingest_text(root: Path, title: str, body: str, folder: str = "raw/inbox") -> dict[str, Any]:
    """Drop a markdown note into raw/ (immutable source layer)."""
    root = Path(root).expanduser()
    folder = folder.replace("\\", "/").strip("/")
    if not folder.startswith("raw/"):
        folder = "raw/inbox"
    slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", title.strip())[:60].strip("-") or "note"
    dest_dir = root / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{time.strftime('%Y%m%d-%H%M%S')}-{slug}.md"
    path = dest_dir / name
    path.write_text(f"# {title.strip()}\n\n{body.strip()}\n", encoding="utf-8")
    append_log(root, f"ingest raw：{folder}/{name}")
    return {"ok": True, "rel": f"{folder}/{name}", "path": str(path)}
