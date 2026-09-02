"""Aggregate provider: combine multiple LLM backends into one.

Typical mixes:
- local-first: ``ollama`` primary, cloud API as backup (free when possible)
- failover: several API keys/relays, automatically skip the broken one
- round-robin: spread load across providers
"""

from __future__ import annotations

import itertools
from typing import Any, Literal

from codeagent.core.types import LLMResponse, Message
from codeagent.llm.base import LLMProvider

Strategy = Literal["fallback", "round-robin"]


class AggregateError(Exception):
    """Raised when every sub-provider failed."""

    def __init__(self, errors: list[tuple[str, Exception]]) -> None:
        self.errors = errors
        detail = "; ".join(f"{name}: {err}" for name, err in errors)
        super().__init__(f"All {len(errors)} providers failed — {detail}")


class AggregateProvider(LLMProvider):
    """Meta-provider routing calls across several providers.

    ``strategy="fallback"`` tries providers in order and moves on when one
    raises; ``strategy="round-robin"`` rotates the starting provider on every
    call while still failing over around the ring.
    """

    name = "aggregate"

    def __init__(
        self,
        providers: list[LLMProvider],
        strategy: Strategy = "fallback",
        max_tokens: int = 8192,
    ) -> None:
        if not providers:
            raise ValueError("AggregateProvider needs at least one provider")
        if strategy not in ("fallback", "round-robin"):
            raise ValueError(f"Unknown strategy {strategy!r}")
        super().__init__(
            model="+".join(p.model for p in providers), max_tokens=max_tokens
        )
        self.providers = list(providers)
        self.strategy: Strategy = strategy
        self.failures: dict[str, int] = {p.name: 0 for p in self.providers}
        self._cycle = itertools.count()

    def __repr__(self) -> str:
        names = ", ".join(f"{p.name}({p.model})" for p in self.providers)
        return f"AggregateProvider([{names}], strategy={self.strategy!r})"

    def _order(self) -> list[LLMProvider]:
        if self.strategy == "round-robin":
            start = next(self._cycle) % len(self.providers)
            return self.providers[start:] + self.providers[:start]
        return list(self.providers)

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        system: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        errors: list[tuple[str, Exception]] = []
        for provider in self._order():
            try:
                return await provider.complete(
                    messages, tools=tools, system=system, **kwargs
                )
            except Exception as exc:  # noqa: BLE001 — failover is the point
                errors.append((provider.name, exc))
                self.failures[provider.name] = self.failures.get(provider.name, 0) + 1
        raise AggregateError(errors)


def parse_provider_spec(
    spec: str,
    strategy: Strategy = "fallback",
    **kwargs: Any,
) -> LLMProvider:
    """Build a provider from a spec like ``"ollama,openrouter,anthropic"``.

    A single name returns a plain provider; a comma-separated list returns an
    :class:`AggregateProvider` over them. Keyword arguments (``model``,
    ``api_key``, ``base_url``) are forwarded to every sub-provider — prefer
    per-service environment variables when mixing services.
    """
    from codeagent.llm.registry import create_provider

    names = [part.strip() for part in spec.split(",") if part.strip()]
    if not names:
        raise ValueError("Empty provider spec")
    providers = [create_provider(name, **kwargs) for name in names]
    if len(providers) == 1:
        return providers[0]
    return AggregateProvider(providers, strategy=strategy)
