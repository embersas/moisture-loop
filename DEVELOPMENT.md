# Development guide

Implementation follows `SPECIFICATION.md` (authoritative) slice by slice as
tracked in `PROGRESS.md`. This file documents the repeatable local commands
established in Slice 0 and used by every later slice.

## Environments

Two deliberately separate environments exist (SPECIFICATION.md §39.1):

| Environment | Requirements file | Purpose |
|---|---|---|
| Pure layer | `requirements_test.txt` | models/state-machine tests, lint, format. **No homeassistant installed** — this proves the pure-core boundary (§37). Any platform, Python ≥ 3.13. |
| HA 2025.9.0 (mandatory) | `requirements_test_ha.txt` | full suite on the exact minimum release (`homeassistant==2025.9.0` via `pytest-homeassistant-custom-component==0.13.277`). Python 3.13, HA-supported platform (CI: ubuntu-latest). |
| HA supported-current | `requirements_test_ha_current.txt` | full suite on the explicitly supported current HA release. Separate pinned environment; never replaces the 2025.9.0 job. |

Note: the HA harness environments require Python 3.13 on a HA-supported
platform. On Windows development machines only the pure-layer environment is
expected to run locally; HA-harness suites run in CI.

## Bootstrap (pure layer)

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements_test.txt   # Windows
# .venv/bin/python -m pip install -r requirements_test.txt     # POSIX
```

## Local validation commands

Run from the repository root with the venv's interpreter:

```sh
# Full pure test suite
python -m pytest

# With coverage (once custom_components/moisture_loop exists)
python -m pytest --cov --cov-branch --cov-report=term-missing

# state_machine.py release gate: 100% branch coverage (Slice 3+)
python -m coverage report --include="*/state_machine.py" --fail-under=100

# Lint
python -m ruff check .

# Format check / format
python -m ruff format --check .
python -m ruff format .
```

## Test-module conventions

- **HA-dependent test modules** must start with
  `pytest.importorskip("homeassistant")` at module level so the pure-layer CI
  job (which has no homeassistant installed) skips them cleanly.
- **Pure test modules** (`tests/test_state_machine.py`, model tests) must not
  import homeassistant, directly or indirectly.
- All time in tests is controlled/mocked; no real sleeps (§39.1).

## CI

`.github/workflows/ci.yml` defines: `lint`, `test-pure`,
`test-ha-2025-9-0` (mandatory, includes the HA1 contract check via
`scripts/check_ha_contract.py --expect 2025.9.0`), `test-ha-current`,
`hassfest`, and `hacs`. The hassfest/HACS jobs are armed but skip honestly
until `custom_components/moisture_loop/manifest.json` (and `hacs.json`)
exist; final packaging is Slice 12.
