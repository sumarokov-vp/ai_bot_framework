---
name: publish
description: Публикация пакета через Git tag + push на GitHub.
allowed-tools: Bash(.claude/skills/publish/scripts/*)
---

Публикация пакета через Git tag на GitHub. $ARGUMENTS

## Инструкции

### Публикация

```bash
.claude/skills/publish/scripts/publish.sh
```

Скрипт автоматически:
- Инкрементирует patch-версию
- Запускает линтеры и тесты
- Коммитит bump версии
- Создаёт git tag (v0.X.Y)
- Пушит коммит и тег на GitHub

### Bump версии (без публикации)

```bash
.claude/skills/publish/scripts/publish.sh bump patch  # 0.1.0 → 0.1.1 (по умолчанию)
.claude/skills/publish/scripts/publish.sh bump minor  # 0.1.1 → 0.2.0
.claude/skills/publish/scripts/publish.sh bump major  # 0.2.0 → 1.0.0
```

### Потребители

Потребители подключают пакет через Git tag в pyproject.toml:

```toml
[tool.uv.sources]
ai-bot-framework = { git = "https://github.com/sumarokov-vp/ai_bot_framework.git", tag = "v0.4.0" }
```
