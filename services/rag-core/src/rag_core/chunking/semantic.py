"""Semantic chunker: splits text where sentence similarity drops below a threshold."""

from __future__ import annotations

import hashlib
import re

import numpy as np

from rag_core.chunking.base import BaseChunker, Chunk


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _split_sentences(text: str) -> list[str]:
    """Naive sentence splitter using punctuation boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if s.strip()]


class SemanticChunker(BaseChunker):
    """Chunks text by detecting semantic discontinuities between sentences.

    A new chunk begins whenever the cosine similarity between the embedding
    of the previous sentence and the current sentence falls below
    *similarity_threshold*.  Short chunks (below *min_chunk_size* characters)
    are merged into the adjacent chunk.

    Args:
        embedding_model_name: Name of a sentence-transformers model used to
            embed individual sentences.
        similarity_threshold: Cosine similarity threshold below which a
            boundary is inserted.
        min_chunk_size: Minimum number of characters a chunk must have;
            chunks shorter than this are merged with their predecessor.
    """

    def __init__(
        self,
        embedding_model_name: str = "BAAI/bge-large-en-v1.5",
        similarity_threshold: float = 0.8,
        min_chunk_size: int = 128,
    ) -> None:
        self.embedding_model_name = embedding_model_name
        self.similarity_threshold = similarity_threshold
        self.min_chunk_size = min_chunk_size
        self._model = None  # Lazy-loaded to avoid slow import at module import time.

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.embedding_model_name)
        return self._model

    def _embed_sentences(self, sentences: list[str]) -> np.ndarray:
        model = self._get_model()
        embeddings = model.encode(
            sentences,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=64,
        )
        return np.array(embeddings)

    def chunk(self, documents: list) -> list[Chunk]:  # type: ignore[override]
        """Split each document into semantically coherent chunks.

        Args:
            documents: List of ``Document`` objects.

        Returns:
            Flat list of ``Chunk`` objects.
        """
        all_chunks: list[Chunk] = []
        for doc in documents:
            parent_id = _sha256(doc.content[:256])
            doc_chunks = self._chunk_document(doc, parent_id)
            all_chunks.extend(doc_chunks)
        return all_chunks

    def _chunk_document(self, doc, parent_id: str) -> list[Chunk]:
        sentences = _split_sentences(doc.content)
        if not sentences:
            return []

        if len(sentences) == 1:
            return [
                Chunk(
                    content=sentences[0],
                    metadata=dict(doc.metadata),
                    chunk_id=_sha256(sentences[0]),
                    parent_doc_id=parent_id,
                    position=0,
                )
            ]

        embeddings = self._embed_sentences(sentences)

        # Identify sentence boundaries.
        boundaries: list[int] = [0]
        for i in range(1, len(sentences)):
            sim = _cosine_similarity(embeddings[i - 1], embeddings[i])
            if sim < self.similarity_threshold:
                boundaries.append(i)
        boundaries.append(len(sentences))

        # Build raw chunks from boundaries.
        raw_chunks: list[str] = []
        for start, end in zip(boundaries, boundaries[1:]):
            chunk_text = " ".join(sentences[start:end]).strip()
            raw_chunks.append(chunk_text)

        # Merge short chunks into their predecessor.
        merged: list[str] = []
        for piece in raw_chunks:
            if merged and len(piece) < self.min_chunk_size:
                merged[-1] = merged[-1] + " " + piece
            else:
                merged.append(piece)

        return [
            Chunk(
                content=text,
                metadata=dict(doc.metadata),
                chunk_id=_sha256(text),
                parent_doc_id=parent_id,
                position=pos,
            )
            for pos, text in enumerate(merged)
            if text.strip()
        ]
