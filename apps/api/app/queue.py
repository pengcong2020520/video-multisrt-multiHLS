from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol


class QueuePort(Protocol):
    def enqueue(self, queue_name: str, payload: dict[str, Any]) -> str:
        ...


@dataclass
class InMemoryQueue:
    jobs: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def enqueue(self, queue_name: str, payload: dict[str, Any]) -> str:
        self.jobs.append((queue_name, payload))
        return f"memjob_{len(self.jobs)}"


class RedisQueue:
    def __init__(self, redis_url: str) -> None:
        try:
            import redis
        except ImportError as exc:  # pragma: no cover - covered by dependency install
            raise RuntimeError("redis package is required for RedisQueue") from exc
        self.client = redis.Redis.from_url(redis_url)

    def enqueue(self, queue_name: str, payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        return str(self.client.rpush(queue_name, encoded))


def build_queue(redis_url: str | None) -> QueuePort:
    if redis_url:
        return RedisQueue(redis_url)
    return InMemoryQueue()
