"""Hybrid retrieval combining dense (vector) and sparse (BM25) search in parallel."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import structlog

from rag_core.retrieval.rrf import SearchResult, rrf_fuse

logger = structlog.get_logger(__name__)

PGVECTOR_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/platform")
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "zero-trust-chunks")


class HybridRetriever:
    """Parallel dense + sparse retrieval with RRF fusion.

    Dense retrieval uses pgvector cosine similarity.
    Sparse retrieval uses OpenSearch BM25.
    Results are fused using Reciprocal Rank Fusion.
    """

    def __init__(
        self,
        embedder: Any | None = None,
        top_k_dense: int = 10,
        top_k_sparse: int = 10,
        rrf_k: int = 60,
    ) -> None:
        self._embedder = embedder
        self.top_k_dense = top_k_dense
        self.top_k_sparse = top_k_sparse
        self.rrf_k = rrf_k

    async def _dense_retrieve(
        self,
        query_vector: list[float],
        top_k: int,
        acl_filter: list[str] | None = None,
    ) -> list[SearchResult]:
        """Retrieve documents using cosine similarity in pgvector."""
        try:
            import psycopg2
            import psycopg2.extras

            conn = psycopg2.connect(PGVECTOR_URL)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            vector_str = f"[{','.join(str(x) for x in query_vector)}]"
            sql = """
                SELECT id AS chunk_id, content, metadata,
                       1 - (embedding <=> %s::vector) AS score
                FROM chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """
            cur.execute(sql, (vector_str, vector_str, top_k))
            rows = cur.fetchall()
            cur.close()
            conn.close()

            results = []
            for row in rows:
                metadata = row.get("metadata") or {}
                if acl_filter and metadata.get("allowed_principals"):
                    allowed = set(metadata["allowed_principals"])
                    if not (set(acl_filter) & allowed):
                        continue
                results.append(
                    SearchResult(
                        chunk_id=str(row["chunk_id"]),
                        content=row["content"],
                        metadata=metadata,
                        score=float(row["score"]),
                    )
                )
            return results
        except Exception as exc:
            logger.warning("dense_retrieval_failed", error=str(exc))
            return []

    async def _sparse_retrieve(
        self,
        query_text: str,
        top_k: int,
        acl_filter: list[str] | None = None,
    ) -> list[SearchResult]:
        """Retrieve documents using OpenSearch BM25."""
        try:
            import httpx

            query: dict = {
                "size": top_k,
                "query": {
                    "multi_match": {
                        "query": query_text,
                        "fields": ["content^2", "metadata.tags"],
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                    }
                },
            }

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{OPENSEARCH_URL}/{OPENSEARCH_INDEX}/_search",
                    json=query,
                )
                resp.raise_for_status()
                data = resp.json()

            results = []
            for hit in data.get("hits", {}).get("hits", []):
                source = hit.get("_source", {})
                metadata = source.get("metadata", {})
                if acl_filter and metadata.get("allowed_principals"):
                    allowed = set(metadata["allowed_principals"])
                    if not (set(acl_filter) & allowed):
                        continue
                results.append(
                    SearchResult(
                        chunk_id=hit["_id"],
                        content=source.get("content", ""),
                        metadata=metadata,
                        score=hit.get("_score", 0.0),
                    )
                )
            return results
        except Exception as exc:
            logger.warning("sparse_retrieval_failed", error=str(exc))
            return []

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        principal_acl: list[str] | None = None,
    ) -> list[SearchResult]:
        """Run dense and sparse retrieval in parallel, fuse with RRF.

        Args:
            query: The search query string.
            top_k: Number of results to return after fusion.
            principal_acl: Optional list of principal IDs/groups for ACL filtering.

        Returns:
            Fused and re-ranked list of SearchResults.
        """
        # Embed query for dense retrieval
        query_vector: list[float] = []
        if self._embedder is not None:
            try:
                vectors = await self._embedder.embed([query])
                query_vector = vectors[0] if vectors else []
            except Exception as exc:
                logger.warning("embedding_failed", error=str(exc))

        # Run dense and sparse retrieval in parallel
        dense_task = asyncio.create_task(
            self._dense_retrieve(query_vector, self.top_k_dense, principal_acl)
            if query_vector
            else asyncio.sleep(0, result=[])
        )
        sparse_task = asyncio.create_task(
            self._sparse_retrieve(query, self.top_k_sparse, principal_acl)
        )

        dense_results, sparse_results = await asyncio.gather(dense_task, sparse_task)

        logger.debug(
            "hybrid_retrieval_raw",
            dense_count=len(dense_results),
            sparse_count=len(sparse_results),
            query_preview=query[:80],
        )

        # Fuse with RRF
        fused = rrf_fuse(
            [r for r in [dense_results, sparse_results] if r],
            k=self.rrf_k,
            top_n=top_k,
        )

        logger.info(
            "hybrid_retrieval_done",
            fused_count=len(fused),
            max_score=fused[0].score if fused else 0.0,
        )

        return fused
