"""Attack: File false tattle reports against a healthy MAS."""
from __future__ import annotations

from datetime import datetime, timezone

import structlog

from playbook import AttackResult, AttackScenario

logger = structlog.get_logger("provocateur.attacks.false_tattle")

SCENARIO = AttackScenario(
    name="false_tattle",
    description="File multiple tattle reports against a healthy Sentinel MAS",
    target_infrastructure="TattleInvestigator",
    expected_defense="Grid investigates, finds target healthy, enters cooldown. Lease NOT revoked.",
    timeout_seconds=30.0,
)


async def execute_false_tattle(ctx, target_mas_id: str = "grid-gauntlet-sentinel", tattle_count: int = 5) -> AttackResult:
    """
    File N tattle reports against a healthy MAS.
    Expected: Grid investigates and dismisses. Lease not revoked.
    """
    started = datetime.now(timezone.utc)
    evidence: dict = {"tattles_filed": 0, "target": target_mas_id}

    # Phase 1: Announce attack intent
    try:
        await ctx.events.publish(
            "grid-gauntlet.provocateur.attacks",
            f'{{"attack":"false_tattle","target":"{target_mas_id}","count":{tattle_count}}}'.encode(),
            event_type="attack_start",
        )
    except Exception as exc:
        logger.warning("announce_failed", error=str(exc))

    # Phase 2: File tattle reports
    for i in range(tattle_count):
        try:
            await ctx.ipc.report_tattle(
                target_mas_id,
                detail=f"Provocateur false tattle #{i+1}: simulated unreachable",
            )
            evidence["tattles_filed"] = i + 1
            logger.info("tattle_filed", count=i + 1, target=target_mas_id)
        except Exception as exc:
            logger.warning("tattle_failed", count=i + 1, error=str(exc))

    # Phase 3: Wait for investigation window
    import asyncio
    await asyncio.sleep(12.0)  # TattleInvestigationTimeout(10s) + buffer

    # Phase 4: Attempt to invoke target — should still respond
    defense_held = True
    observed = "Target still responsive after tattle investigation"
    try:
        # If we can read events from the sentinel's topic, it's still alive
        events = await ctx.events.consume("grid-gauntlet.sentinel.lifecycle", after=0, count=10)
        evidence["sentinel_events_found"] = len(events)
        if len(events) == 0:
            # No events might mean sentinel was revoked
            defense_held = False
            observed = "No sentinel lifecycle events found — possible revocation"
    except Exception as exc:
        # If we can't reach events at all, grid might be down
        defense_held = False
        observed = f"Event consumption failed: {exc}"
        evidence["error"] = str(exc)

    completed = datetime.now(timezone.utc)
    return AttackResult(
        attack_name="false_tattle",
        target="TattleInvestigator",
        started_at=started,
        completed_at=completed,
        defense_held=defense_held,
        expected_behavior=SCENARIO.expected_defense,
        observed_behavior=observed,
        evidence=evidence,
        evolution_trigger=not defense_held,
    )
