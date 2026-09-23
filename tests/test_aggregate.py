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
from codeagent.llm.aggregate import mark_unhealthy, reset_unhealthy
from codeagent.llm.base import LLMProvider


@pytest.fixture(autouse=True)
def _clear_unhealthy_providers():
    reset_unhealthy()
    yield
    reset_unhealthy()


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


@pytest.mark.asyncio
async def test_skips_unhealthy_provider_without_calling_it():
    broken = StubProvider("a", error=RuntimeError("hung"))
    backup = StubProvider("b", "B")
    mark_unhealthy(broken, seconds=60)
    agg = AggregateProvider([broken, backup])
    assert (await agg.complete([])).content == "B"
    assert broken.calls == 0
    assert backup.calls == 1


@pytest.mark.asyncio
async def test_failover_callback_and_cooldown():
    seen: list[tuple[str, str]] = []
    broken = StubProvider("a", error=RuntimeError("视为卡住"))
    backup = StubProvider("b", "B")
    agg = AggregateProvider([broken, backup])
    agg.on_failover = lambda src, exc, dst: seen.append((src.model, dst.model))
    assert (await agg.complete([])).content == "B"
    assert seen == [("a-model", "b-model")]
    # second call must not wait on a again
    assert (await agg.complete([])).content == "B"
    assert broken.calls == 1
    assert backup.calls == 2


@pytest.mark.asyncio
async def test_nested_aggregate_flattens_for_stall_switch():
    """Nested AggregateProvider leaves must all participate in dead-model switch."""
    inner = AggregateProvider(
        [StubProvider("a", error=RuntimeError("视为卡住")), StubProvider("b", "B")],
        strategy="fallback",
    )
    outer = AggregateProvider(
        [inner, StubProvider("c", "C")],
        strategy="fallback",
    )
    resp = await outer.complete([])
    assert resp.content == "B"
    assert outer.providers[0].providers[0].calls == 1
    assert outer.providers[0].providers[1].calls == 1
    assert outer.providers[1].calls == 0


@pytest.mark.asyncio
async def test_timeout_switches_to_next_model(monkeypatch):
    import asyncio

    monkeypatch.setattr("codeagent.llm.aggregate.DEFAULT_CALL_CAP", 0.05)

    class Slow(StubProvider):
        async def complete(self, messages, tools=None, system=None, **kwargs):
            self.calls += 1
            await asyncio.sleep(1)
            return LLMResponse(content="late")

    slow = Slow("slow")
    backup = StubProvider("backup", "ok")
    agg = AggregateProvider([slow, backup], strategy="fallback")
    assert (await agg.complete([])).content == "ok"
    assert slow.calls == 1
    assert backup.calls == 1
    assert (await agg.complete([])).content == "ok"
    assert slow.calls == 1


@pytest.mark.asyncio
async def test_working_idle_watchdog_is_not_killed_by_wall_clock(monkeypatch):
    import asyncio

    monkeypatch.setattr("codeagent.llm.aggregate.DEFAULT_CALL_CAP", 0.05)

    class Working(StubProvider):
        idle_timeout = 600.0

        async def complete(self, messages, tools=None, system=None, **kwargs):
            self.calls += 1
            await asyncio.sleep(0.2)
            return LLMResponse(content="still-working")

    agg = AggregateProvider([Working("thinker", "still-working")])
    assert (await agg.complete([])).content == "still-working"
    assert agg.providers[0].calls == 1


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
