from __future__ import annotations

from typing import Any


class ToolContext:
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data = data or {}

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(
                f"ToolContext has no attribute '{name}'"
            ) from None

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)
