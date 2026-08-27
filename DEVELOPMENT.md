# Development guide

`SPECIFICATION.md` version `0.1.0-spec.6` is authoritative. Home Assistant
2025.9.0 or later is supported; 2025.9.0 is the mandatory minimum and must
remain tested separately from the explicitly pinned supported-current release.
No environment may be upgraded in place from one HA line to the other.

Public repository: [`embersas/moisture-loop`](https://github.com/embersas/moisture-loop).
Use the repository [issue tracker](https://github.com/embersas/moisture-loop/issues)
for reproducible defects; this project is not included in the HACS default store.

## Pinned environments

| Environment | Python | Requirements | Exact HA/harness purpose |
|---|---|---|---|
| Pure/no-HA | 3.13+ | `requirements_test.txt` | Pure models, Store transforms, state machine, SlotManager, foundation and traceability structure. `homeassistant` must be absent. |
| Mandatory minimum | 3.13 | `requirements_test_ha.txt` | `homeassistant==2025.9.0` through `pytest-homeassistant-custom-component==0.13.277`. |
| Supported current | 3.14.2+ | `requirements_test_ha_current.txt` | `homeassistant==2026.8.3` through `pytest-homeassistant-custom-component==0.13.357`. |

The current pin was resolved from the official non-prerelease Home Assistant
release and PyPI dependency metadata on 2026-08-23. It is a release-evidence
pin, not a change to the minimum supported version.

## Bootstrap clean environments

PowerShell examples:

```powershell
py -3.14 -m venv .venv-pure
.venv-pure\Scripts\python.exe -m pip install -r requirements_test.txt

py -3.13 -m venv .venv-ha-min
.venv-ha-min\Scripts\python.exe -m pip install -r requirements_test_ha.txt

py -3.14 -m venv .venv-ha-current
.venv-ha-current\Scripts\python.exe -m pip install -r requirements_test_ha_current.txt
```

Equivalent POSIX environments use `.venv-name/bin/python`. CI runs the HA jobs
on `ubuntu-latest`; Windows harness accommodations in `tests/conftest.py` are
test-only and do not change production behavior.

Verify each HA environment before testing:

```powershell
.venv-ha-min\Scripts\python.exe -c "import homeassistant.const as h; print(h.__version__)"
.venv-ha-current\Scripts\python.exe -c "import homeassistant.const as h; print(h.__version__)"
```

## Pure/no-Home-Assistant gate

First prove that Home Assistant is absent, then run every pure module. The
pure-boundary test must execute here; do not run the whole HA-oriented tree and
call its skips pure evidence.

```powershell
.venv-pure\Scripts\python.exe -m pip show homeassistant  # must report not found
.venv-pure\Scripts\python.exe -m pytest tests/test_models.py tests/test_storage_pure.py tests/test_state_machine.py tests/test_foundation.py tests/test_slot_manager.py tests/test_traceability.py -q --tb=short --junitxml=pure.xml --cov=custom_components.moisture_loop --cov-branch --cov-report=term-missing
.venv-pure\Scripts\python.exe -m coverage report --include="*\state_machine.py" --fail-under=100
```

## Mandatory Home Assistant 2025.9.0 gate

```powershell
.venv-ha-min\Scripts\python.exe scripts/check_ha_contract.py --expect 2025.9.0
.venv-ha-min\Scripts\python.exe -m pytest tests -q --tb=short --junitxml=ha-2025.9.xml --cov=custom_components.moisture_loop --cov-branch --cov-report=term-missing --cov-fail-under=90
.venv-ha-min\Scripts\python.exe -m coverage report --include="*\state_machine.py" --fail-under=100
.venv-ha-min\Scripts\python.exe -m coverage report --fail-under=90
```

HA1/HA2 specifically:

```powershell
.venv-ha-min\Scripts\python.exe -m pytest tests/test_ha_contract.py -q --tb=short
```

The expected HA-environment skip is only
`TestPureBoundary::test_importing_models_does_not_import_homeassistant`; the
same node must pass in the pure report. Normative behavioral evidence may not
be skipped.

## Supported-current gate

Run the same complete integration suite in a separately created Python 3.14
environment. Do not layer these packages over the HA 2025.9 environment.

```powershell
.venv-ha-current\Scripts\python.exe scripts/check_ha_contract.py --expect 2026.8.3
.venv-ha-current\Scripts\python.exe -m pytest tests -q --tb=short --junitxml=ha-current.xml --cov=custom_components.moisture_loop --cov-branch --cov-report=term-missing
```

Review every supported-current skip and coverage change. The mandatory minimum
coverage thresholds remain authoritative even if current harness internals
change collection details.

## Traceability and focused safety regressions

After the pure and mandatory-minimum JUnit reports exist:

```powershell
.venv-ha-min\Scripts\python.exe scripts/check_traceability.py --pure-report pure.xml --ha-report ha-2025.9.xml
.venv-ha-min\Scripts\python.exe scripts/check_traceability.py --show I37 --show T59 --show ND17
```

The executed-evidence checker enforces all 135 normative IDs, I1-I37, T1-T59,
and the documented skip boundary. Its printed totals are derived from the
authoritative mapping in `tests/traceability_manifest.py` rather than
hand-edited literals; do not duplicate that mapping in user documentation.

Useful focused commands, runnable in either compatible HA harness unless noted:

```powershell
python -m pytest tests/test_config_flow.py::TestNativeSubentryDeletion -q --tb=short
python -m pytest tests/test_stage4_on_gate.py -q --tb=short
python -m pytest tests/test_storage_pure.py tests/test_storage.py -q --tb=short
python -m pytest tests/test_entities.py tests/test_services.py tests/test_repairs.py -q --tb=short
python -m pytest tests/test_lifecycle.py tests/test_reconciliation.py -q --tb=short
```

All tests use controlled time; behavioral ordering may use `await
asyncio.sleep(0)` only as an event-loop yield, never wall-clock sleeps.

## Quality and metadata checks

```powershell
python -m ruff check .
python -m ruff format --check .
git diff --check
```

Also parse every JSON/YAML metadata file, confirm `translations/en.json`
carries the fully expanded English strings (custom integrations do not use
Core's build-time `strings.json`, so none is shipped), check
service/icon/entity key parity, confirm manifest
version `0.1.0`, HACS minimum `2025.9.0`, empty runtime requirements, and audit
tracked release contents for virtual environments, caches, JUnit, diagnostics,
secrets, or migration artifacts.

Never delete or hand-edit Home Assistant `.storage` data in development
instructions. Recorder is not a safety reconstruction source.

## Hassfest and HACS

Local hassfest preflight uses the same official container as the action:

```powershell
docker run --rm -v "${PWD}:/github/workspace" ghcr.io/home-assistant/hassfest
```

The required hosted gates remain the workflow actions:

```yaml
uses: home-assistant/actions/hassfest@master
uses: hacs/action@main
```

HACS uses `category: integration` with no ignored checks. Local syntax checks
or container runs are useful preflight evidence but are not substitutes for
GitHub-hosted results on the exact final commit. Public GitHub hosting is also
required for HACS custom repositories; creating, mirroring, pushing, or
publishing is a separate external action.

## CI jobs

`.github/workflows/ci.yml` contains six required, non-optional jobs:

1. `lint` — Ruff lint and format check.
2. `test-pure` — complete no-HA pure suite and 100% state-machine branch gate.
3. `test-ha-2025-9-0` — exact mandatory HA release, HA1, full suite, overall
   at least 90% and state-machine 100% branch coverage.
4. `test-ha-current` — exact supported-current pin on Python 3.14, current HA1
   contract check, full suite, and branch-coverage report.
5. `hassfest` — required GitHub-hosted hassfest validation.
6. `hacs` — required GitHub-hosted HACS Action validation.

Slice 13 real UI, hardware, rename, physical timing, scale, deployment cadence,
and centralized brand/presentation validations are not completed by these jobs.
