"""Scenario: Event Flood Resilience."""
from __future__ import annotations

import pytest

from mocks import MockAuraEvent, MockGridContext


@pytest.mark.asyncio
async def test_event_flood_grid_remains_responsive(mock_ctx: MockGridContext):
    """
    SCENARIO: 1000 telemetry events published in rapid succession.
    EXPECTED: Grid health endpoint still responds. Event consumption still works.
    """
    # Setup: Post-flood consumption works
    mock_ctx.events.set_consume_response(
        "grid-gauntlet.provocateur.attacks",
        [MockAuraEvent(topic_id="grid-gauntlet.provocateur.attacks", sequence_number=1)],
    )

    from attacks.event_flood import execute_event_flood

    # Use smaller count for test speed
    result = await execute_event_flood(ctx=mock_ctx, event_count=100)

    # Defense held: we can still consume events after flood
    assert result.defense_held is True
    assert result.attack_name == "event_flood"
    # All events were published (mock accepts everything)
    assert result.evidence["published"] == 100


@pytest.mark.asyncio
async def test_event_flood_does_not_starve_sentinel_consumption(mock_ctx: MockGridContext):
    """
    SCENARIO: During flood, Sentinel's event consumption continues functioning.
    EXPECTED: Sentinel can still read system.consensus events (separate topic).
    """
    # Setup: Sentinel lifecycle topic has events (sentinel still alive)
    mock_ctx.events.set_consume_response(
        "grid-gauntlet.sentinel.lifecycle",
        [MockAuraEvent(topic_id="grid-gauntlet.sentinel.lifecycle", event_type="heartbeat", sequence_number=10)],
    )
    mock_ctx.events.set_consume_response(
        "grid-gauntlet.provocateur.attacks",
        [MockAuraEvent(topic_id="grid-gauntlet.provocateur.attacks", sequence_number=1)],
    )

    from attacks.event_flood import execute_event_flood

    result = await execute_event_flood(ctx=mock_ctx, event_count=50)

    assert result.defense_held is True
    # Verify sentinel topic is still readable
    sentinel_events = await mock_ctx.events.consume("grid-gauntlet.sentinel.lifecycle")
    assert len(sentinel_events) > 0


@pytest.mark.asyncio
async def test_event_flood_records_publish_count(mock_ctx: MockGridContext):
    """Verify the flood accurately tracks how many events were published."""
    mock_ctx.events.set_consume_response("grid-gauntlet.provocateur.attacks", [
        MockAuraEvent(sequence_number=1)
    ])

    from attacks.event_flood import execute_event_flood

    result = await execute_event_flood(ctx=mock_ctx, event_count=25)

    assert result.evidence["published"] == 25
    assert result.evidence["errors"] == 0
    # All events plus the announce = 26 total publishes
    assert len(mock_ctx.events.published) == 26  # 25 flood + 1 announce
