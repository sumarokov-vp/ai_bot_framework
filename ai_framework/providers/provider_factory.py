from __future__ import annotations

from ai_framework.entities.provider import Provider
from ai_framework.protocols.i_ai_provider import IAIProvider


def create_provider(
    provider: Provider, api_key: str, model: str,
) -> IAIProvider:
    if provider == Provider.ANTHROPIC:
        from ai_framework.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(api_key=api_key, model=model)
    if provider == Provider.CLAUDE_SDK:
        from ai_framework.providers.claude_sdk_provider import ClaudeSdkProvider

        return ClaudeSdkProvider(model=model)
    raise ValueError(f"Unknown provider: {provider}")
