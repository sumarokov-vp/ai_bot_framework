# Architecture

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
