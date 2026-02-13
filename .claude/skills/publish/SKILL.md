---
name: publish
description: Публикация пакета на PyPI через uv.
allowed-tools: Bash(.claude/skills/publish/scripts/*)
---

Публикация пакета на PyPI. $ARGUMENTS

## Инструкции

### Перед публикацией

1. Убедись, что в `.env` заполнена переменная `PYPI_TOKEN`

### Публикация

```bash
.claude/skills/publish/scripts/publish.sh
```

Скрипт автоматически:
- Инкрементирует patch-версию
- Запускает линтеры и тесты
- Собирает пакет
- Публикует на PyPI

### Bump версии (без публикации)

```bash
.claude/skills/publish/scripts/publish.sh bump patch  # 0.1.0 → 0.1.1 (по умолчанию)
.claude/skills/publish/scripts/publish.sh bump minor  # 0.1.1 → 0.2.0
.claude/skills/publish/scripts/publish.sh bump major  # 0.2.0 → 1.0.0
```
