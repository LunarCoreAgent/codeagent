"""Video generation, editing, ops analysis, and publish drafts.

Fuses LibTV / Remotion / 中文剪辑 / 短剧剧本 / 运营分析 / 多平台发布
into one local workspace. Publishing never auto-clicks platform buttons.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from codeagent.skills.skill import Skill, SkillLibrary
from codeagent.videoops.bundled import BUNDLED_SKILLS

CONFIG_PATH = Path("~/.codeagent/videoops.json")
SKILLS_DIR = Path("~/.codeagent/skills")
DEFAULT_WORKSPACE = Path("~/Documents/CodeCoreAgent-VideoOps")

STAGES = (
    ("01-script", "选题剧本"),
    ("02-generate", "生成"),
    ("03-edit", "剪辑成片"),
    ("04-analyze", "运营分析"),
    ("05-publish", "发布草稿"),
)

PIPELINE_MD = """# 视频运营流水线

| 阶段 | 目录 | 状态 |
|------|------|------|
| 选题剧本 | `01-script/` | 待开始 |
| 生成 | `02-generate/` | 待开始 |
| 剪辑成片 | `03-edit/` | 待开始 |
| 运营分析 | `04-analyze/` | 待开始 |
| 发布草稿 | `05-publish/` | 待开始 |

进度请追加到文末。发布必须人工确认，禁止自动点击平台「发布」。
"""

AGENTS_MD = """# CodeCoreAgent 视频运营工作区

按 `pipeline.md` 推进。技能包：`video-ops-pipeline`、`short-drama-script`、
`wan-gradio`、`libtv-generate`、`remotion-video`、`video-edit-zh`、`ops-analyze`、`multi-publish`。

参考来源（工作流，非内嵌上游全文）：
- LibTV CLI 手册
- Remotion skills
- video-use-zh 中文剪辑
- short-drama 短剧流程
- DeepAnalyze 数据分析思路
- auto-publish / AutoPublish 多平台分发（人工确认发布）
"""

DRAFT_JSON = {
    "title": "",
    "description": "",
    "tags": "",
    "video_path": "",
    "cover_path": "",
    "platforms": ["douyin", "xiaohongshu", "channels", "bilibili", "youtube"],
    "confirm_publish": True,
    "note": "各平台停在发布页，由你点击发布。",
}


@dataclass
class VideoOpsConfig:
    enabled: bool = True
    path: str = ""
    bootstrapped: bool = False
    skills_installed: bool = False
    gradio_base: str = ""  # LAN Gradio 文生视频，如 http://192.168.3.23:7860
    comfy_base: str = ""  # ComfyUI，如 http://127.0.0.1:8188

    def __post_init__(self) -> None:
        if not (self.path or "").strip():
            self.path = str(DEFAULT_WORKSPACE.expanduser())

    @classmethod
    def load(cls, path: Path | None = None) -> "VideoOpsConfig":
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

    def workspace(self) -> Path:
        return Path(self.path).expanduser()


def bundled_library() -> SkillLibrary:
    lib = SkillLibrary()
    for name, (desc, body) in BUNDLED_SKILLS.items():
        lib.add(Skill(name=name, description=desc, content=body))
    return lib


def install_bundled_skills(directory: Path | None = None) -> list[str]:
    """Write bundled packs into ~/.codeagent/skills (overwrite same names)."""
    root = Path(directory or SKILLS_DIR).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    lib = SkillLibrary()
    for name, (desc, body) in BUNDLED_SKILLS.items():
        skill = Skill(name=name, description=desc, content=body)
        lib.save(skill, root)
        written.append(name)
    return written


def load_all_skills(*directories: str | Path) -> SkillLibrary:
    """Video packs + fusion packs, then each directory (later files override)."""
    from codeagent.skills.fusion import fusion_library

    library = bundled_library()
    for skill in fusion_library():
        library.add(skill)
    for directory in directories:
        root = Path(directory).expanduser()
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("SKILL.md")):
            library.add(Skill.parse(path.read_text(encoding="utf-8"), path))
    return library


def is_workspace_ready(root: Path) -> bool:
    return (root / "pipeline.md").is_file() and (root / "01-script").is_dir()


def bootstrap_workspace(root: Path) -> dict[str, Any]:
    root = Path(root).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for rel, _label in STAGES:
        d = root / rel
        if not d.is_dir():
            d.mkdir(parents=True, exist_ok=True)
            created.append(rel + "/")
    files = {
        "AGENTS.md": AGENTS_MD,
        "pipeline.md": PIPELINE_MD,
        "05-publish/draft.json": json.dumps(DRAFT_JSON, ensure_ascii=False, indent=2)
        + "\n",
        "01-script/README.md": "# 选题剧本\n\n把立项状态与分集写在此目录。\n",
        "02-generate/README.md": "# 生成\n\nLibTV 下载或 Remotion 工程放这里。\n",
        "03-edit/README.md": "# 剪辑成片\n\n成片 MP4 与抽帧自检图。\n",
        "04-analyze/README.md": "# 运营分析\n\n把后台导出表和 report.md 放这里。\n",
    }
    for rel, body in files.items():
        p = root / rel
        if not p.is_file():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
            created.append(rel)
    return {"ok": True, "path": str(root), "created": created, "ready": is_workspace_ready(root)}


def append_pipeline(root: Path, event: str) -> None:
    log = Path(root).expanduser() / "pipeline.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    if not log.is_file():
        log.write_text(PIPELINE_MD, encoding="utf-8")
    with log.open("a", encoding="utf-8") as f:
        f.write(f"\n- {time.strftime('%Y-%m-%d %H:%M')} {event.strip()}\n")


def save_publish_draft(root: Path, data: dict[str, Any]) -> dict[str, Any]:
    root = Path(root).expanduser()
    dest = root / "05-publish" / "draft.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    draft = dict(DRAFT_JSON)
    for key in ("title", "description", "tags", "video_path", "cover_path"):
        if key in data and data[key] is not None:
            draft[key] = str(data[key])
    if isinstance(data.get("platforms"), list):
        draft["platforms"] = [str(p) for p in data["platforms"]]
    dest.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_pipeline(root, "更新发布草稿（待人工确认）")
    return {"ok": True, "path": str(dest), "draft": draft}


def toolchain_status() -> dict[str, Any]:
    def which(name: str) -> str:
        return shutil.which(name) or ""

    libtv = which("libtv")
    if not libtv:
        home = Path("~/.libtv/libtv").expanduser()
        if home.is_file():
            libtv = str(home)
    return {
        "libtv": libtv,
        "ffmpeg": which("ffmpeg"),
        "node": which("node"),
        "npx": which("npx"),
        "obsidian": which("obsidian"),
    }


def workspace_status(root: Path) -> dict[str, Any]:
    root = Path(root).expanduser()
    exists = root.exists()
    ready = is_workspace_ready(root) if exists else False
    counts: dict[str, int] = {}
    if ready:
        for rel, _label in STAGES:
            d = root / rel
            counts[rel] = sum(1 for p in d.rglob("*") if p.is_file()) if d.is_dir() else 0
    draft = {}
    draft_path = root / "05-publish" / "draft.json"
    if draft_path.is_file():
        try:
            draft = json.loads(draft_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            draft = {}
    return {
        "path": str(root),
        "exists": exists,
        "ready": ready,
        "counts": counts,
        "draft": draft,
        "toolchain": toolchain_status(),
    }
