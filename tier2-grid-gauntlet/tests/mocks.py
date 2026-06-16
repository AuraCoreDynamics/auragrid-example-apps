"""Mock infrastructure for Grid Gauntlet tests."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add sentinel and provocateur to path
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root / "sentinel"))
sys.path.insert(0, str(_root / "provocateur"))


@dataclass
class MockAuraEvent:
    """Mock of AuraEventDto."""
    event_id: str = "mock-event-001"
    topic_id: str = ""
    sequence_number: int = 1
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_node_id: str = "test-node"
    event_type: str | None = None
    payload: str = ""

    @property
    def payload_bytes(self) -> bytes:
        import base64
        try:
            return base64.b64decode(self.payload)
        except Exception:
            return self.payload.encode() if isinstance(self.payload, str) else self.payload


class MockEventClient:
    """Mock event client that records publishes and returns configurable consumed events."""

    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []
        self._consume_responses: dict[str, list[MockAuraEvent]] = {}

    async def publish(self, topic_id: str, payload: bytes, event_type: str | None = None):
        self.published.append({
            "topic_id": topic_id,
            "payload": payload,
            "event_type": event_type,
        })
        return MockAuraEvent(topic_id=topic_id, event_type=event_type)

    async def consume(self, topic_id: str, after: int = 0, count: int = 100):
        return self._consume_responses.get(topic_id, [])

    def set_consume_response(self, topic_id: str, events: list[MockAuraEvent]) -> None:
        self._consume_responses[topic_id] = events


class MockIpcClient:
    """Mock IPC client that records tattle reports."""

    def __init__(self) -> None:
        self.tattles: list[dict[str, Any]] = []

    def report_tattle(self, mas_id: str, detail: str = "") -> None:
        self.tattles.append({"mas_id": mas_id, "detail": detail})


class MockGridContext:
    """Lightweight mock of AsyncGridContext for testing."""

    def __init__(self) -> None:
        self.events = MockEventClient()
        self.ipc = MockIpcClient()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass
