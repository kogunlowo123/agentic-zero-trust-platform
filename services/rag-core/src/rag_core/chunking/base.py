from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    """A chunk of text derived from a source document."""

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    chunk_id: str = ""
    parent_doc_id: str = ""
    position: int = 0


class BaseChunker(ABC):
    """Abstract base class for document chunkers."""

    @abstractmethod
    def chunk(self, documents: list) -> list[Chunk]:
        """Split a list of Documents into a list of Chunks.

        Args:
            documents: List of Document objects to chunk.

        Returns:
            List of Chunk objects.
        """
        raise NotImplementedError
