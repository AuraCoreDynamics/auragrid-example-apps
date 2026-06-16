"""Scenario: False Tattle Defense."""
from __future__ import annotations

import pytest

from mocks import MockAuraEvent, MockGridContext


@pytest.mark.asyncio
async def test_false_tattle_defense_holds(mock_ctx: MockGridContext):
    """
    SCENARIO: Provocateur files TattleThreshold+1 tattles against healthy Sentinel.
    EXPECTED: Grid investigates, finds Sentinel healthy, enters cooldown.
              Sentinel's lease is NOT revoked. Service remains callable.
    """
    # Setup: Sentinel has lifecycle events (proves it's alive)
    mock_ctx.events.set_consume_response(
        "grid-gauntlet.sentinel.lifecycle",
        [MockAuraEvent(topic_id="grid-gauntlet.sentinel.lifecycle", event_type="startup", sequence_number=1)],
    )

    from attacks.false_tattle import execute_false_tattle

    result = await execute_false_tattle(ctx=mock_ctx, target_mas_id="grid-gauntlet-sentinel", tattle_count=5)

    # Defense held: sentinel events still accessible
    assert result.defense_held is True
    assert result.evolution_trigger is False
    assert result.attack_name == "false_tattle"
    # Tattles were filed
    assert len(mock_ctx.ipc.tattles) == 5
    assert all(t["mas_id"] == "grid-gauntlet-sentinel" for t in mock_ctx.ipc.tattles)


@pytest.mark.asyncio
async def test_false_tattle_detects_revocation(mock_ctx: MockGridContext):
    """
    SCENARIO: If sentinel lifecycle events disappear, defense failed.
    EXPECTED: Attack detects lease revocation (evolution trigger).
    """
    # Setup: No sentinel events (simulates revoked/dead sentinel)
    mock_ctx.events.set_consume_response("grid-gauntlet.sentinel.lifecycle", [])

    from attacks.false_tattle import execute_false_tattle

    result = await execute_false_tattle(ctx=mock_ctx, target_mas_id="grid-gauntlet-sentinel", tattle_count=5)

    # Defense did NOT hold: no sentinel events found
    assert result.defense_held is False
    assert result.evolution_trigger is True


@pytest.mark.asyncio
async def test_false_tattle_cooldown_prevents_repeated_investigation(mock_ctx: MockGridContext):
    """
    SCENARIO: After cooldown from first investigation, more tattles are ignored.
    EXPECTED: No second investigation within TattleCooldownPeriod.
    """
    # Setup: Sentinel alive
    mock_ctx.events.set_consume_response(
        "grid-gauntlet.sentinel.lifecycle",
        [MockAuraEvent(topic_id="grid-gauntlet.sentinel.lifecycle", event_type="heartbeat", sequence_number=5)],
    )

    from attacks.false_tattle import execute_false_tattle

    # Execute attack twice
    result1 = await execute_false_tattle(ctx=mock_ctx, target_mas_id="grid-gauntlet-sentinel", tattle_count=3)
    result2 = await execute_false_tattle(ctx=mock_ctx, target_mas_id="grid-gauntlet-sentinel", tattle_count=3)

    # Both should see defense held (sentinel survives both rounds)
    assert result1.defense_held is True
    assert result2.defense_held is True
    # Total tattles filed = 6
    assert len(mock_ctx.ipc.tattles) == 6
