# Tier 1: Sovereign Beacon

## Overview
The **Sovereign Beacon** is the "Hello, World" of the AuraCore ecosystem. It demonstrates a single Managed Application Service (MAS) running with full sovereignty on the AuraGrid distributed compute engine.

## Why AuraCore? (The Difference)
Unlike traditional cloud containers (Docker/K8s) that are "pushed" to a central orchestrator, AuraCore MAS applications are **sovereign**. 
* **Autonomous Lifecycle:** The Beacon manages its own state and heartbeat, communicating directly with the local ProxyWorker.
* **Low-Overhead IPC:** Demonstrates the high-performance local IPC bridge, allowing Python applications to interact with the C# grid core with near-zero latency.
* **Zero-Trust by Default:** The application runs in a restricted environment where every interaction with the outside world is governed by local grid policy.

## AuraCore Tech Showcased
* **MAS Lifecycle API:** Standardized startup, heartbeat, and shutdown hooks.
* **Local IPC Bridge:** Interaction with `/cell/config` and `/cell/membership` without external networking.
* **Python SDK Integration:** Demonstrates the ease of porting existing logic into a managed grid service.

## Evaluation Impact
This app proves the baseline stability of the AuraGrid runtime. It shows how quickly a company can wrap existing logic into a MAS and have it instantly benefit from AuraGrid's distributed observability and lifecycle management.
