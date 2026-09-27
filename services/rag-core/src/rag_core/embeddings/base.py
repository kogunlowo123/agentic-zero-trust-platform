from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    """Abstract base class for text embedders."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts asynchronously.

        Args:
            texts: Texts to embed.

        Returns:
            List of embedding vectors, one per input text.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def dim(self) -> int:
        """Dimensionality of the embedding vectors produced by this embedder."""
        raise NotImplementedError

    def embed_sync(self, texts: list[str]) -> list[list[float]]:
        """Synchronous wrapper around :meth:`embed`.

        Creates a new event loop if one is not already running so the method
        can be called from non-async contexts.

        Args:
            texts: Texts to embed.

        Returns:
            List of embedding vectors.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # We are inside a running event loop — use a thread executor to
            # avoid nested-loop deadlocks.
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, self.embed(texts))
                return future.result()

        return asyncio.run(self.embed(texts))
