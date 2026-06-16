# Tier 5: Signed Gossip Chat

This application demonstrates the hardening of AuraGrid's **SWIM/Gossip** layer using digitally signed messages and pervasive PKI.

## Overview

Unlike standard chat applications, the Signed Chat broadcasts messages over AuraGrid's UDP gossip network. Every packet is signed by the node's private key before being sent and is verified by every peer upon receipt.

## Key Features

-   **Signed Gossip**: Every message travels via a digitally signed packet. Unauthenticated or revoked nodes are physically incapable of broadcasting to the chat topic.
-   **Verification Badges**: The application UI displays a `[VERIFIED]` tag next to messages, proving to the user that the fabric has validated the sender's PKI identity.
-   **Zero-Trust UDP**: Demonstrates how AuraGrid secures the most fundamental cluster communication layer against spoofing and injection.

## Usage

1.  **Start the Chat**:
    ```bash
    $env:PYTHONPATH="C:\projects\auracore\auragrid\src\AuraGrid.PythonSdk"
    python chat.py
    ```

2.  **Broadcast**: Type your message and press ENTER. Your node's `AURAGRID_NODE_ID` will be attached and your PKI identity will sign the envelope.

3.  **Security Drill**: If you revoke a node using `auragrid pki revoke`, its messages will immediately stop appearing on other peers' chat screens, as the fabric will drop the unsigned/invalid packets at the ingress point.

## See Also
-   [**AuraGrid Security Guide**](../../auragrid/docs/security.md)
-   [**Trust Rotation Scenario**](../scenarios/scenario_trust_rotation.py) (shows how to revoke a node)
