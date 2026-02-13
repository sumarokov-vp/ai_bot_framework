from __future__ import annotations

from typing import Any

import anthropic

from ai_framework.entities.ai_response import AIResponse
from ai_framework.entities.message import Message
from ai_framework.entities.token_usage import TokenUsage
from ai_framework.entities.tool import ToolCall
from ai_framework.protocols.tool_definition import ToolDefinition


class AnthropicProvider:
    def __init__(
        self, api_key: str, model: str = "claude-sonnet-4-20250514"
    ) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def send_message(
        self,
        messages: list[Message],
        system: str | None = None,
        tools: list[ToolDefinition] | None = None,
    ) -> AIResponse:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 8192,
            "messages": [self._convert_message(m) for m in messages],
        }

        if system:
            kwargs["system"] = system

        if tools:
            kwargs["tools"] = [self._convert_tool(t) for t in tools]

        response = self._client.messages.create(**kwargs)

        return self._convert_response(response)

    def _convert_message(self, message: Message) -> dict[str, Any]:
        if message.tool_results:
            content: list[dict[str, Any]] = [
                {
                    "type": "tool_result",
                    "tool_use_id": tr.tool_call_id,
                    "content": tr.content,
                    **({"is_error": True} if tr.is_error else {}),
                }
                for tr in message.tool_results
            ]
            return {"role": "user", "content": content}

        if message.role == "assistant" and message.tool_calls:
            content_blocks: list[dict[str, Any]] = []
            if message.content:
                content_blocks.append({"type": "text", "text": message.content})
            for tc in message.tool_calls:
                content_blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    }
                )
            return {"role": "assistant", "content": content_blocks}

        return {"role": message.role, "content": message.content}

    def _convert_tool(self, tool: ToolDefinition) -> dict[str, Any]:
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }

    def _convert_response(self, response: anthropic.types.Message) -> AIResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=dict(block.input),  # pyright: ignore[reportUnknownArgumentType]
                    )
                )

        return AIResponse(
            content="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason,
            usage=TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            ),
        )
