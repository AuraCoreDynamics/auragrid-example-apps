# Tier 4: Direct Inference Bypass

This application pair (Orchestrator and Worker) is built in C# to demonstrate the AuraGrid Direct Inference Bypass fast-path. It implements a basic gRPC inference service where the Orchestrator routes requests directly to the Worker through the YARP proxy using the `X-AuraGrid-IPC-Token` validation mechanism.

## Core Objective

Validate the proxy's capability to route simple unary gRPC payloads securely and correctly, bypassing the buffered middleware to achieve low-latency inference routing.

## Key Scenarios Tested
- **YARP gRPC Reverse Proxy:** The Orchestrator routes through the main Grid proxy on `8088`, using `X-AuraGrid-IPC-Token`.
- **Fast-Path Inference:** Simulating a direct point-to-point inference request using the Grid IPC registry.
