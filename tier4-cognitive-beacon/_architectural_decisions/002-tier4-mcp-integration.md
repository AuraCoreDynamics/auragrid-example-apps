# Architectural Decision Record: Tier 4 Evolution & Comparative AI Routing

## Context
The Tier 4 application ("Cognitive Beacon") aims to validate the "Intelligence Layer" of AuraCore. This requires calling AuraXLM (the brain) from a MAS application running on AuraGrid (the OS). 

The architect (User) requested that the application perform a comparative test:
1. **Direct Routing:** Discover and call AuraXLM's MCP endpoint explicitly.
2. **Implicit Routing:** Call AuraRouter, which should then route the request to AuraXLM implicitly.

## Decision: Evolution Trigger
To enable direct routing, an **Evolution Trigger** was executed in the AuraGrid core:
- **Service Discovery IPC:** The `IServiceRegistry.DiscoverAsync` method was exposed via the IPC bridge (`/cell/registry/discover`).
- **Python SDK Update:** A new `RegistryClient` was added to the SDK to allow MAS applications to find other services by name.

## Dependency Authorization
Per `BLACK.md` Rule 3, the use of the official Anthropic `mcp` Python package is authorized for the MAS application. This avoids "cleanroom" reimplementation of a complex open standard.

## Hypothesis
- **Direct Path:** By discovering the `auraxlm-mas` endpoint, the MAS can establish a standard MCP connection.
- **Implicit Path:** By calling AuraRouter, the MAS leverages the grid-wide catalog and analyzer ranking to find the best expert model (which may be AuraXLM).
- **Equivalence:** Both paths should yield consistent results for the same capability request (e.g., a RAG query).

## Next Steps
Implement the `Cognitive Beacon` MAS and verify both routing paths.
