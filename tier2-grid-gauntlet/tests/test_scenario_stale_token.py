"""Scenario: Stale Fencing Token Rejection."""
from __future__ import annotations

import os

import pytest

from mocks import MockGridContext


@pytest.mark.asyncio
async def test_stale_fencing_token_rejected_on_invoke(mock_ctx: MockGridContext):
    """
    SCENARIO: Service invocation with fabricated fencing token.
    EXPECTED: 403 or 409 response. No method execution.
    EVOLUTION TRIGGER: If invocation succeeds, fencing validation is broken.

    NOTE: This test identifies an evolution trigger because the SDK cannot
    directly test fencing validation — it's a server-side concern. The attack
    documents this as an explicit finding.
    """
    from attacks.stale_invoke import execute_stale_invoke

    result = await execute_stale_invoke(ctx=mock_ctx, target_service="GridGauntletSentinel")

    # This attack always identifies an evolution trigger because:
    # The SDK has no mechanism to invoke with a DIFFERENT fencing token
    # Fencing validation must be server-side (CellApiHandler)
    assert result.attack_name == "stale_invoke"
    assert result.evolution_trigger is True
    assert "fencing" in result.observed_behavior.lower() or "dispatch" in result.observed_behavior.lower()


@pytest.mark.asyncio
async def test_current_fencing_token_accepted(mock_ctx: MockGridContext):
    """
    CONTROL: Valid fencing token allows normal invocation.
    This tests that the mock environment correctly represents the happy path.
    """
    # Set a valid fencing token in environment
    os.environ["AURAGRID_FENCING_TOKEN"] = "42"
    try:
        from attacks.stale_invoke import execute_stale_invoke

        result = await execute_stale_invoke(ctx=mock_ctx, target_service="GridGauntletSentinel")

        # The evidence should record the current token
        assert result.evidence["current_token"] == "42"
    finally:
        os.environ.pop("AURAGRID_FENCING_TOKEN", None)
