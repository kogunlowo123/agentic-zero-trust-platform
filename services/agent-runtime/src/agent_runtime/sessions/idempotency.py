import json

import redis.asyncio as aioredis


class IdempotencyStore:
    """Redis-backed idempotency key manager.

    Prevents duplicate request processing by tracking request keys with a
    TTL.  On the first call for a given key the key is registered and the
    caller should process the request.  On subsequent calls the cached
    response (if any) is returned instead.

    Keys are stored under ``idempotency:{key}``.

    Args:
        redis_client: An async Redis client instance.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    def _key(self, key: str) -> str:
        return f"idempotency:{key}"

    async def check_and_set(self, key: str, ttl: int = 86400) -> bool:
        """Atomically check whether *key* is new and register it if so.

        Uses SET NX (set-if-not-exists) for atomicity.

        Args:
            key: The idempotency key (e.g. a request ID or content hash).
            ttl: Expiry in seconds.  Defaults to 86 400 (24 h).

        Returns:
            True if the key is new (caller should process the request).
            False if the key already exists (duplicate; use cached response).
        """
        redis_key = self._key(key)
        # SET NX returns True when the key was newly created, None otherwise
        result = await self._redis.set(redis_key, "1", nx=True, ex=ttl)
        return result is not None

    async def get_response(self, key: str) -> dict | None:
        """Retrieve the cached response for a duplicate request key.

        A cached response is stored under ``idempotency:{key}:response``.

        Args:
            key: The idempotency key.

        Returns:
            The cached response dict, or None if no response has been stored.
        """
        response_key = self._key(key) + ":response"
        raw = await self._redis.get(response_key)
        if raw is None:
            return None
        return json.loads(raw)

    async def store_response(self, key: str, response: dict, ttl: int = 86400) -> None:
        """Store the response for an idempotency key.

        Should be called after successfully processing the request so that
        future duplicates can receive the cached result.

        Args:
            key: The idempotency key.
            response: The response dict to cache; must be JSON-serialisable.
            ttl: Expiry in seconds.  Defaults to 86 400 (24 h).
        """
        response_key = self._key(key) + ":response"
        await self._redis.set(response_key, json.dumps(response), ex=ttl)
