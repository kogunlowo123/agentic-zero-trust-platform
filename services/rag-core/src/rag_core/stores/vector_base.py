from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from rag_core.chunking.base import Chunk


@dataclass
class SearchResult:
    """A single result returned from a vector similarity search."""

    chunk_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


class BaseVectorStore(ABC):
    """Abstract base class for vector stores."""

    @abstractmethod
    async def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Insert or update chunks with their embeddings.

        Args:
            chunks: List of Chunk objects.
            embeddings: Corresponding embeddings, one per chunk.
        """
        raise NotImplementedError

    @abstractmethod
    async def search(
        self,
        query_vector: list[float],
        top_k: int,
        filter: dict | None = None,
    ) -> list[SearchResult]:
        """Perform approximate nearest-neighbour search.

        Args:
            query_vector: The query embedding.
            top_k: Number of results to return.
            filter: Optional metadata filter (store-specific format).

        Returns:
            Ordered list of SearchResult objects (most similar first).
        """
        raise NotImplementedError
