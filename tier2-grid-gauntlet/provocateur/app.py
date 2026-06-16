"""
grid-gauntlet-provocateur — Tier 2 Adversarial MAS (Offensive)
===============================================================
Controlled adversary that executes attack playbook scenarios against
AuraGrid's control plane infrastructure. Each attack is:
  - Announced (publishes intent)
  - Executed with a timeout
  - Recorded (defense_held / evolution_trigger)

Usage (via grid):
    Grid injects AURAGRID_IPC_PORT, AURAGRID_IPC_TOKEN,
    AURAGRID_MAS_ID, AURAGRID_NODE_ID, AURAGRID_FENCING_TOKEN
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

import structlog

from auragrid import AsyncGridContext, auragrid_method, auragrid_service

# Add parent for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playbook import AttackPlaybook
from attacks.false_tattle import SCENARIO as FALSE_TATTLE_SCENARIO, execute_false_tattle
from attacks.lease_race import SCENARIO as LEASE_RACE_SCENARIO, execute_lease_race
from attacks.event_flood import SCENARIO as EVENT_FLOOD_SCENARIO, execute_event_flood
from attacks.stale_invoke import SCENARIO as STALE_INVOKE_SCENARIO, execute_stale_invoke
from attacks.phantom_registration import SCENARIO as PHANTOM_SCENARIO, execute_phantom_registration

logger = structlog.get_logger("grid-gauntlet-provocateur")


@auragrid_service(
    name="GridGauntletProvocateur",
    description=(
        "Controlled adversary MAS that executes attack playbook scenarios "
        "to test grid defense mechanisms."
    ),
)
class ProvocateurService:
    """Exposes RPC methods for attack control and result retrieval."""

    def __init__(self) -> None:
        self._playbook = AttackPlaybook()
        self._start_time = datetime.now(timezone.utc)
        self._execution_started = False

        # Register all attacks
        self._playbook.register(FALSE_TATTLE_SCENARIO, execute_false_tattle)
        self._playbook.register(LEASE_RACE_SCENARIO, execute_lease_race)
        self._playbook.register(EVENT_FLOOD_SCENARIO, execute_event_flood)
        self._playbook.register(STALE_INVOKE_SCENARIO, execute_stale_invoke)
        self._playbook.register(PHANTOM_SCENARIO, execute_phantom_registration)

    @auragrid_method(description="Get the attack playbook summary and results")
    def get_results(self) -> dict:
        return self._playbook.summary()

    @auragrid_method(description="Get current provocateur status")
    def get_status(self) -> dict:
        uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        return {
            "status": "active",
            "uptime_seconds": round(uptime, 1),
            "execution_started": self._execution_started,
            "scenarios_registered": len(self._playbook.scenarios),
            "results_count": len(self._playbook.results),
            "node_id": os.environ.get("AURAGRID_NODE_ID", "unknown"),
            "mas_id": os.environ.get("AURAGRID_MAS_ID", "unknown"),
        }

    @auragrid_method(description="List all registered attack scenarios")
    def list_attacks(self) -> dict:
        return {
            "attacks": [
                {
                    "name": s.name,
                    "description": s.description,
                    "target": s.target_infrastructure,
                    "enabled": s.enabled,
                    "timeout_seconds": s.timeout_seconds,
                }
                for s in self._playbook.scenarios
            ]
        }

    @auragrid_method(description="Get evolution triggers identified by attacks")
    def get_evolution_triggers(self) -> dict:
        triggers = [r for r in self._playbook.results if r.evolution_trigger]
        return {
            "triggers": [
                {
                    "attack": t.attack_name,
                    "target": t.target,
                    "observed": t.observed_behavior,
                    "evidence": t.evidence,
                }
                for t in triggers
            ],
            "count": len(triggers),
        }


async def main() -> None:
    node_id = os.environ.get("AURAGRID_NODE_ID", "local")
    mas_id = os.environ.get("AURAGRID_MAS_ID", "grid-gauntlet-provocateur")

    logger.info("provocateur_initializing", node_id=node_id, mas_id=mas_id)

    service = ProvocateurService()

    async with AsyncGridContext(service_instances=[service]) as ctx:
        logger.info("grid_context_established")

        # Publish startup
        try:
            await ctx.events.publish(
                "grid-gauntlet.provocateur.lifecycle",
                json.dumps({
                    "event": "startup",
                    "node_id": node_id,
                    "mas_id": mas_id,
                    "attacks_registered": len(service._playbook.scenarios),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }).encode(),
                event_type="startup",
            )
        except Exception as exc:
            logger.warning("startup_event_failed", error=str(exc))

        # Wait for sentinel to be ready (give it 10s head start)
        logger.info("waiting_for_sentinel", delay_seconds=10)
        await asyncio.sleep(10.0)

        # Execute all attacks
        logger.info("executing_playbook")
        service._execution_started = True
        results = await service._playbook.execute_all(ctx=ctx)

        # Publish results
        summary = service._playbook.summary()
        logger.info(
            "playbook_complete",
            total=summary["total_executed"],
            defenses_held=summary["defenses_held"],
            evolution_triggers=summary["evolution_triggers"],
        )

        try:
            await ctx.events.publish(
                "grid-gauntlet.provocateur.lifecycle",
                json.dumps({
                    "event": "playbook_complete",
                    "summary": summary,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }).encode(),
                event_type="playbook_complete",
            )
        except Exception:
            pass

        # Stay alive for RPC queries
        logger.info("provocateur_idle", message="Playbook complete. Waiting for queries.")
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            logger.info("provocateur_shutdown")


if __name__ == "__main__":
    asyncio.run(main())
