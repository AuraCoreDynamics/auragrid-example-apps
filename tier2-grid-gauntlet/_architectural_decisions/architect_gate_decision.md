# Tier 2 Architect Gate — Grid Gauntlet

## Summary
Five adversarial attack scenarios tested the AuraGrid control plane infrastructure built
in App-0 Mitigation Phase 2 (TG1–TG7). Four of five defenses held. One missing feature
(auto-tattle on dispatch failure) was identified and implemented as EP-005.

## Defense Matrix

| Attack | Target | Defense Held? | Evidence | Notes |
|--------|--------|:---:|---|---|
| False Tattle | TattleInvestigator | ✅ | `test_false_tattle_defense_holds` | Threshold + cooldown prevents false revocation |
| Lease Race | SqliteLeaseStore | ✅ | `test_lease_race_fencing_token_rejects_stale_bid` | WAL events don't bypass CAS |
| Stale Token | IPC Bridge | ✅ | `IpcBridge.cs` line ~125 (code review) | Server-side 409 on mismatch |
| Event Flood | WAL/Event Bus | ✅ | `test_event_flood_grid_remains_responsive` | No deadlock; rate limiting deferred to Tier 3 |
| Phantom Registration | Service Registry | ⚠️→✅ | `test_phantom_endpoint_triggers_tattle` | Fixed via EP-005 (auto-tattle) |

## Evolution Triggers Filed

| ID | Description | Status |
|----|-------------|--------|
| EP-005 | Auto-tattle on external dispatch failure | ✅ Implemented |
| EP-006 | Fencing token validation (confirmed existing) | ✅ No action needed |

## Test Counts

| Suite | Tests | Result |
|-------|-------|--------|
| C# (AuraGrid.slnx) | 1,428 | ✅ All pass |
| Sentinel contracts | 16 | ✅ All pass |
| Provocateur contracts | 13 | ✅ All pass |
| Scenario integration | 17 | ✅ All pass |
| **Total** | **1,474** | **✅ 0 failures** |

## Recommendation

**Advance to Tier 3** (Distributed State & Persistence). The control plane defenses are
sound. Key validations:
- Lease fencing prevents unauthorized acquisition
- Tattle system correctly handles false accusations
- Self-healing loop is now complete (dispatch failure → auto-tattle → investigation)
- WAL accepts high-volume writes without deadlock (rate limiting is Tier 3+ concern)

Open items for Tier 3:
- Live grid integration tests (re-run scenarios without mocks)
- WAL rate limiting / topic compaction under sustained load
- Cross-node dispatch auto-tattle (similar to EP-005 but for `CrossNodeServiceDispatcher`)
