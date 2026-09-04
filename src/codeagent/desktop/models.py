"""Model assets for the desktop app (LunarCore Claw style).

Two parallel kinds of callable models:
- **local**: Ollama endpoints (LAN cluster); a model is ``model@endpoint``
- **api**: OpenAI-compatible services; key is optional (ds4/vLLM/llama.cpp
  need none)

Security rules (mirroring LCA):
- API keys never live in the asset store — only ``apikey:{id}`` pointers;
  the key body goes to ``~/.codeagent/secrets.json`` (chmod 600)
- UI only ever shows masked keys (``••••••••`` + last 4)
- Connectivity tests go through the *same* provider construction as real
  chat calls — a probe that takes a different path proves nothing
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

from codeagent.llm.base import LLMProvider

MODELS_PATH = Path("~/.codeagent/models.json")
SECRETS_PATH = Path("~/.codeagent/secrets.json")
DEFAULT_ENDPOINT = "http://localhost:11434"


# ---------------------------------------------------------------------------
# secrets (pointer store + masked display)
# ---------------------------------------------------------------------------

def _secrets_file() -> Path:
    return SECRETS_PATH.expanduser()


def _read_secrets() -> dict[str, str]:
    path = _secrets_file()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_secret(key: str, value: str) -> None:
    secrets = _read_secrets()
    secrets[key] = value
    path = _secrets_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(secrets, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(path, 0o600)  # owner-only, like a Keychain item


def load_secret(key: str) -> str:
    return _read_secrets().get(key, "")


def delete_secret(key: str) -> None:
    secrets = _read_secrets()
    if key in secrets:
        del secrets[key]
        _secrets_file().write_text(
            json.dumps(secrets, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def mask_secret(value: str) -> str:
    return "••••••••" + value[-4:] if value else ""


# ---------------------------------------------------------------------------
# asset store
# ---------------------------------------------------------------------------

@dataclass
class OllamaEndpoint:
    base: str
    label: str = ""
    role: str = "backup"  # "primary" 主推理 | "backup" 备用/快速
    # "" unknown | "ollama" | "openai" OpenAI-compatible | "gradio" 文生视频 UI
    kind: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def __post_init__(self) -> None:
        if not self.label:
            self.label = self.base
        if self.kind not in ("", "ollama", "openai", "gradio"):
            self.kind = ""


@dataclass
class Mixture:
    """聚合池：本地 + API 成员混合路由（LCA Models.tsx 同款）."""

    name: str
    members: list[str]  # "local:model@epid" | "api:{id}"
    strategy: str = "weighted"  # weighted|cascade|vote|rule
    fallback: str = ""
    enabled: bool = True
    calls: int = 0
    id: str = field(default_factory=lambda: "mix-" + uuid.uuid4().hex[:6])

    def __post_init__(self) -> None:
        if not self.fallback and self.members:
            self.fallback = self.members[0]


@dataclass
class ApiModel:
    base_url: str
    model: str
    label: str = ""
    provider: str = ""  # 提供方（识别后自动填）
    status: str = "untested"  # untested | online | error
    latency_ms: int = 0
    cost_per_1k: float = 0.005
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    @property
    def secret_key(self) -> str:
        return f"apikey:{self.id}"

    @property
    def display(self) -> str:
        if self.label:
            return self.label
        if self.provider:
            return f"{self.provider}/{self.model}"
        return f"{self.base_url}/{self.model}"


@dataclass
class ModelAssets:
    endpoints: list[OllamaEndpoint] = field(default_factory=list)
    api_models: list[ApiModel] = field(default_factory=list)
    mixtures: list[Mixture] = field(default_factory=list)
    # "local:{model}@{endpoint_id}" | "api:{id}" | "mix:{id}" | "" (legacy)
    active: str = ""

    @classmethod
    def load(cls, path: Path | None = None) -> "ModelAssets":
        path = Path(path or MODELS_PATH).expanduser()
        if not path.is_file():
            return cls(endpoints=[OllamaEndpoint(base=DEFAULT_ENDPOINT)])
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls(endpoints=[OllamaEndpoint(base=DEFAULT_ENDPOINT)])
        assets = cls(
            endpoints=[OllamaEndpoint(**e) for e in data.get("endpoints", [])],
            api_models=[ApiModel(**m) for m in data.get("api_models", [])],
            mixtures=[Mixture(**m) for m in data.get("mixtures", [])],
            active=data.get("active", ""),
        )
        if not assets.endpoints:
            assets.endpoints.append(OllamaEndpoint(base=DEFAULT_ENDPOINT))
        return assets

    def save(self, path: Path | None = None) -> None:
        path = Path(path or MODELS_PATH).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "endpoints": [asdict(e) for e in self.endpoints],
                    "api_models": [asdict(m) for m in self.api_models],
                    "mixtures": [asdict(m) for m in self.mixtures],
                    "active": self.active,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    # ---------------------------------------------------------- resolution

    def resolve_member(self, ref: str) -> tuple[str, dict[str, Any]] | None:
        """Any member ref → (kind, provider kwargs)."""
        if ref.startswith("local:") and "@" in ref:
            model, ep_id = ref[6:].rsplit("@", 1)
            ep = next((e for e in self.endpoints if e.id == ep_id), None)
            if ep is None:
                return None
            base = ep.base.rstrip("/")
            # OpenAI 兼容本地站已带 /v1；Ollama 用 native，仍拼 /v1 供 strip
            if ep.kind == "gradio":
                return None  # 文生视频，不能当对话 provider
            if ep.kind == "openai":
                openai_base = base if base.endswith("/v1") else base + "/v1"
                return "local_openai", {
                    "model": model,
                    "base_url": openai_base,
                    "api_key": "local",
                }
            return "local", {"model": model, "base_url": base + "/v1"}
        if ref.startswith("api:"):
            am = next((m for m in self.api_models if m.id == ref[4:]), None)
            if am is None:
                return None
            return "api", {
                "model": am.model,
                "base_url": am.base_url,
                "api_key": load_secret(am.secret_key) or None,
            }
        return None

    def resolve_active(self) -> tuple[str, dict[str, Any]] | None:
        """Active asset → (kind, provider kwargs); None = legacy config."""
        if self.active.startswith("mix:"):
            mix = next((m for m in self.mixtures if m.id == self.active[4:]), None)
            if mix is None:
                return None
            return "mix", {"mixture": mix}
        return self.resolve_member(self.active)

    def member_label(self, ref: str) -> str:
        """Human label for a member ref (LCA modelName)."""
        resolved = self.resolve_member(ref)
        if resolved is None:
            return ref
        kind, kwargs = resolved
        if kind in ("local", "local_openai"):
            return f"{kwargs['model']}（本地）"
        am = next((m for m in self.api_models if m.id == ref[4:]), None)
        return am.display if am else ref


def _build_member(assets: ModelAssets, ref: str) -> LLMProvider | None:
    resolved = assets.resolve_member(ref)
    if resolved is None:
        return None
    kind, kwargs = resolved
    if kind == "local":
        from codeagent.llm.ollama import OllamaProvider

        return OllamaProvider(**kwargs)
    from codeagent.llm.openai import OpenAIProvider

    return OpenAIProvider(**kwargs)


def build_active_provider(assets: ModelAssets) -> LLMProvider | None:
    """Construct the provider for the active asset (the *real* call path)."""
    resolved = assets.resolve_active()
    if resolved is None:
        return None
    kind, kwargs = resolved
    if kind == "mix":
        from codeagent.llm.aggregate import AggregateProvider

        mix: Mixture = kwargs["mixture"]
        providers = [
            p for p in (_build_member(assets, ref) for ref in mix.members)
            if p is not None
        ]
        if not providers:
            return None
        # cascade → failover in order; weighted/vote/rule → rotate then fail over
        strategy = "fallback" if mix.strategy == "cascade" else "round-robin"
        return AggregateProvider(providers, strategy=strategy)
    return _build_member(assets, assets.active)


# ---------------------------------------------------------------------------
# probing & detection
# ---------------------------------------------------------------------------

def normalize_endpoint_base(raw: str) -> str:
    """Accept bare host:port / fullwidth colon / trailing slash."""
    s = (raw or "").strip()
    # 中文全角冒号、斜杠 → ASCII（用户常从聊天里粘贴）
    s = s.replace("：", ":").replace("／", "/")
    if not s:
        return ""
    if not re.match(r"^https?://", s, re.I):
        s = "http://" + s
    return s.rstrip("/")


async def probe_endpoint(base: str, timeout: float = 3.0) -> list[str]:
    """List models: Ollama /api/tags, else OpenAI-compatible /v1/models."""
    info = await probe_endpoint_info(base, timeout=timeout)
    if info is None:
        raise RuntimeError("endpoint unreachable or unknown protocol")
    return [m["name"] for m in info["models"]]


async def probe_all(endpoints: list[OllamaEndpoint]) -> dict[str, Any]:
    """Probe every endpoint concurrently; failures are visible, not fatal."""
    import asyncio

    async def one(ep: OllamaEndpoint) -> dict[str, Any]:
        try:
            info = await probe_endpoint_info(ep.base)
            return {
                "id": ep.id, "base": ep.base, "ok": True,
                "kind": info["kind"], "models": [m["name"] for m in info["models"]],
            }
        except Exception as exc:  # noqa: BLE001 — failure must be visible
            return {"id": ep.id, "base": ep.base, "ok": False,
                    "kind": "", "models": [], "error": str(exc)[:120]}

    return {"endpoints": list(await asyncio.gather(*(one(e) for e in endpoints)))}


def _net_error_text(exc: Exception) -> str:
    """httpx 的 Timeout/Connect 异常 str() 常为空，补类型名与可操作提示。"""
    name = type(exc).__name__
    msg = str(exc).strip()[:100]
    text = f"{msg}（{name}）" if msg and name not in msg else (msg or name)
    if name in ("ConnectTimeout", "ConnectError"):
        text += "：端点不可达，请检查网络或 VPN 连接"
    return text


# 同一提供方的孪生域名（Key 不通用，鉴权失败时自动换站重试）
_ALT_HOSTS = {
    "api.moonshot.cn": "api.moonshot.ai",
    "api.moonshot.ai": "api.moonshot.cn",
}


async def detect_service(
    base_url: str, api_key: str = "", timeout: float = 5.0
) -> dict[str, Any]:
    """Dual-protocol sniff: OpenAI /models first, then Ollama /api/tags.

    大多数提供方（OpenAI/DeepSeek/Moonshot…）的 /models 需要鉴权，
    必须带上用户填入的 API Key，否则一律 401 → 误判为"无法识别"。
    鉴权失败且域名有已知孪生站点（如 Kimi 国内/国际）时自动换站重试。
    """
    result = await _detect_once(base_url, api_key, timeout)
    if result["kind"] == "unknown" and api_key.strip() \
            and "鉴权失败" in result.get("error", ""):
        from urllib.parse import urlsplit

        host = urlsplit(base_url).hostname or ""
        alt = _ALT_HOSTS.get(host)
        if alt:
            retry = await _detect_once(base_url.replace(host, alt, 1),
                                       api_key, timeout)
            if retry["kind"] != "unknown":
                retry["note"] = f"Key 属于 {alt}，已自动切换"
                retry["base_url"] = base_url.replace(host, alt, 1)
                return retry
    return result


async def _detect_once(
    base_url: str, api_key: str = "", timeout: float = 5.0
) -> dict[str, Any]:
    base = base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key.strip() else {}
    # 用户可能填根域名或 /v1，两种候选路径都试
    candidates = [base + "/models"]
    if not base.endswith("/v1"):
        candidates.append(base + "/v1/models")
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        auth_error = ""
        conn_error = ""
        for url in candidates:
            try:
                resp = await client.get(url)
                if resp.status_code < 400:
                    data = resp.json()
                    models = [m["id"] for m in data.get("data", [])]
                    return {"kind": "openai", "models": models}
                if resp.status_code in (401, 403):
                    auth_error = (
                        "端点要求鉴权，请先填入 API Key 再识别" if not headers
                        else f"鉴权失败（HTTP {resp.status_code}），请检查 API Key")
                    break
            except Exception as exc:  # noqa: BLE001 — try next candidate / ollama
                if not conn_error:
                    conn_error = _net_error_text(exc)
                continue
        if auth_error:
            return {"kind": "unknown", "models": [], "error": auth_error}
        native = base.removesuffix("/v1")
        ollama_error = conn_error
        try:
            resp = await client.get(native + "/api/tags")
            if resp.status_code < 400:
                models = [m["name"] for m in resp.json().get("models", [])]
                return {"kind": "ollama", "models": models}
            ollama_error = f"HTTP {resp.status_code}"
        except Exception as exc:  # noqa: BLE001 — try Gradio next
            ollama_error = conn_error or _net_error_text(exc)
        gradio = await _probe_gradio(client, native)
        if gradio is not None:
            return {
                "kind": "gradio",
                "models": [m["name"] for m in gradio["models"]],
                "note": "这是 Gradio 服务，不能当作对话模型使用",
            }
        detail = ollama_error or "无法识别"
        return {"kind": "unknown", "models": [],
                "error": f"{detail}：既非 OpenAI/Ollama 对话接口，也非 Gradio"}


async def test_provider(provider: LLMProvider, timeout: float = 45.0) -> dict[str, Any]:
    """Real minimal call through the same path chat uses (hard timeout)."""
    import asyncio

    from codeagent.core.types import Message

    started = time.monotonic()
    try:
        resp = await asyncio.wait_for(
            provider.complete([Message.user("ping，回复 pong 即可")]),
            timeout=timeout,
        )
    except TimeoutError:
        return {"ok": False, "error": f"调用超时（{int(timeout)}s）"}
    except Exception as exc:  # noqa: BLE001 — surface the real diagnosis
        return {"ok": False, "error": str(exc)[:200]}
    latency = int((time.monotonic() - started) * 1000)
    if not resp.content.strip():
        return {"ok": False, "error": "模型返回空内容", "latency_ms": latency}
    return {"ok": True, "latency_ms": latency, "sample": resp.content[:60]}


async def _probe_gradio(
    client: httpx.AsyncClient, root: str
) -> dict[str, Any] | None:
    """Gradio UI (often :7860 文生视频). ``/config`` + optional API info."""
    root = root.rstrip("/")
    try:
        resp = await client.get(root + "/config")
        if resp.status_code >= 400:
            return None
        cfg = resp.json()
    except Exception:  # noqa: BLE001 — not Gradio
        return None
    if not isinstance(cfg, dict):
        return None
    if not isinstance(cfg.get("components"), list) and "dependencies" not in cfg:
        return None
    title = str(cfg.get("title") or "").strip() or "Gradio"
    version = str(cfg.get("version") or "").strip()
    endpoints: list[str] = []
    for path in ("/gradio_api/info", "/info"):
        try:
            info = await client.get(root + path)
            if info.status_code >= 400:
                continue
            payload = info.json()
            named = payload.get("named_endpoints") if isinstance(payload, dict) else None
            if isinstance(named, dict):
                endpoints = [k for k in named if isinstance(k, str)]
            break
        except Exception:  # noqa: BLE001 — title-only Gradio still counts
            break
    blob = f"{title} {' '.join(endpoints)}".lower()
    videoish = "video" in blob or "视频" in title or "wan" in blob
    params = f"Gradio {version}".strip() if version else "Gradio"
    if endpoints:
        params += " · " + "、".join(endpoints[:4])
    return {
        "kind": "gradio",
        "models": [
            {
                "name": title,
                "params": params,
                "quant": "文生视频" if videoish else "Gradio",
                "size": "-",
            }
        ],
    }


async def probe_endpoint_info(
    base: str, timeout: float = 3.0
) -> dict[str, Any] | None:
    """Probe → ``{kind, models}`` or None if offline.

    Prefer Ollama ``/api/tags``; then OpenAI ``/v1/models``; then Gradio ``/config``.
    """
    root = base.rstrip("/")
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.get(root + "/api/tags")
            if resp.status_code < 400:
                out = []
                for m in resp.json().get("models", []):
                    details = m.get("details") or {}
                    out.append(
                        {
                            "name": m.get("name", ""),
                            "params": details.get("parameter_size", "-"),
                            "quant": details.get("quantization_level", "-"),
                            "size": f"{m.get('size', 0) / 1e9:.1f} GB",
                        }
                    )
                return {"kind": "ollama", "models": out}
        except Exception:  # noqa: BLE001 — try OpenAI next
            pass

        for path in ("/v1/models", "/models"):
            try:
                resp = await client.get(root + path)
                if resp.status_code >= 400:
                    continue
                out = []
                for m in resp.json().get("data", []):
                    mid = m.get("id") or m.get("name") or ""
                    if not mid:
                        continue
                    ctx = m.get("context_length")
                    out.append(
                        {
                            "name": mid,
                            "params": f"ctx {ctx}" if ctx else (m.get("name") or "-"),
                            "quant": "-",
                            "size": "-",
                        }
                    )
                return {"kind": "openai", "models": out}
            except Exception:  # noqa: BLE001 — next path
                continue

        return await _probe_gradio(client, root)


async def probe_endpoint_details(
    base: str, timeout: float = 3.0
) -> list[dict[str, Any]] | None:
    """Backward-compat: model detail list only (None if offline)."""
    info = await probe_endpoint_info(base, timeout=timeout)
    return None if info is None else info["models"]


async def running_models(base: str, timeout: float = 3.0) -> set[str]:
    """/api/ps → names currently loaded in memory (status=running)."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(base.rstrip("/") + "/api/ps")
            resp.raise_for_status()
            return {m.get("name", "") for m in resp.json().get("models", [])}
    except Exception:  # noqa: BLE001 — offline → empty set
        return set()


async def set_model_loaded(base: str, model: str, load: bool, timeout: float = 120.0) -> None:
    """Load (keep_alive=10m) or unload (keep_alive=0) a model in memory."""
    body = {"model": model, "prompt": "", "stream": False,
            "keep_alive": "10m" if load else 0}
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(base.rstrip("/") + "/api/generate", json=body)
        resp.raise_for_status()


async def delete_ollama_model(base: str, model: str, timeout: float = 30.0) -> None:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.request(
            "DELETE", base.rstrip("/") + "/api/delete", json={"name": model}
        )
        resp.raise_for_status()


async def pull_ollama_model(base: str, model: str) -> None:
    """Pull a model (long-running; caller runs it in a thread)."""
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST", base.rstrip("/") + "/api/pull",
            json={"name": model, "stream": True},
        ) as resp:
            resp.raise_for_status()
            async for _line in resp.aiter_lines():
                pass
