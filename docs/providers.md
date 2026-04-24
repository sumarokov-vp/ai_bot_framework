# Providers

The `Provider` enum selects the AI backend:

```python
from ai_framework import AIApplication, Provider

# Anthropic API (default)
app = AIApplication(
    api_key="...",
    system_prompt="You are a helpful assistant.",
    database_url="postgresql://...",
    tools=[],
    provider=Provider.ANTHROPIC,
)

# Claude Code SDK (requires: pip install ai-bot-framework[claude-sdk])
app = AIApplication(
    api_key="...",
    system_prompt="You are a helpful assistant.",
    database_url="postgresql://...",
    tools=[],
    provider=Provider.CLAUDE_SDK,
)
```
