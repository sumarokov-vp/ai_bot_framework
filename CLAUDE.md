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

## Publishing

Package is published via Git tags (not PyPI). The `/publish` skill bumps the version, creates a tag `vX.Y.Z`, and pushes to GitHub.

Consumers install via Git tag in `pyproject.toml`:

```toml
[tool.uv.sources]
ai-bot-framework = { git = "https://github.com/sumarokov-vp/ai_bot_framework.git", tag = "v0.4.0" }
```

## Documentation

Detailed docs are in `docs/`:

- [Installation & Quick Start](docs/installation.md) — pip install, minimal working example
- [AIApplication](docs/application.md) — orchestrator config, multi-round tool calling, system prompt, conversation management
- [Tools](docs/tools.md) — BaseTool, suppress_response, ToolContext, dependency injection
- [Providers](docs/providers.md) — Anthropic API vs Claude Code SDK
- [Architecture](docs/architecture.md) — layered imports, requirements

## Architecture

Layered architecture enforced by import-linter (top imports from bottom, not vice versa):

```
providers          → AnthropicProvider, ClaudeSdkProvider
tools              → ToolRegistry, @tool decorator
memory             → InMemoryStore, PostgresMemoryStore, RedisMemoryStore
protocols          → IAIProvider, IMemoryStore, IToolRegistry (Protocol classes)
entities           → Message, ToolCall, ToolResult, AIResponse, TokenUsage (Pydantic models)
```
