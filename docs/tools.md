# Tools

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

## Suppress Response

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

If any tool in the conversation loop has `suppress_response = True`, the final `AIResponse.suppress_response` will be `True`.

**Important:** The framework sets the flag but does not prevent the LLM from generating text — `response.content` will still contain a message. Every call site that sends `response.content` to the user **must** check `suppress_response` and skip sending. Otherwise the user will receive a duplicate message (one from the tool, one from the LLM).

```python
response = app.process_message("user-123", "Send me the report")
if response.suppress_response:
    return  # Tool already handled the response — do NOT send content
send_text(response.content)
```

A common mistake is checking only `response.content`:

```python
# WRONG — suppress_response is ignored, user gets a duplicate message
if not response.content:
    return
send_text(response.content)

# CORRECT — check suppress_response first
if not response.content or response.suppress_response:
    return
send_text(response.content)
```

## Context

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

## Dependency Injection

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
