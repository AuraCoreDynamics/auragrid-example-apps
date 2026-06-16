from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

@dataclass
class InvariantViolation:
    """Record of a detected grid invariant violation."""
    invariant: str
    expected: str
    observed: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    evidence: dict[str, Any] = field(default_factory=dict)

class InvariantChecker:
    """Tracks and validates grid infrastructure invariants."""
    
    def __init__(self) -> None:
        self._violations: list[InvariantViolation] = []
        self._last_fencing_token: int | None = None
        self._topic_sequences: dict[str, int] = {}
        self._tattle_evidence: list[dict[str, Any]] = []
    
    def check_fencing_token(self, new_token: int) -> bool:
        """Invariant: fencing tokens are strictly monotonically increasing."""
        if self._last_fencing_token is not None and new_token <= self._last_fencing_token:
            self._violations.append(InvariantViolation(
                invariant="fencing_token_monotonic",
                expected=f"token > {self._last_fencing_token}",
                observed=f"token = {new_token}",
                evidence={"previous": self._last_fencing_token, "current": new_token},
            ))
            return False
        self._last_fencing_token = new_token
        return True
    
    def check_event_ordering(self, topic: str, seq: int) -> bool:
        """Invariant: event sequence numbers are monotonically increasing per topic."""
        last = self._topic_sequences.get(topic)
        if last is not None and seq <= last:
            self._violations.append(InvariantViolation(
                invariant="event_sequence_monotonic",
                expected=f"seq > {last} on topic '{topic}'",
                observed=f"seq = {seq}",
                evidence={"topic": topic, "previous_seq": last, "current_seq": seq},
            ))
            return False
        self._topic_sequences[topic] = seq
        return True
    
    def check_lease_present(self, lease_data: dict[str, Any] | None, mas_id: str) -> bool:
        """Invariant: our lease should always be present while we are running."""
        if lease_data is None:
            self._violations.append(InvariantViolation(
                invariant="lease_present",
                expected=f"lease exists for mas_id='{mas_id}'",
                observed="lease is None",
                evidence={"mas_id": mas_id},
            ))
            return False
        return True
    
    def record_tattle_against_us(self, tattle_event: dict[str, Any]) -> None:
        """Evidence collection: record when someone tattles on us."""
        self._tattle_evidence.append({
            **tattle_event,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
    
    @property
    def violations(self) -> list[InvariantViolation]:
        return list(self._violations)
    
    @property
    def tattle_evidence(self) -> list[dict[str, Any]]:
        return list(self._tattle_evidence)
    
    @property
    def is_healthy(self) -> bool:
        return len(self._violations) == 0
    
    @property
    def stats(self) -> dict[str, Any]:
        return {
            "violations_count": len(self._violations),
            "tattle_count": len(self._tattle_evidence),
            "last_fencing_token": self._last_fencing_token,
            "topics_tracked": list(self._topic_sequences.keys()),
            "is_healthy": self.is_healthy,
        }
