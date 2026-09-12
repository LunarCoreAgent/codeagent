"""Ollama provider: native /api/chat (streaming NDJSON), not the OpenAI shim.

Why native: Ollama's OpenAI-compatible endpoint silently ignores the
``think`` switch, so thinking models (qwen3, glm-4.7…) burn the whole
num_predict budget on reasoning and return empty content. The native API
takes ``think`` as a *top-level* field (inside ``options`` it is silently
ignored — same lesson LunarCore Claw learned in v0.17.4).
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

import httpx

from codeagent.core.types import LLMResponse, Message, Role, ToolCall, Usage
from codeagent.llm.base import LLMProvider

DEFAULT_MODEL = "qwen2.5-coder:7b"
DEFAULT_BASE_URL = "http://localhost:11434/v1"


def _native_base(base_url: str) -> str:
    """``http://host:11434/v1`` → ``http://host:11434``."""
    return base_url.removesuffix("/v1").rstrip("/")


def _resolve_model(base_url: str, model: str) -> str:
    """Fall back to an installed model when the configured one isn't pulled.

    An unpulled model can never answer (Ollama 404s or returns empty), so
    substituting the first installed model is strictly better. Any lookup
    failure keeps the configured model untouched.
    """
    try:
        with urllib.request.urlopen(
            _native_base(base_url) + "/api/tags", timeout=2
        ) as resp:
            data = json.loads(resp.read())
        installed = [m["name"] for m in data.get("models", [])]
    except Exception:  # noqa: BLE001 — offline/server down: keep as-is
        return model
    if not installed or model in installed:
        return model
    return installed[0]


class OllamaProvider(LLMProvider):
    """Local Ollama model via the native chat API.

    ``think=False`` (default) disables the reasoning stream of thinking
    models — agent loops and one-shot machine calls want the answer, not
    the chain-of-thought eating the token budget.
    """

    name = "ollama"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,  # accepted for spec uniformity, ignored
        max_tokens: int = 8192,
        think: bool = False,
        timeout: float = 300.0,
        **_: Any,
    ) -> None:
        super().__init__(
            model=_resolve_model(base_url, model or DEFAULT_MODEL),
            max_tokens=max_tokens,
        )
        self.base = _native_base(base_url)
        self.think = think
        self.timeout = timeout

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        system: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": self._convert(messages, system),
            "stream": True,
            "think": self.think,  # top level — inside options it's ignored
            "options": {"num_predict": self.max_tokens},
        }
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["parameters"],
                    },
                }
                for t in tools
            ]

        content_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        done_reason = "stop"
        usage = Usage()
        timeout = httpx.Timeout(self.timeout, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", f"{self.base}/api/chat", json=body
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    msg = chunk.get("message") or {}
                    if msg.get("content"):
                        content_parts.append(msg["content"])
                    # Native thinking stream (when think=True on qwen3 / glm…)
                    think_bit = msg.get("thinking") or msg.get("reasoning")
                    if think_bit:
                        thinking_parts.append(str(think_bit))
                    for tc in msg.get("tool_calls") or []:
                        fn = tc.get("function") or {}
                        tool_calls.append(
                            ToolCall(
                                id=tc.get("id") or f"call_{len(tool_calls)}",
                                name=fn.get("name", ""),
                                arguments=fn.get("arguments") or {},
                            )
                        )
                    if chunk.get("done"):
                        done_reason = chunk.get("done_reason") or "stop"
                        usage = Usage(
                            input_tokens=chunk.get("prompt_eval_count") or 0,
                            output_tokens=chunk.get("eval_count") or 0,
                        )

        content = "".join(content_parts)
        reasoning = "".join(thinking_parts).strip()
        if not content and reasoning:
            content, reasoning = reasoning, ""

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=done_reason,
            usage=usage,
            reasoning=reasoning,
        )

    @staticmethod
    def _convert(messages: list[Message], system: str | None) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        if system:
            converted.append({"role": "system", "content": system})
        for msg in messages:
            if msg.role in (Role.SYSTEM, Role.USER):
                converted.append({"role": msg.role.value, "content": msg.content})
            elif msg.role == Role.ASSISTANT:
                entry: dict[str, Any] = {
                    "role": "assistant",
                    "content": msg.content or "",
                }
                if msg.tool_calls:
                    entry["tool_calls"] = [
                        {
                            "type": "function",
                            # native API wants arguments as an object
                            "function": {"name": tc.name, "arguments": tc.arguments},
                        }
                        for tc in msg.tool_calls
                    ]
                converted.append(entry)
            elif msg.role == Role.TOOL:
                for r in msg.tool_results:
                    converted.append({"role": "tool", "content": r.content})
        return converted
