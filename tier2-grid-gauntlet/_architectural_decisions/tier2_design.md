# Tier 2 Design: Sentinel/Provocateur Adversarial Model

## Decision: Paired Adversarial Architecture

Instead of a single chaotic test app, we use two cooperating MAS with distinct roles:

- **Sentinel** — Observes. Validates invariants. Collects evidence. Never attacks.
- **Provocateur** — Attacks. Executes playbook. Records defense outcomes. Never defends.

This separation enables:
1. Clean chain-of-thought capture (attacker/defender perspectives are distinct)
2. Independent contract testing (each app validates in isolation)
3. Composability (future tiers can add more attackers or defenders)

## Attack/Defense Matrix

| # | Attack | Infrastructure Target | Defense Mechanism | Validates (App-0 TG) |
|---|--------|----------------------|-------------------|---------------------|
| 1 | False Tattle | TattleInvestigator | Threshold + investigation + cooldown | TG6 |
| 2 | Lease Race | SqliteLeaseStore + AuctionArbiter | Fencing token CAS, singleton rejection | TG3/TG4 |
| 3 | Event Flood | WAL Event Bus | Backpressure / rate limiting | TG2 |
| 4 | Stale Token Invoke | IPC Bridge / ServiceProxy | Fencing token validation at dispatch | TG3/TG5 |
| 5 | Phantom Registration | ServiceRegistry + Discovery | Dispatch timeout + auto-tattle | TG3/TG6 |

## Key Design Choices

- **Mock-first testing**: Scenario tests mock the IPC bridge (no live grid required for CI)
- **Timeout contract**: Every attack has a 30s max timeout and cleanup step
- **Idempotent attacks**: Running twice produces same result, no permanent corruption
- **SDK-only access**: All attacks go through the Python SDK — no filesystem or shell escape
