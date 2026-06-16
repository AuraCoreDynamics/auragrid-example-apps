import pytest
import respx
import json
from httpx import Response
from entropy import EntropyService, run_entropy
from auragrid import AsyncGridContext

@pytest.mark.asyncio
async def test_entropy_engine_isolates_node():
    """
    SCENARIO: Entropy Engine MAS is instructed to isolate the local node.
    EXPECTED: 
        1. MAS calls /cell/chaos/gossip?suspended=true.
        2. Local chaos status reflects suspension.
    """
    with respx.mock(base_url="http://localhost:5100", assert_all_called=False) as grid_mock:
        # Mock Health check
        grid_mock.get("/api/health").mock(return_value=Response(200, json={"status": "Healthy"}))
        
        # Mock Chaos Suspension
        gossip_mock = grid_mock.post("/cell/chaos/gossip", params={"suspended": "true"}).mock(
            return_value=Response(200, json={"success": True, "suspended": True})
        )
        
        # Mock Chaos Status
        grid_mock.get("/cell/chaos/status").mock(
            return_value=Response(200, json={
                "gossipSuspended": True,
                "storageFaultEnabled": False,
                "networkFaults": {}
            })
        )

        async with AsyncGridContext() as grid:
            service = EntropyService(grid)
            result = await service.isolate_node()
            
            assert result["status"] == "isolated"
            assert gossip_mock.called
            
            status = await grid.chaos.get_status()
            assert status.gossip_suspended is True

@pytest.mark.asyncio
async def test_entropy_engine_fails_storage():
    """
    SCENARIO: Entropy Engine MAS is instructed to fail storage mutations.
    EXPECTED: 
        1. MAS calls /cell/chaos/storage?enabled=true.
    """
    with respx.mock(base_url="http://localhost:5100", assert_all_called=False) as grid_mock:
        grid_mock.get("/api/health").mock(return_value=Response(200, json={"status": "Healthy"}))
        
        storage_mock = grid_mock.post("/cell/chaos/storage", params={"enabled": "true"}).mock(
            return_value=Response(200, json={"success": True, "enabled": True})
        )

        async with AsyncGridContext() as grid:
            service = EntropyService(grid)
            await service.fail_storage(True)
            
            assert storage_mock.called
