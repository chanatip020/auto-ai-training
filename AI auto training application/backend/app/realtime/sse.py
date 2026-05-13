"""In-process event bus for Server-Sent Events.

v1: a per-key fan-out of asyncio.Queues. Anyone can `publish(key, event)`
and any subscriber gets a copy until they unsubscribe. Bounded queues drop
oldest events under backpressure so a slow client can't OOM the server.

Later phase: swap the body for Redis Pub/Sub when we scale beyond one host.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any


class EventBus:
    def __init__(self, queue_max: int = 200) -> None:
        self._subs: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._queue_max = queue_max

    # ---- subscribe / unsubscribe ----
    def subscribe(self, key: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._queue_max)
        self._subs[key].append(q)
        return q

    def unsubscribe(self, key: str, q: asyncio.Queue) -> None:
        if key in self._subs:
            try:
                self._subs[key].remove(q)
            except ValueError:
                pass
            if not self._subs[key]:
                del self._subs[key]

    # ---- publish ----
    def publish(self, key: str, event: dict[str, Any]) -> None:
        for q in self._subs.get(key, []):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest, push new — keeps the latest state visible.
                try:
                    q.get_nowait()
                except Exception:
                    pass
                try:
                    q.put_nowait(event)
                except Exception:
                    pass

    # Sync publishers (called from worker threads) should use this:
    def publish_threadsafe(self, key: str, event: dict[str, Any], loop=None) -> None:
        loop = loop or asyncio.get_event_loop()
        loop.call_soon_threadsafe(self.publish, key, event)


bus = EventBus()


# ---- SSE format helper ----
def format_event(event: dict[str, Any]) -> str:
    """Format a dict as a single SSE message frame.

    Uses a per-event ``event:`` line (if 'type' is set) so clients can use
    ``addEventListener(type, …)``.
    """
    out = []
    et = event.get("type")
    if et:
        out.append(f"event: {et}")
    out.append("data: " + json.dumps(event))
    out.append("")  # blank line terminates the frame
    return "\n".join(out) + "\n"


async def event_stream(
    key: str, *, idle_timeout: float = 25.0
) -> AsyncIterator[str]:
    """Async generator yielding pre-formatted SSE frames for one subscriber.

    Sends a `: keepalive` comment every idle_timeout seconds so proxies
    don't close the stream.
    """
    q = bus.subscribe(key)
    try:
        # Initial hello so clients know they're connected.
        yield format_event({"type": "ready", "subscription_id": str(uuid.uuid4())})
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=idle_timeout)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue
            yield format_event(event)
            if event.get("type") in ("done", "failed", "cancelled"):
                # Server-initiated end of stream.
                break
    finally:
        bus.unsubscribe(key, q)
