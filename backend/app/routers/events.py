"""Server-Sent Events endpoint for live dashboard invalidation."""

import asyncio
import json
import queue

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.event_hub import event_hub

router = APIRouter(prefix="/api/events", tags=["Live Events"])


@router.get("/stream")
async def stream_events(request: Request) -> StreamingResponse:
    """Stream state-change notifications; clients reload canonical REST data."""
    subscriber = event_hub.subscribe()

    async def generate():
        try:
            yield "retry: 5000\n: connected\n\n"
            while not await request.is_disconnected():
                try:
                    event = await asyncio.to_thread(subscriber.get, True, 15)
                except queue.Empty:
                    yield ": keep-alive\n\n"
                    continue
                payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                yield f"id: {event['id']}\ndata: {payload}\n\n"
        finally:
            event_hub.unsubscribe(subscriber)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
