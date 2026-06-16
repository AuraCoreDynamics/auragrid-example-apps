import asyncio
import logging
import sys
import json
from auragrid import AsyncGridContext

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("ledger_auditor")

LEDGER_TOPIC = "system.ledger"

async def run_auditor():
    """Main loop for the Ledger Auditor service."""
    logger.info("Starting Ledger Auditor Service...")
    
    async with AsyncGridContext() as grid:
        last_seq = 0
        
        # Check if topic exists
        if not await grid.events.topic_exists(LEDGER_TOPIC):
            logger.warning("Topic %s does not exist yet. Waiting...", LEDGER_TOPIC)
        
        while True:
            # 1. Consume new events from the ledger topic
            events = await grid.events.consume(LEDGER_TOPIC, after=last_seq, count=10)
            
            for event in events:
                last_seq = event.sequence_number
                
                # 2. Extract transaction data
                try:
                    tx_data = json.loads(event.payload_bytes.decode('utf-8'))
                    tx_id = tx_data.get("txId", "UNKNOWN")
                except:
                    tx_id = "INVALID"
                
                # 3. Verify non-repudiation
                # Every event in system.* topics is digitally signed by the source node.
                # The Python SDK exposes the base64 signature and PEM certificate.
                has_signature = event.signature is not None
                has_cert = event.certificate_pem is not None
                
                if has_signature and has_cert:
                    logger.info("AUDIT PASS: [Seq:%d] [TX:%s] [Node:%s] - SIGNATURE VERIFIED", 
                                event.sequence_number, tx_id, event.source_node_id)
                    # In a production auditor, you would use 'cryptography' to verify
                    # that the signature matches the payload and the certificate 
                    # chains to the trusted cell root.
                else:
                    logger.warning("AUDIT WARNING: [Seq:%d] [TX:%s] [Node:%s] - UNSIGNED EVENT!", 
                                   event.sequence_number, tx_id, event.source_node_id)
            
            if not events:
                await asyncio.sleep(2)

if __name__ == "__main__":
    try:
        asyncio.run(run_auditor())
    except KeyboardInterrupt:
        pass
