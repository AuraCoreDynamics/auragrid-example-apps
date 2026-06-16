"""Integration tests verifying Sentinel's invariant checker against attack patterns."""
from __future__ import annotations

import pytest

from mocks import MockGridContext


class TestInvariantUnderAttack:
    """Verify that the InvariantChecker correctly detects violations caused by attacks."""

    def test_fencing_token_after_lease_race(self, sentinel_checker):
        """
        If a lease race succeeds (it shouldn't), the fencing token would jump backwards.
        Verify the checker catches this.
        """
        sentinel_checker.check_fencing_token(100)
        sentinel_checker.check_fencing_token(101)
        # Simulated corruption: token goes backwards
        result = sentinel_checker.check_fencing_token(50)
        assert result is False
        assert sentinel_checker.violations[0].invariant == "fencing_token_monotonic"

    def test_event_ordering_under_flood(self, sentinel_checker):
        """
        Event flood should not cause sequence number regression.
        If WAL reorders under load, checker catches it.
        """
        # Normal sequence
        for i in range(1, 11):
            sentinel_checker.check_event_ordering("system.telemetry", i)
        assert sentinel_checker.is_healthy is True

        # Simulated reorder: seq goes backwards
        result = sentinel_checker.check_event_ordering("system.telemetry", 5)
        assert result is False
        assert not sentinel_checker.is_healthy

    def test_tattle_evidence_accumulation(self, sentinel_checker):
        """Multiple tattles are all recorded as evidence."""
        for i in range(5):
            sentinel_checker.record_tattle_against_us({
                "masId": "grid-gauntlet-sentinel",
                "reporter": "provocateur",
                "sequence": i,
            })
        assert len(sentinel_checker.tattle_evidence) == 5

    def test_lease_disappearance_detected(self, sentinel_checker):
        """If lease is revoked (None), checker catches it immediately."""
        result = sentinel_checker.check_lease_present(None, "grid-gauntlet-sentinel")
        assert result is False
        assert sentinel_checker.violations[0].invariant == "lease_present"
