"""Attack playbook orchestration for the Provocateur MAS."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

import structlog

logger = structlog.get_logger("provocateur.playbook")


@dataclass
class AttackResult:
    """Outcome of a single attack scenario execution."""
    attack_name: str
    target: str
    started_at: datetime
    completed_at: datetime
    defense_held: bool
    expected_behavior: str
    observed_behavior: str
    evidence: dict[str, Any] = field(default_factory=dict)
    evolution_trigger: bool = False
    error: str | None = None


@dataclass
class AttackScenario:
    """Definition of a single attack scenario."""
    name: str
    description: str
    target_infrastructure: str
    expected_defense: str
    timeout_seconds: float = 30.0
    enabled: bool = True


# Type alias for attack executor functions
AttackExecutor = Callable[..., Awaitable[AttackResult]]


class AttackPlaybook:
    """Orchestrates attack scenarios in sequence with logging and timeout enforcement."""

    def __init__(self) -> None:
        self._scenarios: list[tuple[AttackScenario, AttackExecutor]] = []
        self._results: list[AttackResult] = []

    def register(self, scenario: AttackScenario, executor: AttackExecutor) -> None:
        """Register an attack scenario with its executor function."""
        self._scenarios.append((scenario, executor))

    @property
    def scenarios(self) -> list[AttackScenario]:
        return [s for s, _ in self._scenarios]

    @property
    def results(self) -> list[AttackResult]:
        return list(self._results)

    async def execute_all(self, **kwargs: Any) -> list[AttackResult]:
        """Execute all enabled scenarios in registration order."""
        results: list[AttackResult] = []
        for scenario, executor in self._scenarios:
            if not scenario.enabled:
                logger.info("attack_skipped", name=scenario.name, reason="disabled")
                continue
            result = await self._execute_with_timeout(scenario, executor, **kwargs)
            results.append(result)
            self._results.append(result)
        return results

    async def execute_one(self, name: str, **kwargs: Any) -> AttackResult | None:
        """Execute a single named scenario."""
        for scenario, executor in self._scenarios:
            if scenario.name == name:
                result = await self._execute_with_timeout(scenario, executor, **kwargs)
                self._results.append(result)
                return result
        logger.warning("attack_not_found", name=name)
        return None

    async def _execute_with_timeout(
        self, scenario: AttackScenario, executor: AttackExecutor, **kwargs: Any
    ) -> AttackResult:
        """Execute a scenario with timeout enforcement."""
        started = datetime.now(timezone.utc)
        logger.info(
            "attack_starting",
            name=scenario.name,
            target=scenario.target_infrastructure,
            timeout=scenario.timeout_seconds,
        )
        try:
            result = await asyncio.wait_for(
                executor(**kwargs),
                timeout=scenario.timeout_seconds,
            )
            logger.info(
                "attack_completed",
                name=scenario.name,
                defense_held=result.defense_held,
                evolution_trigger=result.evolution_trigger,
            )
            return result
        except asyncio.TimeoutError:
            completed = datetime.now(timezone.utc)
            logger.warning("attack_timeout", name=scenario.name)
            return AttackResult(
                attack_name=scenario.name,
                target=scenario.target_infrastructure,
                started_at=started,
                completed_at=completed,
                defense_held=False,
                expected_behavior=scenario.expected_defense,
                observed_behavior="TIMEOUT — attack did not complete within limit",
                evolution_trigger=True,
                error=f"Timeout after {scenario.timeout_seconds}s",
            )
        except Exception as exc:
            completed = datetime.now(timezone.utc)
            logger.error("attack_error", name=scenario.name, error=str(exc))
            return AttackResult(
                attack_name=scenario.name,
                target=scenario.target_infrastructure,
                started_at=started,
                completed_at=completed,
                defense_held=False,
                expected_behavior=scenario.expected_defense,
                observed_behavior=f"EXCEPTION: {exc}",
                evolution_trigger=True,
                error=str(exc),
            )

    def summary(self) -> dict[str, Any]:
        """Generate summary of all executed attacks."""
        return {
            "total_executed": len(self._results),
            "defenses_held": sum(1 for r in self._results if r.defense_held),
            "evolution_triggers": sum(1 for r in self._results if r.evolution_trigger),
            "attacks": [
                {
                    "name": r.attack_name,
                    "target": r.target,
                    "defense_held": r.defense_held,
                    "evolution_trigger": r.evolution_trigger,
                }
                for r in self._results
            ],
        }
