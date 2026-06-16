# AuraGrid Tier 2 — Adversarial Grid Gauntlet

> **Generated from**: `docs/prompts/adversarial_grid_evolution.md`, `app-examples/tier1-sovereign-beacon/_architectural_decisions/evolution_proposals.md`, App-0 Mitigation Phase 2 (TG1–TG7) implementation, `CLAUDE.md`
> **Baseline**: 1428 tests (1373 ProxyWorker + 55 Installer), 0 failures, 0 build errors. Tier 1 sovereign-beacon deployed (offline). All 4 EPs resolved.
> **Execution model**: 4 phases with parallel-sequential execution. Phase 1 creates both MAS apps in parallel. Phase 2 implements adversarial scenarios. Phase 3 fixes any grid bugs discovered. Phase 4 integrates and validates.
> **Convention**: Each task group is a self-contained agentic prompt. Feed the group text + `CLAUDE.md` to the agent. Groups within the same phase may execute in parallel.

---

## Motivation

Tier 1 (sovereign-beacon) validated the **singleton lifecycle** and exposed 4 framework bugs (all now fixed). Tier 2 escalates to **inter-service adversarial testing** — two MAS apps probe the new control plane infrastructure built in App-0 Mitigation Phase 2:

| Infrastructure | Built In | Adversarial Target |
|---|---|---|
| SQLite Service Registry | TG3 | Lease fencing, stale writes, concurrent access |
| Lease-Based Consensus | TG4 | Split-brain, leader preemption, token monotonicity |
| ControlPlaneManager | TG5 | ManagementMas failover, Channel saturation |
| Node Tattle | TG6 | False accusations, threshold gaming, cooldown bypass |
| MAS Appraisal | TG6 | Threshold boundary, incumbent displacement |

The app pair:
- **Sentinel** — A defensive MAS that monitors its own lease, watches for revocation, and validates invariants (fencing tokens monotonically increase, lease state matches WAL events, service discovery returns correct endpoints).
- **Provocateur** — An offensive MAS that intentionally misbehaves: files false tattles, races for leases, publishes conflicting events, and attempts to invoke services with stale fencing tokens.

Together they form a **closed-loop adversarial test harness** that either proves the grid's defenses or exposes Evolution Triggers requiring framework fixes.

---

## Execution Topology

```
PHASE 1 (Parallel):     [TG1: Sentinel MAS]         [TG2: Provocateur MAS]
                              │                            │
                              └────────────┬───────────────┘
                                           ▼
PHASE 2 (Sequential):       [TG3: Adversarial Scenario Tests]
                                           │
                                           ▼
PHASE 3 (Conditional):      [TG4: Evolution Proposals & Grid Fixes]
                                           │
                                           ▼
PHASE 4 (Sequential):       [TG5: Integration & Validation]
```

**Phase 1**: Both MAS apps are independent Python applications. Each has its own directory, manifest, and Phase 0 contract tests. No shared state — they discover each other only through the grid.
**Phase 2**: Depends on both Phase 1 apps. Implements the adversarial scenario matrix. Tests are primarily Python `pytest` integration tests that orchestrate both apps via the SDK.
**Phase 3**: CONDITIONAL — only executes if Phase 2 discovers grid bugs. Produces Evolution Proposals following BLACK.md schema. May modify AuraGrid C# source.
**Phase 4**: Full suite validation. Verifies all existing 1428 C# tests still pass. Runs Python scenario tests. Updates CHANGELOG. Produces synthetic training data.

---

## Shared File Conflict Map

| File | Modified By | Strategy |
|------|-------------|----------|
| `app-examples/tier2-grid-gauntlet/` | TG1, TG2 | Each owns a subdirectory (sentinel/, provocateur/) |
| `app-examples/tier2-grid-gauntlet/tests/` | TG3 only | Direct modification |
| `app-examples/tier2-grid-gauntlet/_architectural_decisions/` | TG3, TG4, TG5 | Append-only |
| `src/AuraGrid.ProxyWorker/**` | TG4 only | Only if evolution triggers fire |
| `CHANGELOG.md` | TG5 only | Final assembly |

---

## Task Group 1: Sentinel MAS (Python MAS Development)

### Agent Profile

You are a **Python MAS developer** specializing in AuraGrid distributed applications and defensive monitoring patterns. You are working on AuraGrid, a federated compute fabric with SQLite-backed service registry and lease-based consensus. Read `CLAUDE.md` before starting — it contains all project conventions, constraints, and patterns you must follow.

### Context

The Sentinel is a CellSingleton MAS that validates grid infrastructure invariants from the inside. Unlike sovereign-beacon (which just confirms basic lifecycle), Sentinel actively monitors:

1. **Lease health**: Watches its own lease via `WatchSingletonAsync` events, verifies fencing token monotonicity
2. **Service discovery**: Registers an endpoint, queries the registry to confirm visibility, watches for phantom entries
3. **Event integrity**: Subscribes to `system.service-state` and `system.consensus` topics, validates event ordering and payload schema
4. **Tattle defense**: Detects when tattles are filed against it, logs them as evidence

The Sentinel exposes RPC methods that the Provocateur (and integration tests) can call to query its observed state.

### Files to Read Before Starting

1. `app-examples/tier1-sovereign-beacon/app.py` — Tier 1 MAS pattern (decorators, AsyncGridContext, event publishing)
2. `src/AuraGrid.PythonSdk/auragrid/__init__.py` — SDK public API surface
3. `src/AuraGrid.PythonSdk/auragrid/grid_context.py` — GridContext properties and sub-client access
4. `src/AuraGrid.PythonSdk/auragrid/event_client.py` — Event publish/consume API
5. `src/AuraGrid.PythonSdk/auragrid/ipc.py` — IPC client including `report_tattle`
6. `app-examples/tier1-sovereign-beacon/tests/test_contract.py` — Phase 0 test style

### Constraints

- Do **NOT** modify the AuraGrid Python SDK (`src/AuraGrid.PythonSdk/`)
- Do **NOT** modify any C# source code
- Do **NOT** add dependencies beyond `auragrid`, `pytest`, `structlog` (already available)
- The Sentinel must be a **CellSingleton** (exactly one instance per cell)
- All grid calls must be non-fatal — log failures as evolution triggers, never crash
- Use `structlog` for structured logging (chain-of-thought capture)

### Banned Patterns (DO NOT USE)

- ✗ `import time; time.sleep(...)` — Use `asyncio.sleep()` or `asyncio.wait_for()`
- ✗ Hardcoded ports or node IDs — Read from `AURAGRID_*` environment variables
- ✗ Direct HTTP calls to the management API — Use SDK clients exclusively
- ✗ `try: ... except Exception: pass` — Log ALL exceptions for chain-of-thought
- ✗ Global mutable state — Use instance attributes on the service class

### Tasks

#### T1.1: Create Project Structure

```
app-examples/tier2-grid-gauntlet/
├── sentinel/
│   ├── app.py
│   ├── requirements.txt
│   ├── app.manifest.json
│   └── invariants.py        # Invariant checker logic
├── provocateur/             # (TG2 creates this)
├── tests/                   # (TG3 creates this)
├── _architectural_decisions/
│   └── tier2_design.md
└── README.md
```

Create `requirements.txt`:
```
auragrid>=0.1.0
structlog>=24.0.0
```

Create `app.manifest.json` for Sentinel:
```json
{
  "appId": "grid-gauntlet-sentinel",
  "version": "1.0.0",
  "displayName": "Grid Gauntlet — Sentinel",
  "description": "Defensive MAS that validates grid infrastructure invariants",
  "lifecycle": "CellSingleton",
  "entryPoint": {
    "type": "python",
    "command": "python app.py"
  },
  "workingDirectory": "app-examples/tier2-grid-gauntlet/sentinel",
  "resourceRequirements": {
    "memoryMb": 128,
    "cpuMillicores": 100
  }
}
```

#### T1.2: Implement Invariant Checker Module

Create `sentinel/invariants.py` — a stateful invariant tracker:

```python
@dataclass
class InvariantViolation:
    invariant: str          # e.g., "fencing_token_monotonic"
    expected: str
    observed: str
    timestamp: datetime
    evidence: dict          # raw event/response data

class InvariantChecker:
    """Tracks and validates grid infrastructure invariants."""
    
    def __init__(self):
        self._violations: list[InvariantViolation] = []
        self._last_fencing_token: int | None = None
        self._observed_events: list[dict] = []
        self._tattle_evidence: list[dict] = []
    
    def check_fencing_token(self, new_token: int) -> bool:
        """Invariant: fencing tokens are strictly monotonically increasing."""
        ...
    
    def check_event_ordering(self, topic: str, seq: int) -> bool:
        """Invariant: event sequence numbers are monotonically increasing per topic."""
        ...
    
    def record_tattle_against_us(self, tattle_event: dict) -> None:
        """Evidence collection: record when someone tattles on us."""
        ...
    
    @property
    def violations(self) -> list[InvariantViolation]:
        return list(self._violations)
    
    @property
    def is_healthy(self) -> bool:
        return len(self._violations) == 0
```

#### T1.3: Implement Sentinel Service

Create `sentinel/app.py`:

```python
@auragrid_service(
    name="GridGauntletSentinel",
    description="Defensive MAS that monitors lease health, service discovery, and event integrity."
)
class SentinelService:
    def __init__(self):
        self._checker = InvariantChecker()
        self._start_time = datetime.now(timezone.utc)
        self._observation_log: list[dict] = []
    
    @auragrid_method(description="Returns all observed invariant violations")
    def get_violations(self) -> dict:
        ...
    
    @auragrid_method(description="Returns current sentinel health and observation count")
    def get_status(self) -> dict:
        ...
    
    @auragrid_method(description="Returns evidence of tattles filed against this sentinel")
    def get_tattle_evidence(self) -> dict:
        ...
    
    @auragrid_method(description="Explicitly trigger an invariant check cycle")
    def run_check_cycle(self) -> dict:
        ...
```

Main loop behavior:
1. On startup: register endpoint, confirm discovery via service registry
2. Every 5s: consume `system.service-state` events, validate ordering
3. Every 10s: consume `system.consensus` events, verify leader stability
4. Every 15s: check own lease via context, verify fencing token progression
5. On any invariant violation: log structured evidence, increment violation counter

#### T1.4: Create Phase 0 Contract Tests

Create `sentinel/tests/__init__.py` and `sentinel/tests/test_contract.py`:

Tests to write:
- Service class has `@auragrid_service` decorator with correct name
- All `@auragrid_method` decorated methods return `dict`
- `InvariantChecker.check_fencing_token` detects non-monotonic tokens
- `InvariantChecker.check_event_ordering` detects out-of-order sequences
- Manifest JSON is valid and specifies CellSingleton lifecycle
- No hardcoded ports, IPs, or node IDs in source (regex scan)

#### T1.Final: Blast Radius Updates

1. Create `app-examples/tier2-grid-gauntlet/README.md` with app description
2. Create `app-examples/tier2-grid-gauntlet/_architectural_decisions/tier2_design.md` documenting the Sentinel/Provocateur adversarial model

### Success Criteria

- [ ] `pytest sentinel/tests/ -x -q` — all contract tests pass
- [ ] `InvariantChecker.check_fencing_token(5)` then `check_fencing_token(3)` → violation recorded
- [ ] `InvariantChecker.check_event_ordering("topic", 5)` then `check_event_ordering("topic", 3)` → violation recorded
- [ ] `app.manifest.json` validates: lifecycle=CellSingleton, entryPoint.type=python
- [ ] No `import time` or hardcoded `localhost` in any `.py` file
- [ ] `SentinelService` has at least 4 `@auragrid_method` decorated methods

### Produces / Consumes

- **Produces**: `sentinel/` directory with `app.py`, `invariants.py`, manifest, tests → consumed by TG3
- **Consumes**: Nothing from other groups (uses SDK only)

---

## Task Group 2: Provocateur MAS (Python MAS Development)

### Agent Profile

You are a **Python MAS developer** specializing in chaos engineering and adversarial testing of distributed systems. You are working on AuraGrid, a federated compute fabric. Your job is to build a MAS that intentionally misbehaves to probe grid defenses. Read `CLAUDE.md` before starting.

### Context

The Provocateur is a CellSingleton MAS that acts as a controlled adversary. It does NOT randomly break things — it executes a defined **attack playbook** of scenarios that test specific grid defense mechanisms:

| Attack | Target Infrastructure | Expected Defense |
|---|---|---|
| False Tattle | TattleInvestigator | Cooldown after healthy investigation |
| Lease Race | SqliteLeaseStore | Fencing token CAS rejection |
| Stale Token Invoke | ServiceProxy | 403/409 on stale fencing token |
| Event Flood | WAL/Event Bus | Backpressure or rate limiting |
| Phantom Registration | IServiceRegistry | Endpoint health validation |

The Provocateur is NOT malware — it's a structured test harness. Each attack is:
1. Announced (publishes intent to its own topic)
2. Executed with a timeout
3. Recorded (success/failure of the DEFENSE, not the attack)

### Files to Read Before Starting

1. `app-examples/tier1-sovereign-beacon/app.py` — Base MAS pattern
2. `src/AuraGrid.PythonSdk/auragrid/ipc.py` — `report_tattle()` method
3. `src/AuraGrid.PythonSdk/auragrid/event_client.py` — Event publish/consume
4. `src/AuraGrid.PythonSdk/auragrid/grid_context.py` — Context sub-clients
5. `app-examples/tier2-grid-gauntlet/sentinel/app.py` — The target of some attacks (if available)

### Constraints

- Do **NOT** modify the AuraGrid Python SDK
- Do **NOT** modify any C# source code
- Do **NOT** use raw HTTP requests — all attacks go through the SDK IPC bridge
- Do **NOT** attempt filesystem manipulation or process injection
- Attacks must be **idempotent and reversible** — no permanent grid corruption
- Each attack must have a **timeout** (max 30s) and a **cleanup** step
- All attacks must be **opt-in** — controlled by an attack playbook config, not automatic on startup

### Banned Patterns (DO NOT USE)

- ✗ `os.system()`, `subprocess.run()` — No shell escape
- ✗ `open("/path/to/grid/file", "w")` — No direct filesystem writes to grid data
- ✗ Infinite retry loops without backoff
- ✗ `socket.connect()` — No raw socket operations, SDK only
- ✗ `threading.Thread` — Use `asyncio` exclusively

### Tasks

#### T2.1: Create Project Structure

```
app-examples/tier2-grid-gauntlet/
├── provocateur/
│   ├── app.py
│   ├── requirements.txt
│   ├── app.manifest.json
│   ├── playbook.py          # Attack scenario definitions
│   ├── attacks/
│   │   ├── __init__.py
│   │   ├── false_tattle.py
│   │   ├── lease_race.py
│   │   ├── stale_invoke.py
│   │   ├── event_flood.py
│   │   └── phantom_registration.py
│   └── tests/
│       └── test_contract.py
└── ...
```

Create `app.manifest.json`:
```json
{
  "appId": "grid-gauntlet-provocateur",
  "version": "1.0.0",
  "displayName": "Grid Gauntlet — Provocateur",
  "description": "Controlled adversary MAS for testing grid defense mechanisms",
  "lifecycle": "CellSingleton",
  "entryPoint": {
    "type": "python",
    "command": "python app.py"
  },
  "workingDirectory": "app-examples/tier2-grid-gauntlet/provocateur",
  "resourceRequirements": {
    "memoryMb": 256,
    "cpuMillicores": 200
  }
}
```

#### T2.2: Define Attack Playbook Schema

Create `provocateur/playbook.py`:

```python
@dataclass
class AttackResult:
    attack_name: str
    target: str                    # Infrastructure component targeted
    started_at: datetime
    completed_at: datetime
    defense_held: bool             # True = grid defended correctly
    expected_behavior: str         # What the grid SHOULD do
    observed_behavior: str         # What actually happened
    evidence: dict                 # Raw responses/events
    evolution_trigger: bool        # True = grid bug found

@dataclass  
class AttackScenario:
    name: str
    description: str
    target_infrastructure: str
    expected_defense: str
    timeout_seconds: float = 30.0
    enabled: bool = True

class AttackPlaybook:
    """Orchestrates attack scenarios in sequence with logging."""
    
    def __init__(self):
        self._scenarios: list[AttackScenario] = []
        self._results: list[AttackResult] = []
    
    def register(self, scenario: AttackScenario, executor: Callable) -> None: ...
    async def execute_all(self, ctx: AsyncGridContext) -> list[AttackResult]: ...
    async def execute_one(self, name: str, ctx: AsyncGridContext) -> AttackResult: ...
```

#### T2.3: Implement Attack — False Tattle

Create `provocateur/attacks/false_tattle.py`:

**Scenario**: File multiple tattle reports against the healthy Sentinel MAS.
**Expected Defense**: TattleInvestigator probes Sentinel, finds it healthy, enters cooldown. Sentinel's lease is NOT revoked.
**Validation**: After attack, call `Sentinel.get_status()` — it should still respond. Call `Sentinel.get_tattle_evidence()` — it should show evidence of investigation.

```python
async def execute_false_tattle(ctx: AsyncGridContext, target_mas_id: str) -> AttackResult:
    """File N tattle reports against a healthy MAS. Grid should investigate and dismiss."""
    # 1. Announce attack intent
    # 2. File TattleThreshold + 1 reports via ctx.ipc.report_tattle()
    # 3. Wait for investigation window (TattleInvestigationTimeout + buffer)
    # 4. Attempt to invoke target — should succeed (lease not revoked)
    # 5. Record result
```

#### T2.4: Implement Attack — Lease Race

Create `provocateur/attacks/lease_race.py`:

**Scenario**: Attempt to acquire the Sentinel's singleton lease while Sentinel holds it.
**Expected Defense**: SqliteLeaseStore rejects via fencing token CAS. Auction arbiter rejects (singleton already leased).
**Validation**: Provocateur's acquisition attempt returns `false` / error. Sentinel's fencing token unchanged.

```python
async def execute_lease_race(ctx: AsyncGridContext, target_mas_id: str) -> AttackResult:
    """Attempt to acquire a lease already held by another MAS."""
    # 1. Query current lease state for target_mas_id (via events)
    # 2. Publish a fake bid event to system.service-state
    # 3. Wait for auction resolution
    # 4. Verify: Sentinel still holds lease, our bid was rejected
```

#### T2.5: Implement Attack — Event Flood

Create `provocateur/attacks/event_flood.py`:

**Scenario**: Publish 1000 events to `system.telemetry` in rapid succession.
**Expected Defense**: Events are accepted (WAL is append-only) but TattleInvestigator handles them without OOM or deadlock.
**Validation**: Grid remains responsive. Sentinel can still publish/consume events. No memory growth explosion in grid metrics.

```python
async def execute_event_flood(ctx: AsyncGridContext) -> AttackResult:
    """Flood system.telemetry with high-volume events."""
    # 1. Publish 1000 telemetry events in tight loop
    # 2. After flood: verify grid health endpoint responds
    # 3. Verify Sentinel's event consumption still works
    # 4. Check metrics for memory anomalies
```

#### T2.6: Implement Attack — Stale Token Invoke

Create `provocateur/attacks/stale_invoke.py`:

**Scenario**: Invoke a service method with an explicitly stale/fabricated fencing token.
**Expected Defense**: ServiceProxy or IPC bridge rejects the call with 403/409.
**Validation**: Response is an error (not success). No side effects executed.

```python
async def execute_stale_invoke(ctx: AsyncGridContext, target_service: str) -> AttackResult:
    """Attempt service invocation with a stale fencing token."""
    # 1. Store current fencing token
    # 2. Manually override AURAGRID_FENCING_TOKEN env var (or craft raw request)
    # 3. Attempt to invoke Sentinel.get_status() with stale token
    # 4. Verify: rejected (403/409) or accepted (evolution trigger!)
```

#### T2.7: Implement Attack — Phantom Registration

Create `provocateur/attacks/phantom_registration.py`:

**Scenario**: Register a service endpoint pointing to a non-existent port.
**Expected Defense**: Service discovery returns the endpoint BUT dispatching to it fails gracefully (timeout, not hang). Tattle auto-filed.
**Validation**: Registration succeeds (it should). Dispatch attempt → graceful failure. Eventually the phantom is cleaned up or reported.

```python
async def execute_phantom_registration(ctx: AsyncGridContext) -> AttackResult:
    """Register a fake service endpoint to test discovery integrity."""
    # 1. Register endpoint at port 59999 (nothing listening)
    # 2. Query service discovery — verify phantom appears
    # 3. Attempt dispatch to phantom — verify graceful failure (not hang)
    # 4. Wait and verify: does tattle system eventually detect it?
    # 5. Cleanup: unregister phantom
```

#### T2.8: Create Phase 0 Contract Tests

Create `provocateur/tests/test_contract.py`:

Tests:
- Service class has `@auragrid_service` with correct name
- `AttackPlaybook` can register and list scenarios
- `AttackResult` dataclass serializes to JSON
- Each attack module has an `execute_*` async function
- Manifest JSON is valid CellSingleton
- No `os.system`, `subprocess`, or raw `socket` usage (safety scan)
- All attack functions accept `AsyncGridContext` as first parameter

#### T2.Final: Blast Radius Updates

1. Update `README.md` with Provocateur attack catalog
2. Add to `_architectural_decisions/tier2_design.md`: attack/defense matrix

### Success Criteria

- [ ] `pytest provocateur/tests/ -x -q` — all contract tests pass
- [ ] Each attack module exports exactly one `execute_*` async function
- [ ] `AttackPlaybook.execute_all()` respects `enabled` flag and `timeout_seconds`
- [ ] No `os.system`, `subprocess`, or `socket` imports in any attack module
- [ ] Each attack has documented `expected_defense` and `evolution_trigger` logic
- [ ] Manifest validates: lifecycle=CellSingleton, separate appId from Sentinel

### Produces / Consumes

- **Produces**: `provocateur/` directory with attacks, playbook, manifest, tests → consumed by TG3
- **Consumes**: Sentinel's service name (`GridGauntletSentinel`) and MAS ID (`grid-gauntlet-sentinel`) for targeting

---

## Task Group 3: Adversarial Scenario Tests (Integration Testing)

### Agent Profile

You are an **integration test engineer** specializing in distributed systems adversarial testing. You write pytest-based scenario tests that orchestrate multiple MAS applications through the AuraGrid Python SDK. Read `CLAUDE.md` before starting.

### Context

Phase 1 produced two MAS apps: Sentinel (defensive monitor) and Provocateur (controlled adversary). Phase 2 creates the integration test harness that:

1. Simulates both apps' behavior WITHOUT requiring a live grid (mock the IPC bridge)
2. Validates the attack/defense interaction model
3. Produces a structured test report indicating which defenses held and which are Evolution Triggers

The tests are structured as **scenario-based integration tests**. Each scenario:
- Sets up mock grid state (lease store entries, event streams)
- Executes one Provocateur attack
- Asserts on Sentinel's observed invariants
- Classifies result: DEFENSE_HELD or EVOLUTION_TRIGGER

### Files to Read Before Starting

1. `app-examples/tier2-grid-gauntlet/sentinel/app.py` — Sentinel service
2. `app-examples/tier2-grid-gauntlet/sentinel/invariants.py` — Invariant checker
3. `app-examples/tier2-grid-gauntlet/provocateur/app.py` — Provocateur service
4. `app-examples/tier2-grid-gauntlet/provocateur/playbook.py` — Attack definitions
5. `app-examples/tier2-grid-gauntlet/provocateur/attacks/*.py` — Attack implementations
6. `src/AuraGrid.PythonSdk/tests/` — SDK test patterns (if available)

### Constraints

- Do **NOT** modify Sentinel or Provocateur source (TG1/TG2 artifacts)
- Do **NOT** require a running AuraGrid instance — mock the IPC layer
- Do **NOT** add dependencies beyond `pytest`, `pytest-asyncio`, `respx` (HTTP mocking)
- Tests must be **deterministic** — no timing-dependent assertions without explicit waits
- Each test must clean up any state it creates

### Banned Patterns (DO NOT USE)

- ✗ `time.sleep()` in tests — Use `pytest-asyncio` with controlled event loops
- ✗ Mocking internal SDK implementation details — Mock at the HTTP boundary only
- ✗ Tests that pass trivially (assert True, empty body)
- ✗ Shared mutable test state between test functions

### Tasks

#### T3.1: Create Test Infrastructure

Create `tests/conftest.py`:

```python
import pytest
import respx
from httpx import Response

@pytest.fixture
def mock_grid():
    """Provides a mock AuraGrid IPC bridge for both apps."""
    with respx.mock(base_url="http://localhost:5100") as mock:
        # Default health endpoint
        mock.get("/api/health").mock(return_value=Response(200, json={"status": "healthy"}))
        yield mock

@pytest.fixture
def sentinel_service():
    """Instantiates SentinelService for direct unit interaction."""
    from sentinel.app import SentinelService
    return SentinelService()

@pytest.fixture
def attack_playbook():
    """Instantiates a fresh AttackPlaybook with all attacks registered."""
    from provocateur.playbook import AttackPlaybook
    return AttackPlaybook()
```

#### T3.2: Scenario — False Tattle Defense

Create `tests/test_scenario_false_tattle.py`:

```python
@pytest.mark.asyncio
async def test_false_tattle_defense_holds(mock_grid, sentinel_service):
    """
    SCENARIO: Provocateur files TattleThreshold+1 tattles against healthy Sentinel.
    EXPECTED: Grid investigates, finds Sentinel healthy, enters cooldown.
              Sentinel's lease is NOT revoked. Service remains callable.
    """
    # Setup: Mock tattle endpoint accepts reports
    # Setup: Mock service invoke endpoint (Sentinel responds healthy)
    # Execute: Call false_tattle attack
    # Assert: Sentinel.get_status() still returns active
    # Assert: Sentinel.get_tattle_evidence() shows investigation occurred
    # Assert: attack result.defense_held == True

@pytest.mark.asyncio
async def test_false_tattle_cooldown_prevents_repeated_investigation(mock_grid):
    """
    SCENARIO: After cooldown from first investigation, more tattles are ignored.
    EXPECTED: No second investigation within TattleCooldownPeriod.
    """
```

#### T3.3: Scenario — Lease Race Defense

Create `tests/test_scenario_lease_race.py`:

```python
@pytest.mark.asyncio
async def test_lease_race_fencing_token_rejects_stale_bid(mock_grid):
    """
    SCENARIO: Provocateur attempts to acquire Sentinel's singleton lease.
    EXPECTED: Auction arbiter rejects (singleton already leased).
              Sentinel's fencing token unchanged.
    """

@pytest.mark.asyncio
async def test_lease_race_does_not_corrupt_registry(mock_grid, sentinel_service):
    """
    SCENARIO: After failed lease race, service discovery still returns Sentinel.
    EXPECTED: Registry state unchanged. No phantom entries.
    """
```

#### T3.4: Scenario — Event Flood Resilience

Create `tests/test_scenario_event_flood.py`:

```python
@pytest.mark.asyncio
async def test_event_flood_grid_remains_responsive(mock_grid):
    """
    SCENARIO: 1000 telemetry events published in rapid succession.
    EXPECTED: Grid health endpoint still responds. Event consumption still works.
    """

@pytest.mark.asyncio
async def test_event_flood_does_not_starve_sentinel_consumption(mock_grid, sentinel_service):
    """
    SCENARIO: During flood, Sentinel's event consumption continues functioning.
    EXPECTED: Sentinel can still read system.consensus events (separate topic).
    """
```

#### T3.5: Scenario — Stale Token Rejection

Create `tests/test_scenario_stale_token.py`:

```python
@pytest.mark.asyncio
async def test_stale_fencing_token_rejected_on_invoke(mock_grid):
    """
    SCENARIO: Service invocation with fabricated fencing token.
    EXPECTED: 403 or 409 response. No method execution.
    EVOLUTION TRIGGER: If invocation succeeds, fencing is broken.
    """

@pytest.mark.asyncio
async def test_current_fencing_token_accepted(mock_grid):
    """
    CONTROL: Valid fencing token allows normal invocation.
    """
```

#### T3.6: Scenario — Phantom Registration Cleanup

Create `tests/test_scenario_phantom_registration.py`:

```python
@pytest.mark.asyncio
async def test_phantom_endpoint_dispatch_fails_gracefully(mock_grid):
    """
    SCENARIO: Fake endpoint registered at unreachable port.
    EXPECTED: Dispatch attempt returns error (timeout/connection refused), not hang.
    """

@pytest.mark.asyncio
async def test_phantom_endpoint_triggers_tattle(mock_grid):
    """
    SCENARIO: After failed dispatch, tattle is auto-filed against phantom.
    EXPECTED: system.telemetry contains tattle event for the phantom MAS.
    EVOLUTION TRIGGER: If no auto-tattle, self-healing is incomplete.
    """
```

#### T3.7: Create Aggregate Report Generator

Create `tests/generate_report.py`:

A pytest plugin/conftest that generates `_architectural_decisions/scenario_results.md` after a full test run, summarizing:
- Which defenses held
- Which scenarios triggered evolution proposals
- Evidence for each finding

#### T3.Final: Blast Radius Updates

1. Update `_architectural_decisions/tier2_design.md` with scenario matrix results
2. Add `tests/requirements.txt` with test dependencies (`pytest`, `pytest-asyncio`, `respx`)

### Success Criteria

- [ ] `pytest tests/ -x -q` — all scenario tests pass (with mocked grid)
- [ ] Each scenario test has a clear docstring stating SCENARIO, EXPECTED, and optionally EVOLUTION TRIGGER
- [ ] `test_false_tattle_defense_holds` validates Sentinel lease survives investigation
- [ ] `test_lease_race_fencing_token_rejects_stale_bid` validates CAS rejection
- [ ] `test_event_flood_grid_remains_responsive` validates no deadlock under load
- [ ] `test_stale_fencing_token_rejected_on_invoke` classifies result as defense_held OR evolution_trigger
- [ ] `test_phantom_endpoint_dispatch_fails_gracefully` validates timeout (not hang)
- [ ] Report generator produces markdown summary

### Produces / Consumes

- **Produces**: `tests/` directory with 10+ scenario tests, report generator → consumed by TG5
- **Produces**: Evolution trigger classifications → consumed by TG4 (if any triggers fire)
- **Consumes**: `sentinel/` from TG1, `provocateur/` from TG2

---

## Task Group 4: Evolution Proposals & Grid Fixes (Infrastructure — CONDITIONAL)

### Agent Profile

You are a **C# systems engineer** specializing in AuraGrid's control plane infrastructure. You implement fixes for bugs discovered by adversarial testing. Read `CLAUDE.md` before starting — it defines all conventions for the AuraGrid .NET 10 codebase.

### Context

This task group is **CONDITIONAL** — it only executes if TG3 scenario tests identify Evolution Triggers (grid bugs where the defense did NOT hold). If all defenses hold, this TG is skipped.

Based on the infrastructure analysis, the most likely Evolution Triggers are:

1. **Fencing token not validated on service invocation** — The IPC bridge (`CellApiHandler`) may not check fencing tokens on inbound requests from MAS apps. If so, stale-token attacks succeed.
2. **No auto-tattle on dispatch failure** — `ExternalServiceDispatcher` may not file a tattle report when dispatch to an endpoint fails. If so, phantom registrations persist indefinitely.
3. **Event publish has no rate limiting** — WAL accepts unlimited writes with no backpressure. If so, event floods can exhaust disk or memory.

Each discovered trigger becomes a formal Evolution Proposal (matching the tier1 format) and an implementation fix.

### Files to Read Before Starting

1. `src/AuraGrid.ProxyWorker/Proxy/CellApiHandler.cs` — IPC routing
2. `src/AuraGrid.ProxyWorker/Proxy/ExternalServiceDispatcher.cs` — External dispatch
3. `src/AuraGrid.ProxyWorker/Telemetry/TattleInvestigator.cs` — Tattle handling
4. `src/AuraGrid.ProxyWorker/Eventing/WalEventPublisher.cs` — Event publishing
5. `app-examples/tier2-grid-gauntlet/_architectural_decisions/scenario_results.md` — TG3 findings
6. `app-examples/tier1-sovereign-beacon/_architectural_decisions/evolution_proposals.md` — EP format

### Constraints

- Do **NOT** add NuGet packages
- Do **NOT** modify `SwimProtocol.cs`
- Do **NOT** break existing 1428 tests
- Fixes must be **minimal** — surgical corrections, not refactors
- All new code must be `internal sealed class` where applicable
- Follow existing patterns in `CLAUDE.md`

### Banned Patterns (DO NOT USE)

- ✗ `lock()`, raw `Mutex` — Use existing concurrency patterns
- ✗ `Thread.Sleep()` — Use `Task.Delay()` or timers
- ✗ Throwing exceptions for flow control
- ✗ `public` visibility on new implementation classes

### Tasks

#### T4.1: Assess TG3 Results and Classify Triggers

Read `_architectural_decisions/scenario_results.md`. For each EVOLUTION_TRIGGER:
- Identify the specific C# file and method responsible
- Determine if it's a missing feature, a bug, or a design gap
- Write an Evolution Proposal in the tier1 EP format

Create `app-examples/tier2-grid-gauntlet/_architectural_decisions/evolution_proposals.md`

#### T4.2: Fix — Fencing Token Validation (if triggered)

If `test_stale_fencing_token_rejected_on_invoke` fires an evolution trigger:

In `CellApiHandler.cs` or the appropriate IPC handler, add fencing token validation:
```csharp
// Before dispatching to a MAS's invoke endpoint:
var fencingHeader = request.Headers["X-AuraGrid-Fencing-Token"];
if (!string.IsNullOrEmpty(fencingHeader))
{
    var providedToken = long.Parse(fencingHeader);
    var currentLease = await _leaseStore.GetAsync(masId);
    if (currentLease is null || currentLease.FencingToken != providedToken)
    {
        return Results.Problem("Stale fencing token", statusCode: 409);
    }
}
```

#### T4.3: Fix — Auto-Tattle on Dispatch Failure (if triggered)

If `test_phantom_endpoint_triggers_tattle` fires an evolution trigger:

In `ExternalServiceDispatcher.cs`, after a dispatch failure (timeout/connection refused):
```csharp
catch (HttpRequestException ex) when (ex.StatusCode is null) // Connection failure
{
    // Auto-report tattle for unreachable endpoint
    await _walWriter.AppendAsync(WalTopics.Telemetry, new TattleEvent
    {
        MasId = target.MasId,
        ReportingNodeId = _nodeId,
        FailureCount = 1,
        Detail = $"Dispatch failed: {ex.Message}",
        Timestamp = DateTimeOffset.UtcNow,
    });
    // ... existing error handling
}
```

#### T4.4: Fix — Event Rate Limiting (if triggered)

If `test_event_flood_grid_remains_responsive` triggers:

Add a simple token-bucket rate limiter to `WalEventPublisher`:
```csharp
private readonly SemaphoreSlim _publishGate = new(100, 100); // Max 100 concurrent
private int _publishCount;
private DateTimeOffset _windowStart = DateTimeOffset.UtcNow;

// Reset window every second, cap at 1000 events/sec
```

#### T4.5: Write Tests for Each Fix

For each fix implemented, add corresponding tests in `src/AuraGrid.ProxyWorker.Tests/`:
- Fencing: `Proxy/FencingTokenValidationTests.cs`
- Auto-tattle: `Proxy/AutoTattleOnDispatchFailureTests.cs`
- Rate limit: `Eventing/EventRateLimitTests.cs`

#### T4.Final: Blast Radius Updates

1. Update `CHANGELOG.md` `[Unreleased]` section with fixes
2. Update evolution_proposals.md with resolution status

### Success Criteria

- [ ] `dotnet build AuraGrid.slnx` — 0 errors
- [ ] `dotnet test AuraGrid.slnx` — 0 failures (all 1428+ tests pass)
- [ ] Each evolution trigger has a corresponding EP document
- [ ] Each implemented fix has at least 2 test methods
- [ ] TG3 scenario tests (when re-run with real grid behavior) would now pass

### Recovery Strategy

- **Trigger**: If a fix breaks existing tests and cannot be resolved in 3 attempts
- **Files to revert**: Any modified files in `src/AuraGrid.ProxyWorker/`
- **Escalation**: File the EP as "Deferred — requires architectural review" and proceed to TG5 without the fix

### Produces / Consumes

- **Produces**: Grid fixes (C# code), evolution proposals, new tests → consumed by TG5
- **Consumes**: `_architectural_decisions/scenario_results.md` from TG3

---

## Task Group 5: Integration & Validation (Final Gate)

### Agent Profile

You are a **quality assurance engineer and technical writer** responsible for the final integration validation of the Tier 2 Grid Gauntlet adversarial testing suite. You verify end-to-end correctness, produce synthetic training data, and update project documentation. Read `CLAUDE.md` before starting.

### Context

All prior TGs are complete:
- TG1: Sentinel MAS with invariant checking (Python)
- TG2: Provocateur MAS with attack playbook (Python)
- TG3: Scenario integration tests with defense/trigger classification
- TG4: Grid fixes for any discovered evolution triggers (conditional)

This TG validates the complete delivery, ensures all tests pass, generates the synthetic training data required by `adversarial_grid_evolution.md`, and documents the Architect Gate decision.

### Files to Read Before Starting

1. `app-examples/tier2-grid-gauntlet/README.md` — Project overview
2. `app-examples/tier2-grid-gauntlet/_architectural_decisions/tier2_design.md` — Architecture
3. `app-examples/tier2-grid-gauntlet/_architectural_decisions/scenario_results.md` — TG3 findings
4. `app-examples/tier2-grid-gauntlet/_architectural_decisions/evolution_proposals.md` — TG4 EPs (if any)
5. `docs/prompts/adversarial_grid_evolution.md` — Synthetic training mandate

### Constraints

- Do **NOT** modify any implementation code (Python or C#)
- Do **NOT** modify test assertions
- Documentation and validation only
- All synthetic data must follow the chain-of-thought format from `adversarial_grid_evolution.md`

### Tasks

#### T5.1: Full Test Suite Validation

Run all test suites and record results:
```bash
# C# (must still pass — no regressions)
dotnet test AuraGrid.slnx

# Python scenario tests
cd app-examples/tier2-grid-gauntlet && pytest tests/ -x -q

# Sentinel contract tests
pytest sentinel/tests/ -x -q

# Provocateur contract tests
pytest provocateur/tests/ -x -q
```

Record: total tests, pass/fail counts, any new warnings.

#### T5.2: Generate Synthetic Training Data

Create `_architectural_decisions/tier2_synthetic_training.md`:

Follow the Synthetic Training Mandate format:
```markdown
## Scenario: {Attack Name}

### 1. Intent
{What we were trying to prove/test}

### 2. Hypothesis
{How we expected the grid to behave}

### 3. Execution
{What was actually done — SDK calls, payloads, timing}

### 4. Result vs. Expectation
{Did the defense hold? Evidence.}

### 5. Mitigation/Evolution
{If defense failed: what fix was proposed/implemented.
 If defense held: what this proves about the architecture.}
```

One section per attack scenario (5 total).

#### T5.3: Produce Architect Gate Summary

Create `_architectural_decisions/architect_gate_decision.md`:

```markdown
# Tier 2 Architect Gate — Grid Gauntlet

## Summary
{One paragraph: what was tested, what held, what broke}

## Defense Matrix

| Attack | Target | Defense Held? | Evidence | Notes |
|--------|--------|:---:|---|---|
| False Tattle | TattleInvestigator | ✅/❌ | {test name} | |
| Lease Race | SqliteLeaseStore | ✅/❌ | {test name} | |
| Stale Token | Service Dispatch | ✅/❌ | {test name} | |
| Event Flood | WAL/Event Bus | ✅/❌ | {test name} | |
| Phantom Registration | Service Registry | ✅/❌ | {test name} | |

## Evolution Triggers Filed
{List of EPs, or "None — all defenses held"}

## Recommendation
{Advance to Tier 3 / Hold for fixes / Specific concerns}
```

#### T5.4: Update CHANGELOG

Append to `c:\projects\auracore\auragrid\CHANGELOG.md` under `[Unreleased]`:
```markdown
### Added
- Tier 2 adversarial test suite: Grid Gauntlet (Sentinel + Provocateur)
- 5 attack scenarios validating new control plane infrastructure
- Synthetic training data for adversarial evolution methodology
```

#### T5.Final: Blast Radius Updates

1. Verify `README.md` is complete and accurate
2. Verify all `_architectural_decisions/` files are internally consistent
3. Confirm no uncommitted grid modifications (if TG4 was skipped)

### Success Criteria

- [ ] `dotnet test AuraGrid.slnx` — 0 failures (1428+ tests, no regressions)
- [ ] `pytest tests/ -x -q` — all scenario tests pass
- [ ] `pytest sentinel/tests/ -x -q` — all contract tests pass
- [ ] `pytest provocateur/tests/ -x -q` — all contract tests pass
- [ ] `tier2_synthetic_training.md` has 5 scenario sections in the mandated format
- [ ] `architect_gate_decision.md` has defense matrix with evidence for all 5 attacks
- [ ] `CHANGELOG.md` updated with Tier 2 entry
- [ ] No files modified in `src/AuraGrid.ProxyWorker/` (unless TG4 executed)

### Reflection Gate Criteria

- [ ] **Invariant Coverage**: Sentinel checks at least 3 distinct invariants (fencing token, event ordering, lease presence)
- [ ] **Attack Isolation**: Each Provocateur attack is in a separate module with independent execution
- [ ] **Defense Classification**: Every scenario test clearly classifies as DEFENSE_HELD or EVOLUTION_TRIGGER
- [ ] **Idempotency**: All attacks have cleanup steps; running twice produces same result
- [ ] **SDK Boundary**: No attack uses raw HTTP outside the SDK IPC abstraction
- [ ] **No Grid Corruption**: After full test run, grid state is unchanged (mocked layer guarantees)
- [ ] **Synthetic Data Quality**: Each scenario section has all 5 mandated subsections
- [ ] **Named test exists and passes**: `test_false_tattle_defense_holds`
- [ ] **Named test exists and passes**: `test_lease_race_fencing_token_rejects_stale_bid`
- [ ] **Named test exists and passes**: `test_event_flood_grid_remains_responsive`
- [ ] **Named test exists and passes**: `test_stale_fencing_token_rejected_on_invoke`
- [ ] **Named test exists and passes**: `test_phantom_endpoint_dispatch_fails_gracefully`
- [ ] **Wiring**: Provocateur's `execute_*` functions receive `AsyncGridContext` (not raw client)
- [ ] **Contract**: `InvariantChecker` is consumed by `SentinelService` — verified in Sentinel source
- [ ] **Evolution**: Any identified grid bugs have corresponding EPs in the mandated format

### Produces / Consumes

- **Produces**: Final validated Tier 2 delivery, synthetic training data, Architect Gate decision
- **Consumes**: All artifacts from TG1, TG2, TG3, TG4

---

## Appendix: Architectural Decisions

### A1. Two-App Adversarial Model (Sentinel + Provocateur)

Instead of a single chaotic app, we use a **paired adversarial model** where roles are clearly separated. This produces cleaner chain-of-thought data (the "attacker" and "defender" perspectives are logged separately), enables independent contract testing, and mirrors real-world threat modeling where the attacker and target are distinct entities.

Alternative considered: Single app that attacks itself. Rejected because it conflates the defense observation with the attack execution, making it impossible to determine if a "defense held" classification is genuine or an artifact of co-located state.

### A2. Mock-First Scenario Testing (No Live Grid Required)

Scenario tests mock the IPC bridge at the HTTP boundary using `respx`. This ensures:
- Tests are deterministic (no timing-dependent failures)
- CI/CD can run without a live AuraGrid instance
- Evolution triggers are identified by inspecting mock expectations (what the grid SHOULD do) rather than by timeout

Trade-off: We lose end-to-end confidence. Mitigation: A future TG (Tier 3+) will add live-grid integration tests that re-run these scenarios against a real single-node grid.

### A3. Conditional TG4 (Fix or Document)

TG4 only executes if TG3 discovers real evolution triggers. If all defenses hold (possible given the App-0 Mitigation Phase 2 work), TG4 is skipped and the plan completes with TG5. This avoids speculative framework changes.

However, TG4 pre-documents the LIKELY triggers based on code analysis:
- Fencing token validation is NOT checked on the IPC inbound path (high confidence)
- Auto-tattle on dispatch failure is NOT implemented (high confidence)
- Event rate limiting does NOT exist (high confidence)

These are documented to give the TG4 agent a head start if triggered.

### A4. Attack Timeout and Cleanup Contract

Every attack in the Provocateur has a 30-second timeout and a cleanup function. This ensures:
- A hung grid doesn't block the test suite indefinitely
- State pollution between scenarios is prevented
- The "reversible and idempotent" constraint from `adversarial_grid_evolution.md` is enforced

### A5. Alignment with App-0 Mitigation Phase 2 Outputs

This tier specifically targets the infrastructure built in TG1–TG7:
| Attack | Validates |
|---|---|
| False Tattle | TG6: TattleInvestigator cooldown and threshold logic |
| Lease Race | TG3: SqliteLeaseStore CAS and TG4: LeaseBasedLeaderProvider |
| Stale Token | TG3/TG5: Fencing token propagation through ControlPlaneManager |
| Event Flood | TG2: WAL topic infrastructure under stress |
| Phantom Registration | TG3: SqliteServiceRegistry + TG6: Tattle as self-healing |

This makes the Grid Gauntlet a direct validation of the work just completed — it proves the infrastructure under adversarial conditions, not just unit test conditions.
