import asyncio
import logging
import sys
import json
import httpx
from datetime import datetime
from auragrid import AsyncGridContext

# Import the official mcp package (authorized)
try:
    from mcp import ClientSession
    # Anthropic's 'mcp' package often uses stdio by default, 
    # but we need HTTP for AuraXLM/AuraRouter MAS integration.
    # If HttpClient isn't in the expected location, we'll use a direct implementation.
    try:
        from mcp.client.http import HttpClient
    except ImportError:
        # Fallback for older or different versions of the mcp package
        HttpClient = None
except ImportError:
    print("Error: 'mcp' package not found. Run 'pip install mcp' to execute this MAS.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("cognitive_beacon")

async def call_mcp_http(url: str, tool_name: str, arguments: dict):
    """Generic MCP-over-HTTP caller if the mcp SDK's HttpClient is unavailable or incompatible."""
    async with httpx.AsyncClient() as client:
        # 1. Initialize
        init_resp = await client.post(f"{url}/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "beacon", "version": "1.0"}}
        })
        init_resp.raise_for_status()
        
        # 2. Call Tool
        call_resp = await client.post(f"{url}/mcp", json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments}
        })
        call_resp.raise_for_status()
        result = call_resp.json().get("result", {})
        return result

async def run_beacon():
    """Main loop for the Cognitive Beacon MAS."""
    logger.info("Starting Cognitive Beacon MAS...")
    
    async with AsyncGridContext() as grid:
        # 1. DISCOVERY: Find AuraXLM and AuraRouter
        logger.info("Discovering AI services on the grid...")
        
        xlm_endpoints = await grid.registry.discover("auraxlm-mas")
        router_endpoints = await grid.registry.discover("aurarouter-mas")
        
        if not xlm_endpoints:
            logger.error("AuraXLM not found in registry. Ensure 'auraxlm' is running.")
            return

        xlm_url = xlm_endpoints[0].endpoint_url
        logger.info("Found AuraXLM at: %s", xlm_url)
        
        # 2. DIRECT CALL: Call AuraXLM via MCP
        logger.info("--- PATH A: Direct AuraXLM MCP Call ---")
        try:
            logger.info("Invoking 'auraxlm.query' tool directly...")
            result = await call_mcp_http(xlm_url, "auraxlm.query", 
                                       {"prompt": "Summarize the state of the grid shared storage.", "tier": "lite"})
            
            content = result.get("content", [{"text": "No content"}])[0].get("text", "No text")
            logger.info("Direct Path Result: %s", content[:200] + "...")
        except Exception as e:
            logger.exception("Direct Path A failed: %s", e)

        # 3. IMPLICIT CALL: Call AuraRouter
        if router_endpoints:
            router_url = router_endpoints[0].endpoint_url
            logger.info("--- PATH B: Implicit AuraRouter Call ---")
            logger.info("Found AuraRouter at: %s", router_url)
            
            try:
                logger.info("Invoking 'router.generate' tool (implicitly routes to AuraXLM)...")
                result = await call_mcp_http(router_url, "router.generate",
                                           {"prompt": "Summarize the state of the grid shared storage.", "preferred_expert": "auraxlm"})
                
                content = result.get("content", [{"text": "No content"}])[0].get("text", "No text")
                logger.info("Implicit Path Result: %s", content[:200] + "...")
            except Exception as e:
                logger.exception("Implicit Path B failed: %s", e)
        else:
            logger.warning("AuraRouter not found. Skipping Path B.")

        logger.info("Cognitive Beacon tasks complete.")

if __name__ == "__main__":
    try:
        asyncio.run(run_beacon())
    except KeyboardInterrupt:
        pass
