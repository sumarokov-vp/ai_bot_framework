---
name: publish
description: Публикация пакета на PyPI через uv.
allowed-tools: Bash(.claude/skills/publish/scripts/*)
---

Публикация пакета на PyPI. $ARGUMENTS

## Инструкции

### Перед публикацией

1. Убедись, что в `.env` заполнена переменная `PYPI_TOKEN`
2. Проверь, что версия в `pyproject.toml` обновлена (не совпадает с уже опубликованной)

### Публикация

```bash
.claude/skills/publish/scripts/publish.sh
```

Скрипт автоматически:
- Запускает линтеры и тесты
- Собирает пакет
- Публикует на PyPI

### Bump версии

Если нужно поднять версию перед публикацией, обнови поле `version` в `pyproject.toml`.
