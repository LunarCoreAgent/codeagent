"""Anthropic Claude provider."""

from __future__ import annotations

import os
from typing import Any

from codeagent.core.types import LLMResponse, Message, Role, ToolCall, Usage
from codeagent.llm.base import LLMProvider

DEFAULT_MODEL = "claude-sonnet-4-5"


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        max_tokens: int = 8192,
        **client_kwargs: Any,
    ) -> None:
        super().__init__(model=model, max_tokens=max_tokens)
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise ImportError(
                "The 'anthropic' package is required for AnthropicProvider. "
                "Install it with: pip install codeagent[anthropic]"
            ) from exc
        self.client = AsyncAnthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
            **client_kwargs,
        )

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        system: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": self._convert_messages(messages),
        }
        if system:
            request["system"] = system
        if tools:
            request["tools"] = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "input_schema": t["parameters"],
                }
                for t in tools
            ]
        request.update(kwargs)

        response = await self.client.messages.create(**request)

        content = ""
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
                )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason or "stop",
            usage=Usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            ),
        )

    @staticmethod
    def _convert_messages(messages: list[Message]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == Role.SYSTEM:
                continue  # system prompt is a top-level API parameter
            if msg.role == Role.USER:
                converted.append({"role": "user", "content": msg.content})
            elif msg.role == Role.ASSISTANT:
                blocks: list[dict[str, Any]] = []
                if msg.content:
                    blocks.append({"type": "text", "text": msg.content})
                blocks.extend(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    }
                    for tc in msg.tool_calls
                )
                converted.append({"role": "assistant", "content": blocks})
            elif msg.role == Role.TOOL:
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": r.tool_call_id,
                                "content": r.content,
                                "is_error": r.is_error,
                            }
                            for r in msg.tool_results
                        ],
                    }
                )
        return converted
