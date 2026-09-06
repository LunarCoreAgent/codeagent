"""OpenAI provider (also covers OpenAI-compatible endpoints)."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from codeagent.core.types import LLMResponse, Message, Role, ToolCall, Usage
from codeagent.llm.base import LLMProvider

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
        self.client = AsyncOpenAI(
            api_key=key,
            base_url=base_url,
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

        response = await self._create_with_retry(request)
        choice = response.choices[0]
        msg = choice.message

        tool_calls = [
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=json.loads(tc.function.arguments or "{}"),
            )
            for tc in msg.tool_calls or []
        ]

        # Thinking models (GLM, qwen3 via relays…) may put the answer in
        # reasoning_content when the token budget was eaten by reasoning.
        content = msg.content or getattr(msg, "reasoning_content", None) or ""
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
        )

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
