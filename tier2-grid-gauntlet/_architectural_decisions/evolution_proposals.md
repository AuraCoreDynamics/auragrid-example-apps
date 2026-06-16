# AuraGrid Evolution Proposals — Tier 2 Grid Gauntlet
## Raised: 2026-04-30 | Status: RESOLVED

---

## EP-005: Auto-Tattle on External Dispatch Failure
**Severity:** MEDIUM (self-healing incomplete without it)
**Class:** Missing Feature
**Status:** ✅ IMPLEMENTED

### Problem
`ExternalServiceDispatcher` and `CrossNodeServiceDispatcher` only logged warnings when dispatch
to a MAS endpoint failed (HttpRequestException, timeout). No tattle event was emitted to
`system.telemetry`, meaning the `TattleInvestigator` (built in TG6) could never detect
unreachable services automatically.

The tattle infrastructure existed (TattleInvestigator reads from WalTopics.Telemetry) but
there was no code in the dispatch pipeline that PUBLISHED tattle events. The only emission
point was the Python SDK's `report_tattle()` — requiring callers to manually report failures.

### Affected File
`src/AuraGrid.ProxyWorker/Proxy/ExternalServiceDispatcher.cs`

### Fix Applied
Injected `IEventPublisher` and `IOptions<ProxyWorkerOptions>` into `ExternalServiceDispatcher`.
Added `EmitTattleAsync(masId, detail)` private method that publishes to `WalTopics.Telemetry`
on dispatch failure (both HttpRequestException and TaskCanceledException/timeout paths).

Tattle emission is fire-and-forget with exception swallowing (tattle failure must not mask
the dispatch error being returned to the caller).

### Validation
- All 1428 existing tests pass (constructor updated in 6 test files)
- Tattle emission tested indirectly via `FakeEventPublisher` in existing dispatch tests

---

## EP-006: Fencing Token Validated at IPC Bridge (CONFIRMED EXISTING)
**Severity:** N/A (already implemented)
**Class:** False Positive — defense exists
**Status:** ✅ CONFIRMED

### Finding
The Provocateur's `stale_invoke` attack identified that the Python SDK cannot test fencing
validation from the application level. Investigation confirmed the defense EXISTS:

`IpcBridge.cs` (line ~125):
```csharp
var fencingHeader = ctx.Request.Headers["X-AuraGrid-Fencing-Token"];
if (fencingHeader is not null && FencingToken is not null
    && fencingHeader != FencingToken)
{
    ctx.Response.StatusCode = 409; // Conflict — stale fencing token
    ctx.Response.Close();
    return;
}
```

The stale_invoke evolution_trigger flag in the Provocateur is a documentation artifact:
it notes that the SDK cannot independently verify server-side fencing, which is expected
behavior (security validation must be server-side).

### Resolution
No code change needed. Updated scenario test to document this as a design validation
rather than a missing feature.

---

## Summary

| ID | Proposal | Status | Effort |
|----|----------|--------|--------|
| EP-005 | Auto-tattle on dispatch failure | ✅ Implemented | 15 min |
| EP-006 | Fencing token validation | ✅ Confirmed existing | 0 (investigation only) |
