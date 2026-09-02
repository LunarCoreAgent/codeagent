"""Chat attachment reading for the desktop composer.

Every file type is recognized: text-like files are inlined directly,
Office Open XML documents (.docx/.xlsx/.pptx) are extracted with the
stdlib ``zipfile`` + XML stripping, PDFs use pypdf when installed, and
anything else contributes its metadata so the model still knows the
file exists and can reason about its name/type/size.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

MAX_CHARS = 20_000  # per-file inline cap, keeps prompts within budget

TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".rst", ".log", ".csv", ".tsv", ".json",
    ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env", ".xml",
    ".html", ".htm", ".css", ".js", ".jsx", ".ts", ".tsx", ".py", ".rb",
    ".go", ".rs", ".java", ".kt", ".c", ".h", ".cpp", ".hpp", ".cs",
    ".swift", ".m", ".mm", ".sh", ".bash", ".zsh", ".fish", ".ps1",
    ".sql", ".graphql", ".proto", ".vue", ".svelte", ".php", ".pl",
    ".lua", ".r", ".jl", ".ex", ".exs", ".erl", ".hs", ".scala",
    ".dockerfile", ".gitignore", ".editorconfig", ".tex", ".diff",
}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico", ".heic"}


def _size_label(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def _strip_xml(xml: str) -> str:
    xml = re.sub(r"<w:(?:tab|br)[^>]*/>", " ", xml)
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    return re.sub(r"\n{3,}", "\n\n", xml).strip()


def _read_ooxml(path: Path, members: tuple[str, ...]) -> str:
    """Extract visible text from Office Open XML (zip of XML parts)."""
    out: list[str] = []
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        for member in members:
            if member in names:
                out.append(_strip_xml(zf.read(member).decode("utf-8", "replace")))
        if not out:  # e.g. xlsx: walk shared strings + all sheets
            for name in sorted(names):
                if name.endswith(".xml") and (
                    "sharedStrings" in name or "/worksheets/" in name
                    or "/slides/" in name
                ):
                    out.append(_strip_xml(zf.read(name).decode("utf-8", "replace")))
    return "\n".join(t for t in out if t)


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages[:50])
    except Exception:  # noqa: BLE001 — corrupt pdf → metadata fallback
        return ""


def read_attachment(path: Path) -> dict[str, Any]:
    """Read one file and return {name, size, ext, kind, text, note}."""
    path = Path(path).expanduser()
    name = path.name
    ext = path.suffix.lower()
    size = path.stat().st_size if path.is_file() else 0
    info: dict[str, Any] = {
        "name": name, "size": _size_label(size), "ext": ext,
        "kind": "binary", "text": "", "note": "",
    }

    text = ""
    if ext in TEXT_EXTS or not ext:
        kind = "text"
        text = path.read_text(encoding="utf-8", errors="replace")
    elif ext == ".docx":
        kind = "docx"
        text = _read_ooxml(path, ("word/document.xml",))
    elif ext in (".xlsx", ".pptx"):
        kind = ext[1:]
        text = _read_ooxml(path, ())
    elif ext == ".pdf":
        kind = "pdf"
        text = _read_pdf(path)
    elif ext in IMAGE_EXTS:
        kind = "image"
    else:
        try:  # unknown extension — attempt utf-8 anyway
            text = path.read_text(encoding="utf-8")
            kind = "text"
        except (UnicodeDecodeError, ValueError):
            kind = "binary"

    info["kind"] = kind
    if text:
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS]
            info["note"] = f"内容过长，已截取前 {MAX_CHARS} 字符"
        info["text"] = text
    elif kind == "pdf":
        info["note"] = "PDF 文本提取需要 pypdf（pip install pypdf），已附带文件信息"
    elif kind == "image":
        info["note"] = "图片文件，当前按文件信息处理"
    elif kind == "binary":
        info["note"] = "二进制文件，已附带文件信息"
    return info


def format_attachments(items: list[dict[str, Any]]) -> str:
    """Render attachments as a prompt prefix block."""
    blocks = []
    for it in items:
        head = f"【附件：{it['name']}（{it['size']}）】"
        if it.get("note"):
            head += f"（{it['note']}）"
        blocks.append(head + ("\n" + it["text"] if it.get("text") else ""))
    return "\n\n".join(blocks)
