"""Attack: Attempt to acquire a lease already held by another MAS."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog

from playbook import AttackResult, AttackScenario

logger = structlog.get_logger("provocateur.attacks.lease_race")

SCENARIO = AttackScenario(
    name="lease_race",
    description="Attempt to acquire the Sentinel's singleton lease while Sentinel holds it",
    target_infrastructure="SqliteLeaseStore",
    expected_defense="Fencing token CAS rejection. Auction arbiter rejects (singleton leased).",
    timeout_seconds=15.0,
)


async def execute_lease_race(ctx, target_mas_id: str = "grid-gauntlet-sentinel") -> AttackResult:
    """
    Attempt to acquire a lease already held by another MAS.
    Expected: Rejected by CAS / auction. Sentinel's token unchanged.
    """
    started = datetime.now(timezone.utc)
    evidence: dict = {"target": target_mas_id}

    # Phase 1: Announce attack
    try:
        await ctx.events.publish(
            "grid-gauntlet.provocateur.attacks",
            json.dumps({"attack": "lease_race", "target": target_mas_id}).encode(),
            event_type="attack_start",
        )
    except Exception as exc:
        logger.warning("announce_failed", error=str(exc))

    # Phase 2: Publish a competing bid to service-state topic
    # This simulates what the auction system would do, but from an unauthorized source
    fake_bid = {
        "type": "lease_bid",
        "masId": target_mas_id,
        "bidderNodeId": "provocateur-node",
        "compositeScore": 999.0,  # Unrealistically high score
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    bid_accepted = False
    try:
        await ctx.events.publish(
            "system.service-state",
            json.dumps(fake_bid).encode(),
            event_type="lease_bid",
        )
        evidence["bid_published"] = True
        logger.info("fake_bid_published", target=target_mas_id)
    except Exception as exc:
        evidence["bid_published"] = False
        evidence["bid_error"] = str(exc)
        logger.info("bid_rejected_at_publish", error=str(exc))

    # Phase 3: Wait and check if our bid was honored
    import asyncio
    await asyncio.sleep(3.0)

    # Phase 4: Check service-state for lease changes
    defense_held = True
    observed = "Fake bid did not result in lease acquisition"
    try:
        events = await ctx.events.consume("system.service-state", after=0, count=50)
        for ev in events:
            try:
                payload = json.loads(ev.payload_bytes.decode())
                if (payload.get("masId") == target_mas_id and
                    payload.get("holderNodeId") == "provocateur-node"):
                    defense_held = False
                    observed = "CRITICAL: Fake bid was honored — lease transferred to attacker!"
                    bid_accepted = True
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        evidence["events_scanned"] = len(events)
        evidence["bid_accepted"] = bid_accepted
    except Exception as exc:
        observed = f"Could not verify: {exc}"
        evidence["verification_error"] = str(exc)

    completed = datetime.now(timezone.utc)
    return AttackResult(
        attack_name="lease_race",
        target="SqliteLeaseStore",
        started_at=started,
        completed_at=completed,
        defense_held=defense_held,
        expected_behavior=SCENARIO.expected_defense,
        observed_behavior=observed,
        evidence=evidence,
        evolution_trigger=not defense_held,
    )
