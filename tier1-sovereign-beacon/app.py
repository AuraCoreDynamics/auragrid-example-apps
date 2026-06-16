"""
sovereign-beacon — Tier 1 Adversarial MAS
==========================================
Validates the fundamental AuraGrid CellSingleton lifecycle:
  - Grid starts exactly one instance per cell (lease mechanism)
  - Startup / shutdown events reach the WAL-backed event bus
  - Cell configuration is reachable via the IPC bridge
  - An @auragrid_method is callable via the ServiceProxy

This app intentionally does NOT suppress errors from grid calls —
any failure is logged at WARNING and counted so the chain-of-thought
log captures them as Evolution Triggers.

Usage (direct, no grid):
    python app.py

Usage (via grid):
    Grid injects AURAGRID_IPC_PORT, AURAGRID_IPC_TOKEN,
    AURAGRID_MAS_ID, AURAGRID_NODE_ID, AURAGRID_FENCING_TOKEN
    as environment variables before starting this process.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

from auragrid import AsyncGridContext, auragrid_method, auragrid_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sovereign-beacon")

# ---------------------------------------------------------------------------
# Service definition
# ---------------------------------------------------------------------------

@auragrid_service(
    name="SovereignBeacon",
    description=(
        "Tier 1 sovereignty probe. Validates CellSingleton lifecycle, "
        "cell config reads, and WAL-backed event publication."
    ),
)
class SovereignBeaconService:
    """Exposes a single RPC method so the ServiceProxy has something to route."""

    def __init__(self) -> None:
        self._start_time = datetime.now(timezone.utc)
        self._heartbeat_count: int = 0

    @auragrid_method(
        description=(
            "Returns current status: MAS identity, uptime in seconds, "
            "and the number of heartbeat events published so far."
        )
    )
    def get_status(self) -> dict:
        uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        return {
            "status": "active",
            "heartbeats": self._heartbeat_count,
            "uptime_seconds": round(uptime, 1),
            "node_id": os.environ.get("AURAGRID_NODE_ID", "unknown"),
            "mas_id": os.environ.get("AURAGRID_MAS_ID", "unknown"),
        }

    def _increment_heartbeat(self) -> None:
        self._heartbeat_count += 1


# ---------------------------------------------------------------------------
# IPC probe helpers
# ---------------------------------------------------------------------------

async def _probe_cell_config(ctx: AsyncGridContext) -> None:
    """Read a well-known config key; log the result for the chain-of-thought record."""
    try:
        value = await ctx.config.get("filesystem/grid-root")
        logger.info(
            "PROBE cell-config OK. key=filesystem/grid-root value=%r",
            value if value is not None else "(key not set)",
        )
    except Exception as exc:
        logger.warning("PROBE cell-config WARN: %s", exc)


async def _publish_event(ctx: AsyncGridContext, topic: str, payload: dict, event_type: str) -> None:
    """Publish a single event; log event_id and seq on success, warn on failure."""
    try:
        ev = await ctx.events.publish(
            topic,
            json.dumps(payload, default=str).encode(),
            event_type=event_type,
        )
        logger.info(
            "EVENT published OK. topic=%s type=%s event_id=%s seq=%d",
            topic, event_type, ev.event_id, ev.sequence_number,
        )
    except Exception as exc:
        logger.warning("EVENT publish WARN. topic=%s type=%s error=%s", topic, event_type, exc)


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

async def main() -> None:
    node_id = os.environ.get("AURAGRID_NODE_ID", "local")
    mas_id = os.environ.get("AURAGRID_MAS_ID", "sovereign-beacon-mas")
    fencing_token = os.environ.get("AURAGRID_FENCING_TOKEN")
    ipc_port = os.environ.get("AURAGRID_IPC_PORT", "0")

    logger.info(
        "SovereignBeacon initializing. node=%s mas=%s fencing_token=%s ipc_port=%s",
        node_id, mas_id,
        fencing_token or "none (running outside grid or non-singleton)",
        ipc_port,
    )

    service = SovereignBeaconService()

    async with AsyncGridContext(service_instances=[service]) as ctx:
        logger.info("AsyncGridContext established. IPC bridge active.")

        # --- Phase 1: probe cell configuration ---
        await _probe_cell_config(ctx)

        # --- Phase 2: publish startup lifecycle event ---
        await _publish_event(
            ctx,
            topic="sovereign-beacon.lifecycle",
            payload={
                "event": "startup",
                "node_id": node_id,
                "mas_id": mas_id,
                "fencing_token": fencing_token,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            event_type="startup",
        )

        logger.info("SovereignBeacon is RUNNING. Heartbeat interval: 30s.")

        # --- Phase 3: heartbeat loop ---
        stop_event = asyncio.Event()

        async def _heartbeat_loop() -> None:
            while not stop_event.is_set():
                # Wait up to 30 s; break early if stop_event fires.
                try:
                    await asyncio.wait_for(
                        asyncio.shield(stop_event.wait()), timeout=30.0
                    )
                    break
                except asyncio.TimeoutError:
                    pass

                service._increment_heartbeat()
                await _publish_event(
                    ctx,
                    topic="sovereign-beacon.heartbeat",
                    payload={
                        "event": "heartbeat",
                        "count": service._heartbeat_count,
                        "node_id": node_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    event_type="heartbeat",
                )

        hb_task = asyncio.create_task(_heartbeat_loop(), name="heartbeat-loop")

        try:
            # Block until the grid cancels us (SIGTERM / CancelledError).
            await asyncio.Event().wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            logger.info("SovereignBeacon shutdown initiated.")
            stop_event.set()
            hb_task.cancel()
            try:
                await hb_task
            except asyncio.CancelledError:
                pass

            await _publish_event(
                ctx,
                topic="sovereign-beacon.lifecycle",
                payload={
                    "event": "shutdown",
                    "node_id": node_id,
                    "mas_id": mas_id,
                    "heartbeats_published": service._heartbeat_count,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                event_type="shutdown",
            )

    logger.info(
        "SovereignBeacon stopped cleanly. Total heartbeats published: %d",
        service._heartbeat_count,
    )


if __name__ == "__main__":
    asyncio.run(main())
