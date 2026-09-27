"""Cross-encoder reranker using sentence-transformers."""

from __future__ import annotations

import asyncio
from functools import partial

import structlog

from rag_core.stores.vector_base import SearchResult

logger = structlog.get_logger(__name__)

_DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class CrossEncoderReranker:
    """Reranks retrieval results using a cross-encoder model.

    The cross-encoder produces a relevance score for each (query, passage) pair,
    which is more accurate than the bi-encoder scores used in first-stage
    retrieval.  Inference runs in a thread pool to avoid blocking the event loop.

    Args:
        model_name: HuggingFace model name or local path.
    """

    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        self._model_name = model_name
        self._model = None  # Lazy-loaded.

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name)
        return self._model

    def _rerank_sync(
        self, query: str, results: list[SearchResult], top_k: int
    ) -> list[SearchResult]:
        if not results:
            return []

        model = self._get_model()
        pairs = [(query, r.content) for r in results]
        scores: list[float] = model.predict(pairs).tolist()

        scored = sorted(
            zip(results, scores),
            key=lambda x: x[1],
            reverse=True,
        )

        reranked: list[SearchResult] = []
        for result, score in scored[:top_k]:
            reranked.append(
                SearchResult(
                    chunk_id=result.chunk_id,
                    content=result.content,
                    metadata=result.metadata,
                    score=float(score),
                )
            )

        return reranked

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """Rerank *results* with respect to *query*.

        Args:
            query: The user query string.
            results: Candidate results from first-stage retrieval.
            top_k: Maximum number of results to return after reranking.

        Returns:
            Top-k results ordered by cross-encoder relevance score.
        """
        loop = asyncio.get_event_loop()
        reranked = await loop.run_in_executor(
            None,
            partial(self._rerank_sync, query, results, top_k),
        )
        logger.debug(
            "reranker_done",
            candidates=len(results),
            returned=len(reranked),
        )
        return reranked
