"""Talk to a local ComfyUI server (default http://127.0.0.1:8188)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

DEFAULT_COMFY_BASE = "http://127.0.0.1:8188"


def normalize_comfy_base(base: str) -> str:
    raw = (base or "").strip().rstrip("/")
    if not raw:
        return ""
    if "://" not in raw:
        raw = "http://" + raw
    return raw


def resolve_comfy_base(explicit: str = "") -> str:
    """Configured address, else the usual local 8188."""
    if (explicit or "").strip():
        return normalize_comfy_base(explicit)
    try:
        from codeagent.videoops import VideoOpsConfig

        configured = (VideoOpsConfig.load().comfy_base or "").strip()
    except OSError:
        configured = ""
    return normalize_comfy_base(configured) or DEFAULT_COMFY_BASE


def patch_workflow_prompt(workflow: dict[str, Any], prompt: str) -> int:
    """Write ``prompt`` into the first positive text node (CLIPTextEncode)."""
    graph = workflow.get("prompt", workflow)
    if not isinstance(graph, dict) or not (prompt or "").strip():
        return 0
    candidates: list[dict[str, Any]] = []
    for node in graph.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict) or "text" not in inputs:
            continue
        meta = node.get("_meta") if isinstance(node.get("_meta"), dict) else {}
        title = str(meta.get("title") or node.get("class_type") or "").lower()
        if "negative" in title or title.endswith("neg"):
            continue
        candidates.append(node)
    preferred = [
        n for n in candidates
        if "cliptextencode" in str(n.get("class_type") or "").lower()
    ]
    target = (preferred or candidates)
    if not target:
        return 0
    target[0]["inputs"]["text"] = prompt
    return 1


async def interrupt_comfy(base: str, timeout: float = 5.0) -> dict[str, Any]:
    root = normalize_comfy_base(base)
    if not root:
        return {"ok": False, "error": "未配置 ComfyUI 地址"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(root + "/interrupt")
    except (httpx.HTTPError, OSError) as exc:
        return {"ok": False, "error": str(exc)}
    if r.status_code >= 400:
        return {"ok": False, "error": f"interrupt HTTP {r.status_code}"}
    return {"ok": True}


async def probe_comfy(base: str, timeout: float = 3.0) -> dict[str, Any] | None:
    root = normalize_comfy_base(base)
    if not root:
        return None
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(root + "/system_stats")
            if r.status_code >= 400:
                r = await client.get(root + "/object_info")
            if r.status_code >= 400:
                return None
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            return {"ok": True, "base": root, "info": data if isinstance(data, dict) else {}}
    except (httpx.HTTPError, OSError, ValueError):
        return None


async def queue_comfy_workflow(
    base: str,
    workflow: dict[str, Any],
    dest_dir: Path,
    timeout: float = 600.0,
) -> dict[str, Any]:
    """POST API-format graph to /prompt, poll /history, download /view."""
    root = normalize_comfy_base(base)
    if not root:
        return {"ok": False, "error": "未配置 ComfyUI 地址"}
    prompt = workflow.get("prompt", workflow)
    if not isinstance(prompt, dict):
        return {"ok": False, "error": "工作流必须是 API 格式 JSON（含 prompt 节点图）"}
    client_id = uuid.uuid4().hex
    async with httpx.AsyncClient(timeout=30.0) as client:
        posted = await client.post(
            root + "/prompt",
            json={"prompt": prompt, "client_id": client_id},
        )
        try:
            body = posted.json()
        except Exception:
            return {"ok": False, "error": f"ComfyUI /prompt HTTP {posted.status_code}"}
        if posted.status_code >= 400 or body.get("node_errors"):
            return {"ok": False, "error": str(body.get("node_errors") or body)[:400]}
        prompt_id = str(body.get("prompt_id") or "")
        if not prompt_id:
            return {"ok": False, "error": "ComfyUI 未返回 prompt_id"}
        import asyncio
        import time

        deadline = time.monotonic() + timeout
        history: dict[str, Any] = {}
        while time.monotonic() < deadline:
            h = await client.get(f"{root}/history/{prompt_id}")
            data = h.json() if h.status_code < 400 else {}
            if prompt_id in data:
                history = data[prompt_id]
                break
            await asyncio.sleep(2.0)
        else:
            return {"ok": False, "error": "ComfyUI 任务超时"}
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    outputs = history.get("outputs") or {}
    async with httpx.AsyncClient(timeout=60.0) as client:
        for _nid, node in outputs.items():
            if not isinstance(node, dict):
                continue
            for key in ("gifs", "videos", "images"):
                items = node.get(key) or []
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    filename = item.get("filename")
                    if not filename:
                        continue
                    params = urlencode({
                        "filename": filename,
                        "subfolder": item.get("subfolder") or "",
                        "type": item.get("type") or "output",
                    })
                    vr = await client.get(f"{root}/view?{params}")
                    if vr.status_code >= 400:
                        continue
                    dest = dest_dir / str(filename)
                    dest.write_bytes(vr.content)
                    saved.append(str(dest))
    if not saved:
        return {"ok": False, "error": "ComfyUI 完成但没有可下载的输出"}
    return {"ok": True, "path": saved[0], "files": saved, "via": "comfy"}


def load_workflow_file(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("工作流 JSON 必须是对象")
    return data
