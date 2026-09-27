"""api/pubsub.py — Decoupled Asynchronous Event Bus for Multi-Worker WebSocket Broadcasts.

Enables alert and case state synchronization across multiple Uvicorn ASGI workers:
1. Connects to Redis Pub/Sub if REDIS_URL is configured and reachable.
2. Gracefully falls back to high-throughput in-memory async broadcast when running standalone/offline.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

log = logging.getLogger("event_bus")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
ALERT_CHANNEL = "cybershield:alerts"


class EventBus:
    """Multi-worker pub/sub event bus with hybrid Redis / in-memory async routing."""

    def __init__(self, redis_url: Optional[str] = None) -> None:
        self.redis_url = redis_url or REDIS_URL
        self._subscribers: Set[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = set()
        self._redis_client = None
        self._pubsub_task: Optional[asyncio.Task] = None
        self._is_redis_active = False

    async def start(self) -> None:
        """Initialize Redis connection or in-memory async message bus."""
        try:
            import redis.asyncio as aioredis
            self._redis_client = aioredis.from_url(self.redis_url, decode_responses=True)
            # Test connectivity with short timeout
            await asyncio.wait_for(self._redis_client.ping(), timeout=0.8)
            self._is_redis_active = True
            log.info(f"[EventBus] Connected to Redis cluster at {self.redis_url}")
            self._pubsub_task = asyncio.create_task(self._listen_redis_channel())
        except Exception as e:
            self._is_redis_active = False
            self._redis_client = None
            log.info(f"[EventBus] Running with in-memory async event broker (Redis standalone fallback: {e})")

    async def _listen_redis_channel(self) -> None:
        """Background task reading published messages from Redis channel."""
        try:
            pubsub = self._redis_client.pubsub()
            await pubsub.subscribe(ALERT_CHANNEL)
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await self._dispatch_local(data)
                    except Exception as err:
                        log.warning(f"[EventBus] Error deserializing Redis message: {err}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.warning(f"[EventBus] Redis listener encountered error: {e}")

    def subscribe(self, callback: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]) -> None:
        """Register a WebSocket broadcaster callback."""
        self._subscribers.add(callback)

    def unsubscribe(self, callback: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]) -> None:
        self._subscribers.discard(callback)

    async def _dispatch_local(self, event: Dict[str, Any]) -> None:
        """Dispatches event to all local WebSocket subscribers."""
        if not self._subscribers:
            return
        tasks = [asyncio.create_task(cb(event)) for cb in list(self._subscribers)]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def publish(self, event: Dict[str, Any]) -> None:
        """Publish an alert or intervention event across the cluster."""
        if self._is_redis_active and self._redis_client:
            try:
                msg_str = json.dumps(event, default=str)
                await self._redis_client.publish(ALERT_CHANNEL, msg_str)
                return
            except Exception as e:
                log.warning(f"[EventBus] Redis publish failed, falling back to local dispatch: {e}")

        await self._dispatch_local(event)

    async def stop(self) -> None:
        """Cleanly close connection and stop listener task."""
        if self._pubsub_task:
            self._pubsub_task.cancel()
        if self._redis_client:
            try:
                await self._redis_client.close()
            except Exception:
                pass


GLOBAL_EVENT_BUS = EventBus()
