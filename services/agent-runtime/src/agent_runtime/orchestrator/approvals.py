import json
import os

import redis.asyncio as aioredis
from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient

_REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
_SERVICEBUS_CONN_STR = os.environ.get("AZURE_SERVICEBUS_CONNECTION_STRING", "")
_ACCESS_REQUESTS_QUEUE = "access_requests"
_APPROVAL_TTL = 3600  # seconds


class ApprovalWorkflow:
    """Just-in-time (JIT) access approval workflow.

    Approval state is stored in Redis with a TTL.  New requests are also
    published to the Azure Service Bus 'access_requests' queue so that
    approvers can act on them via an external portal or automation.

    The workflow is stateless across instances — any node that holds a
    Redis client and Service Bus connection can serve approval queries.

    Args:
        redis_client: An authenticated async Redis client.
        servicebus_client: An authenticated async Azure Service Bus client.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        servicebus_client: ServiceBusClient,
    ) -> None:
        self._redis = redis_client
        self._servicebus = servicebus_client

    def _redis_key(self, request_id: str) -> str:
        return f"approval:{request_id}"

    async def request_approval(
        self,
        request_id: str,
        principal: str,
        resource: str,
        justification: str,
    ) -> str:
        """Create a new JIT approval request.

        Persists the request in Redis with status 'pending' and publishes
        a message to the Azure Service Bus queue for downstream processing.

        Args:
            request_id: A unique identifier for this approval request.
            principal: The identity requesting access.
            resource: The resource for which access is requested.
            justification: Free-text justification provided by the principal.

        Returns:
            The string "pending".
        """
        record: dict = {
            "request_id": request_id,
            "principal": principal,
            "resource": resource,
            "justification": justification,
            "status": "pending",
        }
        await self._redis.set(
            self._redis_key(request_id),
            json.dumps(record),
            ex=_APPROVAL_TTL,
        )

        # Publish to Service Bus so approvers can act on the request
        async with self._servicebus.get_queue_sender(_ACCESS_REQUESTS_QUEUE) as sender:
            message = ServiceBusMessage(
                json.dumps(record),
                content_type="application/json",
                subject="jit.access.request",
                message_id=request_id,
            )
            await sender.send_messages(message)

        return "pending"

    async def check_status(self, request_id: str) -> str:
        """Return the current status of an approval request.

        Args:
            request_id: The request ID previously returned by
                        ``request_approval``.

        Returns:
            One of 'pending', 'approved', or 'denied'.
            Returns 'pending' if the request is not found (may have expired).
        """
        raw = await self._redis.get(self._redis_key(request_id))
        if raw is None:
            return "pending"
        record: dict = json.loads(raw)
        return record.get("status", "pending")

    async def set_status(self, request_id: str, status: str) -> None:
        """Update the status of an existing approval request.

        Intended for use by the approval portal or automation that reads
        from the Service Bus queue.

        Args:
            request_id: The request ID to update.
            status: New status — must be 'approved' or 'denied'.

        Raises:
            ValueError: If *status* is not one of the allowed values.
            KeyError: If the request is not found in Redis.
        """
        if status not in ("approved", "denied"):
            raise ValueError(f"Invalid status '{status}'; must be 'approved' or 'denied'")

        raw = await self._redis.get(self._redis_key(request_id))
        if raw is None:
            raise KeyError(f"Approval request '{request_id}' not found")

        record: dict = json.loads(raw)
        record["status"] = status
        await self._redis.set(
            self._redis_key(request_id),
            json.dumps(record),
            ex=_APPROVAL_TTL,
        )
