"""Read one project's chats, thinking traces, and source files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codeagent.desktop.projects import list_conversations, load_conversation

SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache",
    ".pytest_cache", "dist", "build", "conversations", ".obsidian",
}
CODE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs",
    ".ets", ".java", ".kt", ".swift", ".go", ".rs", ".c", ".cc", ".cpp", ".h",
    ".css", ".scss", ".less", ".html", ".vue", ".svelte",
    ".sql", ".prisma", ".graphql",
    ".json", ".yaml", ".yml", ".toml", ".md",
}
LANG_BY_EXT = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".tsx": "React", ".jsx": "React", ".ets": "ArkTS",
    ".java": "Java", ".kt": "Kotlin", ".swift": "Swift",
    ".go": "Go", ".rs": "Rust", ".css": "CSS", ".html": "HTML",
    ".vue": "Vue", ".sql": "SQL", ".prisma": "Prisma",
}
TOPIC_WORDS = (
    "ui", "ux", "设计", "美化", "界面", "组件", "布局", "数据库", "sqlite",
    "schema", "api", "路由", "流程", "架构", "登录", "权限", "记忆",
    "react", "vue", "arkts", "鸿蒙", "harmony", "node", "python",
)
MAX_CONVS = 8
MAX_EVENTS = 40
MAX_FILES = 24
MAX_FILE_CHARS = 2200
MAX_TEXT = 7000


@dataclass
class ProjectCorpus:
    project_id: str
    project_name: str
    path: str
    chats: str = ""
    thinking: str = ""
    code: str = ""
    files: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)

    def digest(self) -> str:
        parts = [
            f"项目：{self.project_name}",
            f"语言：{', '.join(self.languages) or '未识别'}",
            f"主题：{', '.join(self.topics) or self.project_name}",
        ]
        if self.chats:
            parts.append("对话摘录：\n" + self.chats[:MAX_TEXT])
        if self.thinking:
            parts.append("思考过程：\n" + self.thinking[:3500])
        if self.code:
            parts.append("代码摘录：\n" + self.code[:MAX_TEXT])
        return "\n\n".join(parts)


def _clip(text: str, limit: int) -> str:
    blob = (text or "").strip()
    if len(blob) <= limit:
        return blob
    return blob[: limit - 1] + "…"


def _iter_code_files(root: Path) -> list[Path]:
    files: list[Path] = []
    stack = [root]
    while stack and len(files) < MAX_FILES:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir():
                if entry.name not in SKIP_DIRS and not entry.is_symlink():
                    stack.append(entry)
                continue
            if entry.suffix.lower() in CODE_EXTS and entry.name != "memory.json":
                files.append(entry)
            if len(files) >= MAX_FILES:
                break
    return files


def _topics_from_text(*blobs: str) -> list[str]:
    hay = " ".join(blobs).lower()
    found: list[str] = []
    for word in TOPIC_WORDS:
        if word in hay and word not in found:
            found.append(word)
    return found[:10]


def project_has_conversations(project: Any) -> bool:
    """True when the project folder already has at least one chat turn."""
    try:
        return bool(list_conversations(project))
    except Exception:  # noqa: BLE001
        return False


def projects_with_conversations(projects: list[Any]) -> list[Any]:
    """Keep only projects that have had dialogue (skip empty shells)."""
    return [p for p in (projects or []) if project_has_conversations(p)]


def collect_project(project: Any) -> ProjectCorpus:
    """Load chat / thinking / code for one desktop project."""
    root = Path(getattr(project, "path", "") or "").expanduser()
    name = getattr(project, "name", "") or root.name or "未命名"
    pid = getattr(project, "id", "") or ""
    chat_bits: list[str] = []
    think_bits: list[str] = []
    if root.is_dir():
        for conv in list_conversations(project)[:MAX_CONVS]:
            events = load_conversation(project, conv["id"])[-MAX_EVENTS:]
            for ev in events:
                role = ev.get("role") or ""
                text = _clip(str(ev.get("text") or ""), 400)
                if not text:
                    continue
                if role == "thinking":
                    think_bits.append(text)
                elif role in ("user", "assistant"):
                    label = "用户" if role == "user" else "助手"
                    chat_bits.append(f"{label}：{text}")
    files = _iter_code_files(root) if root.is_dir() else []
    code_bits: list[str] = []
    langs: list[str] = []
    rels: list[str] = []
    for path in files:
        rel = str(path.relative_to(root)) if root in path.parents or path.parent == root else path.name
        rels.append(rel)
        lang = LANG_BY_EXT.get(path.suffix.lower())
        if lang and lang not in langs:
            langs.append(lang)
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        code_bits.append(f"// {rel}\n{_clip(body, MAX_FILE_CHARS)}")
    topics = _topics_from_text(name, " ".join(chat_bits), " ".join(think_bits), " ".join(rels))
    if name and name not in topics:
        topics.insert(0, name)
    return ProjectCorpus(
        project_id=pid,
        project_name=name,
        path=str(root),
        chats=_clip("\n".join(chat_bits), MAX_TEXT),
        thinking=_clip("\n".join(think_bits), 3500),
        code=_clip("\n\n".join(code_bits), MAX_TEXT),
        files=rels,
        languages=langs,
        topics=topics or [name],
    )


QUERY_TEMPLATES = (
    ("code", "{topic} {lang} 实现 最佳实践 示例代码"),
    ("ui", "{topic} UI 设计 美化 组件 布局"),
    ("design", "{topic} 视觉设计 设计系统 配色"),
    ("flow", "{topic} 流程设计 架构 工作流"),
    ("database", "{topic} 数据库设计 schema 数据模型"),
    ("tech", "{topic} {lang} 技术 文档"),
)


def build_queries(corpus: ProjectCorpus, limit: int = 6) -> list[tuple[str, str]]:
    """Search queries covering code / UI / design / flow / database / tech."""
    topics = corpus.topics[:3] or [corpus.project_name]
    lang = corpus.languages[0] if corpus.languages else "软件"
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for kind, tmpl in QUERY_TEMPLATES:
        topic = topics[0]
        if kind == "code" and len(topics) > 1:
            topic = topics[1]
        q = re.sub(r"\s+", " ", tmpl.format(topic=topic, lang=lang)).strip()
        if q in seen:
            continue
        seen.add(q)
        out.append((kind, q))
        if len(out) >= limit:
            break
    return out
