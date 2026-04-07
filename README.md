# ai-bot-framework

AI agent framework with tool system, memory management, and multi-round tool calling. Built on Anthropic Claude API.

## Installation

```bash
pip install ai-bot-framework
```

## Quick Start

```python
from pydantic import BaseModel, Field

from ai_framework import AIApplication, BaseTool, ToolContext


class GetWeatherTool(BaseTool):
    name = "get_weather"
    description = "Get current weather for a city"

    class Input(BaseModel):
        city: str = Field(description="City name")

    def execute(self, input: Input, context: ToolContext) -> str:
        return f"Weather in {input.city}: 22C, sunny"


with AIApplication(
    api_key="sk-ant-...",
    system_prompt="You are a helpful assistant.",
    database_url="postgresql://user:pass@localhost/mydb",
    tools=[GetWeatherTool()],
) as app:
    response = app.process_message("user-123", "What's the weather in Moscow?")
    print(response.content)
```

## AIApplication

Central orchestrator. Sends messages to Claude, executes tool calls in a loop, and stores conversation history in PostgreSQL.

```python
app = AIApplication(
    api_key="sk-ant-...",               # Anthropic API key
    system_prompt="You are a helper.",   # system prompt
    database_url="postgresql://...",     # PostgreSQL connection
    tools=[MyTool()],                   # list of BaseTool instances
    model="claude-sonnet-4-20250514",   # model (optional)
    provider=Provider.ANTHROPIC,        # provider (optional)
    max_tool_rounds=10,                 # max tool call rounds per message (optional)
)
```

Use as a context manager — `__enter__` runs database migrations and opens connections, `__exit__` closes them:

```python
with app:
    response = app.process_message("thread-1", "Hello")
```

## Tools

Define tools by subclassing `BaseTool`. Input schema is generated automatically from the Pydantic `Input` model.

```python
from pydantic import BaseModel, Field

from ai_framework import BaseTool, ToolContext


class SearchTool(BaseTool):
    name = "search"
    description = "Search the knowledge base"

    class Input(BaseModel):
        query: str = Field(description="Search query")
        limit: int = Field(default=5, description="Max results to return")

    def __init__(self, search_service: SearchService):
        self.search_service = search_service

    def execute(self, input: Input, context: ToolContext) -> str:
        results = self.search_service.search(input.query, input.limit)
        return "\n".join(results)
```

### Suppress Response

Tools can signal that the bot should not send the final text response to the user. This is useful for tools that handle the response themselves (e.g. sending a file, forwarding a message, or triggering an external action).

Set `suppress_response = True` on the tool class:

```python
class SendFileTool(BaseTool):
    name = "send_file"
    description = "Send a file to the user"
    suppress_response = True

    class Input(BaseModel):
        file_path: str = Field(description="Path to the file")

    def execute(self, input: Input, context: ToolContext) -> str:
        send_file(context.chat_id, input.file_path)
        return "File sent"
```

If any tool in the conversation loop has `suppress_response = True`, the final `AIResponse.suppress_response` will be `True`. The caller can then skip sending the text message:

```python
response = app.process_message("user-123", "Send me the report")
if not response.suppress_response:
    send_text(response.content)
```

### Context

Runtime context (e.g. user ID, chat ID) is available via `ToolContext` — it is not exposed to the LLM:

```python
class GetOrdersTool(BaseTool):
    name = "get_orders"
    description = "Get user's recent orders"

    class Input(BaseModel):
        limit: int = Field(default=10, description="Max orders to return")

    def execute(self, input: Input, context: ToolContext) -> str:
        return str(fetch_orders(context.user_id, input.limit))


# Pass context when processing a message
response = app.process_message(
    "user-123",
    "Show my orders",
    tool_context={"user_id": 42},
)
```

### Dependency Injection

Tools receive dependencies through `__init__`, no factory functions needed:

```python
class SendLeadTool(BaseTool):
    name = "send_lead"
    description = "Send a loan application lead to CRM"

    class Input(BaseModel):
        full_name: str = Field(description="Customer full name")
        phone: str = Field(description="Phone number")
        amount: int = Field(description="Loan amount")

    def __init__(self, lead_sender: ILeadSender):
        self.lead_sender = lead_sender

    def execute(self, input: Input, context: ToolContext) -> dict:
        return self.lead_sender.send(
            context.chat_id, input.full_name, input.phone, input.amount,
        )


# Wire up dependencies
tools = [
    SendLeadTool(lead_sender),
    GetProductsTool(products_provider),
]
app = AIApplication(..., tools=tools)
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

## Architecture

Layered architecture enforced by [import-linter](https://github.com/seddonym/import-linter):

```
application    →  AIApplication (orchestrator)
providers      →  AnthropicProvider, ClaudeSdkProvider
tools          →  ToolRegistry
session        →  Session store (PostgreSQL)
memory         →  Memory store (PostgreSQL)
migrations     →  Database migrations (yoyo)
protocols      →  IAIProvider, IMemoryStore, ISessionStore, BaseTool
entities       →  Message, ToolCall, ToolResult, AIResponse, ToolContext, TokenUsage, Provider
```

Each layer can import from layers below it, but not above.

## Requirements

- Python >= 3.13
- `anthropic` >= 0.52.0
- `pydantic` >= 2.11.0
- `psycopg` >= 3.3.2
