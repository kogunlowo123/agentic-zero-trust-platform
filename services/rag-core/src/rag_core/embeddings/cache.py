"""LRU embedding cache that wraps any BaseEmbedder."""

from __future__ import annotations

import hashlib
from collections import OrderedDict

import structlog

from rag_core.embeddings.base import BaseEmbedder

logger = structlog.get_logger(__name__)


def _cache_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class CachedEmbedder(BaseEmbedder):
    """Wraps a :class:`BaseEmbedder` with an in-process LRU cache.

    Cache keys are SHA-256 hashes of the input text.  On a cache hit the
    underlying embedder is never called for that text.  Cache-hit and miss
    statistics are logged via *structlog* at DEBUG level.

    Args:
        embedder: The underlying embedder to delegate misses to.
        max_size: Maximum number of text → vector entries to keep in memory.
    """

    def __init__(self, embedder: BaseEmbedder, max_size: int = 10000) -> None:
        self._embedder = embedder
        self._max_size = max_size
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    @property
    def dim(self) -> int:
        return self._embedder.dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings, using cache for any text seen before.

        Args:
            texts: Texts to embed.

        Returns:
            List of float vectors aligned with the input list.
        """
        keys = [_cache_key(t) for t in texts]
        results: list[list[float] | None] = [None] * len(texts)

        # Identify misses.
        miss_indices: list[int] = []
        miss_texts: list[str] = []

        for i, (text, key) in enumerate(zip(texts, keys)):
            cached = self._cache.get(key)
            if cached is not None:
                # Move to end (most-recently used)
                self._cache.move_to_end(key)
                results[i] = cached
                self._hits += 1
            else:
                miss_indices.append(i)
                miss_texts.append(text)
                self._misses += 1

        total = len(texts)
        hit_count = total - len(miss_indices)
        logger.debug(
            "embedding_cache_stats",
            hits=hit_count,
            misses=len(miss_indices),
            total=total,
            hit_rate=hit_count / total if total else 0.0,
        )

        # Fetch embeddings for misses.
        if miss_texts:
            fresh = await self._embedder.embed(miss_texts)
            for idx, vec in zip(miss_indices, fresh):
                key = keys[idx]
                self._cache[key] = vec
                self._cache.move_to_end(key)
                results[idx] = vec

                # Evict oldest entry if over capacity.
                if len(self._cache) > self._max_size:
                    self._cache.popitem(last=False)

        return results  # type: ignore[return-value]

    @property
    def cache_size(self) -> int:
        """Current number of entries in the LRU cache."""
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        """Overall cache hit rate since instantiation."""
        total = self._hits + self._misses
        return self._hits / total if total else 0.0
