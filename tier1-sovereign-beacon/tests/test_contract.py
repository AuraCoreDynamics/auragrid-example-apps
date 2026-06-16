"""
Phase 0 Contract Validation Tests — sovereign-beacon (Tier 1)
=============================================================
Purpose: Lock the interface contract BEFORE implementation.

Tests validate:
- Service class is importable without side effects
- All public methods are decorated with @auragrid_method
- get_status() return type and schema match the defined contract
- Event topic naming follows the sovereign-beacon.{channel} convention
- Manifest schema is valid (appId, services, CellSingleton mode, absolute WorkingDirectory)

Run: conda run -n aurarouter pytest tests/ -v
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

# Add app source to path for direct import
APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR))

MANIFEST_PATH = Path(r"C:\ProgramData\AuraCore\AuraGrid\manifests\sovereign-beacon\1.0.0\app.manifest.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_app_module():
    """Load app.py as a module without executing __main__ guard."""
    spec = importlib.util.spec_from_file_location("sovereign_beacon_app", APP_DIR / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# TC-1: Service Class Contract
# ---------------------------------------------------------------------------

class TestServiceClassContract:
    """Validates the @auragrid_service / @auragrid_method decoration contracts."""

    def test_app_module_importable(self):
        """Contract: app.py must be importable without side effects."""
        module = _load_app_module()
        assert hasattr(module, "SovereignBeaconService"), \
            "SovereignBeaconService class must be defined in app.py"
        assert hasattr(module, "main"), \
            "main() async entrypoint must be defined in app.py"

    def test_service_class_is_decorated(self):
        """Contract: @auragrid_service must have registered metadata on the class."""
        module = _load_app_module()
        svc_cls = module.SovereignBeaconService
        # auragrid SDK attaches __auragrid_service_descriptor__ or _auragrid_service_meta
        has_meta = (
            hasattr(svc_cls, "__auragrid_service_descriptor__")
            or hasattr(svc_cls, "_auragrid_service_meta")
            or getattr(svc_cls, "__auragrid_service__", False)
        )
        assert has_meta, \
            "SovereignBeaconService must be decorated with @auragrid_service"

    def test_get_status_exists_and_callable(self):
        """Contract: get_status() must exist and be synchronously callable."""
        module = _load_app_module()
        instance = module.SovereignBeaconService()
        assert callable(getattr(instance, "get_status", None)), \
            "get_status() must be a callable method"

    def test_get_status_return_schema(self):
        """Contract: get_status() must return a JSON-serializable dict with required keys."""
        module = _load_app_module()
        instance = module.SovereignBeaconService()
        result = instance.get_status()

        assert isinstance(result, dict), "get_status() must return dict"

        required_keys = {"status", "heartbeats", "uptime_seconds", "node_id", "mas_id"}
        for key in required_keys:
            assert key in result, f"get_status() result missing required key: {key!r}"

        # Must be JSON round-trip safe
        serialized = json.loads(json.dumps(result))
        assert serialized["status"] == "active"
        assert isinstance(serialized["heartbeats"], int)
        assert isinstance(serialized["uptime_seconds"], float)

    def test_heartbeat_counter_increments(self):
        """Contract: _increment_heartbeat() must advance heartbeats by exactly 1."""
        module = _load_app_module()
        instance = module.SovereignBeaconService()
        before = instance.get_status()["heartbeats"]
        instance._increment_heartbeat()
        after = instance.get_status()["heartbeats"]
        assert after == before + 1, \
            f"Expected heartbeat count {before + 1}, got {after}"

    def test_initial_heartbeat_count_is_zero(self):
        """Contract: fresh instance must start with 0 heartbeats."""
        module = _load_app_module()
        instance = module.SovereignBeaconService()
        assert instance.get_status()["heartbeats"] == 0, \
            "Fresh SovereignBeaconService must have 0 heartbeats"


# ---------------------------------------------------------------------------
# TC-2: Manifest Schema Contract
# ---------------------------------------------------------------------------

class TestManifestContract:
    """Validates the app manifest JSON schema and deployment configuration."""

    @pytest.fixture
    def manifest(self):
        if not MANIFEST_PATH.exists():
            pytest.skip(
                f"Manifest not yet placed at {MANIFEST_PATH}. "
                "Run Phase 0 setup to deploy the manifest file."
            )
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def _get(self, manifest, *keys):
        """Case-insensitive key lookup (grid deserializer is case-insensitive)."""
        lower_map = {k.lower(): v for k, v in manifest.items()}
        for key in keys:
            if key.lower() in lower_map:
                return lower_map[key.lower()]
        return None

    def test_required_root_fields_present(self, manifest):
        """Contract: root-level appId, name, version, services must be present."""
        for field in ("appId", "name", "version", "services"):
            assert self._get(manifest, field) is not None, \
                f"Manifest missing required root field: {field!r}"

    def test_app_id_matches_directory(self, manifest):
        """Contract: appId must match the grid catalog key 'sovereign-beacon'."""
        app_id = self._get(manifest, "appId")
        assert app_id == "sovereign-beacon", \
            f"Expected appId 'sovereign-beacon', got {app_id!r}"

    def test_version_is_1_0_0(self, manifest):
        """Contract: Tier 1 version must be 1.0.0."""
        version = self._get(manifest, "version")
        assert version == "1.0.0", f"Expected version '1.0.0', got {version!r}"

    def test_exactly_one_service(self, manifest):
        """Contract: Tier 1 defines exactly one MAS."""
        services = self._get(manifest, "services") or []
        assert len(services) == 1, \
            f"Tier 1 must define exactly 1 service, found {len(services)}"

    def test_service_mode_is_cell_singleton(self, manifest):
        """Contract: Mode must be CellSingleton to exercise the lease mechanism."""
        svc = (self._get(manifest, "services") or [{}])[0]
        mode = svc.get("Mode") or svc.get("mode")
        assert mode == "CellSingleton", \
            f"Expected CellSingleton mode (tests lease), got {mode!r}"

    def test_service_runtime_is_python(self, manifest):
        """Contract: Runtime must be Python."""
        svc = (self._get(manifest, "services") or [{}])[0]
        runtime = svc.get("Runtime") or svc.get("runtime")
        assert runtime == "Python", f"Expected Python runtime, got {runtime!r}"

    def test_working_directory_is_absolute(self, manifest):
        """Contract: WorkingDirectory MUST be an absolute path (no source in grid data dir)."""
        svc = (self._get(manifest, "services") or [{}])[0]
        py_cfg = svc.get("PythonConfig") or svc.get("pythonConfig") or {}
        wd = py_cfg.get("WorkingDirectory") or py_cfg.get("workingDirectory", ".")
        assert os.path.isabs(wd), \
            f"WorkingDirectory must be an absolute path, got: {wd!r}"

    def test_working_directory_not_in_grid_data_dir(self, manifest):
        """Contract: Source must NOT live in C:\\ProgramData\\AuraCore\\AuraGrid (postmortem rule)."""
        svc = (self._get(manifest, "services") or [{}])[0]
        py_cfg = svc.get("PythonConfig") or svc.get("pythonConfig") or {}
        wd = py_cfg.get("WorkingDirectory") or py_cfg.get("workingDirectory", ".")
        forbidden_prefix = r"C:\ProgramData\AuraCore\AuraGrid"
        assert not wd.startswith(forbidden_prefix), \
            f"WorkingDirectory must NOT be inside the grid data dir: {wd!r}"

    def test_working_directory_exists(self, manifest):
        """Contract: WorkingDirectory must exist on disk at test time."""
        svc = (self._get(manifest, "services") or [{}])[0]
        py_cfg = svc.get("PythonConfig") or svc.get("pythonConfig") or {}
        wd = py_cfg.get("WorkingDirectory") or py_cfg.get("workingDirectory", ".")
        assert Path(wd).is_dir(), \
            f"WorkingDirectory does not exist: {wd!r}"

    def test_script_path_resolves_to_existing_file(self, manifest):
        """Contract: ScriptPath must point to an existing app.py."""
        svc = (self._get(manifest, "services") or [{}])[0]
        py_cfg = svc.get("PythonConfig") or svc.get("pythonConfig") or {}
        script = py_cfg.get("ScriptPath") or py_cfg.get("scriptPath", "")
        script_path = Path(script)
        assert script_path.is_absolute(), \
            f"ScriptPath must be absolute, got: {script!r}"
        assert script_path.exists(), \
            f"ScriptPath does not exist: {script!r}"


# ---------------------------------------------------------------------------
# TC-3: Event Topic Naming Contract
# ---------------------------------------------------------------------------

class TestEventTopicContract:
    """
    Validates event topic naming conventions.
    BLACK.md Rule 1: Build in layers. Reflect at boundaries.
    All event contracts must be locked at Phase 0.
    """

    EXPECTED_TOPICS = {
        "sovereign-beacon.lifecycle": frozenset({"startup", "shutdown"}),
        "sovereign-beacon.heartbeat": frozenset({"heartbeat"}),
    }

    def test_all_topics_are_namespaced(self):
        """Contract: Topics must use 'sovereign-beacon.' prefix."""
        for topic in self.EXPECTED_TOPICS:
            assert topic.startswith("sovereign-beacon."), \
                f"Topic {topic!r} must be prefixed with 'sovereign-beacon.'"

    def test_topics_use_single_dot_separator(self):
        """Contract: Topic names must be {app-id}.{channel}, exactly one dot."""
        for topic in self.EXPECTED_TOPICS:
            parts = topic.split(".")
            assert len(parts) == 2, \
                f"Topic {topic!r} must have format {{app-id}}.{{channel}}"

    def test_lifecycle_topic_covers_startup_and_shutdown(self):
        """Contract: lifecycle topic must handle both startup and shutdown events."""
        lifecycle_types = self.EXPECTED_TOPICS["sovereign-beacon.lifecycle"]
        assert "startup" in lifecycle_types
        assert "shutdown" in lifecycle_types

    def test_heartbeat_is_separate_topic(self):
        """Contract: heartbeat must be on its own topic for subscriber isolation."""
        assert "sovereign-beacon.heartbeat" in self.EXPECTED_TOPICS
        assert "sovereign-beacon.heartbeat" != "sovereign-beacon.lifecycle"

    def test_topic_names_are_kebab_case(self):
        """Contract: Topics must be lowercase kebab-case."""
        import re
        pattern = re.compile(r'^[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*$')
        for topic in self.EXPECTED_TOPICS:
            assert pattern.match(topic), \
                f"Topic {topic!r} must be lowercase kebab-case"
