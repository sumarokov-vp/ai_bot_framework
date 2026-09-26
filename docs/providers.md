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

`Provider.CLAUDE_SDK` runs the `claude` CLI and uses whatever login it has — a subscription logged in on the host needs no API key (`api_key` is ignored). If `ANTHROPIC_API_KEY` is set in the environment, the CLI uses it instead of the subscription.

## Claude Code SDK sessions

`ClaudeSdkProvider` keeps one SDK session per conversation thread: `AIApplication` passes the `thread_id` to the provider, and the next turn of that thread resumes its own session (`resume`), so two threads served by one process never see each other's context. The map `thread_id → session_id` lives in process memory. A thread without a session — its first turn, or any turn after a restart — gets a prompt rebuilt from the stored history.

`AIApplication.clear_context(thread_id)` clears the history and resets the SDK session of that thread (`ClaudeSdkProvider.reset_session(thread_id)`); other threads keep theirs. `last_session_id` still returns the latest session of any thread.

`send_message` takes `thread_id` as an optional keyword. `AnthropicProvider` accepts and ignores it; without it `ClaudeSdkProvider` keeps a single session, as before. A custom provider passed to `ToolLoop` must accept the `thread_id` keyword.

Tools with `suppress_response = True` work through the SDK too: the SDK runs the tool itself, the provider records the call and returns `AIResponse.suppress_response=True` from `process_message`.

## Attachments

Both providers pass [attachments](application.md#attachments) to the model as content blocks in the Claude API format: `image/*` becomes an `image` block, `application/pdf` a `document` block, both with a `base64` source. The message text goes after the blocks; an empty text is not sent.

- **AnthropicProvider** — every message of the history with attachments becomes a list of blocks; messages without attachments stay plain strings.
- **ClaudeSdkProvider** — without attachments the prompt is a string, as before. With attachments the prompt switches to the SDK streaming input: one user message whose content is the attachment blocks plus the text. With a live SDK session (`resume`) only the new turn's attachments are sent — the session already holds the earlier ones. Without a session (a fresh process after restart) the whole history is rebuilt, and attachments of earlier turns are read from the attachment store.

The SDK session transcript (`~/.claude/projects/.../<session>.jsonl` on the bot host) keeps a base64 copy of the attachments sent in that session; it is the Claude Code transcript, not the application database, and `resume` needs it.
