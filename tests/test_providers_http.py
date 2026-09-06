"""HTTP-level provider behavior: native Ollama NDJSON + OpenAI reasoning fallback."""

from __future__ import annotations

import json

import pytest

from codeagent.core.types import Message
from codeagent.llm.ollama import OllamaProvider
from codeagent.llm.openai import LLMError, OpenAIProvider, is_transient_serving_error


# ---------------------------------------------------------------------------
# Ollama native /api/chat
# ---------------------------------------------------------------------------


class _FakeStreamResp:
    def __init__(self, lines: list[str], status: int = 200):
        self._lines = lines
        self.status_code = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeClient:
    """Captures the request body, replays canned NDJSON."""

    captured: dict = {}
    lines: list[str] = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def stream(self, method, url, json=None):
        type(self).captured = {"method": method, "url": url, "json": json}
        return _FakeStreamResp(type(self).lines)


def _patch_httpx(monkeypatch, lines: list[str]) -> dict:
    _FakeClient.lines = lines
    monkeypatch.setattr("codeagent.llm.ollama.httpx.AsyncClient", _FakeClient)
    return _FakeClient.captured


async def test_ollama_native_think_top_level(monkeypatch):
    """think must be TOP LEVEL — inside options Ollama silently ignores it."""
    lines = [
        json.dumps({"message": {"role": "assistant", "content": "2"}, "done": False}),
        json.dumps({"done": True, "done_reason": "stop",
                    "prompt_eval_count": 5, "eval_count": 1}),
    ]
    monkeypatch.setattr(
        OllamaProvider, "_resolve_model", staticmethod(lambda b, m: m), raising=False
    )
    provider = OllamaProvider(model="qwen3:8b")
    monkeypatch.setattr("codeagent.llm.ollama.httpx.AsyncClient", _FakeClient)
    _FakeClient.lines = lines

    resp = await provider.complete([Message.user("1+1=?")])

    body = _FakeClient.captured["json"]
    assert body["think"] is False                    # top level
    assert "think" not in body.get("options", {})    # never inside options
    assert body["options"]["num_predict"] == 8192
    assert _FakeClient.captured["url"] == "http://localhost:11434/api/chat"
    assert resp.content == "2"
    assert resp.usage.output_tokens == 1


async def test_ollama_native_tool_calls(monkeypatch):
    lines = [
        json.dumps({
            "message": {"role": "assistant", "content": "",
                        "tool_calls": [{"function": {"name": "read_file",
                                        "arguments": {"path": "a.txt"}}}]},
            "done": False,
        }),
        json.dumps({"done": True, "done_reason": "stop"}),
    ]
    provider = OllamaProvider(model="qwen3:8b")
    monkeypatch.setattr("codeagent.llm.ollama.httpx.AsyncClient", _FakeClient)
    _FakeClient.lines = lines

    resp = await provider.complete(
        [Message.user("读文件")],
        tools=[{"name": "read_file", "description": "读", "parameters": {}}],
    )
    assert resp.tool_calls[0].name == "read_file"
    assert resp.tool_calls[0].arguments == {"path": "a.txt"}
    assert resp.wants_tool_use
    # tools were forwarded in native shape
    sent = _FakeClient.captured["json"]["tools"][0]
    assert sent["function"]["name"] == "read_file"


# ---------------------------------------------------------------------------
# OpenAI reasoning_content fallback + truncation diagnosis
# ---------------------------------------------------------------------------


class _FakeChoice:
    def __init__(self, content, reasoning=None, finish="stop", tool_calls=None):
        self.message = type("M", (), {
            "content": content,
            "reasoning_content": reasoning,
            "tool_calls": tool_calls,
        })()
        self.finish_reason = finish


class _FakeCompletions:
    def __init__(self, choice):
        self._choice = choice

    async def create(self, **kwargs):
        return type("R", (), {
            "choices": [self._choice],
            "usage": type("U", (), {"prompt_tokens": 1, "completion_tokens": 1})(),
        })()


def _openai_with(choice) -> OpenAIProvider:
    provider = OpenAIProvider(model="m", api_key="k")
    provider.client = type("C", (), {
        "chat": type("Chat", (), {"completions": _FakeCompletions(choice)})()
    })()
    return provider


async def test_openai_reasoning_content_fallback():
    """content empty → fall back to reasoning_content (GLM/qwen3 relays)."""
    provider = _openai_with(_FakeChoice(content="", reasoning="答案在推理里"))
    resp = await provider.complete([Message.user("hi")])
    assert resp.content == "答案在推理里"


async def test_openai_empty_and_length_raises_diagnosis():
    provider = _openai_with(_FakeChoice(content="", reasoning=None, finish="length"))
    with pytest.raises(LLMError, match="截断"):
        await provider.complete([Message.user("hi")])


async def test_openai_empty_stop_raises_diagnosis():
    provider = _openai_with(_FakeChoice(content="", reasoning=None, finish="stop"))
    with pytest.raises(LLMError, match="空内容"):
        await provider.complete([Message.user("hi")])


def test_is_transient_serving_error():
    assert is_transient_serving_error(Exception(
        "Error code: 500 - InternalError.Algo: model serving"
    ))
    assert not is_transient_serving_error(Exception("401 Unauthorized"))


async def test_openai_retries_dashscope_500(monkeypatch):
    calls = {"n": 0}

    class Flaky:
        async def create(self, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError(
                    "Error code: 500 - {'error': {'message': "
                    "'<500> InternalError.Algo: serving'}}"
                )
            return type("R", (), {
                "choices": [_FakeChoice(content="ok")],
                "usage": type("U", (), {"prompt_tokens": 1, "completion_tokens": 1})(),
            })()

    provider = OpenAIProvider(model="qwen3.8-max", api_key="k")
    provider.client = type("C", (), {
        "chat": type("Chat", (), {"completions": Flaky()})()
    })()
    monkeypatch.setattr("codeagent.llm.openai.asyncio.sleep", _instant_sleep)
    resp = await provider.complete([Message.user("hi")])
    assert resp.content == "ok"
    assert calls["n"] == 2


async def _instant_sleep(_delay):
    return None
