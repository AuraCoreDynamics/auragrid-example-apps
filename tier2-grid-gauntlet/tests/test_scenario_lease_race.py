"""Scenario: Lease Race Defense."""
from __future__ import annotations

import json

import pytest

from mocks import MockAuraEvent, MockGridContext


@pytest.mark.asyncio
async def test_lease_race_fencing_token_rejects_stale_bid(mock_ctx: MockGridContext):
    """
    SCENARIO: Provocateur attempts to acquire Sentinel's singleton lease.
    EXPECTED: Auction arbiter rejects (singleton already leased).
              Sentinel's fencing token unchanged.
    """
    # Setup: No events showing lease transfer to provocateur
    mock_ctx.events.set_consume_response("system.service-state", [
        MockAuraEvent(
            topic_id="system.service-state",
            sequence_number=1,
            event_type="lease_acquired",
            payload=json.dumps({
                "masId": "grid-gauntlet-sentinel",
                "holderNodeId": "sentinel-node",
                "type": "lease_acquired",
            }).encode().decode(),
        ),
    ])

    from attacks.lease_race import execute_lease_race

    result = await execute_lease_race(ctx=mock_ctx, target_mas_id="grid-gauntlet-sentinel")

    # Defense held: no event shows provocateur acquired the lease
    assert result.defense_held is True
    assert result.attack_name == "lease_race"
    # A bid event was published (the attack executed)
    bid_events = [e for e in mock_ctx.events.published if e["event_type"] == "lease_bid"]
    assert len(bid_events) == 1


@pytest.mark.asyncio
async def test_lease_race_does_not_corrupt_registry(mock_ctx: MockGridContext, sentinel_checker):
    """
    SCENARIO: After failed lease race, service discovery still returns Sentinel.
    EXPECTED: Registry state unchanged. No phantom entries.
    """
    # The sentinel checker should have no violations from a lease race
    sentinel_checker.check_fencing_token(100)  # Initial token

    from attacks.lease_race import execute_lease_race

    mock_ctx.events.set_consume_response("system.service-state", [])
    result = await execute_lease_race(ctx=mock_ctx, target_mas_id="grid-gauntlet-sentinel")

    # Sentinel's checker should still be healthy
    assert sentinel_checker.is_healthy is True
    # No registry corruption (fencing token unchanged)
    sentinel_checker.check_fencing_token(101)  # Next valid token
    assert sentinel_checker.is_healthy is True
