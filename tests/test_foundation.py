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
        REPO_ROOT / "custom_components" / "moisture_loop" / name
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
    }
    integration = REPO_ROOT / "custom_components" / "moisture_loop"
    for file in integration.glob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        used = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)} | {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        }
        assert not (used & prohibited), f"{file.name} uses {sorted(used & prohibited)}"
