# AuraGrid Evolution Proposals — Tier 1 Sovereign Beacon
## Raised: 2026-04-26 | Status: Awaiting Architect Approval

---

## EP-001: GovernancePolicy Has No Hot-Reload Mechanism
**Severity:** HIGH (blocks all deployments on a live node)
**Class:** Architectural Violation

### Problem
`SharedFileSystemGovernancePolicy` reads `allow-lists.json` exactly once at startup
and caches the result in `_userRoles` (an in-memory `ConcurrentDictionary`). The
`_initialized` bool flag is set to `true` after the first read and never reset.

If `allow-lists.json` is modified after the grid starts (by an admin, a previous
deployment, or a migration script), the in-memory RBAC state diverges from the
on-disk state. On the live `workstation-node`, `anonymous` has `admin` role on disk,
but the in-memory policy returns empty roles → all `POST /api/deployments` → 403.

### Affected File
`c:\projects\auracore\auragrid\src\AuraGrid.ProxyWorker\Governance\SharedFileSystemGovernancePolicy.cs`

### Proposed Fix
Add a `ReloadAsync()` method and call it:
- On any `UpdateAppAllowListAsync` / role-update write (already persists to disk; reload
  in the same call so the in-memory map stays in sync)
- Optionally: register a `FileSystemWatcher` on `allow-lists.json` for live reload

Minimal fix (no new dependencies):
```csharp
// Reset _initialized so EnsureInitializedAsync re-reads on next call
public async Task ReloadAsync(CancellationToken ct = default)
{
    await _lock.WaitAsync(ct);
    try
    {
        _userRoles.Clear();
        _allowLists.Clear();
        _initialized = false;
    }
    finally { _lock.Release(); }
    await EnsureInitializedAsync(ct);
}
```
And call `await ReloadAsync(ct)` at the end of `UpdateAppAllowListAsync`.

### Workaround (Non-Infrastructure)
Restart the AuraGrid.Node process. It will re-read `allow-lists.json` fresh. This is
a LOCAL, REVERSIBLE action on a single-node dev system. Requires Architect approval
because it terminates a running service.

---

## EP-002: FileSystemCatalogLoader Uses Non-Recursive Scan
**Severity:** CRITICAL (no new apps can be added to the catalog without restart AND
the scan is structurally broken — it finds zero files in a correctly-laid-out manifests dir)
**Class:** Architectural Violation

### Problem
`FileSystemCatalogLoader.LoadCatalogEntriesAsync` calls:
```csharp
await foreach (var entry in _storage.ListAsync(manifestsPath, cancellationToken))
```
`ListAsync` only returns **immediate children** (no recursion). The manifests directory
has the structure `{manifestsRoot}/{appId}/{version}/app.manifest.json`, so the immediate
children are app-id directories (e.g., `manifests/sovereign-beacon/`), not manifest files.
The filter `entry.Path.EndsWith(".manifest.json")` never matches a directory name.
**Result: Zero catalog entries are ever loaded from the manifests directory.**

The three apps in the current catalog were not loaded by this service.

### Affected File
`c:\projects\auracore\auragrid\src\AuraGrid.ProxyWorker\Deployment\FileSystemCatalogLoader.cs`

### Proposed Fix
Replace the flat `ListAsync` with a recursive walk:
```csharp
private async IAsyncEnumerable<string> FindManifestFilesAsync(
    string dir, [EnumeratorCancellation] CancellationToken ct)
{
    await foreach (var entry in _storage.ListAsync(dir, ct))
    {
        if (entry.IsDirectory)
        {
            await foreach (var child in FindManifestFilesAsync(entry.Path, ct))
                yield return child;
        }
        else if (entry.Path.EndsWith("app.manifest.json", StringComparison.OrdinalIgnoreCase))
        {
            yield return entry.Path;
        }
    }
}
```
Use this in `LoadCatalogEntriesAsync` instead of the flat `ListAsync` call.

### Workaround (Non-Infrastructure)
None without either (a) framework fix or (b) restarting the grid after this fix lands.

---

## EP-003: FileSystemManifestRetriever Ignores _manifestsRoot and manifestUri
**Severity:** CRITICAL (deployed apps will fail to start if their manifest is in the
standard `manifests/{appId}/{version}/` location)
**Class:** Architectural Violation

### Problem
`FileSystemManifestRetriever` stores `_manifestsRoot` but never uses it:
```csharp
// Stored but IGNORED:
_manifestsRoot = options.Value.ManifestsRootPath ?? "manifests";

// Always uses root-relative path:
var relativePath = $"{appId}/{version}/app.manifest.json";
```
The `manifestUri` parameter passed from the catalog entry is also completely ignored.

The retriever looks for manifests at `{gridRoot}/{appId}/{version}/app.manifest.json`
(e.g., `C:\ProgramData\AuraCore\AuraGrid\sovereign-beacon\1.0.0\app.manifest.json`)
rather than `{gridRoot}\manifests\{appId}\{version}\app.manifest.json`.

This contradicts:
- `GridRootConfiguration.GetManifestPath()` — uses `{ManifestsPath}/{appId}/{version}/`
- The Dockerfile: `ManifestsRootPath=/manifests`
- The Helm chart: `manifestsRootPath: /state/manifests`

### Affected File
`c:\projects\auracore\auragrid\src\AuraGrid.ProxyWorker\Deployment\FileSystemManifestRetriever.cs`

### Proposed Fix (Option A — use _manifestsRoot prefix, canonical)
```csharp
var relativePath = $"{_manifestsRoot}/{appId}/{version}/app.manifest.json";
```

### Proposed Fix (Option B — use manifestUri when provided)
```csharp
var relativePath = !string.IsNullOrEmpty(manifestUri)
    ? manifestUri   // catalog knows the exact path
    : $"{_manifestsRoot}/{appId}/{version}/app.manifest.json";
```

Option B is more flexible (supports custom manifest locations) and is backward-compatible
(existing catalog entries with a valid ManifestUri continue to work).

### Workaround (Non-Infrastructure)
Place the manifest at the ROOT level: `{gridRoot}/{appId}/{version}/app.manifest.json`.
This is a data placement workaround, not a code fix. Acceptable for single-node dev,
but violates the intended directory convention.

---

## EP-004: api/mas/running Endpoint Not Implemented (Documentation Bug)
**Severity:** LOW
**Class:** Minor Deviation

### Problem
`GET /api/mas/running` returns 404. The endpoint is referenced in `DeploymentExample.cs`,
code comments, and the sub-agent exploration report, but is not implemented in
`ManagementApiHandler.cs`.

### Proposed Fix
Either implement the endpoint (returning a list of `MasInstanceDto` from the
`ServiceDispatchRegistry`) or remove all references to it from documentation.

---

## Deployment Gate Decision

**Development is HALTED pending Architect decision on:**

| ID | Proposal | Blocking? | Estimated Effort |
|----|----------|-----------|-----------------|
| EP-001 | Governance hot-reload | YES (403 on all deploys) | 30 min |
| EP-002 | Catalog loader recursive scan | YES (catalog won't auto-load) | 30 min |
| EP-003 | ManifestRetriever path fix | YES (runtime manifest lookup fails) | 15 min |
| EP-004 | api/mas/running 404 | No | 1 hr |

**Architect Options:**
1. **Approve EP-001 fix + grid restart:** Unblocks governance. Still need EP-002/EP-003.
2. **Approve EP-001 + EP-002 + EP-003:** Full end-to-end fix. Rebuild AuraGrid.Node and restart.
3. **Approve workarounds only (no code changes):** Place manifest at root-level path, restart grid. Catalog manually registered via a one-off direct injection.
4. **Approve EP-001 + EP-002 + EP-003 + EP-004:** Full fix including the missing endpoint.

Awaiting Architect override to proceed.
