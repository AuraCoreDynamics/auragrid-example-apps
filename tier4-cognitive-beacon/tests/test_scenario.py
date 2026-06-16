import pytest
import respx
from httpx import Response
from beacon import run_beacon

@pytest.mark.asyncio
async def test_beacon_scenario_routing_equivalence():
    """
    SCENARIO: Cognitive Beacon MAS discovers AuraXLM and AuraRouter.
    EXPECTED: 
        1. MAS calls /cell/registry/discover for both services.
        2. MAS initiates Path A (Direct) to AuraXLM.
        3. MAS initiates Path B (Implicit) to AuraRouter.
        4. Both paths receive successful tool call responses.
    """
    xlm_url = "http://xlm-node:5000"
    router_url = "http://router-node:8080"
    
    with respx.mock(base_url="http://localhost:5100", assert_all_called=False) as grid_mock:
        # Mock Service Discovery
        grid_mock.get("/cell/registry/discover", params={"serviceName": "auraxlm-mas"}).mock(
            return_value=Response(200, json={
                "endpoints": [{
                    "serviceId": "xlm-1", "serviceName": "auraxlm-mas", 
                    "nodeId": "node-xlm", "endpointUrl": xlm_url,
                    "capabilities": ["lite-rag", "mcp"], "metadata": {}
                }]
            })
        )
        grid_mock.get("/cell/registry/discover", params={"serviceName": "aurarouter-mas"}).mock(
            return_value=Response(200, json={
                "endpoints": [{
                    "serviceId": "router-1", "serviceName": "aurarouter-mas", 
                    "nodeId": "node-router", "endpointUrl": router_url,
                    "capabilities": ["routing", "mcp"], "metadata": {}
                }]
            })
        )
        
        # Mock Health check (used by is_connected)
        grid_mock.get("/api/health").mock(return_value=Response(200, json={"status": "Healthy"}))

        # Mock Path A (Direct AuraXLM MCP)
        xlm_mcp = respx.mock(base_url=xlm_url, assert_all_called=True)
        xlm_mcp.post("/mcp").mock(side_effect=[
            # Initialize response
            Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05", "capabilities": {}, "serverInfo": {"name": "AuraXLM", "version": "1.0"}}}),
            # Tool call response
            Response(200, json={"jsonrpc": "2.0", "id": 2, "result": {"content": [{"type": "text", "text": "Path A Response: Direct from AuraXLM"}]}})
        ])
        
        # Mock Path B (Implicit AuraRouter MCP)
        router_mcp = respx.mock(base_url=router_url, assert_all_called=True)
        router_mcp.post("/mcp").mock(side_effect=[
            # Initialize response
            Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05", "capabilities": {}, "serverInfo": {"name": "AuraRouter", "version": "1.0"}}}),
            # Tool call response
            Response(200, json={"jsonrpc": "2.0", "id": 2, "result": {"content": [{"type": "text", "text": "Path B Response: Implicit via AuraRouter"}]}})
        ])

        # Run the beacon logic
        async with xlm_mcp, router_mcp:
            await run_beacon()

    # If we reached here without exception, the beacon logic executed both paths successfully.
    assert True
