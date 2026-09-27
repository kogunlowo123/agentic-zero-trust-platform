"""Reciprocal Rank Fusion (RRF) for merging multiple ranked retrieval lists."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SearchResult:
    chunk_id: str
    content: str
    metadata: dict = field(default_factory=dict)
    score: float = 0.0


def rrf_fuse(
    ranked_lists: list[list[SearchResult]],
    k: int = 60,
    top_n: int | None = None,
) -> list[SearchResult]:
    """Merge multiple ranked result lists using Reciprocal Rank Fusion.

    RRF formula: score(d) = sum_i( 1 / (k + rank_i(d)) )
    where rank_i(d) is the 1-based rank of document d in list i.
    Documents not in a list receive no contribution from that list.

    Args:
        ranked_lists: List of ranked result lists to fuse.
        k: RRF smoothing constant (typically 60).
        top_n: Return only the top-N results. Returns all if None.

    Returns:
        Fused and re-ranked list of SearchResults.
    """
    rrf_scores: dict[str, float] = {}
    # Map chunk_id → SearchResult for deduplication
    results_by_id: dict[str, SearchResult] = {}

    for ranked_list in ranked_lists:
        for rank, result in enumerate(ranked_list, start=1):
            chunk_id = result.chunk_id
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            # Keep the first occurrence (dense scores are generally better)
            if chunk_id not in results_by_id:
                results_by_id[chunk_id] = result

    # Sort by RRF score descending
    sorted_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

    fused = []
    for chunk_id in sorted_ids:
        result = results_by_id[chunk_id]
        # Replace the original score with the RRF score
        fused.append(
            SearchResult(
                chunk_id=result.chunk_id,
                content=result.content,
                metadata=result.metadata,
                score=rrf_scores[chunk_id],
            )
        )

    if top_n is not None:
        fused = fused[:top_n]

    return fused
