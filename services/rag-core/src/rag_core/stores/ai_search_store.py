"""Azure AI Search vector store using azure-search-documents."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import structlog

from rag_core.chunking.base import Chunk
from rag_core.stores.vector_base import BaseVectorStore, SearchResult

logger = structlog.get_logger(__name__)

_INDEX_NAME = "zero-trust-chunks"


def _build_index_definition(embedding_dim: int) -> dict:
    """Return the dict representation of the Azure AI Search index schema."""
    return {
        "name": _INDEX_NAME,
        "fields": [
            {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
            {"name": "chunk_id", "type": "Edm.String", "filterable": True},
            {"name": "content", "type": "Edm.String", "searchable": True},
            {
                "name": "metadata",
                "type": "Edm.ComplexType",
                "fields": [
                    {"name": "source_file", "type": "Edm.String", "filterable": True},
                    {"name": "doc_type", "type": "Edm.String", "filterable": True},
                    {
                        "name": "allowed_principals",
                        "type": "Collection(Edm.String)",
                        "filterable": True,
                    },
                    {"name": "classification", "type": "Edm.String", "filterable": True},
                    {"name": "raw_metadata", "type": "Edm.String"},
                ],
            },
            {
                "name": "embedding",
                "type": f"Collection(Edm.Single)",
                "searchable": True,
                "vectorSearchDimensions": embedding_dim,
                "vectorSearchProfileName": "default-profile",
            },
        ],
        "vectorSearch": {
            "profiles": [
                {
                    "name": "default-profile",
                    "algorithmConfigurationName": "default-algo",
                }
            ],
            "algorithms": [
                {
                    "name": "default-algo",
                    "kind": "hnsw",
                    "hnswParameters": {
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500,
                        "metric": "cosine",
                    },
                }
            ],
        },
    }


class AISearchStore(BaseVectorStore):
    """Vector store backed by Azure AI Search.

    Args:
        endpoint: Azure AI Search service endpoint URL.
        api_key: Admin API key for the service.
        embedding_dim: Dimensionality of stored embedding vectors.
        api_version: Azure AI Search REST API version.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        embedding_dim: int = 1024,
        api_version: str = "2024-03-01-preview",
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._dim = embedding_dim
        self._api_version = api_version
        self._client = None
        self._index_client = None

    def _get_clients(self):
        if self._client is None:
            from azure.core.credentials import AzureKeyCredential
            from azure.search.documents import SearchClient
            from azure.search.documents.indexes import SearchIndexClient

            credential = AzureKeyCredential(self._api_key)
            self._index_client = SearchIndexClient(
                endpoint=self._endpoint,
                credential=credential,
            )
            self._client = SearchClient(
                endpoint=self._endpoint,
                index_name=_INDEX_NAME,
                credential=credential,
            )
        return self._client, self._index_client

    def _run_init(self) -> None:
        from azure.core.exceptions import ResourceNotFoundError
        from azure.search.documents.indexes.models import SearchIndex

        _, index_client = self._get_clients()
        try:
            index_client.get_index(_INDEX_NAME)
            logger.info("ai_search_index_exists", index=_INDEX_NAME)
        except ResourceNotFoundError:
            logger.info("ai_search_creating_index", index=_INDEX_NAME)
            schema = _build_index_definition(self._dim)
            index_client.create_index(schema)
            logger.info("ai_search_index_created", index=_INDEX_NAME)

    async def init(self) -> None:
        """Create the Azure AI Search index if it does not exist."""
        await asyncio.to_thread(self._run_init)

    def _run_upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        client, _ = self._get_clients()
        documents: list[dict[str, Any]] = []
        for chunk, vec in zip(chunks, embeddings):
            meta = chunk.metadata
            doc = {
                "id": chunk.chunk_id or str(uuid.uuid4()),
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "metadata": {
                    "source_file": str(meta.get("source_file", "")),
                    "doc_type": str(meta.get("doc_type", "")),
                    "allowed_principals": meta.get("allowed_principals", []),
                    "classification": str(meta.get("classification", "")),
                    "raw_metadata": json.dumps(meta),
                },
                "embedding": vec,
            }
            documents.append(doc)

        batch_size = 1000
        for i in range(0, len(documents), batch_size):
            client.merge_or_upload_documents(documents[i : i + batch_size])

    async def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Upsert chunks with their embeddings into Azure AI Search.

        Args:
            chunks: Chunk objects to store.
            embeddings: Corresponding embedding vectors.
        """
        await asyncio.to_thread(self._run_upsert, chunks, embeddings)
        logger.debug("ai_search_upsert", count=len(chunks))

    def _run_search(
        self,
        query_vector: list[float],
        top_k: int,
        filter: dict | None,
    ) -> list[SearchResult]:
        client, _ = self._get_clients()
        from azure.search.documents.models import VectorizedQuery

        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_k,
            fields="embedding",
        )

        filter_str: str | None = None
        if filter:
            parts = [
                f"metadata/{k} eq '{v}'"
                for k, v in filter.items()
                if isinstance(v, str)
            ]
            filter_str = " and ".join(parts) if parts else None

        results = client.search(
            search_text=None,
            vector_queries=[vector_query],
            filter=filter_str,
            top=top_k,
            select=["id", "chunk_id", "content", "metadata"],
        )

        search_results: list[SearchResult] = []
        for r in results:
            meta_raw = r.get("metadata", {})
            raw_meta_str = meta_raw.get("raw_metadata", "{}") if isinstance(meta_raw, dict) else "{}"
            try:
                full_meta = json.loads(raw_meta_str)
            except (json.JSONDecodeError, TypeError):
                full_meta = {}
            search_results.append(
                SearchResult(
                    chunk_id=r.get("chunk_id", r.get("id", "")),
                    content=r.get("content", ""),
                    metadata=full_meta,
                    score=r.get("@search.score", 0.0),
                )
            )
        return search_results

    async def search(
        self,
        query_vector: list[float],
        top_k: int,
        filter: dict | None = None,
    ) -> list[SearchResult]:
        """K-nearest-neighbour vector search.

        Args:
            query_vector: Query embedding.
            top_k: Number of results to return.
            filter: Optional metadata filter applied as an OData filter string.

        Returns:
            Ordered list of :class:`SearchResult` objects.
        """
        return await asyncio.to_thread(self._run_search, query_vector, top_k, filter)
