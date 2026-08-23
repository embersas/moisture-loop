"""HA1/HA2 exact-minimum Home Assistant 2025.9.0 evidence."""

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

pytest.importorskip("homeassistant")

import homeassistant.const as ha_const

ROOT = Path(__file__).resolve().parents[1]


def test_ha1_exact_minimum_source_contract() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_ha_contract.py", "--expect", "2025.9.0"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "native subentry removal mutates mapping" in result.stdout
    assert "All HA API contract checks passed" in result.stdout


def test_ha2_exact_minimum_harness_versions() -> None:
    assert ha_const.__version__ == "2025.9.0"
    assert version("pytest-homeassistant-custom-component") == "0.13.277"
    requirements = (ROOT / "requirements_test_ha.txt").read_text(encoding="utf-8")
    assert "homeassistant==2025.9.0" in requirements
    assert "pytest-homeassistant-custom-component==0.13.277" in requirements
    current_requirements = (ROOT / "requirements_test_ha_current.txt").read_text(encoding="utf-8")
    assert "pytest-homeassistant-custom-component==0.13.356" in current_requirements
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "test-ha-2025-9-0:" in workflow
    assert "test-ha-current:" in workflow
    assert "pip install -r requirements_test_ha.txt" in workflow
    assert "pip install -r requirements_test_ha_current.txt" in workflow
