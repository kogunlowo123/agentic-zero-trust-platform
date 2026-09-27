"""Corpus ingestion synchronisation entry-point."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from pathlib import Path

import psycopg2
import psycopg2.extras
import structlog

from rag_core.chunking.recursive import RecursiveChunker
from rag_core.config.settings import Settings
from rag_core.embeddings.local_bge import LocalBGEEmbedder
from rag_core.enrichment.acl_stamper import ACLStamper
from rag_core.enrichment.auto_tagger import AutoTagger
from rag_core.enrichment.metadata import MetadataEnricher
from rag_core.enrichment.pii_tagger import PIITagger
from rag_core.ingestion.loader_registry import registry
from rag_core.stores.pgvector_store import PGVectorStore

logger = structlog.get_logger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS ingested_files (
    id          SERIAL PRIMARY KEY,
    file_path   TEXT NOT NULL UNIQUE,
    file_hash   TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def _hash_file(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            sha.update(block)
    return sha.hexdigest()


def _get_connection(database_url: str):
    return psycopg2.connect(database_url)


def _ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(_CREATE_TABLE)
    conn.commit()


def _already_ingested(conn, file_path: str, file_hash: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT file_hash FROM ingested_files WHERE file_path = %s",
            (file_path,),
        )
        row = cur.fetchone()
    if row is None:
        return False
    return row[0] == file_hash


def _mark_ingested(conn, file_path: str, file_hash: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingested_files (file_path, file_hash)
            VALUES (%s, %s)
            ON CONFLICT (file_path) DO UPDATE
                SET file_hash = EXCLUDED.file_hash,
                    ingested_at = NOW()
            """,
            (file_path, file_hash),
        )
    conn.commit()


async def sync_corpus(source_dir: Path, settings: Settings) -> None:
    """Discover, load, chunk, enrich, embed, and store all documents in *source_dir*.

    Files whose content has not changed since the last run are skipped.

    Args:
        source_dir: Root directory to search for supported documents.
        settings: Application settings.
    """
    source_dir = Path(source_dir)
    database_url = settings.database_url.get_secret_value()

    conn = await asyncio.to_thread(_get_connection, database_url)
    await asyncio.to_thread(_ensure_schema, conn)

    supported_exts = set(registry.extensions)
    files = [
        p
        for p in source_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in supported_exts
    ]

    chunker = RecursiveChunker(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    enricher = MetadataEnricher()
    pii_tagger = PIITagger()
    acl_stamper = ACLStamper()
    auto_tagger = AutoTagger()
    embedder = LocalBGEEmbedder(model_name=settings.embedding_model)
    vector_store = PGVectorStore(
        database_url=database_url,
        embedding_dim=embedder.dim,
    )
    await vector_store.init()

    log = logger.bind(source_dir=str(source_dir), total_files=len(files))
    log.info("starting_corpus_sync")

    for file_path in files:
        file_hash = await asyncio.to_thread(_hash_file, file_path)
        already = await asyncio.to_thread(
            _already_ingested, conn, str(file_path), file_hash
        )
        if already:
            logger.debug("skipping_unchanged_file", path=str(file_path))
            continue

        logger.info("ingesting_file", path=str(file_path))
        try:
            loader = registry.get(file_path)
            documents = await asyncio.to_thread(loader.load, file_path)
        except Exception as exc:
            logger.error("load_error", path=str(file_path), error=str(exc))
            continue

        chunks = chunker.chunk(documents)
        if not chunks:
            logger.warning("no_chunks_produced", path=str(file_path))
            continue

        chunks = enricher.enrich(chunks)
        chunks = pii_tagger.tag(chunks)
        chunks = acl_stamper.stamp(chunks, acl=[])
        chunks = auto_tagger.tag(chunks)

        texts = [c.content for c in chunks]
        embeddings = await embedder.embed(texts)

        await vector_store.upsert(chunks, embeddings)
        await asyncio.to_thread(_mark_ingested, conn, str(file_path), file_hash)
        logger.info(
            "file_ingested",
            path=str(file_path),
            chunks=len(chunks),
        )

    conn.close()
    log.info("corpus_sync_complete")


def main() -> None:
    """Entry point for ``python -m rag_core.sync``."""
    import os

    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    source_dir_env = os.environ.get("CORPUS_DIR", "/data/corpus")
    asyncio.run(sync_corpus(Path(source_dir_env), settings))


if __name__ == "__main__":
    main()
