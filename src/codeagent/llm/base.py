"""Abstract interface every LLM provider implements."""

from __future__ import annotations

from abc import ABC, abstractmethod

from codeagent.core.types import LLMResponse, Message


class LLMProvider(ABC):
    """A chat-completion backend with optional tool use.

    Providers consume the framework's unified :class:`Message` history and
    generic JSON-Schema tool definitions, and return a normalized
    :class:`LLMResponse`. All provider-specific wire formats are translated
    inside the provider implementation.
    """

    name: str = "base"

    def __init__(self, model: str, max_tokens: int = 8192) -> None:
        self.model = model
        self.max_tokens = max_tokens

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        system: str | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Produce the next assistant turn.

        ``tools`` is a list of ``{"name", "description", "parameters"}``
        dicts where ``parameters`` is a JSON Schema object.
        """
