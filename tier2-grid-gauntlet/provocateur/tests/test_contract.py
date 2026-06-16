"""Phase 0 contract tests for Provocateur MAS."""
from __future__ import annotations

import ast
import inspect
import json
import re
from pathlib import Path

import pytest
import sys

# Add provocateur to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playbook import AttackPlaybook, AttackResult, AttackScenario


class TestAttackPlaybook:
    def test_register_and_list_scenarios(self):
        pb = AttackPlaybook()
        scenario = AttackScenario(
            name="test", description="test", target_infrastructure="test",
            expected_defense="test"
        )

        async def fake_executor(**kwargs):
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            return AttackResult(
                attack_name="test", target="test",
                started_at=now, completed_at=now,
                defense_held=True, expected_behavior="test",
                observed_behavior="test",
            )

        pb.register(scenario, fake_executor)
        assert len(pb.scenarios) == 1
        assert pb.scenarios[0].name == "test"

    def test_attack_result_serializable(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        result = AttackResult(
            attack_name="test", target="test",
            started_at=now, completed_at=now,
            defense_held=True, expected_behavior="x",
            observed_behavior="y", evidence={"key": "value"},
        )
        # Should be JSON-serializable (with default=str for datetime)
        serialized = json.dumps({
            "name": result.attack_name,
            "defense_held": result.defense_held,
            "started": result.started_at.isoformat(),
        })
        assert "test" in serialized

    def test_scenario_timeout_default(self):
        s = AttackScenario(name="x", description="x", target_infrastructure="x", expected_defense="x")
        assert s.timeout_seconds == 30.0

    def test_scenario_enabled_default(self):
        s = AttackScenario(name="x", description="x", target_infrastructure="x", expected_defense="x")
        assert s.enabled is True

    def test_playbook_respects_disabled(self):
        pb = AttackPlaybook()
        scenario = AttackScenario(
            name="disabled", description="x", target_infrastructure="x",
            expected_defense="x", enabled=False,
        )

        async def should_not_run(**kwargs):
            raise RuntimeError("Should not execute")

        pb.register(scenario, should_not_run)
        # execute_all should skip disabled
        import asyncio
        results = asyncio.run(pb.execute_all())
        assert len(results) == 0


class TestAttackModules:
    def test_each_module_has_execute_function(self):
        attacks_dir = Path(__file__).resolve().parent.parent / "attacks"
        for py_file in attacks_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            # Each attack module should have an execute_* async function
            assert re.search(r'async def execute_\w+', content), \
                f"No execute_* async function in {py_file.name}"

    def test_each_module_has_scenario_constant(self):
        attacks_dir = Path(__file__).resolve().parent.parent / "attacks"
        for py_file in attacks_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            assert "SCENARIO = AttackScenario(" in content, \
                f"No SCENARIO constant in {py_file.name}"

    def test_no_forbidden_imports(self):
        provocateur_dir = Path(__file__).resolve().parent.parent
        forbidden = ["os.system", "subprocess", "socket.connect"]
        for py_file in provocateur_dir.rglob("*.py"):
            if py_file.parent.name == "tests":
                continue
            content = py_file.read_text()
            for pattern in forbidden:
                assert pattern not in content, \
                    f"Forbidden pattern '{pattern}' found in {py_file.relative_to(provocateur_dir)}"

    def test_execute_functions_accept_ctx(self):
        attacks_dir = Path(__file__).resolve().parent.parent / "attacks"
        for py_file in attacks_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.AsyncFunctionDef) and node.name.startswith("execute_"):
                    args = [a.arg for a in node.args.args]
                    assert "ctx" in args, \
                        f"{py_file.name}:{node.name} missing 'ctx' parameter"


class TestManifest:
    def test_manifest_valid(self):
        manifest_path = Path(__file__).resolve().parent.parent / "app.manifest.json"
        assert manifest_path.exists()
        with open(manifest_path) as f:
            m = json.load(f)
        app_id = m.get("AppId") or m.get("appId")
        assert app_id == "grid-gauntlet-provocateur"
        # Must be different from sentinel
        assert app_id != "grid-gauntlet-sentinel"
        services = m.get("Services") or m.get("services") or []
        assert len(services) == 1
        svc = services[0]
        mode = svc.get("Mode") or svc.get("mode")
        assert mode == "CellSingleton"
        runtime = svc.get("Runtime") or svc.get("runtime")
        assert runtime == "Python"


class TestNoForbiddenPatterns:
    def test_no_os_system(self):
        provocateur_dir = Path(__file__).resolve().parent.parent
        for py_file in provocateur_dir.rglob("*.py"):
            if py_file.parent.name == "tests":
                continue
            content = py_file.read_text()
            assert "os.system(" not in content

    def test_no_subprocess(self):
        provocateur_dir = Path(__file__).resolve().parent.parent
        for py_file in provocateur_dir.rglob("*.py"):
            if py_file.parent.name == "tests":
                continue
            content = py_file.read_text()
            assert "import subprocess" not in content

    def test_no_raw_socket(self):
        provocateur_dir = Path(__file__).resolve().parent.parent
        for py_file in provocateur_dir.rglob("*.py"):
            if py_file.parent.name == "tests":
                continue
            content = py_file.read_text()
            # Allow "socket" in comments/strings but not import socket
            lines = [l for l in content.split('\n') if not l.strip().startswith('#')]
            code = '\n'.join(lines)
            assert "import socket" not in code
