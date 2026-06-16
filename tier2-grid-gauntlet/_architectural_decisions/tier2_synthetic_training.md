# Tier 2 Synthetic Training Data — Grid Gauntlet

> Generated per `docs/prompts/adversarial_grid_evolution.md` Synthetic Training Mandate

---

## Scenario 1: False Tattle

### 1. Intent
Prove that the TattleInvestigator (built in App-0 TG6) correctly handles false accusations.
A malicious or buggy MAS should not be able to revoke a healthy service's lease by filing tattles.

### 2. Hypothesis
Filing TattleThreshold+1 reports against a healthy Sentinel MAS will trigger investigation.
The investigator will probe the Sentinel, find it healthy (responds to health check), enter
cooldown, and dismiss the tattles. The Sentinel's lease should remain intact.

### 3. Execution
- Provocateur calls `ctx.ipc.report_tattle("grid-gauntlet-sentinel", ...)` 5 times
- Waits 12 seconds (TattleInvestigationTimeout=10s + 2s buffer)
- Checks if Sentinel is still publishing lifecycle events (proves lease not revoked)

### 4. Result vs. Expectation
**Defense HELD** (in mocked test environment). Sentinel lifecycle events remain accessible
after tattle filing. The TattleInvestigator's threshold + cooldown mechanism prevents
false-positive revocation.

### 5. Mitigation/Evolution
No evolution needed. The defense architecture (threshold → investigate → probe → cooldown)
correctly protects against false tattle attacks. This validates TG6's design choice of
requiring N reports before triggering investigation rather than acting on single tattles.

---

## Scenario 2: Lease Race

### 1. Intent
Prove that the SqliteLeaseStore (TG3) and AuctionArbiter correctly reject competing bids
for a singleton lease that is already held by another MAS.

### 2. Hypothesis
Publishing a fake "lease_bid" event with an unrealistically high composite score to
system.service-state should NOT result in lease transfer. The auction system validates
at the lease store level (fencing token CAS), not just by score comparison.

### 3. Execution
- Provocateur publishes a lease_bid event with compositeScore=999.0 to system.service-state
- Waits 3 seconds for auction resolution
- Scans service-state events for any lease transfer to "provocateur-node"

### 4. Result vs. Expectation
**Defense HELD**. The WAL accepts the event (it's append-only), but the auction arbiter
never processes raw events as bid submissions. Bids flow through the `ILeaseManager`
interface with proper CAS validation. Publishing to a topic does NOT bypass the lease
acquisition protocol.

### 5. Mitigation/Evolution
No evolution needed. This validates a key architectural separation: the WAL is a log
(accepts all writes), but lease state mutations only occur through the `SqliteLeaseStore`
CAS operations. Event-based attacks cannot corrupt lease state.

---

## Scenario 3: Event Flood

### 1. Intent
Prove that the WAL-backed event bus (TG2) handles high-volume writes without deadlocking,
running out of memory, or starving other consumers.

### 2. Hypothesis
Publishing 1000 events in rapid succession to system.telemetry should succeed (WAL is
append-only and unbounded), and the grid should remain responsive afterward for both
event consumption and health checks.

### 3. Execution
- Provocateur publishes 1000 events to system.telemetry in tight loop (yielding every 100)
- After flood: attempts to consume from a different topic
- Checks if Sentinel lifecycle events are still accessible

### 4. Result vs. Expectation
**Defense HELD** (no crash/deadlock). The WAL accepts all events. Post-flood consumption
works correctly. However, this test runs with mocked infrastructure — a live grid test
would be needed to validate memory pressure under sustained load.

### 5. Mitigation/Evolution
Potential future evolution: WAL should implement per-topic rate limiting or backpressure
to prevent disk exhaustion under sustained flood. Current architecture relies on disk being
large enough and on topic compaction (not yet implemented). Flagged for Tier 3+ evaluation
with a live grid.

---

## Scenario 4: Stale Token Invoke

### 1. Intent
Prove that the service dispatch layer validates fencing tokens before executing method
invocations, preventing split-brain scenarios where a stale MAS instance could affect state.

### 2. Hypothesis
An invocation attempt with a fabricated fencing token should be rejected at the IPC bridge
layer with 409 Conflict. The actual method should NOT execute.

### 3. Execution
- Provocateur records current fencing token from environment
- Attempts to craft a service invocation with stale token (token=1)
- Notes: SDK auto-attaches the CURRENT token from env; cannot directly test stale path
  from application level

### 4. Result vs. Expectation
**Defense CONFIRMED EXISTING** — but not directly testable from SDK level.

Investigation of `IpcBridge.cs` confirmed: server validates `X-AuraGrid-Fencing-Token`
header before routing to CellApiHandler. Returns 409 on mismatch. This is the correct
security boundary: validation at the infrastructure layer, not the application layer.

The SDK's inability to test this directly is by design (defense-in-depth: the SDK should
not be able to bypass fencing).

### 5. Mitigation/Evolution
EP-006 filed as CONFIRMED EXISTING. No code change needed. The evolution trigger in the
Provocateur is reclassified as a "documentation validation" — it proves the SDK correctly
delegates security to the server.

---

## Scenario 5: Phantom Registration

### 1. Intent
Prove that the grid's self-healing mechanisms detect and clean up phantom service endpoints
(registered but unreachable) via the tattle system.

### 2. Hypothesis
Registering a service endpoint at a non-existent port should succeed (registration is
permissive), but dispatch attempts should fail gracefully (timeout, not hang). The dispatch
failure should automatically emit a tattle event, triggering the TattleInvestigator to
eventually revoke the phantom.

### 3. Execution
- Provocateur publishes endpoint_registered event for PhantomService at port 59999
- Waits 5 seconds for potential dispatch and tattle
- Scans system.telemetry for tattle events mentioning the phantom service
- Publishes endpoint_unregistered for cleanup

### 4. Result vs. Expectation
**Defense PARTIALLY HELD** → Evolution Trigger (EP-005).

Initial finding: `ExternalServiceDispatcher` did NOT emit tattle events on dispatch failure.
It only logged warnings and returned 502. The TattleInvestigator existed but had no input
source from the dispatch layer.

After EP-005 fix: dispatch failures now emit tattle events to `WalTopics.Telemetry`,
enabling the self-healing loop:
```
Dispatch failure → Auto-tattle → TattleInvestigator → Investigation → Revocation
```

### 5. Mitigation/Evolution
EP-005 IMPLEMENTED: `ExternalServiceDispatcher` now injects `IEventPublisher` and emits
tattle events on both HttpRequestException and TaskCanceledException (timeout) paths.
The self-healing loop is now complete for external MAS dispatch failures.
