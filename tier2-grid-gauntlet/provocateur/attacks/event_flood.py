"""Attack: Flood system.telemetry with high-volume events."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import structlog

from playbook import AttackResult, AttackScenario

logger = structlog.get_logger("provocateur.attacks.event_flood")

SCENARIO = AttackScenario(
    name="event_flood",
    description="Publish 1000 events to system.telemetry in rapid succession",
    target_infrastructure="WAL/Event Bus",
    expected_defense="Events accepted but grid remains responsive. No OOM or deadlock.",
    timeout_seconds=30.0,
)


async def execute_event_flood(ctx, event_count: int = 1000) -> AttackResult:
    """
    Flood system.telemetry with high-volume events.
    Expected: Grid accepts events without crashing. Health endpoint responds after.
    """
    started = datetime.now(timezone.utc)
    evidence: dict = {"target_count": event_count, "published": 0, "errors": 0}

    # Phase 1: Announce
    try:
        await ctx.events.publish(
            "grid-gauntlet.provocateur.attacks",
            json.dumps({"attack": "event_flood", "count": event_count}).encode(),
            event_type="attack_start",
        )
    except Exception:
        pass

    # Phase 2: Flood events
    for i in range(event_count):
        try:
            await ctx.events.publish(
                "system.telemetry",
                json.dumps({
                    "type": "flood_event",
                    "sequence": i,
                    "source": "provocateur",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }).encode(),
                event_type="flood",
            )
            evidence["published"] = i + 1
        except Exception:
            evidence["errors"] = evidence.get("errors", 0) + 1

        # Yield control every 100 events to avoid starving the event loop
        if i % 100 == 0:
            await asyncio.sleep(0)

    # Phase 3: Verify grid still responsive
    defense_held = True
    observed = "Grid remained responsive after event flood"

    try:
        # Can we still consume events?
        events = await ctx.events.consume("grid-gauntlet.provocateur.attacks", after=0, count=5)
        evidence["post_flood_consume_ok"] = True
    except Exception as exc:
        defense_held = False
        observed = f"Grid unresponsive after flood: {exc}"
        evidence["post_flood_consume_ok"] = False
        evidence["post_flood_error"] = str(exc)

    # Phase 4: Check if sentinel can still operate
    try:
        sentinel_events = await ctx.events.consume(
            "grid-gauntlet.sentinel.lifecycle", after=0, count=5
        )
        evidence["sentinel_still_active"] = len(sentinel_events) > 0
    except Exception:
        evidence["sentinel_still_active"] = False

    completed = datetime.now(timezone.utc)
    return AttackResult(
        attack_name="event_flood",
        target="WAL/Event Bus",
        started_at=started,
        completed_at=completed,
        defense_held=defense_held,
        expected_behavior=SCENARIO.expected_defense,
        observed_behavior=observed,
        evidence=evidence,
        evolution_trigger=not defense_held,
    )
