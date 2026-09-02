"""Provider registry: construct LLM backends from string names."""

from __future__ import annotations

from typing import Any

from codeagent.llm.anthropic import AnthropicProvider
from codeagent.llm.base import LLMProvider
from codeagent.llm.ollama import OllamaProvider
from codeagent.llm.openai import OpenAIProvider
from codeagent.llm.presets import PRESET_PROVIDERS

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
    **PRESET_PROVIDERS,
}


def register_provider(name: str, provider_cls: type[LLMProvider]) -> None:
    """Register a custom provider class under ``name``."""
    if not (isinstance(provider_cls, type) and issubclass(provider_cls, LLMProvider)):
        raise TypeError("provider_cls must be a subclass of LLMProvider")
    _PROVIDERS[name] = provider_cls


def list_providers() -> list[str]:
    return sorted(_PROVIDERS)


def create_provider(name: str, **kwargs: Any) -> LLMProvider:
    """Instantiate a provider by name.

    Extra keyword arguments (``model``, ``api_key``, ``base_url``, ...) are
    forwarded to the provider constructor.
    """
    try:
        provider_cls = _PROVIDERS[name]
    except KeyError:
        available = ", ".join(list_providers())
        raise ValueError(
            f"Unknown provider {name!r}. Available providers: {available}"
        ) from None
    return provider_cls(**kwargs)
