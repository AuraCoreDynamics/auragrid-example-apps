import asyncio
import logging
import sys
from typing import Optional
from auragrid import AsyncGridContext, auragrid_service, auragrid_method

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("model_foundry")

@auragrid_service(name="ModelFoundry", description="Secure LLM Foundry Service")
class ModelFoundryService:
    """Demonstrates Declarative RBAC and Identity Propagation."""
    
    def __init__(self):
        self._is_training = False
        self._current_model = "aura-llama-8b-v1"

    @auragrid_method(name="GetStatus", required_claim="Project:Aura")
    async def get_status(self, user_id: Optional[str] = None) -> dict:
        """Standard operation restricted via ABAC.
        
        Requires the 'Project' attribute to be 'Aura'.
        """
        logger.info("Status query from user: %s", user_id)
        return {
            "model": self._current_model,
            "isTraining": self._is_training,
            "authorizedUser": user_id
        }

    @auragrid_method(name="StartTraining", required_role="FoundryAdmin")
    async def start_training(self, config_json: str, user_id: Optional[str] = None) -> str:
        """Sensitive operation protected by FoundryAdmin role."""
        if self._is_training:
            return "Training already in progress."
            
        logger.info("CRITICAL: Training initiated by %s with config: %s", user_id, config_json)
        self._is_training = True
        
        # Simulate long-running job
        asyncio.create_task(self._simulate_training())
        
        return f"Training job started by {user_id}. Monitor logs for progress."

    @auragrid_method(name="EmergencyStop", required_role="GridAdmin")
    async def emergency_stop(self, user_id: Optional[str] = None) -> bool:
        """Ultra-sensitive operation requiring fabric-level admin role."""
        logger.warning("EMERGENCY STOP requested by %s", user_id)
        self._is_training = False
        return True

    async def _simulate_training(self):
        await asyncio.sleep(30)
        self._is_training = False
        self._current_model = "aura-llama-8b-v2-STABLE"
        logger.info("Training complete. Model updated to v2.")

async def run_foundry():
    """Main loop for the Model Foundry MAS."""
    logger.info("Starting Model Foundry Service...")
    
    # Initialize the service instance
    foundry_svc = ModelFoundryService()
    
    # Start AsyncGridContext with the service instance to expose it via RPC
    async with AsyncGridContext(service_instances=[foundry_svc]) as grid:
        logger.info("Service server active. Port: %d", grid._service_servers[0].port)
        
        # Keep the process alive
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(run_foundry())
    except KeyboardInterrupt:
        pass
