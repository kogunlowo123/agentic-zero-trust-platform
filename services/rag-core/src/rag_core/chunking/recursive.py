"""Recursive character-based text splitter — no external NLP dependencies."""

from __future__ import annotations

import hashlib
from typing import Any

from rag_core.chunking.base import BaseChunker, Chunk


class RecursiveChunker(BaseChunker):
    """Splits documents by trying a sequence of separator strings in order.

    Splitting strategy (from most to least preferred separator):
    ``["\\n\\n", "\\n", ". ", " "]``

    If a piece is still larger than *chunk_size* after splitting on the
    current separator, the next separator is tried recursively until
    individual characters are the fallback.

    Args:
        chunk_size: Maximum number of characters in a single chunk.
        chunk_overlap: Number of characters to repeat at the start of each
            successive chunk for context continuity.
    """

    _SEPARATORS = ["\n\n", "\n", ". ", " "]

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk(self, documents: list) -> list[Chunk]:
        """Split every document into overlapping text chunks.

        Args:
            documents: List of ``Document`` objects.

        Returns:
            Flat list of ``Chunk`` objects in document order.
        """
        all_chunks: list[Chunk] = []
        for doc in documents:
            parent_id = _sha256(doc.content[:256])
            pieces = self._split_text(doc.content, self._SEPARATORS)
            for position, piece in enumerate(pieces):
                chunk_id = _sha256(piece)
                all_chunks.append(
                    Chunk(
                        content=piece,
                        metadata=dict(doc.metadata),
                        chunk_id=chunk_id,
                        parent_doc_id=parent_id,
                        position=position,
                    )
                )
        return all_chunks

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _split_text(self, text: str, separators: list[str]) -> list[str]:
        """Recursively split *text* using the ordered *separators* list."""
        if not text:
            return []

        if len(text) <= self.chunk_size:
            return [text]

        separator = separators[0] if separators else ""
        remaining_seps = separators[1:] if separators else []

        if separator:
            raw_splits = text.split(separator)
        else:
            # Character-level fallback
            raw_splits = list(text)

        good_splits: list[str] = []
        current: list[str] = []
        current_len = 0

        for split in raw_splits:
            split_len = len(split)
            sep_len = len(separator)

            if current_len + split_len + (sep_len if current else 0) > self.chunk_size:
                if current:
                    merged = separator.join(current)
                    if len(merged) > self.chunk_size and remaining_seps:
                        good_splits.extend(self._split_text(merged, remaining_seps))
                    else:
                        good_splits.append(merged)

                    # Keep overlap from the tail of `current`.
                    overlap_text = separator.join(current)
                    overlap_start = max(0, len(overlap_text) - self.chunk_overlap)
                    overlap_content = overlap_text[overlap_start:]
                    current = [overlap_content] if overlap_content else []
                    current_len = len(overlap_content)

            current.append(split)
            current_len += split_len + (sep_len if len(current) > 1 else 0)

        if current:
            merged = separator.join(current)
            if len(merged) > self.chunk_size and remaining_seps:
                good_splits.extend(self._split_text(merged, remaining_seps))
            else:
                good_splits.append(merged)

        return [s for s in good_splits if s.strip()]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
