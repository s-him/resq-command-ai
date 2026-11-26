"""Small thread-safe in-process pub/sub hub for dashboard invalidation events."""

import json
import queue
import threading
from itertools import count
from typing import Any


class EventHub:
    """Fan out compact JSON-safe events to active subscribers."""

    def __init__(self, queue_size: int = 100) -> None:
        if queue_size < 1:
            raise ValueError("queue_size must be positive")
        self._queue_size = queue_size
        self._lock = threading.Lock()
        self._subscribers: set[queue.Queue] = set()
        self._ids = count(1)

    def subscribe(self) -> queue.Queue:
        """Create a bounded subscriber queue."""
        subscriber: queue.Queue = queue.Queue(maxsize=self._queue_size)
        with self._lock:
            self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: queue.Queue) -> None:
        """Remove a subscriber; repeated removal is harmless."""
        with self._lock:
            self._subscribers.discard(subscriber)

    def publish(self, event_type: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Publish without allowing a slow client to block application writes."""
        if not event_type or not isinstance(event_type, str):
            raise ValueError("event_type must be a non-empty string")
        safe_data = json.loads(json.dumps(data or {}, ensure_ascii=False, default=str))
        with self._lock:
            event = {"id": next(self._ids), "type": event_type, "data": safe_data}
            subscribers = tuple(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(event)
            except queue.Full:
                # Clients reload canonical REST data, so keep the newest signal.
                try:
                    subscriber.get_nowait()
                except queue.Empty:
                    pass
                try:
                    subscriber.put_nowait(event)
                except queue.Full:
                    pass
        return event


event_hub = EventHub()


def publish_event(event_type: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Publish a dashboard invalidation event through the shared hub."""
    return event_hub.publish(event_type, data)
