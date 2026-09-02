"""Provider presets: aggregation gateways and local deployment servers.

Aggregation gateways expose many upstream models behind one
OpenAI-compatible endpoint (one key, every model). Local servers run
models on this machine, key-free.
"""

from __future__ import annotations

import os
from typing import Any

from codeagent.llm.openai import OpenAIProvider


def _make_preset(
    name: str,
    preset_base_url: str,
    preset_model: str,
    env_key: str | None,
) -> type[OpenAIProvider]:
    """Create an OpenAI-compatible provider class pinned to an endpoint."""

    def __init__(
        self,
        model: str = preset_model,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 8192,
        **client_kwargs: Any,
    ) -> None:
        key = api_key or (os.environ.get(env_key) if env_key else None) or "local"
        OpenAIProvider.__init__(
            self,
            model=model,
            api_key=key,
            base_url=base_url or preset_base_url,
            max_tokens=max_tokens,
            **client_kwargs,
        )

    return type(
        f"{name.title().replace('-', '').replace('_', '')}Provider",
        (OpenAIProvider,),
        {"name": name, "__init__": __init__, "__module__": __name__},
    )


# --- aggregation gateways (one key → many upstream models) -----------------

OpenRouterProvider = _make_preset(
    "openrouter",
    preset_base_url="https://openrouter.ai/api/v1",
    preset_model="openai/gpt-4o-mini",
    env_key="OPENROUTER_API_KEY",
)

SiliconFlowProvider = _make_preset(
    "siliconflow",
    preset_base_url="https://api.siliconflow.cn/v1",
    preset_model="Qwen/Qwen2.5-Coder-32B-Instruct",
    env_key="SILICONFLOW_API_KEY",
)

AiHubMixProvider = _make_preset(
    "aihubmix",
    preset_base_url="https://aihubmix.com/v1",
    preset_model="gpt-4o-mini",
    env_key="AIHUBMIX_API_KEY",
)

# Self-hosted relays: One-API / New-API / sub2api — point base_url at yours.
OneAPIProvider = _make_preset(
    "oneapi",
    preset_base_url="http://localhost:3000/v1",
    preset_model="gpt-4o-mini",
    env_key="ONEAPI_API_KEY",
)

# --- local deployment (run on this machine, no key needed) ------------------

LMStudioProvider = _make_preset(
    "lmstudio",
    preset_base_url="http://localhost:1234/v1",
    preset_model="local-model",
    env_key=None,
)

VLLMProvider = _make_preset(
    "vllm",
    preset_base_url="http://localhost:8000/v1",
    preset_model="local-model",
    env_key=None,
)

LlamaCppProvider = _make_preset(
    "llamacpp",
    preset_base_url="http://localhost:8080/v1",
    preset_model="local-model",
    env_key=None,
)

PRESET_PROVIDERS: dict[str, type[OpenAIProvider]] = {
    cls.name: cls
    for cls in (
        OpenRouterProvider,
        SiliconFlowProvider,
        AiHubMixProvider,
        OneAPIProvider,
        LMStudioProvider,
        VLLMProvider,
        LlamaCppProvider,
    )
}
