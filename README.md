# ai-bot-framework

AI agent framework with tool system, memory management, and multi-round tool calling. Built on Anthropic Claude API.

## Installation

```bash
pip install ai-bot-framework
```

## Quick Start

```python
from ai_framework import AIApplication
from ai_framework.tools import tool

@tool(name="get_weather", description="Get current weather for a city")
def get_weather(city: str) -> str:
    return f"Weather in {city}: 22C, sunny"

with AIApplication(
    api_key="sk-ant-...",
    system_prompt="You are a helpful assistant.",
    database_url="postgresql://user:pass@localhost/mydb",
    tools=[get_weather],
) as app:
    response = app.process_message("user-123", "What's the weather in Moscow?")
    print(response.content)
```

## AIApplication

Central orchestrator. Sends messages to Claude, executes tool calls in a loop, and stores conversation history in PostgreSQL.

```python
app = AIApplication(
    api_key="sk-ant-...",               # Anthropic API key
    system_prompt="You are a helper.",  # system prompt
    database_url="postgresql://...",    # PostgreSQL connection
    tools=[my_tool],                    # list of tools (empty list if none)
    model="claude-sonnet-4-20250514",   # model string from Anthropic docs (optional)
    provider=Provider.ANTHROPIC,        # provider enum (optional)
    max_tool_rounds=10,                 # max tool call rounds per message (optional)
)
```

Use as a context manager — `__enter__` runs database migrations and opens connections, `__exit__` closes them:

```python
app = AIApplication(...)

with app:
    response = app.process_message("thread-1", "Hello")
```

## Tools

Define tools with the `@tool` decorator. Input schema is generated automatically from type hints.

```python
from ai_framework.tools import tool

@tool(name="search", description="Search the knowledge base")
def search(query: str, limit: int = 5) -> str:
    results = do_search(query, limit)
    return "\n".join(results)
```

### Context Parameters

Inject runtime context (e.g. user ID) into tools without exposing it to the LLM:

```python
@tool(
    name="get_orders",
    description="Get user's recent orders",
    context_params=["user_id"],
)
def get_orders(user_id: int, limit: int = 10) -> str:
    return str(fetch_orders(user_id, limit))

# user_id is excluded from the schema sent to Claude
# and injected at call time via tool_context
response = app.process_message(
    "user-123",
    "Show my orders",
    tool_context={"user_id": 42},
)
```

## Multi-round Tool Calling

`process_message` runs a loop: send message to Claude, execute any tool calls, send results back, repeat until Claude responds with text or `max_tool_rounds` is reached.

```python
response = app.process_message("thread-1", "Book a flight to Berlin")
print(response.content)       # final text response
print(response.tool_calls)    # tool calls from the last round
print(response.usage)         # token usage (input_tokens, output_tokens)
```

## System Prompt

Set at construction or update at runtime:

```python
app.update_system_prompt("You now speak French only.")
```

## Conversation Management

```python
# Clear conversation history for a thread
app.clear_context("user-123")
```

## Providers

The `Provider` enum selects the AI backend:

```python
from ai_framework import AIApplication, Provider

# Anthropic API (default)
app = AIApplication(api_key="...", provider=Provider.ANTHROPIC, ...)

# Claude Code SDK (requires: pip install ai-bot-framework[claude-sdk])
app = AIApplication(api_key="...", provider=Provider.CLAUDE_SDK, ...)
```

## Bot Framework Integration

`AIStep` integrates with [bot-framework](https://github.com/sumarokov-vp/bot-framework) for Telegram bots:

```python
from ai_framework import AIApplication, AIStep

with AIApplication(
    api_key="...",
    system_prompt="...",
    database_url="postgresql://...",
    tools=[],
) as app:
    step = AIStep(ai_application=app, message_sender=my_sender)
```

## Architecture

Layered architecture enforced by [import-linter](https://github.com/seddonym/import-linter):

```
integrations   →  AIStep (bot-framework bridge)
application    →  AIApplication (orchestrator)
providers      →  AnthropicProvider, ClaudeSdkProvider
tools          →  ToolRegistry, @tool decorator
session        →  Session store (PostgreSQL)
memory         →  Memory store (PostgreSQL)
migrations     →  Database migrations (yoyo)
protocols      →  IAIProvider, IMemoryStore, ISessionStore
entities       →  Message, ToolCall, ToolResult, AIResponse, TokenUsage, Provider
```

Each layer can import from layers below it, but not above.

## Requirements

- Python >= 3.13
- `anthropic` >= 0.52.0
- `pydantic` >= 2.11.0
- `psycopg` >= 3.3.2
