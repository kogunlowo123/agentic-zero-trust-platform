import json
import math

import redis.asyncio as aioredis


class EpisodicMemory:
    """Redis-backed episodic memory store for agent sessions.

    Each entry is stored under the key ``episodic:{session_id}:{key}``
    and serialised as JSON.  Vector-similarity search is approximated via
    a cosine-similarity scan over all keys in the session namespace.

    Args:
        redis_client: An async Redis client instance.
        ttl: Time-to-live in seconds for each stored entry.
    """

    def __init__(self, redis_client: aioredis.Redis, ttl: int = 86400) -> None:
        self._redis = redis_client
        self._ttl = ttl

    def _make_key(self, session_id: str, key: str) -> str:
        return f"episodic:{session_id}:{key}"

    async def store(self, session_id: str, key: str, value: dict) -> None:
        """Serialise *value* and store it under the given session and key.

        Args:
            session_id: Unique session identifier.
            key: Arbitrary string key within the session namespace.
            value: Dict payload to store; must be JSON-serialisable.
        """
        redis_key = self._make_key(session_id, key)
        payload = json.dumps(value)
        await self._redis.set(redis_key, payload, ex=self._ttl)

    async def retrieve(self, session_id: str, key: str) -> dict | None:
        """Retrieve a previously stored value.

        Args:
            session_id: Unique session identifier.
            key: The key used when storing the value.

        Returns:
            The deserialized dict, or None if the key does not exist.
        """
        redis_key = self._make_key(session_id, key)
        raw = await self._redis.get(redis_key)
        if raw is None:
            return None
        return json.loads(raw)

    async def search_similar(
        self,
        session_id: str,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        """Return the *top_k* entries most similar to *query_embedding*.

        This implementation does a full scan of the session namespace and
        computes cosine similarity in Python.  Entries without an
        ``embedding`` field are skipped.

        Args:
            session_id: Unique session identifier.
            query_embedding: Dense float vector of the query.
            top_k: Maximum number of results to return.

        Returns:
            List of value dicts sorted by descending similarity, capped at
            *top_k*.
        """
        pattern = f"episodic:{session_id}:*"
        results: list[tuple[float, dict]] = []

        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
            for raw_key in keys:
                raw = await self._redis.get(raw_key)
                if raw is None:
                    continue
                try:
                    entry: dict = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                embedding = entry.get("embedding")
                if not embedding or len(embedding) != len(query_embedding):
                    continue
                score = _cosine_similarity(query_embedding, embedding)
                results.append((score, entry))
            if cursor == 0:
                break

        results.sort(key=lambda t: t[0], reverse=True)
        return [entry for _, entry in results[:top_k]]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
