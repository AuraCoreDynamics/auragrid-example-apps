# Tier 2: Grid Gauntlet

## Overview
The **Grid Gauntlet** is a multi-MAS communication scenario featuring two distinct services: the **Sentinel** (a detector) and the **Provocateur** (an actor). It demonstrates how AuraCore handles inter-cell communication and event-driven coordination.

## Why AuraCore? (The Difference)
In standard microservices, communication requires service meshes, sidecars, and complex load balancers. In AuraCore, **the Fabric is the Message Bus**.
* **WAL-Backed Eventing:** Every communication is backed by a Write-Ahead Log (WAL), ensuring that if a node fails, the message is never lost.
* **Location Transparency:** The Sentinel doesn't need to know *where* the Provocateur is. It simply publishes an event to a topic, and the Grid's Gossip protocol ensures it finds its target.
* **Hardware-Aware Routing:** Demonstrates how the Grid uses "AuraScores" to route events to the node best equipped (CPU/MEM/GPU) to handle them.

## AuraCore Tech Showcased
* **Event Pub/Sub client:** High-throughput, persistent eventing via the Python SDK.
* **Gossip-based Discovery:** Automatic service resolution across nodes without a central DNS or Consul.
* **Topic Management:** Dynamic creation and partitioning of communication channels.

## Evaluation Impact
This app proves that AuraCore is more than a runner; it is a **Distributed OS**. It shows how complex, multi-component systems can be built with far less "glue code" than traditional cloud-native architectures.
