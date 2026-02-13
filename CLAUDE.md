# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI agent framework with tool system, memory management, and multi-round tool calling. Built on Anthropic Claude API.

## Commands

```bash
uv sync                    # Install dependencies
uv run pytest              # Run all tests
uv run pytest tests/test_foo.py::test_name  # Run single test
uv run ruff check src/     # Lint
uv run mypy src/           # Type check
uv run pyright src/        # Type check (pyright)
```

## Architecture

Layered architecture enforced by import-linter (top imports from bottom, not vice versa):

```
providers          → AnthropicProvider, ClaudeSdkProvider
tools              → ToolRegistry, @tool decorator
memory             → InMemoryStore, PostgresMemoryStore, RedisMemoryStore
protocols          → IAIProvider, IMemoryStore, IToolRegistry (Protocol classes)
entities           → Message, ToolCall, ToolResult, AIResponse, TokenUsage (Pydantic models)
```

**AIApplication** (`application.py`) — central orchestrator. Accepts provider, memory store, and tool registry via constructor. Runs multi-round tool calling loop (send → execute tools → send results → repeat until done or max rounds).

**Tool system** — `@tool` decorator auto-generates JSON schema from function type hints. `ToolRegistry` stores and executes tools by name.

**Providers** convert between internal `Message`/`AIResponse` format and external API formats. `ClaudeSdkProvider` supports async claude-code-sdk with session resumption.

**Integration** — `AIStep` bridges with bot-framework (Telegram bot flow step).
