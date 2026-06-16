# Architectural Decision Record: Tier 3 Evolution Trigger

## Context
During the design of the Tier 3 "Sovereign Ledger" application, it was discovered that the AuraGrid infrastructure lacked critical IPC routes for storage mutations and lease management. 

Specifically:
- `IStorageProvider` mutation methods (write, append, delete) were not exposed via the IPC Bridge.
- `ILeaseManager` was completely unexposed to MAS applications, preventing distributed locking and fencing.

## Decision
Following the `BLACK.md` methodology, we halted application development and implemented an **Evolution Trigger** in the AuraGrid core.

### Phase 1 Implementation:
1.  **C# IPC Bridge Upgrades:**
    - Updated `IpcRouteConstants.cs` with new storage and lease routes.
    - Enhanced `CellApiHandler.cs` to handle `POST` and `DELETE` requests for storage.
    - Integrated `ILeaseManager` into `CellApiHandler` to expose lease acquisition, renewal, and release.
2.  **Python SDK Upgrades:**
    - Expanded `storage_client.py` to support `write`, `append`, and `delete`.
    - Created `lease_client.py` to provide a high-level interface for lease management and fencing tokens.
    - Updated `grid_context.py` to expose the new `lease` client.

## Hypothesis
By exposing these low-level primitives, MAS applications can now implement complex distributed patterns (like the Sovereign Ledger) with full protection against split-brain scenarios using fencing tokens.

## Verification
- C# unit tests (`StorageIpcRouteTests`, `LeaseIpcRouteTests`) confirmed the IPC bridge correctly routes requests to the underlying providers.
- Python SDK tests (`test_storage_mutations`, `test_lease_client`) confirmed the SDK correctly communicates with the bridge.

## Next Steps
Proceed with Phase 2: Implementation of the "Sovereign Ledger" application.
