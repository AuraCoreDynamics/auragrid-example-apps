# Tier 4: Telemetry Torrent

This application pair (Client and Worker) is built in C# to stress-test the AuraGrid unbuffered HTTP/2 gRPC streaming path. It implements a bidirectional gRPC stream where the client continuously streams randomized payload chunks to the server as fast as possible, and the server yields immediate acknowledgment tokens (`ACKs`) back to the client.

## Core Objective

Validate the proxy's capability to route large, sustained streaming payloads without buffering them into memory, maintaining strict compliance with the unbuffered HTTP/2 proxy configuration.

## Key Scenarios Tested
- **Unbuffered gRPC:** Yielding ACKs on the response stream before the request stream completes.
- **YARP gRPC Reverse Proxy:** The torrent client routes through the main Grid proxy on `8088`, using `X-AuraGrid-IPC-Token`.
- **High Throughput:** Simulating heavy telemetry traffic.
