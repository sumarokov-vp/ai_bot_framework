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

## Attachments

A user message can carry images and PDFs. The model receives them as content blocks (`image`, `document`) and reads them itself — including scans without a text layer.

Supported `media_type`: `image/jpeg`, `image/png`, `image/gif`, `image/webp`, `application/pdf`. Size limits are not checked by the library: they are set by Claude (an image is at most 5 MB) and by the consumer.

Attachments need an attachment store. Bytes never go to the database: `process_message` puts them into the store, and the conversation history (`ai_messages.attachments`, JSONB) keeps only `{key, media_type, filename}`. `Attachment.data` is excluded from serialization, so bytes cannot reach Postgres or Redis even by mistake.

The library ships `S3AttachmentStore` for any S3-compatible storage — DigitalOcean Spaces, MinIO, AWS S3. It needs the `s3` extra (`boto3`); consumers without attachments do not pull it:

```bash
pip install "ai-bot-framework[s3]"
```

```python
import os

from ai_framework import AIApplication, Attachment, Provider
from ai_framework.attachments.s3_attachment_store import S3AttachmentStore

attachment_store = S3AttachmentStore(
    endpoint_url="https://fra1.digitaloceanspaces.com",
    bucket="assistant-attachments",
    access_key=os.environ["SPACES_ACCESS_KEY"],
    secret_key=os.environ["SPACES_SECRET_KEY"],
    region="fra1",
    prefix="assistant",               # optional: keys become assistant/<uuid>.<ext>
)

app = AIApplication(
    api_key="",
    system_prompt="You are a helpful assistant.",
    database_url="postgresql://...",
    tools=[],
    provider=Provider.CLAUDE_SDK,
    attachment_store=attachment_store,
)

with app:
    response = app.process_message(
        "user-123",
        "When does this passport expire?",
        attachments=[
            Attachment(media_type="image/jpeg", filename="passport.jpg", data=photo_bytes),
        ],
    )
```

Rules:

- `attachments` without `attachment_store` — `ValueError` before the model is called.
- `S3AttachmentStore` does not create the bucket; the bucket and its keys are provisioned outside the library. Objects are never overwritten (every `put` gets a fresh key) and never deleted — `clear_context` removes the history, not the objects.
- `AIApplication` wraps the store in `CachedAttachmentStore` — an in-process LRU cache (64 MB by default); `put` fills it immediately. A running process never reads an attachment back from the bucket; after a restart each object is read once, when the history is rebuilt for the model.
- Previous turns' attachments are sent as they were stored; limit them with `history_turns_limit`.
- Any other storage fits as long as it implements `IAttachmentStore` (`put(data, media_type) -> key`, `get(key) -> bytes`, `KeyError` for a missing key). `InMemoryAttachmentStore` from `ai_framework.attachments` is meant for tests.

Messages without attachments work exactly as before.
