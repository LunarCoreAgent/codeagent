"""Aggregate provider, provider presets, and provider-spec parsing."""

from __future__ import annotations

import pytest

from codeagent import (
    AggregateError,
    AggregateProvider,
    create_provider,
    list_providers,
    parse_provider_spec,
)
from codeagent.core.types import LLMResponse
from codeagent.llm.base import LLMProvider


class StubProvider(LLMProvider):
    def __init__(self, name: str, answer: str = "ok", error: Exception | None = None):
        super().__init__(model=f"{name}-model")
        self._name = name
        self._answer = answer
        self._error = error
        self.calls = 0

    @property
    def name(self) -> str:  # type: ignore[override]
        return self._name

    async def complete(self, messages, tools=None, system=None, **kwargs):
        self.calls += 1
        if self._error:
            raise self._error
        return LLMResponse(content=self._answer)


# ---------------------------------------------------------------------------
# AggregateProvider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fallback_uses_first_when_healthy():
    agg = AggregateProvider([StubProvider("a", "A"), StubProvider("b", "B")])
    assert (await agg.complete([])).content == "A"
    assert agg.providers[1].calls == 0


@pytest.mark.asyncio
async def test_fallback_skips_broken_provider():
    agg = AggregateProvider(
        [StubProvider("a", error=RuntimeError("down")), StubProvider("b", "B")]
    )
    assert (await agg.complete([])).content == "B"
    assert agg.failures["a"] == 1


@pytest.mark.asyncio
async def test_all_failed_raises_aggregate_error():
    agg = AggregateProvider(
        [
            StubProvider("a", error=RuntimeError("boom-1")),
            StubProvider("b", error=ValueError("boom-2")),
        ]
    )
    with pytest.raises(AggregateError) as exc_info:
        await agg.complete([])
    assert len(exc_info.value.errors) == 2
    assert "boom-1" in str(exc_info.value)
    assert "boom-2" in str(exc_info.value)


@pytest.mark.asyncio
async def test_round_robin_rotates_starting_provider():
    agg = AggregateProvider(
        [StubProvider("a", "A"), StubProvider("b", "B")], strategy="round-robin"
    )
    answers = [(await agg.complete([])).content for _ in range(4)]
    assert answers == ["A", "B", "A", "B"]


@pytest.mark.asyncio
async def test_round_robin_still_fails_over():
    agg = AggregateProvider(
        [StubProvider("a", error=RuntimeError("x")), StubProvider("b", "B")],
        strategy="round-robin",
    )
    assert (await agg.complete([])).content == "B"  # starts at a, fails over to b
    assert (await agg.complete([])).content == "B"  # starts at b directly


def test_aggregate_requires_providers():
    with pytest.raises(ValueError):
        AggregateProvider([])


def test_aggregate_rejects_unknown_strategy():
    with pytest.raises(ValueError):
        AggregateProvider([StubProvider("a")], strategy="yolo")


def test_aggregate_model_name_joins_sub_models():
    agg = AggregateProvider([StubProvider("a"), StubProvider("b")])
    assert agg.model == "a-model+b-model"


# ---------------------------------------------------------------------------
# presets
# ---------------------------------------------------------------------------


def test_presets_registered():
    providers = list_providers()
    for name in (
        "openrouter", "siliconflow", "aihubmix", "oneapi",
        "lmstudio", "vllm", "llamacpp",
    ):
        assert name in providers


def test_aggregator_preset_endpoint():
    p = create_provider("openrouter", api_key="k")
    assert str(p.client.base_url).rstrip("/") == "https://openrouter.ai/api/v1"
    assert p.model == "openai/gpt-4o-mini"


def test_aggregator_preset_reads_env_key(monkeypatch):
    monkeypatch.setenv("SILICONFLOW_API_KEY", "env-key")
    p = create_provider("siliconflow")
    assert p.client.api_key == "env-key"


def test_local_preset_no_key_needed(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    p = create_provider("lmstudio")
    assert str(p.client.base_url).rstrip("/") == "http://localhost:1234/v1"
    assert p.model == "local-model"


def test_preset_base_url_overridable():
    p = create_provider("oneapi", api_key="k", base_url="http://relay.internal:3000/v1")
    assert str(p.client.base_url).rstrip("/") == "http://relay.internal:3000/v1"


# ---------------------------------------------------------------------------
# parse_provider_spec
# ---------------------------------------------------------------------------


def test_spec_single_returns_plain_provider():
    p = parse_provider_spec("openai", api_key="k")
    assert not isinstance(p, AggregateProvider)
    assert p.name == "openai"


def test_spec_comma_builds_aggregate():
    p = parse_provider_spec("openai, openrouter", api_key="k")
    assert isinstance(p, AggregateProvider)
    assert [sub.name for sub in p.providers] == ["openai", "openrouter"]


def test_spec_rejects_empty():
    with pytest.raises(ValueError):
        parse_provider_spec(" , ")


def test_spec_unknown_provider_error_lists_presets():
    with pytest.raises(ValueError, match="openrouter"):
        parse_provider_spec("nonexistent")
