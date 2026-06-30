# AuraCore Application Examples

This directory contains a suite of progressively complex Managed Application Services (MAS) designed to stress-test and demonstrate the capabilities of the AuraGrid distributed compute engine. These examples follow the [Adversarial Grid Evolution](../docs/prompts/adversarial_grid_evolution.md) methodology.

## Example Tiers

### [Tier 1: Sovereign Beacon](./tier1-sovereign-beacon/README.md)
The "Hello, World" of the AuraCore ecosystem. Demonstrates a single MAS running with full sovereignty, autonomous lifecycle management, low-overhead IPC, and zero-trust defaults.

### [Tier 2: Grid Gauntlet](./tier2-grid-gauntlet/README.md)
A multi-MAS communication scenario featuring two distinct services (Sentinel and Provocateur). Demonstrates how AuraCore handles inter-cell communication, WAL-backed eventing, location transparency, and hardware-aware routing.

### [Tier 3: Secure Sovereign Ledger](./tier3-sovereign-ledger/README.md)
A distributed, append-only journal service. Demonstrates shared state, data integrity, non-repudiation, and hardware-verified fencing tokens to prevent split-brain corruption.

### [Tier 4: Cognitive Beacon](./tier4-cognitive-beacon/README.md)
An intelligent agent demonstrating integration between AuraGrid and AuraXLM. Showcases native Model Context Protocol (MCP) interactions, Intelligence Routing, and Universal Latent Space (ULS) integration.

### [Tier 4: Zero-Trust Model Foundry](./tier4-model-foundry/README.md)
Demonstrates the power of AuraGrid's Attribute-Based Access Control (ABAC) and Identity Propagation in a secure machine learning context, simulating an LLM training/inference service with restricted operations.

### [Tier 4: Telemetry Torrent](./tier4-telemetry-torrent/README.md)
A high-throughput client and worker pair written in C# designed to stress-test unbuffered HTTP/2 gRPC streaming via the AuraGrid YARP reverse proxy, sending telemetry chunks at maximum velocity and receiving immediate ACKs.

### [Tier 4: Direct Inference Bypass](./tier4-direct-inference-bypass/README.md)
A client and worker pair written in C# designed to validate the fast-path direct inference bypassing the buffered middleware to achieve low-latency inference routing using YARP.

### [Tier 5: Entropy Engine](./tier5-entropy-engine/README.md)
A privileged "Fault Injector" chaos engineering tool. Demonstrates Grid resilience by intentionally suspending heartbeats, injecting latency, and testing auto-healing governance and split-brain immunity.

### [Tier 5: Signed Gossip Chat](./tier5-signed-chat/README.md)
A secure chat application broadcasting over AuraGrid's UDP gossip network. Every packet is signed by the node's private key and verified by peers, demonstrating the hardening of the SWIM/Gossip layer.

### [Tier 6: Container Resource Glutton](./tier6-container-resource-glutton/)
A stress-testing application designed to provision native host container subsystems (like Docker) and deploy MAS instances as isolated container workloads. Validates `ContainerWorkloadExecutor`, volume remapping, and kernel-level resource clamping (MemoryMax, CPUQuota).
