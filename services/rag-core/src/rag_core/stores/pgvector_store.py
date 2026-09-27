"""pgvector-backed vector store using psycopg2 connection pooling."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import psycopg2
import psycopg2.extras
import psycopg2.pool
import structlog

from rag_core.chunking.base import Chunk
from rag_core.stores.vector_base import BaseVectorStore, SearchResult

logger = structlog.get_logger(__name__)

_CREATE_EXTENSION = "CREATE EXTENSION IF NOT EXISTS vector;"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id    TEXT UNIQUE NOT NULL,
    content     TEXT NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{}',
    embedding   vector({dim}),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
"""

_UPSERT_SQL = """
INSERT INTO chunks (chunk_id, content, metadata, embedding)
VALUES (%s, %s, %s, %s)
ON CONFLICT (chunk_id) DO UPDATE
    SET content    = EXCLUDED.content,
        metadata   = EXCLUDED.metadata,
        embedding  = EXCLUDED.embedding,
        created_at = NOW();
"""

_SEARCH_SQL = """
SELECT chunk_id,
       content,
       metadata,
       1 - (embedding <=> %s::vector) AS score
FROM   chunks
{where}
ORDER  BY embedding <=> %s::vector
LIMIT  %s;
"""


def _vec_to_pg_literal(vec: list[float]) -> str:
    return "[" + ",".join(map(str, vec)) + "]"


class PGVectorStore(BaseVectorStore):
    """Vector store backed by PostgreSQL + pgvector.

    Uses a psycopg2 threaded connection pool (min_conn=5, max_conn=20).
    All blocking I/O is wrapped in :func:`asyncio.to_thread` so the event
    loop is never blocked.

    Args:
        database_url: PostgreSQL connection string.
        embedding_dim: Number of dimensions in the stored vectors.
    """

    def __init__(self, database_url: str, embedding_dim: int = 1024) -> None:
        self._database_url = database_url
        self._dim = embedding_dim
        self._pool: psycopg2.pool.ThreadedConnectionPool | None = None

    def _get_pool(self) -> psycopg2.pool.ThreadedConnectionPool:
        if self._pool is None:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=5,
                maxconn=20,
                dsn=self._database_url,
            )
        return self._pool

    def _run_init(self) -> None:
        pool = self._get_pool()
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(_CREATE_EXTENSION)
                cur.execute(_CREATE_TABLE.format(dim=self._dim))
                cur.execute(_CREATE_INDEX)
            conn.commit()
        finally:
            pool.putconn(conn)

    async def init(self) -> None:
        """Create the pgvector extension, table, and index if they do not exist."""
        await asyncio.to_thread(self._run_init)
        logger.info("pgvector_store_initialised", dim=self._dim)

    def _run_upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        pool = self._get_pool()
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                for chunk, vec in zip(chunks, embeddings):
                    cur.execute(
                        _UPSERT_SQL,
                        (
                            chunk.chunk_id or str(uuid.uuid4()),
                            chunk.content,
                            json.dumps(chunk.metadata),
                            _vec_to_pg_literal(vec),
                        ),
                    )
            conn.commit()
        finally:
            pool.putconn(conn)

    async def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Insert or update chunks with their embeddings.

        Args:
            chunks: Chunk objects to store.
            embeddings: Corresponding embedding vectors.
        """
        await asyncio.to_thread(self._run_upsert, chunks, embeddings)
        logger.debug("pgvector_upsert", count=len(chunks))

    def _run_search(
        self,
        query_vector: list[float],
        top_k: int,
        filter: dict | None,
    ) -> list[SearchResult]:
        pool = self._get_pool()
        conn = pool.getconn()
        try:
            vec_literal = _vec_to_pg_literal(query_vector)
            where_clause = ""
            params: list[Any] = [vec_literal]

            if filter:
                where_clause = "WHERE metadata @> %s"
                params.append(json.dumps(filter))

            params.extend([vec_literal, top_k])
            sql = _SEARCH_SQL.format(where=where_clause)

            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        finally:
            pool.putconn(conn)

        return [
            SearchResult(
                chunk_id=row[0],
                content=row[1],
                metadata=row[2] if isinstance(row[2], dict) else json.loads(row[2]),
                score=float(row[3]),
            )
            for row in rows
        ]

    async def search(
        self,
        query_vector: list[float],
        top_k: int,
        filter: dict | None = None,
    ) -> list[SearchResult]:
        """Cosine similarity search.

        Args:
            query_vector: Query embedding.
            top_k: Number of results to return.
            filter: Optional JSONB containment filter applied with ``@>``.

        Returns:
            Ordered list of :class:`SearchResult` objects (most similar first).
        """
        return await asyncio.to_thread(self._run_search, query_vector, top_k, filter)
