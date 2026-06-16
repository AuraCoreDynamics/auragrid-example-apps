import asyncio
import logging
import os
import sys
import json
from datetime import datetime
from auragrid import AsyncGridContext
from auragrid.lease_client import WalMarker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("sovereign_ledger")

# Topic for ledger events. system.* topics are automatically signed by AuraGrid.
LEDGER_TOPIC = "system.ledger"
MAS_ID = "sovereign-ledger"

async def run_ledger():
    """Main loop for the Secure Sovereign Ledger MAS."""
    logger.info("Starting Secure Sovereign Ledger MAS...")
    
    async with AsyncGridContext() as grid:
        # 1. Attempt to acquire the singleton lease
        logger.info("Attempting to acquire lease for %s...", MAS_ID)
        
        bid = {
            "nodeId": os.environ.get("AURAGRID_NODE_ID", "local-node"),
            "cpuScore": 100,
            "memoryScore": 100,
            "instructionSetScore": 100,
            "metadataScore": 100,
            "compositeScore": 500,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "nonce": 0
        }
        
        result = await grid.lease.try_acquire_lease(MAS_ID, bid)
        
        if not result.acquired:
            logger.error("Failed to acquire lease: %s. Exiting.", result.reason)
            return

        lease = result.lease
        fencing_token = lease.fencing_token
        logger.info("Lease acquired! Fencing Token: %d", fencing_token)
        
        # 2. Write loop
        try:
            counter = 0
            while True:
                counter += 1
                
                # Create a structured transaction record
                transaction = {
                    "txId": f"TX-{counter:04}",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "payload": "Financial transfer data",
                    "amount": 100.0,
                    "fencingToken": fencing_token
                }
                
                payload = json.dumps(transaction).encode('utf-8')
                
                logger.info("Publishing signed transaction %d to WAL...", counter)
                
                # 3. Publish to system.ledger topic.
                # The AuraGrid SharedFsWalWriter will automatically sign this 
                # with the node's private key before committing it to the WAL.
                event = await grid.events.publish(LEDGER_TOPIC, payload, event_type="Transaction")
                
                logger.info("Transaction committed. Seq: %d, Signed by: %s", 
                            event.sequence_number, event.source_node_id)
                
                # 4. Periodically renew the lease and update WAL marker
                if counter % 5 == 0:
                    logger.info("Renewing lease and committing marker...")
                    marker = WalMarker(topic_id=LEDGER_TOPIC, sequence_number=event.sequence_number)
                    extended = await grid.lease.renew_lease(MAS_ID, fencing_token, marker)
                    
                    if not extended:
                        logger.error("Lease renewal failed! Another node may have taken over. HALTING.")
                        break
                
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            logger.info("Sovereign Ledger received shutdown signal.")
        finally:
            logger.info("Releasing lease...")
            await grid.lease.release_lease(MAS_ID, fencing_token)

if __name__ == "__main__":
    try:
        asyncio.run(run_ledger())
    except KeyboardInterrupt:
        pass
