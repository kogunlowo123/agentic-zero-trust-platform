"""Corrective Retrieval Augmented Generation (CRAG) pattern."""

from __future__ import annotations

import structlog

from rag_core.retrieval.hybrid import HybridRetriever
from rag_core.stores.vector_base import SearchResult

logger = structlog.get_logger(__name__)

_QUALITY_THRESHOLD = 0.7
_REFORMULATION_PREFIX = "zero trust policy: "


class CorrectiveRetriever:
    """Wraps a :class:`HybridRetriever` with a retrieval quality gate.

    If the top-ranked result from the first retrieval attempt has a score
    below *quality_threshold*, the query is reformulated and retrieval is
    attempted once more.  The reformulated query has
    ``"zero trust policy: "`` prepended to anchor the search in the
    zero-trust domain.

    Args:
        base_retriever: The underlying hybrid retriever.
        quality_threshold: Minimum acceptable score for the best result.
            If the best result's RRF score falls below this, retrieval is
            retried with a reformulated query.
    """

    def __init__(
        self,
        base_retriever: HybridRetriever,
        quality_threshold: float = _QUALITY_THRESHOLD,
    ) -> None:
        self._retriever = base_retriever
        self._threshold = quality_threshold

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        principal_acl: list[str] | None = None,
    ) -> list[SearchResult]:
        """Retrieve results, retrying with a reformulated query if quality is low.

        Args:
            query: User query string.
            top_k: Number of results to return.
            principal_acl: ACL list for post-retrieval filtering.

        Returns:
            Best available list of :class:`SearchResult` objects.
        """
        results = await self._retriever.retrieve(
            query, top_k=top_k, principal_acl=principal_acl
        )

        max_score = max((r.score for r in results), default=0.0)
        logger.debug(
            "corrective_retrieval_quality",
            query=query[:80],
            max_score=max_score,
            threshold=self._threshold,
        )

        if max_score < self._threshold:
            reformulated = _REFORMULATION_PREFIX + query
            logger.info(
                "corrective_retrieval_reformulating",
                original_query=query[:80],
                reformulated=reformulated[:120],
            )
            retry_results = await self._retriever.retrieve(
                reformulated, top_k=top_k, principal_acl=principal_acl
            )
            # Return whichever attempt produced the better top result.
            retry_max = max((r.score for r in retry_results), default=0.0)
            if retry_max >= max_score:
                return retry_results

        return results
