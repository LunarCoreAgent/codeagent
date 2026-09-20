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
安装 / 首次启动时由软件自动部署；Agent 读写本库时请遵守下列规则。

灵感对齐（本地落地，不强制外挂服务）：
- OpenViking 式分层加载（L0/L1/L2）与「按需读全文」
- TencentDB Agent Memory 式四类可复用资产（对话记忆 / Skill / Wiki / 代码图谱）

## 三层结构（磁盘）

1. `raw/` — 原始资料，只增不改（对话摘录、文档、链接笔记）。
2. `wiki/` — 由 LLM 维护的维基页（概念、实体、项目、综合）。
3. 本文件 `AGENTS.md` — 操作约定（Schema）。

## 上下文分层（读写策略）

| 层 | 含义 | 本库对应 |
|----|------|----------|
| L0 摘要 | 一句话判断是否相关 | 页首「摘要」或 `wiki/overview.md` / index 一行 |
| L1 概览 | 结构与要点，够做计划 | 概念/项目页正文前半；`[[wikilinks]]` |
| L2 详情 | 全文与出处 | 完整 wiki 页 + `raw/` 原文 |

查询时：**先 L0/L1，再按需打开 L2**，避免整库灌进上下文。

## 四类记忆资产（写入时归类）

1. **Chat Memory** — 偏好、决策、事实 → `wiki/entities/`；对话摘录与长期记忆自动备份进 `raw/conversations/`
2. **Skill** — 可复用步骤/清单 → `wiki/concepts/`（或软件 `~/.codeagent/skills/`）
3. **LLM-Wiki** — 文档/设计沉淀 → `wiki/projects/` / `wiki/syntheses/`
4. **Code-Graph** — 模块关系与入口说明 → `wiki/concepts/` + 大量 `[[wikilinks]]`（非强制外挂图库）

## 写入约定

- 新建概念 → `wiki/concepts/<slug>.md`
- 新建实体（人/库/服务）→ `wiki/entities/<slug>.md`
- 项目纪要 → `wiki/projects/<slug>.md`
- 综合对比 → `wiki/syntheses/<slug>.md`
- 每次 ingest / 重要更新后：更新 `wiki/index.md`，并在 `wiki/log.md` **追加**一行。
- 使用 `[[wikilinks]]` 互相引用；YAML frontmatter 可选：`tags`, `updated`, `status`, `layer`。

## 查询约定

1. 先读 `wiki/overview.md` 与 `wiki/index.md`（L0/L1）。
2. 再按关键词打开相关 `concepts/` / `entities/` / `projects/` 页（L2）。
3. 原始出处在 `raw/`；不要修改 `raw/` 已有文件。

## 可选增强（外挂，非默认）

- 向量 / 会话编译 / viking:// 虚拟文件系统 → 见技能 `openviking`
- 团队级 Memory Hub / Proxy 共享 → 见技能 `tencentdb-agent-memory`
默认桌面安装**只**依赖本机 Markdown 库，无需 Docker / 云密钥即可用。

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
| [[context-layers]] | 概念 | L0/L1/L2 分层加载 |
| [[memory-assets]] | 概念 | 四类记忆资产 |
| [[openviking]] | 概念 | OpenViking 可选增强 |
| [[tencentdb-agent-memory]] | 概念 | 腾讯云 Agent Memory 可选增强 |

> 随软件安装自动部署；用 Obsidian 打开本库可查看图谱与反向链接。
"""

OVERVIEW_MD = """# Overview

CodeCoreAgent 知识库已随软件自动部署并就绪。

## 快速入口

- [[index]] — 页面目录
- [[log]] — 变更日志
- [[context-layers]] — 分层加载（OpenViking 思路的本地版）
- [[memory-assets]] — 四类资产（TencentDB Agent Memory 思路的本地版）
- `raw/inbox/` — 投放待整理的原始材料
- `wiki/concepts/` — 概念页
- `wiki/projects/` — 项目纪要

## 跨电脑

将本库放在 NAS / 网盘同步目录，并在各台电脑的「知识库」设置中指向同一路径即可共享。
"""

LOG_MD = """# Wiki Log

| 时间 | 事件 |
|------|------|
| {ts} | {event} |
"""

CONTEXT_LAYERS_MD = """---
tags: [concept, openviking]
updated: auto
status: active
layer: L1
---

# 上下文分层（L0 / L1 / L2）

对齐 [OpenViking](https://github.com/volcengine/OpenViking) 的分层加载思想，落地为本地 Wiki 读写约定。

## 摘要

先用短摘要判断相关，再读概览，最后才拉全文——省 token、降延迟。

## 怎么用

1. **L0**：看 `wiki/index.md` 一行说明或页首摘要。
2. **L1**：读概念/项目页的结构与要点、`[[wikilinks]]`。
3. **L2**：打开完整页或 `raw/` 原文。

Agent 应优先调用 `knowledge_search`，再 `knowledge_read` 打开少量页面，禁止整库粘贴。

## 关联

- [[memory-assets]]
- [[openviking]]
"""

MEMORY_ASSETS_MD = """---
tags: [concept, tencentdb-agent-memory]
updated: auto
status: active
layer: L1
---

# 四类记忆资产

对齐 [TencentDB Agent Memory](https://github.com/TencentCloud/tencentdb-agent-memory) 的资产划分，映射到本机目录。

## 摘要

对话、文档、代码经验应变成可复用资产，而不是每次从零解释。

| 资产 | 本地落点 |
|------|----------|
| Chat Memory | `raw/conversations/` + `wiki/entities/` |
| Skill | `wiki/concepts/` 或 `~/.codeagent/skills/` |
| LLM-Wiki | `wiki/projects/` / `wiki/syntheses/` |
| Code-Graph | 带链接的概念/项目页 |

## 关联

- [[context-layers]]
- [[tencentdb-agent-memory]]
"""

OPENVIKING_MD = """---
tags: [concept, openviking]
updated: auto
status: reference
layer: L1
---

# OpenViking（可选增强）

来源：https://github.com/volcengine/OpenViking （AGPL-3.0）

## 摘要

自进化的 Agent 上下文库：统一 Memory、Knowledge RAG 与 Skills；`viking://` 虚拟文件系统 + 分层检索。

## CodeCoreAgent 默认策略

- **默认**：本机 Markdown Wiki（本目录），无需 pip / 服务端。
- **进阶**：征得同意后 `pip install openviking`，按上游 `openviking-server init` / `doctor` 配置嵌入与 VLM；细节见技能 `openviking`。
- 不要把 AGPL 服务端默认打进桌面安装包。

## 关联

- [[context-layers]]
"""

TENCENTDB_MEMORY_MD = """---
tags: [concept, tencentdb-agent-memory]
updated: auto
status: reference
layer: L1
---

# TencentDB Agent Memory（可选增强）

来源：https://github.com/TencentCloud/tencentdb-agent-memory

## 摘要

团队级 Agent 记忆中枢：Chat Memory / Skill / LLM-Wiki / Code-Graph，经 Memory Hub + Proxy 跨框架共享。

## CodeCoreAgent 默认策略

- **默认**：本机四类资产映射到 `raw/` + `wiki/`（见 [[memory-assets]]）。
- **进阶**：Docker 一键 `deploy/global-images/start-all.sh`（需 Node/LLM 配置）；细节见技能 `tencentdb-agent-memory`。
- 桌面安装包不捆绑其多容器栈。

## 关联

- [[memory-assets]]
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


def bootstrap_vault(root: Path, *, event: str = "") -> dict[str, Any]:
    """Create the CodeCoreAgent LLM Wiki / Obsidian layout. Idempotent."""
    root = Path(root).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for rel in VAULT_DIRS:
        d = root / rel
        if not d.is_dir():
            d.mkdir(parents=True, exist_ok=True)
            created.append(rel + "/")

    ts = time.strftime("%Y-%m-%d %H:%M")
    log_event = (event or "").strip() or "部署：创建 CodeCoreAgent LLM Wiki 结构"
    files: dict[str, str] = {
        "AGENTS.md": AGENTS_MD,
        "wiki/index.md": INDEX_MD,
        "wiki/overview.md": OVERVIEW_MD,
        "wiki/log.md": LOG_MD.format(ts=ts, event=log_event),
        "wiki/concepts/context-layers.md": CONTEXT_LAYERS_MD,
        "wiki/concepts/memory-assets.md": MEMORY_ASSETS_MD,
        "wiki/concepts/openviking.md": OPENVIKING_MD,
        "wiki/concepts/tencentdb-agent-memory.md": TENCENTDB_MEMORY_MD,
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


_vault_seeded: set[str] = set()


def ensure_knowledge_vault(
    cfg: KnowledgeConfig | None = None,
    *,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Ensure the configured vault exists (auto-deploy on install / first launch).

    Safe to call repeatedly: already-ready vaults are not re-scanned every time
    (seed pages filled at most once per process per path).
    """
    cfg = cfg or KnowledgeConfig.load(config_path)
    if not cfg.enabled:
        return {
            "ok": True,
            "skipped": True,
            "reason": "disabled",
            "path": str(cfg.vault_path()),
            "ready": is_vault_ready(cfg.vault_path()),
        }
    root = cfg.vault_path()
    try:
        key = str(root)
    except OSError:
        key = cfg.path
    if is_vault_ready(root):
        if key not in _vault_seeded:
            result = bootstrap_vault(root, event="升级补种：知识库种子页")
            _vault_seeded.add(key)
        else:
            result = {
                "ok": True,
                "path": str(root),
                "created": [],
                "ready": True,
            }
        if not cfg.bootstrapped:
            cfg.bootstrapped = True
            cfg.save(config_path)
        result["ensured"] = True
        result["bootstrapped"] = True
        return result
    try:
        result = bootstrap_vault(
            root, event="随软件自动部署：创建 CodeCoreAgent LLM Wiki 结构"
        )
    except OSError as exc:
        return {"ok": False, "error": str(exc)[:200], "path": str(root)}
    _vault_seeded.add(key)
    cfg.bootstrapped = True
    cfg.enabled = True
    cfg.save(config_path)
    result["ensured"] = True
    result["bootstrapped"] = True
    return result


def vault_status(root: Path, *, count_pages: bool = True) -> dict[str, Any]:
    root = Path(root).expanduser()
    exists = False
    try:
        exists = root.exists()
    except OSError:
        exists = False
    ready = is_vault_ready(root) if exists else False
    writable = False
    if exists:
        try:
            writable = os.access(root, os.W_OK)
        except OSError:
            writable = False
    pages = 0
    if ready and count_pages:
        # 网络盘跳过全库 rglob，避免 UI 卡死
        try:
            from codeagent.desktop.projects import is_network_storage_path

            skip_scan = is_network_storage_path(root)
        except Exception:  # noqa: BLE001
            skip_scan = False
        if skip_scan:
            pages = -1
        else:
            try:
                pages = sum(1 for _ in (root / "wiki").rglob("*.md"))
            except OSError:
                pages = 0
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


def append_memory_backup(root: Path, zone: str, body: str) -> dict[str, Any]:
    """Append a long-term memory snapshot into raw/conversations/ (append-only)."""
    root = Path(root).expanduser()
    slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", (zone or "global").strip())[:60].strip("-") or "global"
    dest_dir = root / "raw" / "conversations"
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{slug}.md"
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    chunk = f"\n## {ts}\n\n{body.strip()}\n"
    if not path.is_file():
        path.write_text(
            f"# 长期记忆备份 · {zone or 'global'}\n\n"
            "由 CodeCoreAgent 在写入长期记忆时自动追加，不改历史段落。\n",
            encoding="utf-8",
        )
    with path.open("a", encoding="utf-8") as fh:
        fh.write(chunk)
    return {"ok": True, "rel": f"raw/conversations/{slug}.md", "path": str(path)}
