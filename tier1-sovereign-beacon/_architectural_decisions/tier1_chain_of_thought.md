# Tier 1 Chain of Thought — Sovereign Beacon
## AuraGrid Adversarial Evolution Log
### Session: 2026-04-26 | Node: workstation-node | Author: Black System Orchestrator

---

## Phase 0: Contract-Driven Design

### Intent
Validate the complete Tier 1 lifecycle of a CellSingleton Python MAS on the live grid.
The `sovereign-beacon` app is designed to probe:
- CellSingleton lease acquisition
- Cell configuration reads via the IPC bridge
- WAL-backed event publication to two topics
- ServiceProxy-reachable `get_status()` RPC method

### Hypothesis
A correctly-written Python MAS using `AsyncGridContext` and `@auragrid_service` decorators
will:
1. Deploy via `POST /api/deployments` after the catalog loader picks up the manifest
2. Start within ~10s as a CellSingleton, acquiring the lease
3. Successfully read cell configuration and publish lifecycle events to the WAL
4. Expose `SovereignBeacon.get_status` via the ServiceProxy at port 8088

### Execution — Phase 0 (Pre-Deployment)

**Step 1: Grid Probe**
- Management API: `http://localhost:7087/`
- Grid root: `C:\ProgramData\AuraCore\AuraGrid`
- Node ID: `workstation-node` (single-node, no other members)
- Existing catalog: `aurarouter-v2 v0.5.5`, `auraxlm v0.1.0`, `zreach v2.0.0`
- Active deployments: **none** (empty deployment list)
- Active services: **none**
- `api/mas/running`: **404 Not Found** — Observation #1 (see below)

**Step 2: Contract Tests**
All 21/21 Phase 0 contract validation tests passed:
- Service class decoration, method signatures, return type schema
- Manifest schema validation (CellSingleton, absolute WorkingDirectory, not in grid data dir)
- Event topic naming conventions (kebab-case, namespaced, separate channels)

**Step 3: Deployment Attempt**
`POST /api/deployments {"appId":"sovereign-beacon","version":"1.0.0"}` → **403 Forbidden**
Error: `"User does not have 'deployer' role"`

---

## Probing & Root Cause Analysis

### Investigation Thread 1: Governance Policy State

**Finding:** The `SharedFileSystemGovernancePolicy` initializes from `allow-lists.json` ONCE
at startup (`_initialized` bool flag). After initialization, no hot-reload exists.

**File on disk:** `C:\ProgramData\AuraCore\AuraGrid\governance\allow-lists.json`
Contains: `{"version": 1, "allowLists": {}, "userRoles": {"anonymous": ["admin"]}}`
→ `anonymous` user has `admin` role → `IsAdminAsync("anonymous")` should return `true`

**In-memory state:** `_userRoles` is EMPTY (roleCount defaults to 5 = the constant, not actual users)
`IsAdminAsync("anonymous")` returns `false` → falls through to deployer check → **403**

**Root cause:** The `allow-lists.json` on disk was modified AFTER the governance policy
initialized at grid startup. The in-memory `_userRoles` dictionary was populated from an
empty (or differently-structured) file, and there is no reload mechanism.

### Investigation Thread 2: Catalog Loader Non-Recursive Scan

**Finding:** `FileSystemCatalogLoader.LoadCatalogEntriesAsync` calls
`_storage.ListAsync("manifests", ct)` which is **non-recursive** (only immediate children).
The manifests directory structure is:
```
manifests/
  sovereign-beacon/         ← directory, filtered out
    1.0.0/                  ← directory, filtered out
      app.manifest.json     ← target file, NEVER reached
```
The loader only keeps entries whose path ends with `.manifest.json`. Since the immediate
children are subdirectories, zero manifest files are ever found.

**Consequence:** The `sovereign-beacon` app can never be added to the catalog by this loader.
The three apps already in the catalog (`aurarouter-v2`, `auraxlm`, `zreach`) must have been
populated by a different mechanism (likely manual catalog injection in a previous session, or
by the CatalogChannelReconciler with a now-disabled channel config).

### Investigation Thread 3: ManifestRetriever Ignores _manifestsRoot and manifestUri

**Finding:** `FileSystemManifestRetriever` stores `_manifestsRoot = options.Value.ManifestsRootPath ?? "manifests"`
but its `RetrieveAsync` method computes:
```csharp
var relativePath = $"{appId}/{version}/app.manifest.json";  // ← no _manifestsRoot prefix!
```
Both the `_manifestsRoot` field and the `manifestUri` parameter passed to `RetrieveAsync`
are completely ignored. The retriever always looks for the manifest at the ROOT of the
grid data directory: `C:\ProgramData\AuraCore\AuraGrid\{appId}\{version}\app.manifest.json`.

This conflicts with:
- The actual file placement convention: `manifests/{appId}/{version}/app.manifest.json`
- `GridRootConfiguration.GetManifestPath()` which uses `{ManifestsPath}/{appId}/{version}/manifest.json`
- The Dockerfile and Helm chart which configure `ManifestsRootPath` explicitly

### Observation: api/mas/running → 404

`GET /api/mas/running` returns 404 Not Found. The endpoint is documented and referenced in
example code but is not implemented in `ManagementApiHandler`. This is a missing feature or
documentation inconsistency.

---

## Result vs. Expectation

| Expectation | Result | Status |
|---|---|---|
| Grid is live and reachable | Confirmed at http://localhost:7087/ | ✅ |
| Governance permits anonymous admin | 403 — in-memory state stale | ❌ |
| Catalog loader finds sovereign-beacon | Not found — non-recursive scan | ❌ |
| Manifest retriever would find the file | Wrong path — missing manifestsRoot prefix | ❌ |
| api/mas/running endpoint works | 404 Not Found | ❌ |
| 21/21 Phase 0 contract tests pass | All tests green | ✅ |

---

## Evolution Triggers (filed below)

Three Evolution Proposals have been raised to the Architect. Development is HALTED until
the Architect approves the proposals and the framework fixes are implemented or waived.

See: `_architectural_decisions/evolution_proposals.md`
