"""
grid-gauntlet-sentinel — Tier 2 Adversarial MAS (Defensive)
============================================================
Validates AuraGrid infrastructure invariants under adversarial conditions:
  - Fencing token monotonicity
  - Event sequence ordering
  - Lease presence and continuity
  - Tattle defense evidence collection

Usage (via grid):
    Grid injects AURAGRID_IPC_PORT, AURAGRID_IPC_TOKEN,
    AURAGRID_MAS_ID, AURAGRID_NODE_ID, AURAGRID_FENCING_TOKEN
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone

import structlog

from auragrid import AsyncGridContext, auragrid_method, auragrid_service
from invariants import InvariantChecker

logger = structlog.get_logger("grid-gauntlet-sentinel")

SYSTEM_SERVICE_STATE = "system.service-state"
SYSTEM_CONSENSUS = "system.consensus"
SYSTEM_TELEMETRY = "system.telemetry"

@auragrid_service(
    name="GridGauntletSentinel",
    description=(
        "Defensive MAS that monitors lease health, service discovery, "
        "event integrity, and tattle defense for adversarial testing."
    ),
)
class SentinelService:
    """Exposes observation RPC methods and runs background invariant checks."""

    def __init__(self) -> None:
        self._checker = InvariantChecker()
        self._start_time = datetime.now(timezone.utc)
        self._check_cycles: int = 0
        self._observation_log: list[dict] = []

    @auragrid_method(description="Returns all observed invariant violations")
    def get_violations(self) -> dict:
        return {
            "violations": [
                {
                    "invariant": v.invariant,
                    "expected": v.expected,
                    "observed": v.observed,
                    "timestamp": v.timestamp.isoformat(),
                    "evidence": v.evidence,
                }
                for v in self._checker.violations
            ],
            "count": len(self._checker.violations),
        }

    @auragrid_method(description="Returns current sentinel health and observation count")
    def get_status(self) -> dict:
        uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        return {
            "status": "active" if self._checker.is_healthy else "degraded",
            "is_healthy": self._checker.is_healthy,
            "uptime_seconds": round(uptime, 1),
            "check_cycles": self._check_cycles,
            "node_id": os.environ.get("AURAGRID_NODE_ID", "unknown"),
            "mas_id": os.environ.get("AURAGRID_MAS_ID", "unknown"),
            "stats": self._checker.stats,
        }

    @auragrid_method(description="Returns evidence of tattles filed against this sentinel")
    def get_tattle_evidence(self) -> dict:
        return {
            "tattle_evidence": self._checker.tattle_evidence,
            "count": len(self._checker.tattle_evidence),
        }

    @auragrid_method(description="Explicitly trigger an invariant check cycle and return results")
    def run_check_cycle(self) -> dict:
        self._check_cycles += 1
        return {
            "cycle": self._check_cycles,
            "healthy": self._checker.is_healthy,
            "violations_total": len(self._checker.violations),
        }


async def _check_fencing_token(service: SentinelService) -> None:
    """Check the current fencing token for monotonicity."""
    raw = os.environ.get("AURAGRID_FENCING_TOKEN")
    if raw is not None:
        try:
            token = int(raw)
            result = service._checker.check_fencing_token(token)
            logger.info("fencing_token_check", token=token, valid=result)
        except ValueError:
            logger.warning("fencing_token_parse_error", raw=raw)


async def _event_monitor(ctx: AsyncGridContext, service: SentinelService, topic: str) -> None:
    """Long-running event monitor for a single topic via subscribe()."""
    consumer_id = f"sentinel-{topic}"
    try:
        async for event in ctx.events.subscribe(topic, consumer_id=consumer_id, count=50):
            try:
                service._checker.check_event_ordering(topic, event.sequence_number)
                logger.info("event_processed", topic=topic, seq=event.sequence_number)
            except Exception as exc:
                logger.warning("event_processing_failed", topic=topic, seq=event.sequence_number, error=str(exc))
    except asyncio.CancelledError:
        logger.info("event_monitor_stopped", topic=topic)
    except Exception as exc:
        logger.warning("event_monitor_failed", topic=topic, error=str(exc))


async def _tattle_monitor(ctx: AsyncGridContext, service: SentinelService) -> None:
    """Long-running tattle scanner on system.telemetry via subscribe()."""
    mas_id = os.environ.get("AURAGRID_MAS_ID", "")
    consumer_id = "sentinel-tattles"
    try:
        async for event in ctx.events.subscribe(SYSTEM_TELEMETRY, consumer_id=consumer_id, count=100):
            try:
                payload = json.loads(event.payload_bytes.decode())
                if payload.get("masId") == mas_id:
                    service._checker.record_tattle_against_us(payload)
                    logger.warning("tattle_detected", payload=payload)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
            except Exception as exc:
                logger.warning("tattle_processing_failed", seq=event.sequence_number, error=str(exc))
    except asyncio.CancelledError:
        logger.info("tattle_monitor_stopped")
    except Exception as exc:
        logger.warning("tattle_monitor_failed", error=str(exc))


async def main() -> None:
    node_id = os.environ.get("AURAGRID_NODE_ID", "local")
    mas_id = os.environ.get("AURAGRID_MAS_ID", "grid-gauntlet-sentinel")

    logger.info("sentinel_initializing", node_id=node_id, mas_id=mas_id)

    service = SentinelService()

    async with AsyncGridContext(service_instances=[service]) as ctx:
        logger.info("grid_context_established")

        # Initial fencing token check
        await _check_fencing_token(service)

        # Publish startup event
        try:
            await ctx.events.publish(
                "grid-gauntlet.sentinel.lifecycle",
                json.dumps({
                    "event": "startup",
                    "node_id": node_id,
                    "mas_id": mas_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }).encode(),
                event_type="startup",
            )
        except Exception as exc:
            logger.warning("startup_event_failed", error=str(exc))

        logger.info("sentinel_running")

        # Spawn background subscribe-based event monitors
        background_tasks: list[asyncio.Task] = []
        for topic in [SYSTEM_SERVICE_STATE, SYSTEM_CONSENSUS]:
            task = asyncio.create_task(
                _event_monitor(ctx, service, topic),
                name=f"sentinel-monitor-{topic}",
            )
            background_tasks.append(task)

        tattle_task = asyncio.create_task(
            _tattle_monitor(ctx, service),
            name="sentinel-tattle-monitor",
        )
        background_tasks.append(tattle_task)

        stop_event = asyncio.Event()

        async def _health_loop() -> None:
            """Periodic health checks (fencing token, cycle counter)."""
            cycle = 0
            while not stop_event.is_set():
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=5.0)
                    break
                except asyncio.TimeoutError:
                    pass

                cycle += 1
                service.run_check_cycle()

                # Every 3rd cycle: check fencing token
                if cycle % 3 == 0:
                    await _check_fencing_token(service)

                logger.info(
                    "check_cycle_complete",
                    cycle=cycle,
                    healthy=service._checker.is_healthy,
                    violations=len(service._checker.violations),
                )

        health_task = asyncio.create_task(_health_loop(), name="sentinel-health")

        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            logger.info("sentinel_shutdown_initiated")
            stop_event.set()

            # Cancel health loop
            health_task.cancel()
            try:
                await health_task
            except asyncio.CancelledError:
                pass

            # Cancel all background subscribe monitors
            for task in background_tasks:
                task.cancel()
            await asyncio.gather(*background_tasks, return_exceptions=True)
            background_tasks.clear()

            try:
                await ctx.events.publish(
                    "grid-gauntlet.sentinel.lifecycle",
                    json.dumps({
                        "event": "shutdown",
                        "node_id": node_id,
                        "mas_id": mas_id,
                        "check_cycles": service._check_cycles,
                        "violations": len(service._checker.violations),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }).encode(),
                    event_type="shutdown",
                )
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(main())
