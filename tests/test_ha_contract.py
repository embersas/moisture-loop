"""HA1/HA2 minimum and supported-current Home Assistant evidence."""

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

pytest.importorskip("homeassistant")

import homeassistant.const as ha_const

ROOT = Path(__file__).resolve().parents[1]
MINIMUM_HA = "2025.9.0"
MINIMUM_HARNESS = "0.13.277"
CURRENT_HA = "2026.8.3"
CURRENT_HARNESS = "0.13.357"


def test_ha1_exact_minimum_source_contract() -> None:
    expected = ha_const.__version__
    assert expected in {MINIMUM_HA, CURRENT_HA}
    result = subprocess.run(
        [sys.executable, "scripts/check_ha_contract.py", "--expect", expected],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "native subentry removal mutates mapping" in result.stdout
    assert "All HA API contract checks passed" in result.stdout


def test_ha2_exact_minimum_harness_versions() -> None:
    installed_ha = ha_const.__version__
    installed_harness = version("pytest-homeassistant-custom-component")
    assert (installed_ha, installed_harness) in {
        (MINIMUM_HA, MINIMUM_HARNESS),
        (CURRENT_HA, CURRENT_HARNESS),
    }
    requirements = (ROOT / "requirements_test_ha.txt").read_text(encoding="utf-8")
    assert f"homeassistant=={MINIMUM_HA}" in requirements
    assert f"pytest-homeassistant-custom-component=={MINIMUM_HARNESS}" in requirements
    current_requirements = (ROOT / "requirements_test_ha_current.txt").read_text(encoding="utf-8")
    assert f"homeassistant=={CURRENT_HA}" in current_requirements
    assert f"pytest-homeassistant-custom-component=={CURRENT_HARNESS}" in current_requirements
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "test-ha-2025-9-0:" in workflow
    assert "test-ha-current:" in workflow
    assert "pip install -r requirements_test_ha.txt" in workflow
    assert "pip install -r requirements_test_ha_current.txt" in workflow
