"""OpenAI provider (also covers OpenAI-compatible endpoints)."""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

from codeagent.core.types import LLMResponse, Message, Role, ToolCall, Usage
from codeagent.llm.base import LLMProvider
from codeagent.llm.ollama import STALL_SWITCH_SECONDS, StallTimeout

DEFAULT_MODEL = "gpt-4o"

# DashScope/通义、部分兼容网关会把服务端故障包装成 InternalError.Algo
_SERVING_MARKERS = (
    "internalerror.algo",
    "internal_server_error",
    "error code: 500",
    "error code: 502",
    "error code: 503",
    "bad gateway",
    "service unavailable",
    "overloaded",
)


def is_transient_serving_error(exc: BaseException) -> bool:
    """True for retryable cloud 5xx / DashScope InternalError.Algo."""
    status = getattr(exc, "status_code", None)
    if status in {500, 502, 503, 529}:
        return True
    text = str(exc).lower()
    if any(token in text for token in ("401", "403", "unauthorized", "invalid api key")):
        return False
    return any(marker in text for marker in _SERVING_MARKERS)


def _tool_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _tool_parameters(raw: Any) -> dict[str, Any]:
    """DashScope rejects / 500s on empty or typeless function schemas."""
    if not isinstance(raw, dict) or not raw:
        return {"type": "object", "properties": {}}
    params = dict(raw)
    if params.get("type") is None:
        params["type"] = "object"
    if params["type"] == "object" and "properties" not in params:
        params["properties"] = {}
    return params


class LLMError(RuntimeError):
    """Provider call succeeded at HTTP level but yielded no usable answer."""


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 8192,
        **client_kwargs: Any,
    ) -> None:
        super().__init__(model=model, max_tokens=max_tokens)
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ImportError(
                "The 'openai' package is required for OpenAIProvider. "
                "Install it with: pip install codeagent[openai]"
            ) from exc
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if key is None and base_url:
            # 免鉴权自建端点（ds4/vLLM/llama.cpp）：占位 key，头部被忽略
            key = "EMPTY"
        self.idle_timeout = STALL_SWITCH_SECONDS
        self.client = AsyncOpenAI(
            api_key=key,
            base_url=base_url,
            timeout=3600.0,
            **client_kwargs,
        )

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        system: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        converted = self._convert_messages(messages)
        if system:
            converted.insert(0, {"role": "system", "content": system})

        request: dict[str, Any] = {
            "model": self.model,
            "messages": converted,
            "max_tokens": self.max_tokens,
        }
        if tools:
            request["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": _tool_parameters(t.get("parameters")),
                    },
                }
                for t in tools
            ]
        request.update(kwargs)
        request["stream"] = True

        try:
            response = await asyncio.wait_for(
                self._create_with_retry(request),
                timeout=self.idle_timeout,
            )
        except TimeoutError as exc:
            raise StallTimeout(self._stall_message()) from exc
        if hasattr(response, "__aiter__"):
            return await self._from_stream(response)
        return self._from_completion(response)

    def _from_completion(self, response: Any) -> LLMResponse:
        choice = response.choices[0]
        msg = choice.message

        tool_calls = [
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=_tool_arguments(tc.function.arguments),
            )
            for tc in msg.tool_calls or []
        ]

        content = msg.content or ""
        reasoning = (getattr(msg, "reasoning_content", None) or "").strip()
        if not content and reasoning:
            content, reasoning = reasoning, ""
        finish = choice.finish_reason or "stop"
        if not content and not tool_calls:
            if finish == "length":
                raise LLMError(
                    f"输出被 token 上限（{self.max_tokens}）截断：思考型模型把预算"
                    "烧在了推理链上。请调大 max_tokens，或要求模型先给结论。"
                )
            raise LLMError(
                "模型返回空内容（思考型模型可能把正文放在 reasoning 字段，"
                "或服务端异常）"
            )

        usage = Usage()
        if response.usage:
            usage = Usage(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=finish,
            usage=usage,
            reasoning=reasoning,
        )

    async def _from_stream(self, stream: Any) -> LLMResponse:
        """Switch away when a stream stays silent: no thinking and no work."""
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tools: dict[int, dict[str, str]] = {}
        finish = "stop"
        usage = Usage()
        self._useful_deadline = time.monotonic() + self.idle_timeout
        agen = stream.__aiter__()
        try:
            while True:
                remaining = self._useful_deadline - time.monotonic()
                if remaining <= 0:
                    raise StallTimeout(self._stall_message())
                try:
                    chunk = await asyncio.wait_for(agen.__anext__(), timeout=remaining)
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError as exc:
                    raise StallTimeout(self._stall_message()) from exc
                if self._absorb_chunk(chunk, content_parts, reasoning_parts, tools):
                    self._useful_deadline = time.monotonic() + self.idle_timeout
                choice = (getattr(chunk, "choices", None) or [None])[0]
                if choice is not None and getattr(choice, "finish_reason", None):
                    finish = choice.finish_reason
                raw_usage = getattr(chunk, "usage", None)
                if raw_usage is not None:
                    usage = Usage(
                        input_tokens=getattr(raw_usage, "prompt_tokens", 0) or 0,
                        output_tokens=getattr(raw_usage, "completion_tokens", 0) or 0,
                    )
        finally:
            aclose = getattr(stream, "aclose", None) or getattr(agen, "aclose", None)
            if callable(aclose):
                await aclose()

        tool_calls = [
            ToolCall(
                id=item["id"] or f"call_{index}",
                name=item["name"],
                arguments=_tool_arguments(item["arguments"]),
            )
            for index, item in sorted(tools.items())
        ]
        content = "".join(content_parts)
        reasoning = "".join(reasoning_parts).strip()
        if not content and reasoning:
            content, reasoning = reasoning, ""
        if not content and not tool_calls:
            if finish == "length":
                raise LLMError(
                    f"输出被 token 上限（{self.max_tokens}）截断：思考型模型把预算"
                    "烧在了推理链上。请调大 max_tokens，或要求模型先给结论。"
                )
            raise LLMError(
                "模型返回空内容（思考型模型可能把正文放在 reasoning 字段，"
                "或服务端异常）"
            )
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=finish or "stop",
            usage=usage,
            reasoning=reasoning,
        )

    def _stall_message(self) -> str:
        return (
            f"{self.model} 超过 {int(self.idle_timeout)} 秒没有思考也没有工作，视为卡住"
        )

    @staticmethod
    def _absorb_chunk(chunk: Any, content: list[str], reasoning: list[str], tools: dict[int, dict[str, str]]) -> bool:
        choice = (getattr(chunk, "choices", None) or [None])[0]
        if choice is None:
            return False
        delta = getattr(choice, "delta", None)
        if delta is None:
            return False
        useful = False
        text = getattr(delta, "content", None)
        if text:
            content.append(str(text))
            useful = True
        thought = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
        if thought:
            reasoning.append(str(thought))
            useful = True
        for tc in getattr(delta, "tool_calls", None) or []:
            useful = True
            index = int(getattr(tc, "index", 0) or 0)
            slot = tools.setdefault(index, {"id": "", "name": "", "arguments": ""})
            if getattr(tc, "id", None):
                slot["id"] = tc.id
            fn = getattr(tc, "function", None)
            if fn is None:
                continue
            if getattr(fn, "name", None):
                slot["name"] += fn.name
            if getattr(fn, "arguments", None):
                slot["arguments"] += fn.arguments
        return useful

    async def _create_with_retry(self, request: dict[str, Any]) -> Any:
        """Retry DashScope/compat 500s once — first failure is often transient."""
        last: Exception | None = None
        for attempt in range(2):
            try:
                return await self.client.chat.completions.create(**request)
            except Exception as exc:  # noqa: BLE001 — classify, then retry or raise
                last = exc
                if attempt == 1 or not is_transient_serving_error(exc):
                    raise
                await asyncio.sleep(0.5)
        raise last  # pragma: no cover

    @staticmethod
    def _convert_messages(messages: list[Message]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
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
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                converted.append(entry)
            elif msg.role == Role.TOOL:
                converted.extend(
                    {
                        "role": "tool",
                        "tool_call_id": r.tool_call_id,
                        "content": r.content,
                    }
                    for r in msg.tool_results
                )
        return converted
