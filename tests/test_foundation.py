"""Slice 0 foundation smoke tests.

Non-behavioural: these verify the toolchain and repository conventions, not
integration runtime behaviour (none exists yet).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_python_version_floor() -> None:
    """HA 2025.9.0 requires Python >= 3.13; the toolchain targets the same."""
    assert sys.version_info >= (3, 13)


def test_ci_workflow_exists_and_keeps_mandatory_ha_job() -> None:
    """The mandatory HA 2025.9.0 job must remain present (HA2)."""
    workflow = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    assert workflow.is_file()
    text = workflow.read_text(encoding="utf-8")
    assert "test-ha-2025-9-0" in text
    assert "pytest-homeassistant-custom-component==0.13.277" in (
        (REPO_ROOT / "requirements_test_ha.txt").read_text(encoding="utf-8")
    )


def test_ha_contract_check_script_present() -> None:
    """HA1 source-contract verification has a defined execution path."""
    assert (REPO_ROOT / "scripts" / "check_ha_contract.py").is_file()


def test_pure_modules_have_no_homeassistant_import() -> None:
    """The pure domain layer must never import homeassistant (§37).

    Passes trivially until Slice 1 creates the modules; from then on it is a
    live audit of every pure-layer file.
    """
    pure_files = [
        REPO_ROOT / "custom_components" / "soilsync" / name
        for name in ("models.py", "const.py", "state_machine.py", "slot_manager.py")
    ]
    for file in pure_files:
        if not file.is_file():
            continue
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                assert not name.startswith("homeassistant"), f"{file.name} imports {name}"


def test_production_source_uses_no_prohibited_config_entry_internals() -> None:
    """Stage 5 negative contract: current integration uses public HA APIs only."""
    prohibited = {
        "async_update_reload_and_abort",
        "_async_update_entry",
        "_async_save_and_notify",
        "_async_dispatch",
        "SIGNAL_CONFIG_ENTRY_CHANGED",
        "async_dispatcher_send_internal",
        "async_prepare_delete",
        "websocket_intercept",
    }
    integration = REPO_ROOT / "custom_components" / "soilsync"
    for file in integration.glob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        used = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)} | {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        }
        assert not (used & prohibited), f"{file.name} uses {sorted(used & prohibited)}"


def test_local_only_and_no_recorder_dependency() -> None:
    """I28: production safety has no cloud/network/Recorder dependency."""
    prohibited_imports = {
        "aiohttp",
        "httpx",
        "requests",
        "socket",
        "urllib",
        "homeassistant.components.recorder",
    }
    integration = REPO_ROOT / "custom_components" / "soilsync"
    for file in integration.glob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
        assert not any(
            imported == prohibited or imported.startswith(prohibited + ".")
            for imported in imports
            for prohibited in prohibited_imports
        ), file.name


def test_schema1_compatibility_is_migration_only() -> None:
    """ZoneRecord/schema 1 cannot be current watering or reconciliation authority."""
    integration = REPO_ROOT / "custom_components" / "soilsync"
    allowed = {"models.py", "storage.py"}
    for file in integration.glob("*.py"):
        text = file.read_text(encoding="utf-8")
        if file.name not in allowed:
            assert "ZoneRecord" not in text
            assert "Schema1StoreData" not in text
            assert "migrate_schema1_to_schema2" not in text

    models_tree = ast.parse((integration / "models.py").read_text(encoding="utf-8"))
    store_data = next(
        node
        for node in models_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "StoreData"
    )
    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "zones"
        for node in store_data.body
    )
    storage_text = (integration / "storage.py").read_text(encoding="utf-8")
    for obsolete in (
        "async_update_zone",
        "async_update_record_runtime",
        "legacy_record_for",
        "to_legacy_record",
        "async_rebase_soaking_owner(",
    ):
        assert obsolete not in storage_text


def test_blocker_ownership_is_safety_record_only() -> None:
    """I19: physical hazard calls never key blockers by zone/subentry ID."""
    integration = REPO_ROOT / "custom_components" / "soilsync"
    calls = 0
    for file in integration.glob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"async_add_blocker", "async_remove_blocker"}:
                continue
            calls += 1
            assert node.args
            first = ast.unparse(node.args[0])
            assert not first.endswith(".zone_id"), (file.name, node.lineno, first)
            assert not first.endswith(".subentry_id"), (file.name, node.lineno, first)
    assert calls > 0


def test_no_production_stop_event_shutdown_owner() -> None:
    """spec.5 §24.1: EVENT_HOMEASSISTANT_STOP owns no SoilSync safety work.

    It fires only after Core cancelled background tasks and set
    CoreState.stopping, where Store.async_save merely queues its payload for
    final write, so it can never satisfy the §23.4 fresh-read verification.
    """
    prohibited = {
        "EVENT_HOMEASSISTANT_STOP",
        "EVENT_HOMEASSISTANT_FINAL_WRITE",
        "async_handle_ha_stop",
        "install_stop_listener",
        "async_listen_once",
    }
    integration = REPO_ROOT / "custom_components" / "soilsync"
    for file in integration.glob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        used: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                used.add(node.attr)
            elif isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                used.update(alias.asname or alias.name for alias in node.names)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                used.add(node.value)
        assert not (used & prohibited), f"{file.name} uses {sorted(used & prohibited)}"


def test_exactly_one_stage1_shutdown_owner_registration() -> None:
    """spec.5 §22.1/§24.1: one removable Stage-1 job, owned by entry unload."""
    runtime = (REPO_ROOT / "custom_components" / "soilsync" / "runtime.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(runtime)
    registrations = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "async_add_shutdown_job"
    ]
    assert len(registrations) == 1
    assert "self.entry.async_on_unload(self.remove_shutdown_job)" in runtime
    assert "async def async_stage1_shutdown(" in runtime
    # No other production module may own or initiate process shutdown.
    integration = REPO_ROOT / "custom_components" / "soilsync"
    for file in integration.glob("*.py"):
        if file.name == "runtime.py":
            continue
        text = file.read_text(encoding="utf-8")
        assert "async_add_shutdown_job" not in text, file.name
        assert "async_stage1_shutdown" not in text, file.name


def test_one_shared_off_implementation() -> None:
    """I16: flow exits converge on the controller's one OFF future."""
    integration = REPO_ROOT / "custom_components" / "soilsync"
    callers: list[tuple[str, int]] = []
    for file in integration.glob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "async_turn_off"
            ):
                callers.append((file.name, node.lineno))
    # One normal controller implementation plus startup-only defensive
    # reconciliation when no live session owner can exist.
    assert [name for name, _line in callers].count("zone_controller.py") == 1
    assert [name for name, _line in callers].count("runtime.py") == 1
    assert len(callers) == 2
    controller = (integration / "zone_controller.py").read_text(encoding="utf-8")
    assert "def begin_off_operation(" in controller
    assert "async def _ensure_off_operation(" in controller
    assert "self._off_operation" in controller
