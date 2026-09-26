from __future__ import annotations

from collections import OrderedDict

from ai_framework.protocols.i_attachment_store import IAttachmentStore


DEFAULT_CACHE_MAX_BYTES = 64 * 1024 * 1024


class CachedAttachmentStore:
    def __init__(
        self,
        inner: IAttachmentStore,
        max_bytes: int = DEFAULT_CACHE_MAX_BYTES,
    ) -> None:
        if max_bytes < 0:
            raise ValueError("max_bytes must be non-negative")
        self._inner = inner
        self._max_bytes = max_bytes
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._cached_bytes = 0

    def put(self, data: bytes, media_type: str) -> str:
        key = self._inner.put(data, media_type)
        self._remember(key, data)
        return key

    def get(self, key: str) -> bytes:
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached
        data = self._inner.get(key)
        self._remember(key, data)
        return data

    def _remember(self, key: str, data: bytes) -> None:
        if len(data) > self._max_bytes:
            return
        previous = self._cache.pop(key, None)
        if previous is not None:
            self._cached_bytes -= len(previous)
        self._cache[key] = data
        self._cached_bytes += len(data)
        while self._cached_bytes > self._max_bytes:
            _, evicted = self._cache.popitem(last=False)
            self._cached_bytes -= len(evicted)
