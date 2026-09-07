"""Director desk: script → shots → Comfy/WAN/cloud generate → ffmpeg assemble.

Follows ComfyUI local API (https://docs.comfy.org/zh , https://github.com/Comfy-Org/ComfyUI):
Save (API Format) JSON → POST /prompt → GET /history/{id} → GET /view.
Comfy is a node graph, not a chat model.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from codeagent.videoops import VideoOpsConfig, append_pipeline, bootstrap_workspace

DESK_DIR = "00-desk"
DESK_FILE = "desk.json"
SHOTS_DIR = "shots"
ASSEMBLE_DIR = "assembly"

ENGINES = ("auto", "comfy", "wan", "minimax", "kimi")
ASPECTS = ("9:16", "16:9", "1:1")
STAGES = ("plan", "board", "generate", "assemble", "final")
STAGE_LABELS = {
    "plan": "企划",
    "board": "分镜",
    "generate": "生成",
    "assemble": "合成",
    "final": "成片",
}


@dataclass
class Shot:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    title: str = ""
    prompt: str = ""
    seconds: float = 4.0
    engine: str = "auto"
    status: str = "draft"  # draft | queued | running | done | error
    clip: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        if self.engine not in ENGINES:
            self.engine = "auto"
        try:
            self.seconds = max(1.0, min(20.0, float(self.seconds)))
        except (TypeError, ValueError):
            self.seconds = 4.0


@dataclass
class Desk:
    title: str = ""
    logline: str = ""
    aspect: str = "9:16"
    duration_sec: int = 24
    engine: str = "comfy"
    workflow_path: str = ""
    stage: str = "plan"
    shots: list[Shot] = field(default_factory=list)
    assembled: str = ""
    updated: str = ""

    def __post_init__(self) -> None:
        if self.aspect not in ASPECTS:
            self.aspect = "9:16"
        if self.engine not in ENGINES:
            self.engine = "comfy"
        if self.stage not in STAGES:
            self.stage = "plan"
        raw = self.shots
        out: list[Shot] = []
        for item in raw:
            if isinstance(item, Shot):
                out.append(item)
            elif isinstance(item, dict):
                known = {k: item[k] for k in Shot.__dataclass_fields__ if k in item}
                out.append(Shot(**known))
        self.shots = out


def desk_root(workspace: Path | None = None) -> Path:
    cfg = VideoOpsConfig.load()
    root = Path(workspace or cfg.workspace()).expanduser()
    return root / DESK_DIR


def desk_path(workspace: Path | None = None) -> Path:
    return desk_root(workspace) / DESK_FILE


def load_desk(workspace: Path | None = None) -> Desk:
    path = desk_path(workspace)
    if not path.is_file():
        return Desk()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return Desk()
    if not isinstance(data, dict):
        return Desk()
    known = {k: data[k] for k in Desk.__dataclass_fields__ if k in data}
    return Desk(**known)


def save_desk(desk: Desk, workspace: Path | None = None) -> Path:
    root = desk_root(workspace)
    root.mkdir(parents=True, exist_ok=True)
    (root / SHOTS_DIR).mkdir(exist_ok=True)
    (root / ASSEMBLE_DIR).mkdir(exist_ok=True)
    desk.updated = time.strftime("%Y-%m-%d %H:%M:%S")
    dest = root / DESK_FILE
    dest.write_text(
        json.dumps(asdict(desk), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return dest


def ensure_desk_workspace() -> Path:
    cfg = VideoOpsConfig.load()
    root = cfg.workspace()
    bootstrap_workspace(root)
    desk_root(root).mkdir(parents=True, exist_ok=True)
    (desk_root(root) / SHOTS_DIR).mkdir(exist_ok=True)
    (desk_root(root) / ASSEMBLE_DIR).mkdir(exist_ok=True)
    readme = desk_root(root) / "README.md"
    if not readme.is_file():
        readme.write_text(
            "# 导演台\n\n企划 → 分镜 → ComfyUI/WAN/云端生成 → ffmpeg 合成。\n"
            "Comfy 工作流须为菜单 Save (API Format) 的 JSON。\n"
            "文档：https://docs.comfy.org/zh  ·  https://github.com/Comfy-Org/ComfyUI\n",
            encoding="utf-8",
        )
    return root


def desk_dict(desk: Desk) -> dict[str, Any]:
    return asdict(desk)


def parse_script_shots(text: str) -> list[Shot]:
    """Turn a script / shot list into director-desk shots."""
    raw = (text or "").replace("\r\n", "\n").strip()
    if not raw:
        return []
    marks = [m.start() for m in re.finditer(
        r"(?m)^(?:#{1,3}\s+|\d+\s*[.、．:：]\s+)", raw,
    )]
    chunks: list[str]
    if marks:
        bounds = marks + [len(raw)]
        chunks = [raw[a:b].strip() for a, b in zip(bounds, bounds[1:])]
    else:
        chunks = [p.strip() for p in re.split(r"\n{2,}", raw) if p.strip()]
    shots: list[Shot] = []
    for i, block in enumerate(chunks, 1):
        if not block:
            continue
        first, _, rest = block.partition("\n")
        title = re.sub(r"^#{1,3}\s*", "", first)
        title = re.sub(r"^\s*\d+\s*[.、．:：]\s*", "", title).strip() or f"镜头 {i}"
        prompt = (rest.strip() or title).strip()
        shots.append(Shot(title=title[:80], prompt=prompt[:2000], seconds=4.0))
    return shots[:40]


def apply_desk_patch(desk: Desk, data: dict[str, Any]) -> Desk:
    if "title" in data:
        desk.title = str(data.get("title") or "")[:120]
    if "logline" in data:
        desk.logline = str(data.get("logline") or "")[:800]
    if data.get("aspect") in ASPECTS:
        desk.aspect = str(data["aspect"])
    if "duration_sec" in data:
        try:
            desk.duration_sec = max(4, min(180, int(data["duration_sec"])))
        except (TypeError, ValueError):
            pass
    if data.get("engine") in ENGINES:
        desk.engine = str(data["engine"])
    if "workflow_path" in data:
        desk.workflow_path = str(data.get("workflow_path") or "").strip()
    if data.get("stage") in STAGES:
        desk.stage = str(data["stage"])
    if isinstance(data.get("shots"), list):
        desk.shots = []
        for item in data["shots"]:
            if isinstance(item, dict):
                known = {k: item[k] for k in Shot.__dataclass_fields__ if k in item}
                desk.shots.append(Shot(**known))
            elif isinstance(item, str) and item.strip():
                desk.shots.append(Shot(title=item[:40], prompt=item[:2000]))
    return desk


async def generate_one_shot(desk: Desk, shot_id: str) -> dict[str, Any]:
    """Queue one shot through video_generate backends. Mutates and saves desk."""
    shot = next((s for s in desk.shots if s.id == shot_id), None)
    if shot is None:
        return {"ok": False, "error": "镜头不存在"}
    prompt = (shot.prompt or shot.title or desk.logline or desk.title).strip()
    if not prompt:
        shot.status = "error"
        shot.error = "镜头没有画面描述"
        save_desk(desk)
        return {"ok": False, "error": shot.error}

    root = ensure_desk_workspace()
    dest_dir = desk_root(root) / SHOTS_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    engine = shot.engine if shot.engine != "auto" else desk.engine
    shot.status = "running"
    shot.error = ""
    save_desk(desk)

    from codeagent.videoops.tools import VideoGenerateTool

    seconds = int(round(shot.seconds))
    frames = max(33, min(81, seconds * 12))
    result_text = await VideoGenerateTool().execute(
        prompt=prompt,
        provider=engine,
        resolution="720p" if desk.aspect != "16:9" else "1080p",
        num_frames=frames,
        duration=seconds,
        workflow_path=desk.workflow_path,
        dest_dir=str(dest_dir),
    )
    if result_text.startswith("saved:"):
        clip = result_text.split("saved:", 1)[1].strip()
        shot.clip = clip
        shot.status = "done"
        shot.error = ""
        save_desk(desk)
        append_pipeline(root, f"导演台镜头 {shot.title or shot.id} → {Path(clip).name}")
        return {"ok": True, "shot": asdict(shot)}
    shot.status = "error"
    shot.error = result_text[:400]
    save_desk(desk)
    return {"ok": False, "error": shot.error, "shot": asdict(shot)}


def assemble_desk(desk: Desk) -> dict[str, Any]:
    clips = [Path(s.clip).expanduser() for s in desk.shots if (s.clip or "").strip()]
    clips = [p for p in clips if p.is_file()]
    if not clips:
        return {"ok": False, "error": "没有已生成的镜头文件。先在「生成」把分镜跑完。"}
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {"ok": False, "error": "未安装 ffmpeg。合成成片需要本机 ffmpeg。"}
    root = ensure_desk_workspace()
    dest = desk_root(root) / ASSEMBLE_DIR / f"cut-{time.strftime('%Y%m%d-%H%M%S')}.mp4"
    dest.parent.mkdir(parents=True, exist_ok=True)
    lst = dest.with_suffix(".txt")
    lines = []
    for clip in clips:
        p = str(clip.resolve()).replace("'", r"'\''")
        lines.append(f"file '{p}'")
    lst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(dest)]
    ran = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if ran.returncode != 0 or not dest.is_file():
        cmd = [
            ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
            str(dest),
        ]
        ran = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if ran.returncode != 0 or not dest.is_file():
        err = (ran.stderr or ran.stdout or "ffmpeg failed")[-400:]
        return {"ok": False, "error": err}
    desk.assembled = str(dest)
    desk.stage = "final"
    save_desk(desk)
    append_pipeline(root, f"导演台合成 {dest.name}（{len(clips)} 镜）")
    return {"ok": True, "path": str(dest), "clips": len(clips)}
