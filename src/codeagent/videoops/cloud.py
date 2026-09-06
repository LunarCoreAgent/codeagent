"""Cloud / local HTTP video backends: MiniMax Hailuo, Kimi, ComfyUI.

MiniMax Hailuo uses async ``/v1/video_generation``. Kimi/Moonshot is tried
as OpenAI-style ``/v1/videos`` then MiniMax-shaped ``/v1/video_generation``
on the same host (some consoles expose a video model there).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from codeagent.desktop.models import ApiModel, ModelAssets, load_secret

VIDEO_NAME_RE = re.compile(
    r"hailuo|t2v-|i2v-|minimax-h3|video-0|cogvideo|kling|wan[-_]?2|svd",
    re.I,
)
MINIMAX_HOST_RE = re.compile(r"minimax", re.I)
KIMI_HOST_RE = re.compile(r"moonshot|kimi\.com|kimi\.", re.I)


def api_origin(base_url: str) -> str:
    """``https://host/v1`` → ``https://host``."""
    raw = (base_url or "").strip().rstrip("/")
    if raw.endswith("/v1"):
        raw = raw[:-3]
    return raw.rstrip("/")


def is_video_api_model(
    model: str = "",
    base_url: str = "",
    provider: str = "",
) -> bool:
    """True when the model *name* is a video generator (not a chat LLM)."""
    return bool(VIDEO_NAME_RE.search(model or "") or VIDEO_NAME_RE.search(provider or ""))


def video_backend(
    model: str = "",
    base_url: str = "",
    provider: str = "",
) -> str:
    blob = f"{model} {base_url} {provider}"
    if MINIMAX_HOST_RE.search(blob):
        return "minimax"
    if KIMI_HOST_RE.search(blob):
        return "kimi"
    if "comfy" in blob.lower() or ":8188" in blob:
        return "comfy"
    if VIDEO_NAME_RE.search(model or ""):
        return "minimax"
    return ""


def _from_api(m: ApiModel) -> dict[str, str]:
    return {
        "id": m.id,
        "model": m.model,
        "base_url": m.base_url,
        "provider": m.provider,
        "label": m.display,
        "api_key": load_secret(m.secret_key),
        "backend": video_backend(m.model, m.base_url, m.provider),
    }


def list_video_credentials() -> list[dict[str, str]]:
    assets = ModelAssets.load()
    rows: list[dict[str, str]] = []
    for m in assets.api_models:
        row = _from_api(m)
        kind = row["backend"]
        host = f"{m.base_url} {m.provider}"
        if kind or MINIMAX_HOST_RE.search(host) or KIMI_HOST_RE.search(host):
            if not kind:
                row["backend"] = (
                    "minimax" if MINIMAX_HOST_RE.search(host) else "kimi"
                )
            rows.append(row)
    return rows


def pick_credential(backend: str, preferred_model: str = "") -> dict[str, str] | None:
    rows = list_video_credentials()
    if preferred_model:
        for row in rows:
            if row["model"] == preferred_model and (
                not backend or row["backend"] == backend
            ):
                return row
    for row in rows:
        if backend and row["backend"] == backend and row.get("api_key"):
            return row
    for row in rows:
        if backend and row["backend"] == backend:
            return row
    return None


def map_hailuo_resolution(resolution: str) -> str:
    raw = (resolution or "720p").lower().replace(" ", "")
    if raw in {"1080p", "1080", "1920x1080", "1920x1088"}:
        return "1080P"
    if raw in {"480p", "480", "720p", "720", "768p", "768"}:
        if "480" in raw:
            return "720P"
        return "768P"
    if raw.endswith("p"):
        return raw[:-1].upper() + "P"
    return "768P"


def map_duration(num_frames: int, duration: int | None = None) -> int:
    if duration in (4, 5, 6, 10, 15):
        return int(duration)
    if num_frames in (6, 10):
        return int(num_frames)
    return 6


def _minimax_error(data: dict[str, Any]) -> str:
    resp = data.get("base_resp") or {}
    code = resp.get("status_code")
    msg = resp.get("status_msg") or data.get("error") or data.get("message")
    if code not in (None, 0):
        return f"{code}: {msg or 'MiniMax 请求失败'}"
    if isinstance(msg, str) and msg and msg.lower() not in {"success", "ok"}:
        return msg
    return ""


async def _download(url: str, dest: Path, headers: dict[str, str] | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers or {})
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    return dest


async def generate_minimax_video(
    prompt: str,
    dest: Path,
    *,
    api_key: str,
    base_url: str,
    model: str = "MiniMax-Hailuo-2.3",
    resolution: str = "720p",
    duration: int = 6,
) -> dict[str, Any]:
    if not api_key.strip():
        return {"ok": False, "error": "未找到 MiniMax API Key。请在「模型」里为 MiniMax 填密钥。"}
    origin = api_origin(base_url) or "https://api.minimax.chat"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    model = model.strip() or "MiniMax-Hailuo-2.3"
    if not VIDEO_NAME_RE.search(model) and "minimax" not in model.lower():
        model = "MiniMax-Hailuo-2.3"
    payload = {
        "model": model,
        "prompt": prompt,
        "duration": map_duration(0, duration),
        "resolution": map_hailuo_resolution(resolution),
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        created = await client.post(
            f"{origin}/v1/video_generation", headers=headers, json=payload,
        )
        try:
            data = created.json()
        except Exception:
            return {"ok": False, "error": f"MiniMax 创建任务失败 HTTP {created.status_code}"}
        err = _minimax_error(data)
        if created.status_code >= 400 or err:
            return {"ok": False, "error": err or f"HTTP {created.status_code}"}
        task_id = str(data.get("task_id") or "")
        if not task_id:
            return {"ok": False, "error": "MiniMax 未返回 task_id"}
        file_id = ""
        for _ in range(90):
            q = await client.get(
                f"{origin}/v1/query/video_generation",
                headers=headers,
                params={"task_id": task_id},
            )
            body = q.json() if q.headers.get("content-type", "").startswith("application/json") else {}
            status = str(body.get("status") or "").lower()
            if status in {"success", "succeed", "succeeded"}:
                file_id = str(body.get("file_id") or "")
                url = ""
                content = body.get("content")
                if isinstance(content, dict):
                    url = str(content.get("url") or "")
                if url:
                    await _download(url, dest, headers)
                    return {"ok": True, "path": str(dest), "via": "minimax", "task_id": task_id}
                break
            if status in {"fail", "failed", "error"}:
                return {"ok": False, "error": body.get("base_resp", {}).get("status_msg") or "MiniMax 生成失败"}
            await _sleep(4)
        if not file_id:
            return {"ok": False, "error": "MiniMax 任务超时或未返回 file_id"}
        rec = await client.get(
            f"{origin}/v1/files/retrieve",
            headers=headers,
            params={"file_id": file_id},
        )
        rec_data = rec.json() if rec.status_code < 500 else {}
        file_info = rec_data.get("file") or rec_data
        url = str(file_info.get("download_url") or file_info.get("url") or "")
        if not url:
            return {"ok": False, "error": "MiniMax 未返回下载地址"}
        await _download(url, dest)
        return {"ok": True, "path": str(dest), "via": "minimax", "task_id": task_id}


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


async def generate_kimi_video(
    prompt: str,
    dest: Path,
    *,
    api_key: str,
    base_url: str,
    model: str = "",
    resolution: str = "720p",
    duration: int = 6,
) -> dict[str, Any]:
    if not api_key.strip():
        return {"ok": False, "error": "未找到 Kimi / Moonshot API Key。请在「模型」里为 Kimi 填密钥。"}
    origin = api_origin(base_url) or "https://api.moonshot.cn"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    model = (model or "").strip()
    seconds = map_duration(0, duration)
    async with httpx.AsyncClient(timeout=60.0) as client:
        openai_body = {
            "model": model or "kimi-k2.6",
            "prompt": prompt,
            "seconds": str(seconds),
            "size": "1280x720" if "1080" not in resolution.lower() else "1920x1080",
        }
        r = await client.post(f"{origin}/v1/videos", headers=headers, json=openai_body)
        if r.status_code < 400:
            data = r.json()
            video_id = str(data.get("id") or "")
            if video_id:
                for _ in range(90):
                    q = await client.get(f"{origin}/v1/videos/{video_id}", headers=headers)
                    body = q.json() if q.status_code < 500 else {}
                    st = str(body.get("status") or "").lower()
                    if st in {"completed", "succeeded", "success"}:
                        url = ""
                        if isinstance(body.get("url"), str):
                            url = body["url"]
                        content = body.get("content")
                        if isinstance(content, dict):
                            url = url or str(content.get("url") or "")
                        if url:
                            await _download(url, dest, headers)
                            return {"ok": True, "path": str(dest), "via": "kimi", "id": video_id}
                        content_url = f"{origin}/v1/videos/{video_id}/content"
                        cr = await client.get(content_url, headers=headers)
                        if cr.status_code < 400 and cr.content:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            dest.write_bytes(cr.content)
                            return {"ok": True, "path": str(dest), "via": "kimi", "id": video_id}
                    if st in {"failed", "error"}:
                        return {"ok": False, "error": str(body.get("error") or "Kimi 视频生成失败")}
                    await _sleep(4)
        mm_model = model if VIDEO_NAME_RE.search(model) else ""
        if mm_model:
            return await generate_minimax_video(
                prompt, dest, api_key=api_key, base_url=origin + "/v1",
                model=mm_model, resolution=resolution, duration=seconds,
            )
    return {
        "ok": False,
        "error": (
            "Kimi / Moonshot 当前密钥下没有可用的文生视频接口"
            "（对话模型只理解视频）。请在模型管理添加视频模型名，"
            "或改用 MiniMax Hailuo / 局域网 WAN / ComfyUI。"
        ),
    }


async def generate_cloud_video(
    prompt: str,
    dest: Path,
    *,
    backend: str,
    resolution: str = "720p",
    num_frames: int = 60,
    duration: int | None = None,
    model: str = "",
) -> dict[str, Any]:
    cred = pick_credential(backend, preferred_model=model)
    if cred is None:
        label = {"minimax": "MiniMax", "kimi": "Kimi"}.get(backend, backend)
        return {"ok": False, "error": f"未接入 {label}。请到「模型」添加该提供方并保存 API Key。"}
    seconds = map_duration(num_frames, duration)
    if backend == "minimax":
        return await generate_minimax_video(
            prompt, dest,
            api_key=cred["api_key"],
            base_url=cred["base_url"],
            model=model or cred["model"],
            resolution=resolution,
            duration=seconds,
        )
    if backend == "kimi":
        return await generate_kimi_video(
            prompt, dest,
            api_key=cred["api_key"],
            base_url=cred["base_url"],
            model=model or cred["model"],
            resolution=resolution,
            duration=seconds,
        )
    return {"ok": False, "error": f"未知视频后端 {backend}"}
