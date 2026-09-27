import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient


@dataclass
class CloudEvent:
    """CloudEvents 1.0 envelope for zero-trust platform events."""

    specversion: str
    type: str
    source: str
    id: str
    time: str
    datacontenttype: str
    data: dict

    def to_json(self) -> str:
        payload = asdict(self)
        return json.dumps(payload)


class EventPublisher:
    """Publishes zero-trust platform CloudEvents to Azure Service Bus.

    Args:
        servicebus_client: An authenticated async Azure Service Bus client.
        queue_name: The Service Bus queue to publish events to.
                    Defaults to 'zero-trust-events'.
    """

    def __init__(
        self,
        servicebus_client: ServiceBusClient,
        queue_name: str = "zero-trust-events",
    ) -> None:
        self._client = servicebus_client
        self._queue_name = queue_name

    async def _publish(self, event: CloudEvent) -> None:
        """Serialize and send a CloudEvent to the Service Bus queue."""
        async with self._client.get_queue_sender(self._queue_name) as sender:
            message = ServiceBusMessage(
                event.to_json(),
                content_type="application/cloudevents+json",
                subject=event.type,
            )
            await sender.send_messages(message)

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    async def publish_policy_violation(
        self,
        principal: str,
        resource: str,
        action: str,
        decision: dict,
    ) -> None:
        """Publish a 'policy.violation' event when access is denied.

        Args:
            principal: The identity that was denied.
            resource: The resource that was requested.
            action: The action that was requested.
            decision: The full PolicyDecision dict from the OPA evaluation.
        """
        event = CloudEvent(
            specversion="1.0",
            type="policy.violation",
            source="urn:zerotrust:policy-enforcer",
            id=str(uuid.uuid4()),
            time=self._now_iso(),
            datacontenttype="application/json",
            data={
                "principal": principal,
                "resource": resource,
                "action": action,
                "decision": decision,
            },
        )
        await self._publish(event)

    async def publish_access_granted(
        self,
        request_id: str,
        principal: str,
        resource: str,
    ) -> None:
        """Publish an 'access.granted' event after JIT approval.

        Args:
            request_id: The JIT approval request ID.
            principal: The identity whose access was granted.
            resource: The resource that access was granted to.
        """
        event = CloudEvent(
            specversion="1.0",
            type="access.granted",
            source="urn:zerotrust:access-reviewer",
            id=str(uuid.uuid4()),
            time=self._now_iso(),
            datacontenttype="application/json",
            data={
                "request_id": request_id,
                "principal": principal,
                "resource": resource,
            },
        )
        await self._publish(event)

    async def publish_posture_degraded(
        self,
        principal: str,
        old_score: float,
        new_score: float,
    ) -> None:
        """Publish a 'posture.degraded' event when posture score drops.

        Args:
            principal: The identity whose posture degraded.
            old_score: Previous posture score (0-100).
            new_score: New posture score (0-100).
        """
        event = CloudEvent(
            specversion="1.0",
            type="posture.degraded",
            source="urn:zerotrust:posture-assessor",
            id=str(uuid.uuid4()),
            time=self._now_iso(),
            datacontenttype="application/json",
            data={
                "principal": principal,
                "old_score": old_score,
                "new_score": new_score,
                "delta": old_score - new_score,
            },
        )
        await self._publish(event)
