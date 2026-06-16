"""Attack: Register a fake service endpoint pointing to a non-existent port."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import structlog

from playbook import AttackResult, AttackScenario

logger = structlog.get_logger("provocateur.attacks.phantom_registration")

SCENARIO = AttackScenario(
    name="phantom_registration",
    description="Register a service endpoint pointing to a non-existent port",
    target_infrastructure="Service Registry / Discovery",
    expected_defense="Registration succeeds but dispatch fails gracefully. Auto-tattle filed.",
    timeout_seconds=20.0,
)


async def execute_phantom_registration(ctx) -> AttackResult:
    """
    Register a fake endpoint at an unreachable port.
    Expected: Dispatch fails gracefully (timeout, not hang). Tattle auto-filed.
    """
    started = datetime.now(timezone.utc)
    phantom_service = "PhantomService"
    phantom_port = 59999
    evidence: dict = {"phantom_service": phantom_service, "phantom_port": phantom_port}

    # Phase 1: Announce
    try:
        await ctx.events.publish(
            "grid-gauntlet.provocateur.attacks",
            json.dumps({
                "attack": "phantom_registration",
                "service": phantom_service,
                "port": phantom_port,
            }).encode(),
            event_type="attack_start",
        )
    except Exception:
        pass

    # Phase 2: Register phantom endpoint via service-state event
    registration_event = {
        "type": "endpoint_registered",
        "serviceId": f"phantom-{phantom_port}",
        "serviceName": phantom_service,
        "nodeId": "provocateur-node",
        "grpcEndpoint": f"http://localhost:{phantom_port}",
        "metadata": {"synthetic": "true"},
    }

    try:
        await ctx.events.publish(
            "system.service-state",
            json.dumps(registration_event).encode(),
            event_type="endpoint_registered",
        )
        evidence["registration_published"] = True
        logger.info("phantom_registered", service=phantom_service, port=phantom_port)
    except Exception as exc:
        evidence["registration_published"] = False
        evidence["registration_error"] = str(exc)

    # Phase 3: Wait for potential dispatch attempt and tattle
    await asyncio.sleep(5.0)

    # Phase 4: Check if auto-tattle was filed against phantom
    defense_held = False
    observed = "No auto-tattle mechanism detected for phantom endpoints"

    try:
        events = await ctx.events.consume("system.telemetry", after=0, count=100)
        tattle_for_phantom = [
            ev for ev in events
            if phantom_service in ev.payload_bytes.decode(errors="ignore")
        ]
        if tattle_for_phantom:
            defense_held = True
            observed = f"Auto-tattle filed for phantom service ({len(tattle_for_phantom)} events)"
            evidence["tattle_events_found"] = len(tattle_for_phantom)
        else:
            evidence["tattle_events_found"] = 0
            observed = (
                "No auto-tattle detected for phantom registration. "
                "Self-healing mechanism not triggered by event-based registration."
            )
    except Exception as exc:
        observed = f"Could not verify tattle: {exc}"
        evidence["verification_error"] = str(exc)

    # Phase 5: Cleanup — publish unregistration
    try:
        await ctx.events.publish(
            "system.service-state",
            json.dumps({
                "type": "endpoint_unregistered",
                "serviceId": f"phantom-{phantom_port}",
                "serviceName": phantom_service,
            }).encode(),
            event_type="endpoint_unregistered",
        )
        evidence["cleanup_done"] = True
    except Exception:
        evidence["cleanup_done"] = False

    completed = datetime.now(timezone.utc)
    return AttackResult(
        attack_name="phantom_registration",
        target="Service Registry / Discovery",
        started_at=started,
        completed_at=completed,
        defense_held=defense_held,
        expected_behavior=SCENARIO.expected_defense,
        observed_behavior=observed,
        evidence=evidence,
        evolution_trigger=not defense_held,
    )
