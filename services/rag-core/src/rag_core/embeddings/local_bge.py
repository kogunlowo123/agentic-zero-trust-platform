"""Local sentence-transformer embedder using the BGE-large model."""

from __future__ import annotations

import asyncio
from functools import partial

from rag_core.embeddings.base import BaseEmbedder


class LocalBGEEmbedder(BaseEmbedder):
    """Generates embeddings locally using the BAAI/bge-large-en-v1.5 model.

    Encoding runs in a :class:`concurrent.futures.ThreadPoolExecutor` so the
    asyncio event loop is never blocked by CPU-bound SentenceTransformer work.

    Args:
        model_name: Name or path of the SentenceTransformer model to load.
        batch_size: Number of texts to encode per forward pass.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-large-en-v1.5",
        batch_size: int = 32,
    ) -> None:
        self._model_name = model_name
        self._batch_size = batch_size
        self._model = None  # Lazy-loaded to defer the slow model download.

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    @property
    def dim(self) -> int:
        """Dimensionality of bge-large-en-v1.5 embeddings."""
        return 1024

    def _encode_sync(self, texts: list[str]) -> list[list[float]]:
        """Blocking encode call — intended to run in a thread executor."""
        model = self._get_model()
        vectors = model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [v.tolist() for v in vectors]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed *texts* asynchronously, delegating blocking work to a thread pool.

        Args:
            texts: Plain text strings to embed.

        Returns:
            List of normalised 1024-dimensional float vectors.
        """
        if not texts:
            return []

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            partial(self._encode_sync, texts),
        )
