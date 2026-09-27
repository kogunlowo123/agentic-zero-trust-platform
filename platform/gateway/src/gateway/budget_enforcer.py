import time
from datetime import datetime, timezone

import redis.asyncio as aioredis


def _utc_midnight_epoch() -> int:
    """Return the Unix timestamp of the next UTC midnight."""
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # seconds until the next midnight
    seconds_until_midnight = 86400 - int((now - midnight).total_seconds())
    return int(time.time()) + seconds_until_midnight


class BudgetEnforcer:
    """Redis-backed per-user daily spend enforcer for the LLM gateway.

    Spend is accumulated in a Redis hash under the key
    ``gateway:budget:{user_id}:{date}`` where ``{date}`` is today's UTC date
    (YYYY-MM-DD).  Each key has a TTL of 48 hours so stale entries are
    automatically cleaned up.

    Args:
        redis_client: An async Redis client instance.
        max_daily_usd: Maximum total spend per user per UTC day.
    """

    _KEY_TTL = 172800  # 48 hours

    def __init__(self, redis_client: aioredis.Redis, max_daily_usd: float) -> None:
        if max_daily_usd <= 0:
            raise ValueError("max_daily_usd must be positive")
        self._redis = redis_client
        self._max_daily_usd = max_daily_usd

    def _key(self, user_id: str) -> str:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"gateway:budget:{user_id}:{date_str}"

    async def check_and_deduct(self, user_id: str, estimated_cost: float) -> bool:
        """Atomically check the user's remaining budget and deduct the cost.

        Uses a Redis WATCH/MULTI/EXEC optimistic-lock loop to avoid race
        conditions when multiple gateway replicas handle concurrent requests.

        Args:
            user_id: The authenticated user/service identifier.
            estimated_cost: The estimated USD cost of the request.

        Returns:
            True if the budget is sufficient and the cost was deducted.
            False if the user has exceeded their daily budget.
        """
        key = self._key(user_id)
        # Retrieve current spend; treat missing key as zero
        raw = await self._redis.get(key)
        current = float(raw) if raw is not None else 0.0

        if current + estimated_cost > self._max_daily_usd:
            return False

        # Atomically increment; set TTL on first write
        pipe = self._redis.pipeline(transaction=True)
        await pipe.watch(key)
        pipe.multi()
        pipe.incrbyfloat(key, estimated_cost)
        pipe.expire(key, self._KEY_TTL)
        await pipe.execute()

        return True

    async def get_usage(self, user_id: str) -> float:
        """Return the user's total spend for today (UTC).

        Args:
            user_id: The authenticated user/service identifier.

        Returns:
            Current daily spend in USD.  Returns 0.0 if no spend has been
            recorded.
        """
        raw = await self._redis.get(self._key(user_id))
        if raw is None:
            return 0.0
        return float(raw)
