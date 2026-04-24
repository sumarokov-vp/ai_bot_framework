# AIApplication

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
