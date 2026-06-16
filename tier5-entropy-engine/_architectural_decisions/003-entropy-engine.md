# Architectural Decision Record: Tier 5 Chaos & Fault Injection

## Context
To reach Tier 5 ("Chaos Engineering"), the AuraGrid platform required the ability to simulate catastrophic infrastructure failures from within a Managed Application Service (MAS). Standard MAS isolation prevents such destructive actions.

## Decision: The Chaos Management API
We implemented a privileged **Chaos Management API** to allow authorized adversarial applications (like the Entropy Engine) to trigger faults.

### Infrastructure Evolution:
1.  **IChaosManager Abstraction:** Defined in `AuraGrid.Abstractions`. Provides methods to:
    - Suspend SWIM Gossip (simulate node death).
    - Inject Network Latency/Faults (simulate partitions/congestion).
    - Trigger Storage Failures (simulate disk/shared filesystem outages).
2.  **Cross-Cutting Instrumentation:**
    - **SWIM Protocol:** Instrumented to check for suspension before heartbeat rounds.
    - **Service Dispatcher:** Instrumented to inject latency or return 500s based on node-specific fault rules.
    - **Storage Provider:** Instrumented to throw `IOExceptions` on mutations when storage chaos is active.
3.  **Python SDK expansion:** Added `ChaosClient` to provide a high-level API for MAS applications.

## Synthetic Training Data: Split-Brain Recovery
During the implementation of the Entropy Engine, we captured the sequence of events required to recover from a "Split-Brain" partition:
1. **Detection:** Healthy nodes detect missing heartbeats (SWIM Suspect -> Dead).
2. **Isolation:** The Entropy Engine triggers `isolate_node()`.
3. **Failover:** Singleton leases are released (or expired) and re-auctioned.
4. **Fencing:** The newly implement storage fencing tokens (Tier 3) reject any "zombie" writes from the isolated node once the partition heals.

## Technical Debt & Refinements
- **Test Compatibility:** Updated the `CellApiHandler` constructor to make `IOptions` and other providers optional/nullable, ensuring backward compatibility with 20+ existing C# unit tests while allowing for easy injection of the new `IChaosManager`.
- **MCP Package Refinement:** In the Tier 4 Beacon app, a custom `call_mcp_http` helper was implemented to ensure protocol stability regardless of the specific `mcp` package version installed in the environment.

## Next Steps
This concludes the 5-tier adversarial evolution of AuraGrid. The platform is now hardened against intelligence routing, distributed state corruption, and catastrophic failure scenarios.
