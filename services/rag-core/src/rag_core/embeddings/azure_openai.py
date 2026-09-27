"""Azure OpenAI text embedder with batching and exponential-backoff retry."""

from __future__ import annotations

import asyncio
from typing import Any

from openai import AsyncAzureOpenAI
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from rag_core.embeddings.base import BaseEmbedder

# Conservative token-budget estimate: ~4 characters per token.
# text-embedding-3-large has a 8191-token input limit; we target ~2048 tokens
# per batch request, which equals ~8192 characters per batch.
_CHARS_PER_TOKEN = 4
_MAX_TOKENS_PER_BATCH = 2048
_MAX_CHARS_PER_BATCH = _MAX_TOKENS_PER_BATCH * _CHARS_PER_TOKEN


class AzureOpenAIEmbedder(BaseEmbedder):
    """Embeds texts via the Azure OpenAI text-embedding-3-large model.

    Args:
        endpoint: Azure OpenAI resource endpoint URL.
        api_key: Azure OpenAI API key.
        deployment: The deployment name for the embedding model.
        api_version: Azure OpenAI API version to use.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment: str = "text-embedding-3-large",
        api_version: str = "2024-02-01",
    ) -> None:
        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )
        self._deployment = deployment

    @property
    def dim(self) -> int:
        """Dimensionality of text-embedding-3-large vectors."""
        return 3072

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed *texts* in batches with automatic retry on transient errors.

        Args:
            texts: Plain text strings to embed.

        Returns:
            List of float vectors aligned with the input list.
        """
        if not texts:
            return []

        batches = _make_batches(texts, _MAX_CHARS_PER_BATCH)
        all_embeddings: list[list[float]] = []

        for batch in batches:
            embeddings = await self._embed_batch_with_retry(batch)
            all_embeddings.extend(embeddings)

        return all_embeddings

    async def _embed_batch_with_retry(self, batch: list[str]) -> list[list[float]]:
        from openai import APIConnectionError, APITimeoutError, RateLimitError

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(
                (RateLimitError, APIConnectionError, APITimeoutError)
            ),
            wait=wait_exponential(multiplier=1, min=1, max=60),
            stop=stop_after_attempt(5),
            reraise=True,
        ):
            with attempt:
                response = await self._client.embeddings.create(
                    input=batch,
                    model=self._deployment,
                )
        return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


def _make_batches(texts: list[str], max_chars: int) -> list[list[str]]:
    """Split *texts* into batches where total characters stay below *max_chars*."""
    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_chars = 0

    for text in texts:
        text_len = len(text)
        if current_batch and current_chars + text_len > max_chars:
            batches.append(current_batch)
            current_batch = []
            current_chars = 0
        current_batch.append(text)
        current_chars += text_len

    if current_batch:
        batches.append(current_batch)

    return batches
