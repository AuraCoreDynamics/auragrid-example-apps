import asyncio
import logging
import sys
import json
import os
from datetime import datetime
from auragrid import AsyncGridContext

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("signed_chat")

CHAT_TOPIC = "chat.global"

async def run_chat():
    """Main loop for the Signed Gossip Chat application."""
    logger.info("Initializing Signed Chat Client...")
    
    async with AsyncGridContext() as grid:
        # 1. Start a listener for chat messages
        # Note: In AuraGrid, application-level gossip topics are also 
        # subject to signature verification at the fabric layer.
        asyncio.create_task(listen_for_messages(grid))
        
        node_id = os.environ.get("AURAGRID_NODE_ID", "anonymous")
        
        logger.info("Chat active. Type your message and press ENTER to broadcast.")
        logger.info("(Messages are digitally signed by your node's PKI identity)")
        
        # 2. Main input loop
        while True:
            # We use loop.run_in_executor to avoid blocking the event loop with input()
            message = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            message = message.strip()
            
            if not message:
                continue
                
            if message.lower() == "/exit":
                break
                
            chat_packet = {
                "user": node_id,
                "msg": message,
                "sentAt": datetime.utcnow().isoformat() + "Z"
            }
            
            payload = json.dumps(chat_packet).encode('utf-8')
            
            # 3. Publish to the gossip network
            # Because this is a user-defined topic, we can use the event client
            # to broadcast it. If configured as a gossip topic in manifests,
            # it travels via UDP SWIM packets.
            await grid.events.publish(CHAT_TOPIC, payload, event_type="ChatMessage")

async def listen_for_messages(grid):
    """Consumer loop that verifies and displays incoming messages."""
    last_seq = 0
    while True:
        try:
            events = await grid.events.consume(CHAT_TOPIC, after=last_seq, count=5)
            for event in events:
                last_seq = event.sequence_number
                
                try:
                    data = json.loads(event.payload_bytes.decode('utf-8'))
                    user = data.get("user", "???")
                    msg = data.get("msg", "")
                except:
                    continue
                
                # 4. Fabric-Level Verification
                # The AuraGrid SDK informs us if the message was verified 
                # by the ProxyWorker during ingress.
                verified_status = "[VERIFIED]" if event.signature else "[UNSIGNED]"
                
                print(f"\n{verified_status} <{user}>: {msg}")
                sys.stdout.flush()
                
            if not events:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error("Error consuming messages: %s", e)
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(run_chat())
    except KeyboardInterrupt:
        pass
