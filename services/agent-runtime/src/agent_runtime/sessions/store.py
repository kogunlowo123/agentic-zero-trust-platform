import json
from datetime import datetime, timezone

import redis.asyncio as aioredis


class SessionStore:
    """Redis-backed session state store.

    Sessions are serialised as JSON under the key ``session:{session_id}``.
    The TTL is fixed at 3600 seconds (one hour) and is reset on every write.

    Args:
        redis_client: An async Redis client instance.
    """

    _TTL = 3600

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def create(self, session_id: str, principal: str, agent_id: str) -> dict:
        """Create a new session record and persist it.

        Raises:
            ValueError: If a session with the same ID already exists.

        Returns:
            The new session dict.
        """
        existing = await self._redis.exists(self._key(session_id))
        if existing:
            raise ValueError(f"Session '{session_id}' already exists")

        now = datetime.now(timezone.utc).isoformat()
        session: dict = {
            "session_id": session_id,
            "principal": principal,
            "agent_id": agent_id,
            "created_at": now,
            "updated_at": now,
            "status": "active",
            "tool_call_count": 0,
            "budget_used_usd": 0.0,
        }
        await self._redis.set(self._key(session_id), json.dumps(session), ex=self._TTL)
        return session

    async def get(self, session_id: str) -> dict | None:
        """Retrieve an existing session by ID.

        Returns:
            The session dict, or None if it does not exist.
        """
        raw = await self._redis.get(self._key(session_id))
        if raw is None:
            return None
        return json.loads(raw)

    async def update(self, session_id: str, updates: dict) -> None:
        """Merge *updates* into an existing session record.

        Raises:
            KeyError: If the session does not exist.
        """
        session = await self.get(session_id)
        if session is None:
            raise KeyError(f"Session '{session_id}' not found")
        session.update(updates)
        session["updated_at"] = datetime.now(timezone.utc).isoformat()
        await self._redis.set(self._key(session_id), json.dumps(session), ex=self._TTL)

    async def expire(self, session_id: str) -> None:
        """Mark a session as expired and remove it from Redis."""
        session = await self.get(session_id)
        if session is None:
            return
        session["status"] = "expired"
        session["expired_at"] = datetime.now(timezone.utc).isoformat()
        # Keep a short-lived tombstone so callers can detect the expiry
        await self._redis.set(self._key(session_id), json.dumps(session), ex=60)
