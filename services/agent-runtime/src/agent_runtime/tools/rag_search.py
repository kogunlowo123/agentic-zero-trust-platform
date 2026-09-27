import os

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from agent_runtime.tools.base import BaseTool

_RAG_CORE_URL = os.environ.get("RAG_CORE_URL", "http://rag-core:8000")


class RAGSearchTool(BaseTool):
    """Search the zero-trust policy corpus via the rag-core service."""

    @property
    def name(self) -> str:
        return "rag_search"

    @property
    def description(self) -> str:
        return (
            "Search the zero-trust policy corpus for documents relevant to a query. "
            "Returns ranked documents with content, metadata, and relevance scores."
        )

    @property
    def schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of documents to return.",
                    "default": 5,
                },
                "principal": {
                    "type": "string",
                    "description": "Optional principal ID for access-scoped retrieval.",
                },
            },
            "required": ["query"],
        }

    async def call(
        self,
        query: str,
        top_k: int = 5,
        principal: str | None = None,
    ) -> dict:
        """Execute a semantic search against the rag-core service.

        Args:
            query: The search query string.
            top_k: Maximum number of documents to return.
            principal: Optional principal ID passed as a request header for
                       access-scoped retrieval.

        Returns:
            A dict with a 'results' key containing a list of SearchResult dicts,
            each having 'content', 'metadata', and 'score' fields.

        Raises:
            RuntimeError: When the rag-core service is unreachable or returns an error.
        """
        results = await rag_search_tool(query=query, top_k=top_k, principal=principal)
        return {"results": results}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
async def rag_search_tool(
    query: str,
    top_k: int = 5,
    principal: str | None = None,
) -> list[dict]:
    """Search the zero-trust policy corpus.

    Args:
        query: The search query string.
        top_k: Maximum number of results to return.
        principal: Optional principal ID used to scope retrieval results.

    Returns:
        A list of SearchResult dicts, each containing:
            - content (str): Document text.
            - metadata (dict): Document metadata (id, title, source, etc.).
            - score (float): Relevance score between 0.0 and 1.0.

    Raises:
        RuntimeError: On HTTP error or unreachable service.
    """
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if principal:
        headers["X-Principal-ID"] = principal

    payload: dict = {"query": query, "top_k": top_k}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{_RAG_CORE_URL}/search",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"rag-core search failed with status {exc.response.status_code}: "
                f"{exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Failed to reach rag-core service at {_RAG_CORE_URL}: {exc}"
            ) from exc

        body = response.json()

    # Normalise the response: expect {results: [{content, metadata, score}]}
    raw_results = body.get("results", [])
    normalised: list[dict] = []
    for item in raw_results:
        normalised.append(
            {
                "content": item.get("content", ""),
                "metadata": item.get("metadata", {}),
                "score": float(item.get("score", 0.0)),
            }
        )
    return normalised
