"""Aggregate provider: combine multiple LLM backends into one.

Typical mixes:
- local-first: ``ollama`` primary, cloud API as backup (free when possible)
- failover: several API keys/relays, automatically skip the broken one
- round-robin: spread load across providers
"""

from __future__ import annotations

import asyncio
import itertools
import time
from collections.abc import Callable
from typing import Any, Literal

from codeagent.core.types import LLMResponse, Message
from codeagent.llm.base import LLMProvider

Strategy = Literal["fallback", "round-robin"]

# After a stall, keep that model off the chain so the next turn does not
# wait another 600s on it. A fresh process still tries the preferred model first.
SKIP_AFTER = 1800.0
# Safety cap when a provider has no idle watchdog of its own.
DEFAULT_CALL_CAP = 600.0
_UNHEALTHY: dict[str, float] = {}


def _provider_key(provider: LLMProvider) -> str:
    base = getattr(provider, "base", "") or getattr(
        getattr(provider, "client", None), "base_url", ""
    ) or ""
    return f"{provider.name}:{provider.model}:{base}"


def mark_unhealthy(provider: LLMProvider, seconds: float = SKIP_AFTER) -> None:
    _UNHEALTHY[_provider_key(provider)] = time.monotonic() + max(0.0, seconds)


def clear_unhealthy(provider: LLMProvider) -> None:
    _UNHEALTHY.pop(_provider_key(provider), None)


def reset_unhealthy() -> None:
    _UNHEALTHY.clear()


def is_unhealthy(provider: LLMProvider, now: float | None = None) -> bool:
    until = _UNHEALTHY.get(_provider_key(provider), 0.0)
    return until > (now if now is not None else time.monotonic())


def _call_cap(provider: LLMProvider) -> float | None:
    """Wall-clock backstop only for backends with no idle watchdog.

    Providers that already stop on 600s of silence must not be killed while
    they are still thinking or working.
    """
    if getattr(provider, "idle_timeout", None) is not None:
        return None
    return DEFAULT_CALL_CAP


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

    On stall/timeout the failed backend is marked unhealthy so later agent
    tool-rounds keep working on the backup without waiting on it again.
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
        self.on_failover: Callable[[LLMProvider, Exception, LLMProvider], None] | None = None

    def __repr__(self) -> str:
        names = ", ".join(f"{p.name}({p.model})" for p in self.providers)
        return f"AggregateProvider([{names}], strategy={self.strategy!r})"

    @staticmethod
    def _flatten(providers: list[LLMProvider]) -> list[LLMProvider]:
        """Expand nested aggregates so stall switch walks every leaf model."""
        flat: list[LLMProvider] = []
        for provider in providers:
            if isinstance(provider, AggregateProvider):
                flat.extend(AggregateProvider._flatten(provider.providers))
            else:
                flat.append(provider)
        return flat

    def _ring(self) -> list[LLMProvider]:
        leaves = self._flatten(self.providers)
        if not leaves:
            return []
        if self.strategy == "round-robin":
            start = next(self._cycle) % len(leaves)
            return leaves[start:] + leaves[:start]
        return list(leaves)

    def _order(self) -> list[LLMProvider]:
        ring = self._ring()
        now = time.monotonic()
        ready = [p for p in ring if not is_unhealthy(p, now)]
        return ready or ring

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        system: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        errors: list[tuple[str, Exception]] = []
        order = self._order()
        for index, provider in enumerate(order):
            try:
                response = await asyncio.wait_for(
                    provider.complete(
                        messages, tools=tools, system=system, **kwargs
                    ),
                    timeout=_call_cap(provider),
                )
                clear_unhealthy(provider)
                return response
            except Exception as exc:  # noqa: BLE001 — failover is the point
                if isinstance(exc, asyncio.TimeoutError):
                    cap = _call_cap(provider) or DEFAULT_CALL_CAP
                    exc = TimeoutError(
                        f"{provider.model} 超过 {int(cap)} 秒没有思考也没有工作，视为卡住"
                    )
                errors.append((provider.name, exc))
                self.failures[provider.name] = self.failures.get(provider.name, 0) + 1
                mark_unhealthy(provider)
                nxt = order[index + 1] if index + 1 < len(order) else None
                if nxt is not None and self.on_failover is not None:
                    try:
                        self.on_failover(provider, exc, nxt)
                    except Exception:  # noqa: BLE001 — UI callback must not abort failover
                        pass
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
