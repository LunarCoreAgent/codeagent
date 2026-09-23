"""Ollama provider: native /api/chat (streaming NDJSON), not the OpenAI shim.

Why native: Ollama's OpenAI-compatible endpoint silently ignores the
``think`` switch, so thinking models (qwen3, glm-4.7…) burn the whole
num_predict budget on reasoning and return empty content. The native API
takes ``think`` as a *top-level* field (inside ``options`` it is silently
ignored — same lesson LunarCore Claw learned in v0.17.4).
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.request
from typing import Any

import httpx

from codeagent.core.types import LLMResponse, Message, Role, ToolCall, Usage
from codeagent.llm.base import LLMProvider

DEFAULT_MODEL = "qwen2.5-coder:7b"
DEFAULT_BASE_URL = "http://localhost:11434/v1"
# 所有模型同一条线：连续这么久没有思考、也没有工作，就视为卡住并切换。
STALL_SWITCH_SECONDS = 600.0


class StallTimeout(TimeoutError):
    """Local model produced no stream bytes for too long."""


def _idle_timeout_for(model: str) -> float:
    """Every model, including small ones, stalls at the same 600s silence."""
    del model
    return STALL_SWITCH_SECONDS


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
        idle_timeout: float | None = None,
        **_: Any,
    ) -> None:
        super().__init__(
            model=_resolve_model(base_url, model or DEFAULT_MODEL),
            max_tokens=max_tokens,
        )
        self.base = _native_base(base_url)
        self.think = think
        self.timeout = timeout
        self.idle_timeout = (
            float(idle_timeout) if idle_timeout is not None
            else _idle_timeout_for(self.model)
        )

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
        # read 略大于空闲上限，真正卡住由「无有效输出」看门狗判定
        # （加载中的空 NDJSON / keep-alive 不会刷新截止时间）
        timeout = httpx.Timeout(
            connect=5.0,
            read=max(self.idle_timeout + 30.0, 60.0),
            write=30.0,
            pool=5.0,
        )
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", f"{self.base}/api/chat", json=body
                ) as resp:
                    resp.raise_for_status()
                    async for line in self._iter_useful_lines(resp):
                        if not line.strip():
                            continue
                        chunk = json.loads(line)
                        msg = chunk.get("message") or {}
                        useful = False
                        if msg.get("content"):
                            content_parts.append(msg["content"])
                            useful = True
                        # Native thinking stream (when think=True on qwen3 / glm…)
                        think_bit = msg.get("thinking") or msg.get("reasoning")
                        if think_bit:
                            thinking_parts.append(str(think_bit))
                            useful = True
                        for tc in msg.get("tool_calls") or []:
                            useful = True
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
                            useful = True
                        if useful:
                            self._mark_useful()
        except StallTimeout:
            await self._release_model()
            raise
        except (httpx.ReadTimeout, httpx.TimeoutException) as exc:
            await self._release_model()
            raise StallTimeout(self._stall_message()) from exc

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

    def _stall_message(self) -> str:
        return (
            f"{self.model} 超过 {int(self.idle_timeout)} 秒没有思考也没有工作，视为卡住"
        )

    def _mark_useful(self) -> None:
        self._useful_deadline = time.monotonic() + self.idle_timeout

    async def _iter_useful_lines(self, resp: Any):
        """Yield stream lines; stall if no content/thinking/tools within idle_timeout.

        Empty keep-alive / load-progress NDJSON does **not** extend the deadline,
        so a silent 120B load cannot look "alive" forever.
        """
        self._useful_deadline = time.monotonic() + self.idle_timeout
        agen = resp.aiter_lines()
        try:
            while True:
                remaining = self._useful_deadline - time.monotonic()
                if remaining <= 0:
                    raise StallTimeout(self._stall_message())
                try:
                    line = await asyncio.wait_for(agen.__anext__(), timeout=remaining)
                except StopAsyncIteration:
                    return
                except asyncio.TimeoutError as exc:
                    raise StallTimeout(self._stall_message()) from exc
                yield line
        finally:
            aclose = getattr(agen, "aclose", None)
            if callable(aclose):
                await aclose()

    async def _release_model(self) -> None:
        """Drop a stuck Ollama model from VRAM so a backup can load."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                post = getattr(client, "post", None)
                if post is None:
                    return
                await post(
                    f"{self.base}/api/generate",
                    json={"model": self.model, "keep_alive": 0, "prompt": ""},
                )
        except Exception:  # noqa: BLE001 — unload is best-effort
            return

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
