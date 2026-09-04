"""LAN Gradio 文生视频（WAN-1.3B 等）。

Matches the Gradio-exported Python API:

    Client(url).predict(..., api_name="/generate_video")
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

from codeagent.videoops import VideoOpsConfig

RESOLUTIONS = {
    "480": "480p (832x480)",
    "480p": "480p (832x480)",
    "720": "720p (1280x720)",
    "720p": "720p (1280x720)",
    "1080": "1080p (1920x1088)",
    "1080p": "1080p (1920x1088)",
}


def normalize_resolution(value: str) -> str:
    raw = (value or "720p").strip()
    key = raw.lower().replace(" ", "")
    for prefix, label in RESOLUTIONS.items():
        if key == prefix or key.startswith(prefix):
            return label
    if "832x480" in raw:
        return RESOLUTIONS["480p"]
    if "1280x720" in raw:
        return RESOLUTIONS["720p"]
    if "1920x1088" in raw or "1920x1080" in raw:
        return RESOLUTIONS["1080p"]
    return RESOLUTIONS["720p"]


def parse_sse_complete(text: str) -> Any:
    """Return the JSON payload of the last SSE ``complete`` event, or None."""
    event = "message"
    data_lines: list[str] = []
    complete: Any = None
    error: str | None = None

    def flush() -> None:
        nonlocal event, complete, error
        if not data_lines:
            event = "message"
            return
        raw = "\n".join(data_lines).strip()
        data_lines.clear()
        parsed: Any = None
        if raw and raw != "null":
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw
        if event == "error":
            error = str(parsed)[:400]
        elif event == "complete":
            complete = parsed
        event = "message"

    for line in text.splitlines():
        if line.startswith("event:"):
            event = line[6:].strip() or "message"
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
        elif line == "":
            flush()
    flush()
    if error:
        raise RuntimeError(error)
    return complete


def extract_file(payload: Any) -> dict[str, Any]:
    """Unwrap Gradio FileData from predict / SSE complete payload."""
    cur: Any = payload
    for _ in range(6):
        if isinstance(cur, dict) and ("path" in cur or "url" in cur):
            return {
                "path": str(cur.get("path") or ""),
                "url": str(cur.get("url") or ""),
                "orig_name": str(cur.get("orig_name") or ""),
            }
        if isinstance(cur, dict) and "data" in cur:
            cur = cur["data"]
            continue
        if isinstance(cur, list) and cur:
            cur = cur[0]
            continue
        break
    raise RuntimeError(f"Gradio 未返回视频文件：{str(payload)[:200]}")


def resolve_gradio_base(cfg: VideoOpsConfig | None = None) -> str:
    cfg = cfg or VideoOpsConfig.load()
    raw = (cfg.gradio_base or "").strip().rstrip("/")
    if raw:
        return raw
    try:
        from codeagent.desktop.models import ModelAssets

        for ep in ModelAssets.load().endpoints:
            if ep.kind == "gradio" and ep.base:
                return ep.base.rstrip("/")
    except Exception:  # noqa: BLE001 — assets optional
        pass
    return ""


async def probe_gradio_app(base: str, timeout: float = 4.0) -> dict[str, Any] | None:
    root = (base or "").rstrip("/")
    if not root:
        return None
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(root + "/config")
            if resp.status_code >= 400:
                return None
            cfg = resp.json()
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(cfg, dict):
        return None
    if not isinstance(cfg.get("components"), list) and "dependencies" not in cfg:
        return None
    title = str(cfg.get("title") or "").strip() or "Gradio"
    endpoints: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            info = await client.get(root + "/gradio_api/info")
            if info.status_code < 400:
                named = (info.json() or {}).get("named_endpoints") or {}
                if isinstance(named, dict):
                    endpoints = [k for k in named if isinstance(k, str)]
    except Exception:  # noqa: BLE001 — title-only still online
        pass
    return {
        "title": title,
        "version": str(cfg.get("version") or ""),
        "endpoints": endpoints,
    }


def _event_id(payload: Any) -> str:
    if isinstance(payload, dict):
        eid = payload.get("event_id") or payload.get("eventId")
        if eid:
            return str(eid)
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    raise RuntimeError(f"Gradio 未返回 event_id：{str(payload)[:200]}")


async def _start_job(
    client: httpx.AsyncClient,
    base: str,
    prompt: str,
    resolution: str,
    num_frames: int,
    num_inference_steps: int,
) -> str:
    body_named = {
        "prompt": prompt,
        "resolution": resolution,
        "num_frames": num_frames,
        "num_inference_steps": num_inference_steps,
    }
    resp = await client.post(base + "/gradio_api/call/v2/generate_video", json=body_named)
    if resp.status_code >= 400:
        resp = await client.post(
            base + "/gradio_api/call/generate_video",
            json={"data": [prompt, resolution, num_frames, num_inference_steps]},
        )
        resp.raise_for_status()
    return _event_id(resp.json())


async def _wait_result(
    client: httpx.AsyncClient, base: str, event_id: str
) -> Any:
    url = f"{base}/gradio_api/call/generate_video/{event_id}"
    chunks: list[str] = []
    async with client.stream("GET", url) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            chunks.append(line)
    return parse_sse_complete("\n".join(chunks) + "\n")


async def _download(
    client: httpx.AsyncClient, base: str, fileinfo: dict[str, Any], dest: Path
) -> Path:
    url = (fileinfo.get("url") or "").strip()
    if url and not re.match(r"^https?://", url, re.I):
        url = urljoin(base + "/", url.lstrip("/"))
    if not url:
        raise RuntimeError("Gradio 视频没有下载 URL")
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = await client.get(url)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return dest


def _predict_with_client(
    base: str,
    prompt: str,
    resolution: str,
    num_frames: int,
    num_inference_steps: int,
) -> Any:
    """Official Gradio Python client (api_name=/generate_video)."""
    from gradio_client import Client

    client = Client(base)
    return client.predict(
        prompt=prompt,
        resolution=resolution,
        num_frames=float(num_frames),
        num_inference_steps=float(num_inference_steps),
        api_name="/generate_video",
    )


def _save_predict_result(result: Any, dest: Path) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(result, (str, Path)):
        src = Path(result)
        if src.is_file():
            if src.resolve() != dest.resolve():
                shutil.copy2(src, dest)
            return dest
    info = extract_file(result)
    src = Path(info.get("path") or "")
    if src.is_file():
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        return dest
    raise RuntimeError(f"gradio_client 未返回本地视频文件：{str(result)[:200]}")


async def generate_wan_video(
    base: str,
    prompt: str,
    resolution: str = "720p",
    num_frames: int = 60,
    num_inference_steps: int = 50,
    dest: Path | None = None,
    timeout: float = 600.0,
) -> dict[str, Any]:
    root = (base or "").rstrip("/")
    prompt = (prompt or "").strip()
    if not root:
        return {"ok": False, "error": "未配置 Gradio 地址"}
    if not prompt:
        return {"ok": False, "error": "prompt 为空"}
    res = normalize_resolution(resolution)
    frames = max(33, min(81, int(num_frames)))
    steps = max(20, min(50, int(num_inference_steps)))
    dest = Path(dest) if dest is not None else Path("wan-output.mp4")
    client_err = ""
    try:
        result = await asyncio.to_thread(
            _predict_with_client, root, prompt, res, frames, steps
        )
        saved = _save_predict_result(result, dest)
        return {"ok": True, "path": str(saved), "via": "gradio_client"}
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001 — fall back to HTTP API
        client_err = str(exc)[:200]
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0),
            follow_redirects=True,
        ) as client:
            event_id = await _start_job(client, root, prompt, res, frames, steps)
            payload = await _wait_result(client, root, event_id)
            if payload is None:
                raise RuntimeError("Gradio 生成未完成或返回为空")
            fileinfo = extract_file(payload)
            saved = await _download(client, root, fileinfo, dest)
    except Exception as exc:  # noqa: BLE001 — surface Gradio/network errors
        msg = str(exc)[:300]
        if client_err:
            msg = f"{msg}（gradio_client: {client_err}）"
        return {"ok": False, "error": msg}
    return {
        "ok": True,
        "path": str(saved),
        "file": fileinfo,
        "event_id": event_id,
        "via": "http",
    }
