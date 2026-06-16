import asyncio
import logging
import os
import sys
import psutil
from datetime import datetime
from auragrid import AsyncGridContext, auragrid_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("entropy_engine")

@auragrid_service(name="entropy-engine")
class EntropyService:
    """Chaos-control service exposed via MCP."""
    
    def __init__(self, grid: AsyncGridContext):
        self._grid = grid

    async def trigger_cpu_stress(self, percent: int, duration_sec: int):
        """Consume CPU for a specified duration."""
        logger.warning("Chaos: Triggering CPU stress (%d%% for %ds)", percent, duration_sec)
        # Simplified stress: run busy loop in background
        async def burn():
            start = datetime.utcnow()
            while (datetime.utcnow() - start).total_seconds() < duration_sec:
                # Busy wait for a slice of a second to simulate load
                # (This is a naive implementation for demo purposes)
                pass
        asyncio.create_task(burn())
        return {"status": "started"}

    async def isolate_node(self):
        """Simulate a network partition by suspending gossip."""
        logger.warning("Chaos: Isolating this node from the cell!")
        await self._grid.chaos.suspend_gossip(True)
        return {"status": "isolated"}

    async def heal_node(self):
        """Restore network connectivity."""
        logger.info("Chaos: Healing network partition.")
        await self._grid.chaos.suspend_gossip(False)
        return {"status": "healed"}

    async def fail_storage(self, enabled: bool):
        """Toggle storage mutation failures."""
        logger.warning("Chaos: Setting storage fault to %s", enabled)
        await self._grid.chaos.set_storage_fault(enabled)
        return {"status": "updated", "enabled": enabled}

async def run_entropy():
    """Main loop for the Entropy Engine MAS."""
    logger.info("Starting Entropy Engine MAS (Fault Injector)...")
    
    # Entropy Engine is a special MAS that requires chaos-control capability.
    # In this example, it's also exposing itself as a service.
    async with AsyncGridContext() as grid:
        service = EntropyService(grid)
        # Register the service manually since we are using AsyncGridContext's server
        await grid._start_service_servers([service])
        
        logger.info("Entropy Engine is online. Node: %s", grid.node_id)
        
        # Monitor local health
        while True:
            status = await grid.chaos.get_status()
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent
            
            if status.gossip_suspended or status.storage_fault_enabled:
                logger.warning("[CHAOS ACTIVE] CPU: %.1f%% | MEM: %.1f%% | Gossip: %s | Storage: %s",
                               cpu, mem, 
                               "SUSPENDED" if status.gossip_suspended else "OK",
                               "FAULTED" if status.storage_fault_enabled else "OK")
            else:
                logger.info("System Normal. CPU: %.1f%% | MEM: %.1f%%", cpu, mem)
            
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(run_entropy())
    except KeyboardInterrupt:
        pass
