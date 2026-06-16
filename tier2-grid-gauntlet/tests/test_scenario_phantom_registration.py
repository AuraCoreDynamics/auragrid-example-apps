"""Scenario: Phantom Registration Cleanup."""
from __future__ import annotations

import json

import pytest

from mocks import MockAuraEvent, MockGridContext


@pytest.mark.asyncio
async def test_phantom_endpoint_dispatch_fails_gracefully(mock_ctx: MockGridContext):
    """
    SCENARIO: Fake endpoint registered at unreachable port.
    EXPECTED: Dispatch attempt returns error (timeout/connection refused), not hang.
    """
    # Setup: No tattle events in telemetry (no auto-tattle mechanism)
    mock_ctx.events.set_consume_response("system.telemetry", [])

    from attacks.phantom_registration import execute_phantom_registration

    result = await execute_phantom_registration(ctx=mock_ctx)

    # Attack completes within timeout (not hanging)
    assert result.attack_name == "phantom_registration"
    assert result.completed_at is not None
    # Registration event was published
    reg_events = [e for e in mock_ctx.events.published if e["event_type"] == "endpoint_registered"]
    assert len(reg_events) == 1


@pytest.mark.asyncio
async def test_phantom_endpoint_triggers_tattle(mock_ctx: MockGridContext):
    """
    SCENARIO: After failed dispatch, tattle is auto-filed against phantom.
    EXPECTED: system.telemetry contains tattle event for the phantom MAS.
    EVOLUTION TRIGGER: If no auto-tattle, self-healing is incomplete.
    """
    # Setup: Telemetry topic has a tattle for our phantom
    mock_ctx.events.set_consume_response("system.telemetry", [
        MockAuraEvent(
            topic_id="system.telemetry",
            sequence_number=1,
            payload=json.dumps({
                "masId": "PhantomService",
                "type": "tattle",
                "detail": "dispatch failed",
            }).encode().decode(),
        ),
    ])

    from attacks.phantom_registration import execute_phantom_registration

    result = await execute_phantom_registration(ctx=mock_ctx)

    # Defense held: auto-tattle was found
    assert result.defense_held is True
    assert result.evolution_trigger is False


@pytest.mark.asyncio
async def test_phantom_no_auto_tattle_is_evolution_trigger(mock_ctx: MockGridContext):
    """
    SCENARIO: No auto-tattle for phantom registration.
    EXPECTED: Evolution trigger identified.
    """
    # Setup: No tattle events
    mock_ctx.events.set_consume_response("system.telemetry", [])

    from attacks.phantom_registration import execute_phantom_registration

    result = await execute_phantom_registration(ctx=mock_ctx)

    # No auto-tattle = evolution trigger
    assert result.defense_held is False
    assert result.evolution_trigger is True
    # Cleanup was attempted
    cleanup_events = [e for e in mock_ctx.events.published if e["event_type"] == "endpoint_unregistered"]
    assert len(cleanup_events) == 1
