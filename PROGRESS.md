# Moisture Loop Implementation Progress

This document tracks implementation work against the approved `SPECIFICATION.md` version `0.1.0-spec.4`, whose architectural-review verdict is **READY WITH PROTOTYPE VALIDATIONS**.

> **Source-of-truth boundary:** `SPECIFICATION.md` is authoritative for architecture, safety behaviour, state-machine behaviour, persistence behaviour, Home Assistant integration behaviour, lifecycle behaviour, terminology, acceptance criteria, and prototype validations. `PROGRESS.md` is authoritative only for implementation status, slice status, work completed, work remaining, tests actually run, implementation blockers, implementation notes, and deviations requiring review. `PROGRESS.md` must never override, weaken, reinterpret, or silently amend `SPECIFICATION.md`. If implementation appears to require contradicting the specification, record `[?] Requires specification review` under the affected slice and stop that work until the specification is explicitly reviewed.

## Current Position

- Current authorized slice: `None`
- Specification version: `0.1.0-spec.4`
- Historical implementation baseline: `Implementation and test records produced against spec.3 remain valid evidence of the work actually performed. Slices 0-8 and 10-11 were historically completed under spec.3; Slice 9 was partially implemented but did not complete deletion conformance; Slice 12 has implementation artifacts but remains in progress.`
- Current spec.4 conformance: `Spec.4 Remediation Stage 1 is complete. Its canonical schema-2 models, strict schema-1 migration, and focused persistence evidence are current; Slices 1 and 4 remain [~] because Stages 2/3 still own blocker/resource identity, zone-history handoff, reconciliation, and runtime consumption. Slices 2 and 6 remain fully conformant within their documented scopes. Slices 0, 3, 5, and 7-12 still require spec.4 implementation changes and/or new evidence.`
- Slice 9 specification status: `Resolved by approved spec.4. The former lack-of-pre-delete-hook specification question is closed by update-listener-driven tombstoned reconciliation and authoritative final ON gates. Slice 9 implementation remediation is not complete and has not been tested against the approved design.`
- Next implementation work: `Stage 2 is technically unblocked by the completed Stage-1 persistence primitives, but may begin only after explicit user authorization. No implementation work is currently authorized.`
- Release gates: `Spec.4 Remediation Stages 2-8 and the integrated named-test evidence remain outstanding; the supported-current Home Assistant harness has not been evidenced; GitHub-hosted hassfest and HACS Action have not been evidenced; all §46 prototype validations remain outstanding.`
- Slice 13: `Not started. No mock or existing automated result is treated as §46 prototype evidence.`
- Overall status: `Not release-ready. Stage 1 is complete with 421 passed/1 skipped in its focused HA 2025.9.0 coverage suite and 92.39% affected-module branch coverage (state_machine.py 100%). The broad historical-runtime suite currently has 555 passed, 90 expected downstream failures, 1 skipped, and 1 teardown error because Stages 2/3 have not yet created/consumed canonical records during runtime setup. Historical spec.3 evidence remains preserved.`

On 2026-08-22 the user explicitly authorized Spec.4 Remediation Stage 1 only. That work is complete and the authorization has returned to `None`. The 2026-08-21 instruction "implement as per progress.md" remains recorded only as the historical authorization under which the spec.3 implementation was produced. Any Stage 2-8 implementation or prototype work requires new explicit user authorization.

## Status Legend

- `[ ]` Not started
- `[~]` In progress / current-spec remediation required
- `[x]` Complete
- `[!]` Blocked
- `[?]` Requires specification review

A slice may be marked `[x]` only when all work in scope is complete, its acceptance criteria pass, its required automated tests pass, and no unresolved blockers remain. Prototype validations requiring real Home Assistant behaviour or physical hardware must never be marked complete based solely on mocks.

For this reconciliation, `[~] Spec.4 remediation required` means the slice's historical spec.3 completion and test record are preserved, but its current spec.4 conformance is incomplete. It does not mean remediation has started or is authorized. Unless explicitly updated as current-spec text, the original per-slice objectives, references, scope, acceptance criteria, completed/remaining work, test records, decisions, deviations, and blockers below remain the historical spec.3 baseline. Current conformance and remaining work are controlled by each current Status plus the Spec.4 Remediation Assessment and Plan above; a historical `None` under Remaining work or Blockers is not a spec.4 completion claim. Dated session-log entries remain unchanged historical evidence.

## Progress Summary

| Slice | Name | Status |
|---:|---|:---:|
| 0 | Repository and quality foundation | [~] Spec.4 remediation required |
| 1 | Pure domain models | [~] Spec.4 remediation required |
| 2 | Pure state machine | [x] |
| 3 | State-machine and invariant test suite | [~] Spec.4 remediation required |
| 4 | Persistence and run-integrity layer | [~] Spec.4 remediation required |
| 5 | Global SlotManager and resource blockers | [~] Spec.4 remediation required |
| 6 | Home Assistant moisture sensor adapter | [x] |
| 7 | Zone runtime controller | [~] Spec.4 remediation required |
| 8 | Startup, reload, reconfiguration, and shutdown lifecycle | [~] Spec.4 remediation required |
| 9 | Config flow and zone subentries | [~] Spec.4 remediation required; specification blocker resolved |
| 10 | Home Assistant entities and actions | [~] Spec.4 remediation required |
| 11 | Repairs, diagnostics, events, and logging | [~] Spec.4 remediation required |
| 12 | Distribution and documentation | [~] Spec.4 remediation and existing release gates required |
| 13 | Prototype validations | [ ] |

The `[x]` status for Slice 2 is retained because spec.4 explicitly preserves T1-T59 topology, guards, actions, destinations, and reasons; the broadened T21/T39 trigger source is a lifecycle-dispatch obligation outside the pure decision engine. Slice 6 remains `[x]` because spec.4 does not change its entity-filtered changed/unchanged-report normalization contract; persistent sensor identity and configuration handoff belong to the models/persistence/reconciliation work. Both slices still require regression execution in the eventual full spec.4 suite, but no new slice-scope behaviour has been identified.

All other previously completed slices marked `[~]` retain their dated spec.3 implementation and passing-test records below. They are not currently conformant because spec.4 changes their scope or requires new evidence. Slice 9's specification blocker is resolved, but implementation remediation and native HA 2025.9 websocket deletion evidence remain incomplete. Slice 12 also requires a post-remediation documentation/distribution pass in addition to its existing release gates.

## Specification Traceability

These are implementation-wide targets. Their definitions remain authoritative in `SPECIFICATION.md`; this list is a tracking index, not a substitute.

| Target | Authoritative location | Progress evidence required |
|---|---|---|
| 59 formal state transitions | §§14-15, T1-T59 | Table/diagram parity plus transition-test results; do not reproduce the transition set here. |
| 37 safety invariants | §27, I1-I37; §39.3 | Every invariant mapped to passing named tests at the appropriate layer, including the new configuration/deletion/identity obligations I32-I37. |
| 134 unique normative named behavioural test IDs | §39.2 | Mechanically inventoried from the approved specification: SR1-SR13, PI1-PI27, MF1-MF5, AC1-AC4, ER1-ER12, LC1-LC13, ND1-ND17, TB1-TB12, AR1-AR17, RC1-RC12, and HA1-HA2. This is a specification count, not an implementation/pass count. |
| Runtime Store schema 2 | §§23.2-23.5, 25, 42 | Verified schema-1 -> schema-2 migration, canonical safety records, independent zone histories/`zone_runtime`, durable tombstones, and full-payload read-back before grants. |
| Five controller states | §§12, 14-15 | `DISABLED`, `IDLE`, `WATERING`, `SOAKING`, and `FAULT`; runtime lifecycle remains orthogonal. |
| Pure state-machine branch coverage | §§37, 39.3 | 100% branch coverage for `state_machine.py`; overall suite target at least 90%. |
| Home Assistant minimum | metadata; §§5.1, 39.1-39.2 HA1-HA2, 41, 45.23-45.24 | Home Assistant >= 2025.9.0 source-contract verification and mandatory harness job; no 2025.7/2025.8 compatibility claim. |
| Local-only operation | §§1, 3, 40; I28; §45.28 | Dependency/network audit confirms no cloud, telemetry, API key, or outbound runtime dependency. |
| No Recorder safety dependency | §§3, 19.2, 23.1, 23.5; I28; §45.28 | Storage/recovery tests and dependency audit show safety decisions do not use Recorder. |
| No WATERING resume | §§24-25; I13; §45.12 | Restart, crash, reload, and reconfigure tests prove interrupted WATERING never resumes. |
| One idempotent OFF path | §§11.3, 22; I16; §45.9-45.10 | Race/lifecycle tests prove one shared OFF future and cooperative termination. |
| Keyed global resource blockers | §§6, 11.4, 21-22; I18-I19; §45.10-45.11 | ER1-ER12, TB1-TB12, AR1-AR17, and concurrency evidence prove independent `(safety_record_id, reason)` blockers across deletion, reactivation, and A -> B replacement. |
| Atomic, read-back-verified runtime Store | §23; I15, I24, I29, I31, I33-I37; §45.15-45.19 and §45.32-45.39 | `atomic_writes=True`, schema-1 migration, monotonic revisions, fresh-Store read-back, injected-failure tests, and initialization/tombstone/identity results. |
| Prototype validation separation | §§39.1, 46 and readiness verdict | Real HA/hardware evidence is recorded only in Slice 13; mocks alone never complete a prototype item. |

### Current test-evidence boundary

- **Normative named tests specified:** 134 unique IDs. A mechanical scan of §39.2 matched 134 entries, found 134 unique IDs, and found zero duplicates.
- **Tests currently implemented:** Stage-1 portions of PI21, PI22, PI23, PI27, TB7, and TB11 are implemented, together with strict schema/migration/cross-reference/contribution tests and retained relevant PI1-PI20 Store/run-integrity coverage. PI24-PI26 and all coordinator/runtime portions remain explicitly unclaimed for Stage 3.
- **Tests actually run/passing:** the 2026-08-22 Stage-1 focused HA 2025.9.0 coverage suite passed 421 tests with 1 expected pure-boundary skip; the pure Python 3.14.5 suite passed 391 tests; focused HA storage passed 31 tests. A broader inventory run produced 555 passed, 90 expected downstream failures, 1 skipped, and 1 teardown error at the temporary fail-closed runtime seam. Historical 2026-08-21 spec.3 totals remain unchanged below.

## Spec.4 Remediation Assessment

This assessment compares the approved spec.4 requirements with the dated spec.3 baseline and current remediation state. Stage 1 now declares Store schema 2 and persists canonical `safety_records` plus independent `zone_histories[*].zone_runtime`; `ZoneRecord` remains only a non-serialized temporary projection for untouched historical callers. SlotManager and runtime callers still use spec.3 zone identity, startup still lacks config+Store union and a reconciliation coordinator, config flow still owns old reload behaviour, and no authoritative current-subentry/snapshot/lifecycle gate surrounds actuator ON. Repairs/diagnostics/entities also still expose spec.3 runtime concepts. Those remaining observations assign Stages 2-8 and are not Stage-1 defects.

| Slice | Current assessment | Actual spec.4 impact |
|---:|---|---|
| 0 | `[~] Spec.4 remediation required` | The quality foundation remains useful, but HA1 currently checks the incompatible reload helper and lacks the approved listener/removal/`async_update_and_abort` contract. CI must later carry the new test inventory and current-HA evidence. |
| 1 | `[~] Stage 1 complete; later remediation required` | Stage 1 added `safety_record_id`, `safety_lineage_id`, independent `zone_history_id`/`zone_runtime`, immutable applied shadows, durable actuator identity/status, orthogonal lifecycle, contribution identity, and strict ownership validation. Stages 2/3 must consume these authorities in resource/runtime reconciliation. |
| 2 | `[x]` | The pure five-state T1-T59 decision semantics are unchanged. Reconciliation must dispatch the broadened T21/T39 trigger, but no new pure transition/state is required. |
| 3 | `[~] Spec.4 remediation required` | Historical T1-T59 proof remains valid, but traceability stops at I31 and does not supply LC13 or the new PI/ND/TB/AR/RC evidence for I32-I37. |
| 4 | `[~] Stage 1 complete; later remediation required` | Schema 2, strict schema-1 reading/migration, canonical records/histories, tombstones, contribution primitives, strict cross-references, Store-only migration, and verified atomic writes now pass Stage-1 evidence. Stages 2/3 still own live blocker reconstruction, A -> B handoff/merge orchestration, and startup reconciliation consumption. |
| 5 | `[~] Spec.4 remediation required` | SlotManager keys are `(zone_id, reason)` and admission has only a broad startup enable flag. It needs `(safety_record_id, reason)`, exact retained-record ownership, and the entry reconciliation dirty/running/failed/superseded barrier. |
| 6 | `[x]` | Entity-filtered changed/unchanged report delivery, normalization, timestamp, and freshness semantics remain normative. Persistent sensor identity and reconciliation handoff are assigned to Slices 1/4/8; real rename validation remains Slice 13. |
| 7 | `[~] Spec.4 remediation required` | The controller has write-ahead intent and one OFF path, but lacks the complete final pre-ON membership/fingerprint/snapshot/generation/lifecycle gate, no-suspension dispatch boundary, in-flight possible-flow marker, post-call recheck, deletion compensation, and safety-record blocker identity. |
| 8 | `[~] Spec.4 remediation required` | EntryRuntime has no listener-owned coordinator, immutable applied shadows, dirty/latest-snapshot barrier, add/change/remove classification, `DELETE_PENDING`/`RETIRED` handoff, startup config+Store union, exact same-record reactivation, or A -> B reconciliation. It currently skips Store-only hazardous records when configuration is absent. |
| 9 | `[~] Spec.4 remediation required` | The specification question is resolved. The implementation still has add-owned reload scheduling, `async_update_reload_and_abort`, no update-listener ownership, no native post-removal reconciliation, and no actual HA 2025.9 websocket deletion evidence. |
| 10 | `[~] Spec.4 remediation required` | Existing entities/actions remain useful, but actions do not yet reject non-`ACTIVE` or dirty/failed reconciliation and presentation lacks schema-2 safety/lineage/history/lifecycle/reconciliation ownership. |
| 11 | `[~] Spec.4 remediation required` | Existing events/logs/diagnostics/Repairs remain a baseline, but spec.4 requires exact-record tombstone/identity/reconciliation issues, an entry-level fix flow, safety/lineage/history identities, lifecycle/barrier/merge diagnostics, and deleted-zone-safe event payloads. |
| 12 | `[~] Spec.4 remediation and existing release gates required` | README/distribution metadata require a post-remediation accuracy pass; current traceability artifacts and HA1 contract must be updated. Supported-current HA, GitHub-hosted hassfest, and GitHub-hosted HACS Action evidence remain absent. |
| 13 | `[ ] Not started` | All seven real §46 validations remain outstanding. Existing mocks and harness tests do not satisfy them. |

## Spec.4 Implementation Remediation Plan

Stage 1 was explicitly authorized and is complete. No later stage is authorized or started. A later stage may be marked complete only after its named evidence is implemented and actually run.

### Stage 1 - Canonical models and Store schema-1 -> schema-2 migration

- **Status:** `[x] Complete on 2026-08-22`; authorization returned to `None` after the focused model, migration, Store, regression, lint, formatting, and coverage gates passed.

- **Objective:** introduce the approved ownership model: one canonical safety record per durable actuator lineage, independent zone histories with `zone_runtime`, durable identities/applied shadows/lifecycles/contribution IDs, strict schema-1 parsing, and atomic verified schema-2 migration without dropping any schema-1 fact.
- **Affected existing slices/files:** Slices 1 and 4; `const.py`, `models.py`, `storage.py`, `tests/test_models.py`, `tests/test_storage_pure.py`, and `tests/test_storage.py`.
- **Specification sections:** §§6, 12.4, 19.3-19.5, 23, 25.2-25.5, 42; I20, I23-I24, I29, I31, I33-I35, I37.
- **Required named tests:** PI21-PI23, PI27, TB7, and TB11; retain and rerun PI1-PI20.
- **Prerequisite stages:** none.
- **Completion evidence:** schema-1 preservation/migration and malformed/write/read-back failure cases pass; schema-2 round trips show correct single-authority field ownership; no grant or watering-capable runtime can use unverified migrated data. Full identity reactivation tests PI24-PI26 close in Stage 3.

### Stage 2 - Safety-record blocker identity and zone-history continuity

- **Objective:** re-key all hazards to `(safety_record_id, reason)`, add the reconciliation admission barrier to SlotManager, and implement deterministic contribution deduplication/conservative merge plus exact A/B hazard separation.
- **Affected existing slices/files:** Slices 1, 4, and 5; `models.py`, `storage.py`, `slot_manager.py`, controller/runtime call sites, `sensor.py`, and their focused tests.
- **Specification sections:** §§6, 11.4, 19.5, 21-22, 23.2, 24.4, 25.5; I18-I21, I23, I33, I35-I37.
- **Required named tests:** ER1-ER12, TB1-TB4, AR2-AR10, and AR17; exact-key portions are repeated end-to-end in Stage 7.
- **Prerequisite stages:** Stage 1.
- **Completion evidence:** snapshots and tests expose only safety-record blocker keys; one record/reason cannot clear another; dirty/reconciling/failed admission prevents grants; A-owned hazards stay A-owned while zone budget/interval continuity is conservatively verified.

### Stage 3 - Configuration reconciliation coordinator and runtime lifecycle

- **Objective:** register the entry update listener before grants, normalize immutable applied shadows, serialize/coalesce latest-snapshot reconciliation, materialize `ACTIVE`/`DELETE_PENDING`/`RETIRED`, reconcile current-config + Store union at startup, safely reactivate the exact same record, execute A -> B handoff, and coordinate unload/reload/shutdown without stale publication.
- **Affected existing slices/files:** Slices 4, 5, 8, and 9; `__init__.py`, `runtime.py`, the spec-aligned reconciliation component, `models.py`, `storage.py`, `slot_manager.py`, and lifecycle/reconciliation/storage tests.
- **Specification sections:** §§5.1, 12.4, 22.4, 23.2-23.5, 24, 25, 30, 37; I18-I19, I26, I32-I37.
- **Required named tests:** PI24-PI27, LC13, ND1-ND3, ND6, ND13-ND16, TB5-TB11, AR1-AR17, and RC5-RC12.
- **Prerequisite stages:** Stages 1-2.
- **Completion evidence:** actual add/change/remove snapshots are classified and published only at the latest verified generation; Store-only implicit tombstones block grants; exact UUID re-add mutates one record; A -> B preserves A hazards and logical-zone state/budget rules; listener/Store/reload/supersession failures remain fail closed.

### Stage 4 - Final pre-ON gate and delete/in-flight compensation

- **Objective:** place the complete authoritative live-configuration gate after all preparatory awaits, create the no-suspension dispatch boundary and in-memory possible-flow ownership, recheck immediately after ON returns/raises, and route every deletion race through one OFF/accounting operation with no resurrection.
- **Affected existing slices/files:** Slices 7 and 8; `zone_controller.py`, `runtime.py`/reconciliation interfaces, `slot_manager.py`, `storage.py`, and controller/lifecycle/deletion race tests.
- **Specification sections:** §§11.2-11.3, 13, 18.1, 22.1-22.3, 23.4, 24.4, 25; I15-I19, I22, I32-I34, I36-I37.
- **Required named tests:** ND4-ND12, ND17, RC1-RC6, and AC1-AC4; rerun SR5-SR13 and MF1-MF5 to prove watchdog/manual behaviour is unchanged.
- **Prerequisite stages:** Stages 1-3.
- **Completion evidence:** deterministic future/event interleavings prove no post-mismatch ON, durable intent covers every crash window, in-flight calls compensate immediately, and each outcome has one terminal reason, one idempotent OFF, honest accounting, retained blockers, and no future pulse/session resurrection.

### Stage 5 - Config flows and reconciler-owned reload application

- **Objective:** retain pre-mutation quiescence where applicable, replace `async_update_reload_and_abort` with `async_update_and_abort`, remove add/flow-owned reload scheduling, validate durable identity/same-record/A -> B conflicts, and make the reconciler the sole zero-or-one reload owner.
- **Affected existing slices/files:** Slices 0, 8, and 9; `config_flow.py`, `runtime.py`/reconciliation component, `scripts/check_ha_contract.py`, strings/translations, and `tests/test_config_flow.py`/lifecycle tests.
- **Specification sections:** §§5.1, 9, 24.3-24.5, 29-30, 39.1; I26, I32-I36.
- **Required named tests:** LC3, LC13, ND1-ND2, AR1, AR5-AR6, AR11-AR16, RC7-RC8, and HA1.
- **Prerequisite stages:** Stages 1-4.
- **Completion evidence:** source/runtime checks prove the approved helper/listener pairing; add/reconfigure/delete bursts have one application owner; actual native removal supplies the post-removal mapping; delete-only work does not reload; a stable mixed batch schedules at most one supported reload after durable safety handoff.

### Stage 6 - Entities, actions, Repairs, diagnostics, events, and logging

- **Objective:** reject actions/entities against deleted, non-`ACTIVE`, dirty, failed, or unavailable runtime; expose safety/lineage/history/lifecycle/barrier/merge facts; implement exact-record tombstone Repairs and fix flow; and keep deleted-zone events independent of removed device IDs.
- **Affected existing slices/files:** Slices 10 and 11; `services.py`, `entity.py`, `sensor.py`, `binary_sensor.py`, `switch.py`, `button.py`, `repairs.py`, `diagnostics.py`, event/logging integration, strings/translations/icons, and surface tests.
- **Specification sections:** §§5.3, 26.3, 28, 31-34, 37; I25, I27, I32-I37.
- **Required named tests:** LC1-LC2, ND14, ND16-ND17, TB12, AR14, and RC9-RC11, plus the existing MF3-MF5 and AC4 event-order regressions.
- **Prerequisite stages:** Stages 1-5.
- **Completion evidence:** translated refusal tests cover non-ACTIVE/dirty runtime; exact-record fix flows reject stale/cross-record/unproven-OFF acknowledgement; diagnostics/events identify the owning safety record without inventing a device; registry cleanup cannot destroy safety ownership.

### Stage 7 - Full HA 2025.9 behavioural suite and I1-I37 traceability

- **Objective:** implement and run the complete approved named-test set against the integrated schema-2 architecture, including the real HA 2025.9 websocket removal route and registry cleanup, while retaining pure-state-machine and coverage guarantees.
- **Affected existing slices/files:** Slices 0 and 3-11; all existing tests plus spec.4 reconciliation/deletion test modules and the HA contract checker.
- **Specification sections:** §§14-15, 27, 39, 45; T1-T59 and I1-I37.
- **Required named tests:** all 134 unique IDs: SR1-SR13, PI1-PI27, MF1-MF5, AC1-AC4, ER1-ER12, LC1-LC13, ND1-ND17, TB1-TB12, AR1-AR17, RC1-RC12, and HA1-HA2.
- **Prerequisite stages:** Stages 1-6.
- **Completion evidence:** exact commands, environment/Core versions, counts, failures, coverage, T1-T59 parity, and I1-I37 mapping are recorded; native deletion uses `config_entries/subentries/delete`; no real sleeps; no mock result is claimed as §46 evidence.

### Stage 8 - Post-remediation documentation, supported-current HA, and distribution CI

- **Objective:** align user/developer documentation with safe native deletion and schema 2, then execute the separately pinned supported-current HA job and GitHub-hosted hassfest/HACS release gates without publishing.
- **Affected existing slices/files:** Slices 0 and 12; `README.md`, `DEVELOPMENT.md`, manifest/HACS metadata if accuracy changes are required, `.github/workflows/ci.yml`, `scripts/check_ha_contract.py`, and tracking/release documentation.
- **Specification sections:** §§39.1, 41-43, 45-46.
- **Required named tests:** HA1-HA2 and the full 134-ID suite as the release regression; hassfest and HACS Action are additional distribution gates, not behavioural test IDs.
- **Prerequisite stages:** Stage 7.
- **Completion evidence:** supported-current HA version/command/count is recorded; mandatory 2025.9.0 remains green; GitHub-hosted hassfest and HACS Action results are recorded; docs no longer describe the spec.3 deletion limitation; Slice 13 remains separately unstarted until explicitly authorized.

## Rules for Codex

1. Read `SPECIFICATION.md` before beginning or modifying an implementation slice.
2. `SPECIFICATION.md` overrides `PROGRESS.md`.
3. Work only on the slice explicitly authorized by the user.
4. Do not begin future slices simply because they appear easy or related.
5. A prerequisite outside the current slice may be added only if strictly necessary, and it must be documented.
6. Do not silently change architecture or safety semantics.
7. Ambiguity that affects behaviour must be recorded under Blockers / Specification Review.
8. Update `PROGRESS.md` after every implementation session.
9. Record tests actually run, not tests merely expected to pass.
10. Record exact failures or known limitations.
11. Do not mark a slice complete until its acceptance criteria and required tests pass.
12. Do not mark hardware/prototype validations complete using mocks.
13. Preserve Home Assistant 2025.9.0 minimum-version compatibility unless the specification is formally revised.
14. Preserve the pure state-machine boundary defined by the specification.
15. Never weaken fail-closed water safety to make a test pass.
16. Never amend `SPECIFICATION.md` as part of an implementation slice unless the user explicitly authorizes a specification revision.

## Slice 0 - Repository and quality foundation

### Status

`[~] Spec.4 remediation required (historically complete under spec.3 on 2026-08-21)`

### Objective

Establish the repository layout, repeatable development/test environment, and quality/CI foundation without implementing integration runtime behaviour.

### Specification references

- §§5.6, 38, 39.1, 41 and 42.
- Minimum-platform checks HA1-HA2 in §39.2.
- Acceptance criteria §45.23-45.24, limited here to foundational tooling and job setup; final release compliance belongs to Slice 12.

### Scope

- Establish the repository/test layout anticipated by §38.
- Configure Home Assistant custom-integration development dependencies, pytest, linting, formatting, and coverage collection.
- Establish CI jobs for unit/HA tests, hassfest, and HACS validation, with a mandatory Home Assistant 2025.9.0 test environment and a separate supported-current environment where needed.
- Add release-source API-contract-check scaffolding for HA1.
- Document the local validation commands used by later slices.

### Out of scope

- Domain models, controller states, guards, transitions, runtime controllers, HA listeners, actuator commands, persistence behaviour, entities, config flows, or actions.
- Final manifest/HACS metadata, release documentation, branding, or a claim that distribution validation passes; those belong to Slice 12.
- Any runtime scaffolding that implies watering behaviour.

### Dependencies

None. This is the first implementation slice, but it still requires explicit user authorization.

### Expected files

- Root dependency and quality configuration, such as `pyproject.toml` and test requirements/constraints files.
- `.gitignore` if required.
- `.github/workflows/` quality/test workflow files.
- `tests/` harness configuration and shared non-behavioural fixtures where required.
- Repository layout directories from §38 only where tooling requires them; no runtime implementation files.

### Acceptance criteria

- A clean environment can install the declared development dependencies reproducibly.
- Pytest, lint, format-check, and coverage commands are defined and execute successfully against the foundation.
- CI syntax is valid and separates the mandatory HA 2025.9.0 job from supported-current testing when one matrix is impractical.
- hassfest and HACS validation jobs are configured for their eventual release gates without falsely claiming a not-yet-created package passes.
- No runtime controller behaviour or future-slice implementation exists.

### Required tests / verification

- Run and record dependency installation or environment bootstrap verification.
- Run and record pytest collection/smoke verification.
- Run and record lint and formatting checks.
- Validate CI workflow syntax/configuration.
- Verify the HA 2025.9.0 job remains mandatory and HA1 source-contract checks have a defined execution path.

### Completed work

- `pyproject.toml`: ruff (lint+format), pytest (`asyncio_mode=auto`, `testpaths=tests`), coverage (branch, source `custom_components/moisture_loop`) configuration. No packaging metadata (HACS distribution, not a pip package).
- `requirements_test.txt`: pinned pure-layer environment (pytest 9.1.1, pytest-asyncio 1.4.0, pytest-cov 7.1.0, coverage 7.15.4, ruff 0.16.4); deliberately excludes homeassistant to prove the §37 boundary.
- `requirements_test_ha.txt`: mandatory HA 2025.9.0 environment via `pytest-homeassistant-custom-component==0.13.277` (verified on PyPI 2026-08-21 to pin exactly `homeassistant==2025.9.0`, Python >= 3.13).
- `requirements_test_ha_current.txt`: supported-current environment via `pytest-homeassistant-custom-component==0.13.356` (pins `homeassistant==2026.8.2`), kept as a separate pinned environment per §39.1.
- `.github/workflows/ci.yml`: jobs `lint`, `test-pure` (asserts homeassistant absent; enforces the state_machine 100%-branch gate once the file exists), `test-ha-2025-9-0` (mandatory; exact-version assert plus HA1 contract check), `test-ha-current`, `hassfest`, `hacs`. hassfest/HACS jobs are armed but skip honestly until `manifest.json`/`hacs.json` exist (Slice 12), so no false pass is claimed.
- `scripts/check_ha_contract.py`: HA1 execution path — verifies, inside the exactly pinned HA environment, every §5.1 normative API: `ConfigSubentryFlow.async_update_reload_and_abort(..., reload_even_if_entry_is_unchanged)`, `ConfigEntry.runtime_data`/`ConfigSubentry`, state change/report/entity-registry event helpers, `State.last_reported`, `Store(atomic_writes=...)`, nested `DeviceSelectorConfig.filter`, `IssueSeverity` WARNING/ERROR/CRITICAL, `ValveEntityFeature` OPEN/CLOSE, `EVENT_HOMEASSISTANT_STOP`, `ServiceValidationError`.
- `tests/conftest.py` (minimal, HA-import-free) and `tests/test_foundation.py` (toolchain smoke, mandatory-job presence check, HA1 script presence, AST-based no-homeassistant-import audit of the pure layer).
- `DEVELOPMENT.md`: environments, bootstrap, and all local validation commands for later slices; test-module conventions (`pytest.importorskip("homeassistant")` for HA suites).
- `.gitignore`.

### Remaining work

None.

### Tests actually run

All on 2026-08-21, Windows 11, local venv Python 3.14.6:

- `python -m venv .venv` + `pip install -r requirements_test.txt` equivalent (packages installed and frozen into `requirements_test.txt`) -> PASS (reproducible pinned environment).
- `python -m pytest -q` -> PASS (4 passed: foundation smoke suite).
- `python -m ruff check .` -> PASS (after auto-fix/format of initial findings).
- `python -m ruff format --check .` -> PASS (7 files).
- CI workflow YAML syntax validation (`yaml.safe_load` of `.github/workflows/ci.yml`; 6 jobs parsed) -> PASS.
- HA 2025.9.0 job verified mandatory in workflow (asserted by `tests/test_foundation.py::test_ci_workflow_exists_and_keeps_mandatory_ha_job`); HA1 has a defined execution path (`scripts/check_ha_contract.py --expect 2025.9.0` wired into that job) -> PASS.

Not run here: actual GitHub Actions execution (repository is not yet a git repo / not pushed) and the HA-harness jobs themselves (require Python 3.13 on a HA-supported platform; the local machine is Windows / Python 3.14). Those run in CI.

### Decisions / implementation notes

- Local development machine is Windows with Python 3.14; HA 2025.9.0 requires Python 3.13 on a HA-supported platform, so HA-harness suites are CI-only. The pure layer runs and is verified locally. Recorded as an environment constraint, not a deviation.
- The directory is not a git repository and `git init`/commits were not performed (not requested). CI workflows take effect once the repo is pushed to GitHub.
- Pure-layer CI job proves the no-homeassistant boundary by asserting the package is absent, then running the full test tree; HA-dependent test modules self-skip via `pytest.importorskip("homeassistant")`.
- Coverage release gates are enforced by CI commands (guarded by file existence) rather than static `fail_under`, so the foundation passes honestly before code exists.

### Deviations from specification

None.

### Blockers

None.

## Slice 1 - Pure domain models

### Status

`[~] Spec.4 remediation required (historically complete under spec.3 on 2026-08-21)`

### Objective

Implement the Home Assistant-independent types that express the specification's controller vocabulary and deterministic transition inputs/results.

### Specification references

- §§6, 9, 12, 18.2, 19, 20, 23.2, and 26.
- Pure-layer boundary in §§3.11 and 37; proposed layout in §38.
- Relevant invariants I6-I12, I22-I24, I29-I31 in §27.

### Scope

- Controller-state, session-mode, moisture-classification, fault, completion-reason, runtime-estimation-reason, and related enums.
- `ZoneConfig`, `MoistureObservation`, `SessionContext`, normalized transition input/result, guard-result, and pure session/runtime structures required by the specification.
- Exact configuration bounds and model-level structural validation where that validation is HA-independent.
- Fields required for the five-state model, retained sensor-fault overlay, freshness/deadline token decisions, runtime accounting metadata, run IDs, and Store schema representation where appropriate as pure data.

### Out of scope

- Transition decision logic, HA imports/events/entities/selectors, Store I/O, timers, locks/tasks, actuator calls, and action handlers.
- Adding states, modes, faults, completion reasons, or configuration semantics not defined by the specification.

### Dependencies

- Slice 0 complete.

### Expected files

- `custom_components/moisture_loop/models.py`
- `custom_components/moisture_loop/const.py`
- Focused pure-model test files under `tests/` where needed.

### Acceptance criteria

- All specification-defined states, modes, moisture classifications, faults, completion reasons, estimation reasons, and required data fields are represented without semantic additions or omissions.
- Configuration constraints match §9 exactly, including strict threshold ordering.
- Pure model modules import no `homeassistant` package and perform no I/O.
- Equality, serialization-friendly values, and model validation are deterministic and covered by tests.

### Required tests / verification

- Unit tests for enum/value completeness and round-trip-safe representations.
- Boundary tests for every §9 range and strict `start_threshold < target_threshold` rule.
- Tests for valid/invalid `MoistureObservation`, session fields, fault overlay data, manual clamp metadata, and runtime-estimation metadata.
- Import/dependency audit proving the pure domain layer has no Home Assistant imports.

### Completed work

- `custom_components/moisture_loop/const.py`: domain, store schema version, config keys, config-entry identity keys (`runtime_store_generation_id`, `runtime_store_initialized`), §9 defaults and exact bounds (durations integer seconds), moisture value range, actuator domains, OFF retry count, and the §14 guard identifiers.
- `custom_components/moisture_loop/models.py` (pure, frozen dataclasses + StrEnums):
  - Enums with exact spec spellings: `ControllerState` (5), `SessionMode` (2), `MoistureClassification` (4), `FaultCode` (8, with the full §26.1 property matrix: blocks_automatic always, sensor-only/manual-allowed, auto-clear, user-ack, reconfigure-only), `CompletionReason` (14, with §26.2 reason classes), `RuntimeEstimationReason` (4), `BlockerReason` (3), `ManualClampReason` (3), `ActuatorFinding`, `TimerKind`.
  - `MoistureObservation` (§6) with structural validation, `is_fresh` (equality is fresh), `fresh_until`.
  - `WatchdogToken` (generation + deadline, exact-match semantics, §18.5).
  - `ZoneConfig` with every §9 bound including strict `start < target` and dynamic pulse-duration lower bounds for session/daily limits; HA-independent entity-ID domain shape checks (existence/feature checks stay in the config flow).
  - `SessionContext` (§12.2, immutable with `evolve()`, retained fault restricted to sensor-only), `SessionSummary` (§23.2), `DailyRuntime`, `GuardResult`, `ActuatorAssessment` (conservative, contradiction-rejecting), `ResourceAssessment`.
  - Normalized controller event union (27 event types covering evaluation, manual, deadlines, watchdog token callbacks, moisture reports, actuator confirmations/timeouts, external interference, lifecycle, integrity, startup reconciliation, slot grants) and requested-action union (persist/ON/OFF/timers/watchdog/slot/blockers/events) as pure data.
  - `TransitionInput` / `Decision` structures for the Slice 2 engine, with structural invariants (UTC-aware datetimes enforced everywhere; no-op decisions cannot carry state changes or actions).
- `custom_components/moisture_loop/__init__.py`: docstring-only package marker (no HA imports, no runtime behaviour) — documented prerequisite so the package is importable by tests; lifecycle implementation remains Slice 8.
- `tests/test_models.py`: 73 new tests (see below).

### Remaining work

None. (Slice 2 may extend models.py only where already-specified pure result structures require it.)

### Tests actually run

All on 2026-08-21, local venv Python 3.14.6, no homeassistant installed:

- `python -m pytest -q` -> PASS (77 passed: 73 model tests + 4 foundation).
- `python -m pytest --cov --cov-branch` -> PASS; coverage 100.00% (branch) for `const.py`, `models.py`, `__init__.py`.
- `python -m ruff check .` / `ruff format --check .` -> PASS.
- Import/dependency audit -> PASS twice over: AST audit (`test_pure_modules_have_no_homeassistant_import`) plus runtime `sys.modules` audit (`test_importing_models_does_not_import_homeassistant`).

Test content: enum completeness/exact-value sets and round-trip by value for all enums; full §26.1 fault matrix; §26.2 reason classes; §9 boundary matrix (min-1/min/max/max+1 for every ranged field), strict threshold ordering incl. equality refusal, dynamic session/daily lower bound = pulse duration, entity-domain checks; §10 observation structure incl. 0/100 valid, NaN/inf/out-of-range rejection, freshness equality boundary; session context immutability/evolve/retained-fault restriction; guard-result/actuator-assessment/decision/transition-input invariants; UTC-awareness enforcement.

### Decisions / implementation notes

- Durations are modeled as integer seconds (`*_s`), matching the §23.2 fingerprint canonicalization; thresholds are floats (percent).
- All model datetimes must be timezone-aware UTC; naive or non-UTC datetimes raise at construction/validation. This makes timestamp-comparison semantics (§18.4 equality rules) safe by construction.
- The controller-event and requested-action unions were defined here (Slice 1 scope covers "normalized transition input/result") so Slice 2's `state_machine.py` defines logic only. Slice 2 may still extend these where a specified pure result structure requires it.
- `Decision.transition_id` carries the §14 row ("T1".."T59") only on formal transitions; commit-phase/bookkeeping/no-op decisions carry `None`, matching the §14 note that watchdog no-ops and slot waits are controller events, not transitions. This enables the Slice 3 mechanical T1-T59 parity audit.

### Deviations from specification

None.

### Blockers

None.

## Slice 2 - Pure state machine

### Status

`[x] Complete (2026-08-21; spec.4 leaves the pure T1-T59 behaviour unchanged)`

### Objective

Implement the complete deterministic five-state decision engine using normalized inputs and pure results only.

### Specification references

- §§12-18, 20, 22.2, 26, 27, and 37.
- Formal transition table T1-T59 in §14 and its §15 projection.
- Hysteresis rules in §17; pulse/soak/recheck and watchdog decisions in §18.
- Acceptance criteria §45.2, §45.4-45.9, §45.12, §45.20, and §45.26.

### Scope

- All five states and every formal transition T1-T59.
- Formal guards, exact threshold/equality behaviour, whole-pulse fit, cycle/session/daily limits, and minimum-session interval decisions.
- AUTO and MANUAL decisions, retained sensor-fault overlay, completion/fault outcomes, and first-terminal-reason arbitration that belongs in pure logic.
- Post-soak qualification, grace decisions, and generation/deadline-token watchdog decisions from normalized events.
- Pure decisions that request ON, OFF, persistence, waiting, faulting, completion, or no-op without performing side effects.

### Out of scope

- HA service calls, timers, listener registration, persistence I/O, actuator adapters, locks/tasks, SlotManager implementation, events, entities, or Repairs.
- Reinterpreting a callback timestamp as a report timestamp or allowing HA objects into the pure core.

### Dependencies

- Slice 1 complete.

### Expected files

- `custom_components/moisture_loop/state_machine.py`
- Updates to `custom_components/moisture_loop/models.py` only where already-specified pure result structures are required.
- Focused transition tests may begin alongside the implementation, with the exhaustive proof completed in Slice 3.

### Acceptance criteria

- T1-T59 are implemented with destinations, guards, actions, reasons, and faults matching §14.
- The pure engine implements exact hysteresis and boundary semantics with no epsilon.
- It distinguishes automatic freshness expiry from SOAKING recheck/grace and keeps MANUAL sensor-independent.
- It produces deterministic no-op decisions for stale watchdog tokens and other non-transition controller events described after T59.
- It contains no Home Assistant imports, service/timer/persistence/actuator calls, hidden global clock, or I/O.
- No state, guard, transition, or safety behaviour exists beyond or contrary to the specification.

### Required tests / verification

- Focused unit tests for every implemented guard and state family during development.
- Threshold, equality, whole-fit, manual-fault-overlay, post-soak, watchdog-token, and first-terminal-request tests.
- Mechanical audit that exactly T1-T59 are represented and remain consistent with §15.
- Pure-layer import and side-effect audit.
- Full transition/invariant suite and 100% branch coverage are completed in Slice 3.

### Completed work

- `custom_components/moisture_loop/state_machine.py`: complete pure decision engine, one function `decide(TransitionInput) -> Decision`, implementing all T1-T59 with destinations, guards, actions, reasons, and faults per §14; the §14 guard legend as named helper predicates; exact §17 hysteresis with no epsilon; §18.1/18.3/18.4/18.5 pulse/soak/recheck/grace and the exact six-step watchdog-callback algorithm with generation/deadline-token no-op semantics; §19.1/19.2 accounting anchors (measured commanded->OFF; RESTART_RECOVERY from intent; clamped at zero; open accounting on unproven OFF); §20.1 manual clamp formula with all-caps-below-request clamp reasons; §22.2 first-terminal-request arbitration and ACTUATOR_OFF_TIMEOUT destination supersede; §25.2/25.3 startup decisions (T48-T51) including the owner-only rebase.
- Model extensions permitted by this slice (already-specified pure structures): `SessionIdentity` (deterministic session identity supplied by the controller — the pure core cannot generate UUIDs), `ScheduleEvaluation` action (T47), `Decision.secondary_fault` (MF5 §12.3), `Decision.final_session` (closed-session snapshot accompanying `clear_session` for §23.2 summary building), `TransitionInput.external_on` (T58/T59 occupancy guard) and `.new_session_identity`, `StartupPersistedSoaking.current_run_id`/`.unsafe_fault` (T50/T51).

### Remaining work

None.

### Tests actually run

See Slice 3 (the focused development tests and the exhaustive suite were built together in this session; all results recorded there). Import/side-effect audits: AST + runtime `sys.modules` audits prove no homeassistant import; the only time source is `TransitionInput.now_utc` (no datetime.now/utcnow calls exist in the module).

### Decisions / implementation notes

- **Two-phase WATERING exits.** Terminal triggers produce a commit decision (sets `pending_termination_reason` — the §12.2 field — first request wins, requests the one idempotent OFF, latches any fault immediately so "AUTO WATERING stops immediately" is visible); OFF evidence produces the formal §14 row: `OffConfirmed` finalizes the committed reason's row with the destination evaluated at OFF confirmation (as §20.3 requires for T7/T8/T9), `OffNotConfirmed` yields T15/T34/T49. The zone presents WATERING while OFF executes, matching §12.1 ("ON until termination/OFF sequence"). T16 finalizes directly at the external-OFF event because that observation is itself trustworthy closure evidence (§19.1). Commit decisions carry `transition_id=None`; row IDs appear exactly once per completed transition, which is what makes the Slice 3 mechanical audit exact.
- Normal AUTO pulse end is a continuation, not a termination: `PulseDeadlineReached` requests OFF without setting a pending reason; `OffConfirmed` with no pending reason on an AUTO session is T6 (soak deadlines derived from `off_confirmed_at_utc`). Manual deadlines commit `MANUAL_COMPLETE`.
- Waiting for the global slot and declining an offered grant are non-transition resource decisions (`RequestSlot`/`ReleaseSlot` with a recorded G-SLOT guard result), per the §14 note after T59.
- The finalize destination applies the `POST(retained/new fault)` legend plus the §22.3 rule that Disable controls operational state: any non-fault finalize with `enabled=false` lands in DISABLED.
- `assert` statements are internal-consistency checks on adapter contracts (e.g., a VALID observation carries `reported_at_utc`), not decision logic; they are excluded from the branch-coverage gate via `coverage` config (`exclude_also`), while every real guard/decision branch is measured and covered. Contract violations that are meaningful (WATERING/SOAKING without a session; session creation without identity; trusted adoption without a run ID) raise `ValueError` and are covered by tests.
- `ConfigurationInvalid` during WATERING/SOAKING is not a §14 row; entity removal reaches the engine as sensor/actuator unavailability (T10/T13 paths), matching §10.4. T5 fires from IDLE (and from FAULT when a different fault was active); T53 from setup.

### Deviations from specification

None. (The two-phase commit/finalize split is an execution model for the §14 rows, not a semantic change: every row keeps its trigger, guard, actions, destination, and reason; §14's own preamble requires committed reasons with deferred `session_finished` on unproven OFF.)

### Blockers

None.

## Slice 3 - State-machine and invariant test suite

### Status

`[~] Spec.4 remediation required (historically complete under spec.3 on 2026-08-21)`

### Objective

Prove the pure control logic exhaustively before any Home Assistant runtime is permitted to command water.

### Specification references

- T1-T59 in §14 and diagram parity in §15.
- I1-I31 in §27 and invariant-to-test mapping in §39.3.
- Test mechanics and named groups SR1-SR13, PI1-PI20, MF1-MF5, AC1-AC4, ER1-ER12, LC1-LC12, and HA1-HA2 in §39.
- Acceptance criteria §45.2, §45.4-45.9, §45.12, and §45.26-45.28 as applicable to the pure layer.

### Scope

- Table-driven coverage for every formal transition T1-T59, including every conditional destination.
- Pure decision tests for all I1-I31 obligations that belong at the state-machine boundary, with an explicit traceability matrix for obligations whose side-effect proof is completed in later slices.
- Exact threshold and time equality tests, manual-fault paths, post-soak timing, watchdog token/current-deadline semantics, whole-pulse limits, and deterministic race/event ordering in pure logic.
- Coverage enforcement at 100% branch coverage for `state_machine.py`.

### Out of scope

- Claiming that pure tests prove HA listener delivery, Store durability, actuator acknowledgement, lifecycle cleanup, entity behaviour, real HA UX, or physical hardware behaviour.
- Implementing HA adapters or side effects to satisfy a test.

### Dependencies

- Slice 2 complete.

### Expected files

- `tests/test_state_machine.py`
- Additional pure test-data/traceability helpers under `tests/` if required.
- Coverage configuration established in Slice 0.

### Acceptance criteria

- Every T1-T59 row has at least one passing table-driven test and every guard branch/conditional destination is exercised.
- Every I1-I31 invariant is mapped to named evidence; pure responsibilities pass here and later-layer obligations remain explicitly assigned rather than falsely claimed.
- Equality at start, target, freshness, soak, grace, session, and daily boundaries matches the specification.
- Manual overlay, post-soak, watchdog, and pure race decisions are deterministic.
- `state_machine.py` reports 100% branch coverage.
- The pure suite uses controlled time inputs and no real sleeps.

### Required tests / verification

- Run the complete pure unit suite and record the exact command/result.
- Run branch coverage and record the exact `state_machine.py` result.
- Run a mechanical T1-T59 inventory/parity check.
- Review the I1-I31 traceability matrix for omissions and identify future-slice evidence without marking it already complete.

### Completed work

`tests/test_state_machine.py` (244 tests), including:

- **Mechanical T1-T59 inventory/parity**: a canonical-input table with exactly one representative input per row; `test_inventory_is_exactly_t1_to_t59` asserts the ID set is exactly {T1..T59}; the parametrized table test asserts each row produces its own `transition_id` and its expected destination state.
- **Guard-branch coverage**: every T1 guard failure individually recorded in T2 (G-EN, G-FRESH stale + unavailable, G-START, G-INT, G-ACT unknown + observed-ON, G-DAY); slot-wait and blocker-wait non-transitions; SlotGranted re-run/decline; the full manual refusal matrix (invalid/NaN/negative duration, disabled, active session in WATERING/SOAKING/lingering record, blocking fault, actuator, daily exhausted, occupied resource, slot queue).
- **Exact equality (§§10/17/18, SR3/SR12)**: start threshold (29.999 starts / 30.0 does not), target (39.999 continues / 40.0 completes), freshness boundary (exactly max_age fresh; 1 µs older not), interval boundary, daily and session whole-fit equality, report exactly at `soak_ends` qualifies / 1 µs earlier does not, report exactly at the grace deadline qualifies.
- **Watchdog (§18.5, SR5-SR13 pure)**: extension from a report's own timestamp without reaching the old deadline (SR6/SR7), older-replay no-shortening, the exact SR13 regression (10:00->12:00 arm, 11:59->13:59 re-arm, deliberately executed stale (g1, 12:00) callback no-ops with zero actions/fault/reason and WATERING preserved), current-token expiry commit, future-deadline re-arm, both exact boundary interleavings deterministic (report-first prevents expiry; watchdog-first terminates permanently and a later report cannot resurrect), MANUAL exemption, mismatched/absent token no-ops, post-commit no-ops.
- **Termination arbitration (§22, AC1/AC2 pure)**: first terminal request owns the reason; nine second-request event types no-op; Stop vs pulse expiry produces one reason and one OFF; Disable-after-Stop still lands DISABLED; T15/T49 supersede semantics with open accounting (no `session_finished`, blocker added, estimation flagged); delayed OFF proof closes accounting at the later timestamp in FAULT and DISABLED (AC4 pure) while the acknowledgement-required fault stays latched.
- **Manual (§20, MF1-MF5 pure)**: the exact §35.5 clamp example (45 req / 30 / 20 / 12 -> 12 min with all three clamp reasons), tie-not-a-clamp, per-fault allow/refuse matrix, T8 no-event-churn, T9 finish-then-clear ordering, MF5 actuator-fault supersede with secondary sensor context, Stop-during-manual retained/recovered destinations.
- **Soak/recheck (§18.4)**: SR2's 10-seconds-after-OFF report never deciding, T23 grace arming, post-deadline INVALID/UNAVAILABLE fault paths at report and grace time, stale-replay waits, T25 cycle increment/anchor reset/watchdog re-arm, T26/T27/T28 reasons, T32 from both event and recheck path, external interference commit/T33/T34 with blocker key independence, T37 preservation, T50 owner-only rebase (LC10's pure assertion: the rebased session equals the original except `owner_run_id`) with offline-deadline timer selection, T51 safe/unsafe/disabled destinations, T48 intent-anchor estimation (never scheduled pulse end), found-ON/UNPROVEN commit-then-escalate paths.
- **Accounting (§19.1/§19.2 pure)**: measured commanded->OFF, zero-flow zero charge, negative-interval clamp, restart intent anchor.
- **I1-I31 traceability matrix**: all 31 invariants mapped; pure obligations reference named tests in this module (existence mechanically verified); side-effect obligations are explicitly assigned to Slices 4-12 as named future test groups, not claimed.
- Determinism spot-checks (same input -> equal Decision) and error paths (missing session/identity/run-id raise).

### Remaining work

None at the pure layer. Later-layer invariant obligations remain explicitly assigned in `INVARIANT_EVIDENCE` (Slices 4-12).

### Tests actually run

All on 2026-08-21, local venv Python 3.14.6, no homeassistant installed, controlled time inputs, no sleeps:

- `python -m pytest -q` -> PASS: **321 passed** (244 state-machine + 73 models + 4 foundation).
- `python -m pytest --cov --cov-branch` -> PASS; `python -m coverage report --include="*/state_machine.py" --fail-under=100` -> PASS: **state_machine.py 100.00% (526 statements, 316 branches, 0 missed)**.
- `python -m coverage report --fail-under=90` -> PASS: overall **100.00%** (1045 statements, 394 branches).
- `python -m ruff check .` and `ruff format --check .` -> PASS.
- Mechanical T1-T59 parity check -> PASS (`TestTransitionTable`).
- I1-I31 traceability review -> PASS (`TestInvariantTraceability`; 31/31 mapped, pure references mechanically verified to exist, future-slice evidence explicitly assigned, never claimed complete).

### Decisions / implementation notes

- Coverage excludes `assert` lines only (see Slice 2 note); the 100% branch figure covers every real guard and decision branch.
- §15 diagram parity is subsumed by the table audit at this layer: every row ID is produced by exactly one canonical decision with its §15-projected destination asserted. The release-gate diagram review is re-run mechanically in Slice 12.

### Deviations from specification

None.

### Blockers

None.

## Slice 4 - Persistence and run-integrity layer

### Status

`[~] Spec.4 remediation required (historically complete under spec.3 on 2026-08-21)`

### Objective

Implement the safety-critical runtime Store, initialization identity, verified writes, conservative accounting, and run/session integrity primitives.

### Specification references

- §§18.2, 19, 23, 25.2-25.3, 26, 37-38, and 42.
- Persistence tests PI1-PI20 and lifecycle adoption tests LC5-LC10 in §39.2.
- Invariants I10-I15, I23-I24, I29, and persistence portion of I31.
- Acceptance criteria §45.7, §45.13-45.19.

### Scope

- Independent config-entry `runtime_store_generation_id` and `runtime_store_initialized` transaction.
- Runtime Store schema 1, matching generation, monotonically increasing `store_revision`, and one entry-wide persistence lock.
- Construction with `atomic_writes=True` and fresh same-key Store read-back verification of schema, generation, revision, and expected safety payload.
- Run-ID protocol using `active_run_id` and `last_clean_shutdown_run_id` primitives; lifecycle orchestration uses them in Slice 8.
- Write-ahead hazardous intent and ordered persistence anchors before/after actuator commands.
- Missing, corrupt/unloadable, future-version, generation-mismatched, interrupted-initialization, and unverifiable-write handling.
- Conservative measured/estimated runtime accounting, open intervals, current-local-day budgets, HA-local midnight/DST splitting, and multi-day reconciliation calculations.
- Persisted session/fault/summary data and stable config fingerprint support.

### Out of scope

- Issuing actuator commands, startup listener ordering, controller task/timer orchestration, trusted-SOAKING activation, full shutdown, config-entry reload, or subentry flows.
- Using Recorder, direct `.storage` filesystem probes, or scheduled pulse end as a crash-accounting upper bound.
- Authorizing water from an unverified safety write.

### Dependencies

- Slices 0-3 complete.

### Expected files

- `custom_components/moisture_loop/storage.py`
- Relevant pure persistence structures in `models.py`.
- `tests/test_storage.py`

### Acceptance criteria

- The exact §23.5 initialization/integrity matrix is implemented, including safe PI2 interrupted-initialization adoption and fail-closed integrity loss.
- Every safety Store uses `atomic_writes=True`; every safety write increments revision and passes exact fresh-Store read-back before dependent action.
- Failed, stale, missing, mismatched, corrupt, unloadable, or future-version data cannot authorize AUTO or MANUAL watering or reset current-day history to zero.
- Integrity reconstruction exhausts the current day's budget and preserves same-day exhaustion after acknowledgement.
- Write-ahead intent is verified before any future ON caller can proceed.
- Runtime uncertainty is overestimated, labelled, split at HA-local calendar boundaries including DST, and fully charged.
- Concurrent zone writes serialize without lost updates.

### Required tests / verification

- PI1-PI20, including injected crashes/write/read-back failures and concurrent revision tests.
- Property/boundary tests that estimates never undercount every modeled plausible stop in the uncertainty interval.
- Normal, midnight, DST spring/fall, and multi-day accounting tests using controlled time.
- Schema/generation/revision/payload round-trip tests through a fresh `Store` instance.
- Verify no Recorder dependency and no direct storage-filesystem probing.

### Completed work

- `custom_components/moisture_loop/storage.py` — `SafetyStore`:
  - §23.5 setup decision matrix (`async_classify_setup`): first install, safe interrupted-initialization adoption (PI2), and every integrity-loss row (initialized+absent, corrupt-returns-None, unloadable-raises, generation mismatch under both flag values, future schema, present-but-malformed with initialized=false); previously initialized state can never be reinterpreted as a first install (I29).
  - §23.5 first-install transaction steps 3-4 (`async_first_initialize`: schema-1 initial safe state, matching generation, null run IDs, revision 1, atomic save + fresh-Store read-back) and integrity-loss reconstruction steps 4-5 (`async_reconstruct_after_integrity_loss`: every zone FAULT/RESTORED_FROM_UNSAFE_STATE with the detection-day budget exhausted at `max_daily_runtime`).
  - §23.4 verified-write core: every Store constructed `atomic_writes=True`; every safety write increments `store_revision`, saves, loads through a fresh same-key Store, and compares generation, revision, and full payload; any failure raises `StoreWriteVerificationError` and the in-memory snapshot is not adopted (schema equality is guaranteed by the strict parser, which only accepts schema 1).
  - §23.3 run-ID primitives: `async_begin_new_run` (captures previous IDs, persists/verifies the new active ID, leaves last-clean unchanged), `async_mark_clean_shutdown`, and `RunIds.previous_run_was_clean` (clean only when both non-null and equal).
  - Entry-wide persistence lock serializing all load/modify/save/verify operations; `async_update_zone` writes complete merged snapshots (PI20); `async_rebase_soaking_owner` changes only `session.owner_run_id` with verified persistence (the §25.3 storage primitive; LC9/LC10 storage portions).
- `models.py` additions (pure persistence structures, per this slice's expected files):
  - §23.2 schema-1 structures `RunIds`, `ZoneRecord`, `StoreData` and strict serializers (`store_data_to_dict/from_dict`, zone/session/summary converters) with exact §23.2 field names; live-only session fields (freshness deadline, watchdog generation, last recheck value, pending reason) are deliberately not persisted; distinct `FutureStoreVersion` vs `MalformedStoreData` errors; UTC-aware ISO datetimes enforced.
  - §19.3 accounting: `split_interval_by_local_days` (real local midnights converted to UTC — never fixed 24-hour additions; DST days of 23/25 hours proven) and `current_day_charge`; §23.2 `config_fingerprint` (SHA-256 of versioned canonical JSON: both entity IDs, all §9 settings as integer-second durations, HA timezone, sorted keys).
- `tests/test_storage.py` (HA harness; 29 tests) and `tests/test_storage_pure.py` (pure; 57 tests — documented addition so schema/accounting proofs run in the no-homeassistant environment too).
- Local HA 2025.9.0 verification environment established: `uv`-provisioned Python 3.13.12 venv (`.venv-ha`) with `pytest-homeassistant-custom-component==0.13.277` (`homeassistant==2025.9.0` exactly). Windows accommodations (all local-only; CI is Linux with none of them): pycares pinned to 4.4.0 for aiodns compatibility, a `resource`-module stub inside the venv, a win32-only conftest block (Selector event loop policy, pytest-socket neutralization — Windows asyncio needs AF_INET socketpairs, and an inert zeroconf-resolver fixture override).

### Remaining work

None at this layer. PI12-PI14 (crash-recovery actuator reconciliation end-to-end) intentionally complete in Slice 8, which lists them again; their decision/accounting components are already proven (T48/T49 in Slice 3; interval math here).

### Tests actually run

All on 2026-08-21:

- HA 2025.9.0 environment (`.venv-ha`, Python 3.13.12, `homeassistant==2025.9.0`): `python -m pytest tests/ --cov=custom_components/moisture_loop --cov-branch` -> PASS: **406 passed, 1 skipped** (env-specific pure-boundary test self-skips); coverage **100.00% branch on every module** including `storage.py` (123 stmts, 20 branches).
- Pure environment (Python 3.14.6, no homeassistant): `python -m pytest --cov --cov-branch` -> PASS: **379 passed, 1 skipped**; models/state_machine/const at 100.00%; storage.py excluded from pure execution by design (HA import).
- `python scripts/check_ha_contract.py --expect 2025.9.0` in `.venv-ha` -> PASS: **all 11 HA1 API contract checks pass against the exact pinned release** (after fixing runtime_data detection to read class annotations).
- `ruff check` / `ruff format --check` -> PASS.
- PI evidence at this layer: PI1-PI11 fully (matrix, adoption, fail-closed writes, swallowed-write detection via read-back, previous-revision preservation, tamper-detection for generation/revision/payload, atomic_writes assertion, budget-blocking after reconstruction and after simulated same-day acknowledgement, cross-checked through the pure state machine's guards); PI15-PI17 (conservative estimation property, §35.4 midnight split, Sydney 23 h/25 h DST days, Berlin DST-gap split, multi-day outage recognition); PI18-PI20 (run-ID cleanliness, crashed-intermediate-run rejection, unverified-run-ID fail-closed, concurrent-write serialization with strictly increasing revisions and no lost updates).

### Decisions / implementation notes

- Store key is `moisture_loop.<entry_id>`; generation identity (not the key) is the §23.5 authority.
- `async_classify_setup` treats present-but-malformed data with `initialized=false` as integrity loss: data exists, so it is not a first install and cannot be silently replaced.
- Reconstruction restarts `store_revision` at 1 in the replacement Store (the prior revision is unknowable); monotonicity holds per Store lifetime.
- Recorder independence and no-filesystem-probing hold by construction: `storage.py` imports only `homeassistant.helpers.storage.Store`; there is no recorder import and no direct file access anywhere in the integration (final audit re-run in Slice 12).
- The local `.venv-ha` accommodations weaken no repository guarantee: CI jobs run the untouched harness on Linux; the socket-block neutralization lives in a win32-only conftest branch that never executes in CI.

### Deviations from specification

None.

### Blockers

None.

## Slice 5 - Global SlotManager and resource blockers

### Status

`[~] Spec.4 remediation required (historically complete under spec.3 on 2026-08-21)`

### Objective

Implement integration-wide FIFO watering serialization and independently keyed conservative physical-flow blockers.

### Specification references

- Water-resource definition in §6; actuator interference in §11.4.
- §§21, 22.3, 25.1, 25.4, and 37.
- T15, T33-T34, T49, T54-T55, and T58-T59.
- ER1-ER8 and ER12 in §39.2.
- Invariants I18-I19 and I21; acceptance criteria §45.10-45.11.

### Scope

- Global FIFO ownership with at most one integration-commanded flowing zone.
- Deterministic blocker set keyed by `(zone_id, reason)`.
- Independent `external_flow`, `integration_off_unconfirmed`, and `actuator_not_proven_off` reasons.
- Grant/refusal/wait behaviour requiring no owner and an empty blocker set, with guards rechecked on offer.
- Tail requeue after SOAKING and safe release only after proven terminal OFF.
- Startup population/update primitives and serialized actuator-observation-versus-grant handling.
- Diagnostics-ready blocker/owner snapshots and concurrency correctness.

### Out of scope

- Zone-state decisions, actuator service calls, HA listener installation, startup lifecycle orchestration, user-facing entities, or an administrator override not specified for v0.1.
- A single global boolean or any removal of a different zone/reason key.

### Dependencies

- Slices 0-4 complete.

### Expected files

- `custom_components/moisture_loop/slot_manager.py`
- `tests/test_slot_manager.py`

### Acceptance criteria

- FIFO ownership prevents concurrent integration ON commands.
- Every blocker is keyed and independently addable/removable; one OFF observation cannot clear another zone or reason.
- Unknown/unavailable/transitional state never proves OFF or releases a blocker.
- No grant occurs during startup reconciliation or while any blocker/owner remains.
- External IDLE/DISABLED flow is respected while globally blocking integration watering.
- Adversarial interleavings of observations, blocker updates, releases, and slot requests are deterministic.

### Required tests / verification

- ER1-ER8 and ER12.
- Two-zone and multi-zone FIFO ordering tests.
- Concurrent owner/blocker/grant interleaving tests with deterministic futures/events.
- Key-independence tests for multiple zones and multiple reasons on one zone.
- Startup-disabled-grant tests and full guard recheck on offered grants.

### Completed work

- `custom_components/moisture_loop/slot_manager.py` — pure-asyncio `SlotManager` (no homeassistant imports; added to the AST purity audit):
  - Global FIFO ownership: at most one owner; requests queue in order; a zone has at most one live request (duplicates return the same handle); an owner's repeat request is already granted; cancellation and cancelled-future skip handling.
  - Deterministic keyed blocker set `(zone_id, BlockerReason)` with the three reasons (`external_flow`, `integration_off_unconfirmed`, `actuator_not_proven_off`); adds idempotent; removal is exact-key only and can never clear another zone/reason.
  - Grant rule: grants enabled (startup reconciliation complete) AND no owner AND empty blocker set; every state change re-evaluates under one lock, so blocker updates and grant decisions serialize (ER8/ER12 semantics). Grantees re-run all guards on the offer; a declined offer (release) triggers the next offer.
  - `async_requeue_tail` for post-pulse soaking fairness (§21); `async_release` refuses non-owners; startup gating via `async_enable_grants`/`async_disable_grants` (grants disabled at construction).
  - Diagnostics-ready `snapshot()` (owner, queue order, sorted blockers, gating flag).
- `tests/test_slot_manager.py` (pure, 21 tests): manager-level ER1, ER3-ER8, ER12 portions; multi-zone FIFO ordering; tail requeue; decline flow; startup gating; adversarial interleavings of external blocker add/remove with concurrent zone requests proving every grant occurred with an empty blocker set; a 10-zone concurrency test proving at-most-one concurrent owner (I21); exact-key independence including removal of non-existent keys.

### Remaining work

None at this layer. Controller integration (ER9-ER11 and grant-to-guard wiring) is Slice 7; the startup subscribe-before-snapshot interleaving (full ER12) is Slice 8; ER2's DISABLED-zone framing needs the zone controller and completes in Slice 7/8 (the manager-level blocker behaviour it depends on is proven here and is zone-state-independent by design).

### Tests actually run

All on 2026-08-21:

- Pure environment: `python -m pytest --cov --cov-branch` -> PASS: **400 passed, 1 skipped**; `slot_manager.py` **100.00% branch** (95 stmts, 20 branches); models/state_machine/const also 100.00%.
- HA 2025.9.0 environment: `python -m pytest tests/ --cov --cov-branch` -> PASS: **427 passed, 1 skipped; 100.00% branch coverage across all six modules**.
- `ruff check` / `ruff format --check` -> PASS.

### Decisions / implementation notes

- The slot queue is not persisted (§21); the manager is rebuilt at startup with grants disabled and blockers repopulated before `async_enable_grants` (proven by the pre-enable blocker test).
- Grant delivery is future-based (`SlotRequest.granted`); offers assign ownership immediately, and guard re-checks happen in the grantee under its zone lock — a failed re-check declines via `async_release`, which is also the deterministic "decline" path tested here.
- `async_disable_grants` stops new offers without touching current ownership; safe-OFF handling of the owner remains the controller's job.

### Deviations from specification

None.

### Blockers

None.

## Slice 6 - Home Assistant moisture sensor adapter

### Status

`[x] Complete (2026-08-21; adapter scope is unchanged by spec.4)`

### Objective

Convert Home Assistant moisture-entity activity into the specification's normalized, timestamp-correct domain observations without implementing watering control.

### Specification references

- §§5.2, 6, 10, 16, 18.4-18.5, 22.3, and 37.
- SR1-SR4, SR6-SR8, SR12-SR13 in §39.2 as adapter inputs/normalization obligations.
- Invariants I1-I5, I30; acceptance criteria §45.2-45.6.

### Scope

- Entity-filtered `async_track_state_change_event` and `async_track_state_report_event` subscriptions for configured moisture entity IDs.
- Changed and unchanged report normalization through the same `MoistureObservation` path.
- Use of `State.last_reported`/event `last_reported`, never callback or fallback-scan time as report time.
- VALID, STALE, INVALID, and UNAVAILABLE classification, finite `[0, 100]` validation, age/freshness calculation, and exact equality semantics.
- Entity-registry update/removal tracking inputs, with rename behaviour left for the §46 prototype validation.
- Lightweight callback and fallback-scan observation seams that feed normalized events only.

### Out of scope

- Starting/stopping water, actuator services, session tasks, state-machine reinterpretation, Store writes, slot grants, entities/actions, or lifecycle orchestration.
- Global `state_reported` subscription followed by Python filtering.
- Treating a fallback scan as a new report.

### Dependencies

- Slices 0-3 complete; Slice 5 interfaces available before controller integration.

### Expected files

- The moisture-listener/normalization portion of `custom_components/moisture_loop/zone_controller.py`, or another existing architecture-aligned adapter seam if implementation structure requires it.
- `tests/test_state_reported.py`
- Shared HA test fixtures established under `tests/`.

### Acceptance criteria

- Changed and byte-for-byte identical state/attribute writes reach one normalized-observation contract through their correct HA event helpers.
- Entity IDs are passed directly to `async_track_state_report_event`; no wildcard/global listener exists.
- `reported_at_utc`, freshness, classification, numeric bounds, NaN/infinity, and exact equality match §§6 and 10.
- Callbacks remain lightweight and cannot call actuator services or authorize water.
- Entity removal produces the specified invalid-configuration input; rename handling is instrumented for later real-HA validation without inventing fallback semantics.

### Required tests / verification

- HA harness reproduction from §39.1: identical second `hass.states.async_set` emits the report path and advances `last_reported` without relying on a state-change callback.
- Adapter portions of SR1-SR4, SR6-SR8, SR12-SR13.
- Classification table tests for absent, unavailable, unknown, unparsable, NaN, infinity, out-of-range, stale, and valid boundary values.
- Listener entity-filtering, cleanup, fallback-scan, and registry removal/update tests.

### Completed work

- `custom_components/moisture_loop/zone_controller.py` (Slice 6 portion — moisture adapter only; the session owner is Slice 7):
  - `classify_moisture`: one shared normalization path for both event kinds implementing the exact §10.2 table (UNAVAILABLE for absent/`unavailable`; INVALID for `unknown`, unparsable, NaN, ±infinity, <0, >100 — rejected, never clamped; 0 and 100 valid; VALID/STALE by report-time freshness with equality fresh; a finite value with no report timestamp is conservatively INVALID). `age_s` derives from the report time and is floored at zero.
  - `MoistureAdapter`: entity-filtered `async_track_state_change_event` + `async_track_state_report_event` with the configured entity ID passed directly (no wildcard/global listener); the changed path uses `new_state.last_reported` and the unchanged path uses the report event's `last_reported` (never callback time); `async_track_entity_registry_updated_event` feeds removal (-> the CONFIGURATION_INVALID input) and rename (instrumented with a WARNING plus optional hook for §46 item 3, no invented fallback); `scan_current()` re-reads the stored State's `last_reported` and can never manufacture a new report; idempotent start, full unsubscribe on stop; injectable clock for deterministic tests; callbacks are lightweight observation-only sinks.
- `tests/test_state_reported.py` (HA harness, 29 tests).

### Remaining work

None at this layer. Controller wiring (coalescing, zone lock, feeding `decide()`) is Slice 7; live rename auto-fixup validation is §46 item 3 (Slice 13).

### Tests actually run

All on 2026-08-21:

- HA 2025.9.0 environment: `python -m pytest tests/ --cov --cov-branch` -> PASS: **456 passed, 1 skipped; 100.00% branch coverage on all seven modules** including `zone_controller.py`.
- Pure environment: `python -m pytest` -> PASS: 400 passed, 2 skipped (both HA suites self-skip; the pure gate modules remain 100.00%).
- `ruff check` / `ruff format --check` -> PASS.
- §39.1 harness reproduction on real HA 2025.9.0 -> PASS: a second byte-for-byte identical `hass.states.async_set` (same state, same attributes) emits the entity-filtered report path, advances `last_reported`, and requires no ordinary state-change callback (the change path is proven to have run exactly once, for the first write).
- Adapter portions of SR1/SR3 (identical report advances the timestamp and qualifies at the exact soak deadline through the pure T25 path), SR8 (INVALID/UNAVAILABLE classification specifics), SR12 (freshness equality at exactly `sensor_max_age` fresh, one microsecond older stale).
- Classification-table matrix (absent, unavailable, unknown, unparsable, empty, NaN, ±inf, -0.1, 100.1, 1e6, boundary 0/100, stale, valid); structural `validate()` on the produced observations.
- Listener entity-filtering (another entity's changed and identical writes never reach the sink), idempotent start, unsubscribe-on-stop, fallback-scan report-time semantics (a scan an hour later keeps the stored timestamp; past max age the same report classifies STALE — a scan cannot manufacture freshness), registry removal/rename/unrelated-update handling, and a no-service-call proof (mock switch services registered; observation events never call them).

### Decisions / implementation notes

- Rename handling is deliberately instrumentation-only pending §46 item 3: WARNING log plus an `on_renamed` hook the entry runtime may use once real-HA validation decides between auto-fixup and Repair-and-reconfigure.
- The adapter's clock is injectable for deterministic freshness tests; the default is `homeassistant.util.dt.utcnow`.

### Deviations from specification

None.

### Blockers

None.

## Slice 7 - Zone runtime controller

### Status

`[~] Spec.4 remediation required (historically complete under spec.3 on 2026-08-21)`

### Objective

Implement the asynchronous per-zone session execution layer that applies pure decisions safely to Home Assistant actuators, timers, persistence, and SlotManager resources.

### Specification references

- Actuator contract §11; session model §12; evaluation §§16-18; limits/manual §§19-20; concurrency §22; architecture §37.
- T1, T3, T6-T21, T22-T36, T40-T41, T56-T57 as runtime-executed decisions.
- SR2-SR13, MF1-MF5, AC1-AC4, ER9-ER11 in §39.2.
- Invariants I3-I10, I15-I23, I27, I30; acceptance criteria §45.2-45.12 and §45.20.

### Scope

- One session-owner task, one transition lock, cooperative termination signalling, first-terminal-request handling, and one shared idempotent OFF future per active zone.
- Switch and valve ON/OFF adapters with tagged HA Context, acknowledgement, timeout, retry, and terminal-state/position semantics.
- Verified write-ahead intent gate before ON and persistence of command/confirmation/deadline/accounting anchors.
- Pulse/manual deadlines, SOAKING deadlines, post-soak/grace handling, and AUTO sensor-freshness generation/deadline watchdog tokens.
- Stale queued callback no-op behaviour and exact simultaneous report/watchdog ordering under the zone lock.
- External actuator interference during WATERING/SOAKING, runtime accounting handoff, SlotManager acquisition/release/blockers, and state-machine result execution.
- Evaluation coalescing, fallback scan handling, and timer/listener unsubscribe ownership.

### Out of scope

- Startup/reload/reconfiguration/full-shutdown orchestration, config flows, public actions/entities, Repairs/diagnostics/event presentation, packaging, or hardware claims.
- `Task.cancel()` as routine Stop/Disable/fault/reload control.
- Any ON outside the session owner or any second normal OFF sequence.

### Dependencies

- Slices 0-6 complete.

### Expected files

- `custom_components/moisture_loop/zone_controller.py`
- Supporting architecture-aligned actuator adapter code within the §38 layout.
- `tests/test_zone_controller.py`
- Updates to `tests/test_state_reported.py`, `tests/test_storage.py`, and `tests/test_slot_manager.py` only for controller integration coverage.

### Acceptance criteria

- Normal AUTO and bounded MANUAL sessions execute only after pure guards, slot grant/recheck, and verified hazardous intent.
- Every integration-owned WATERING exit converges on one idempotent OFF future; OFF proof/retry/fault/blocker/accounting semantics match §11.3.
- Pulse, soak, recheck, grace, and AUTO freshness timers use absolute deadlines and controlled, race-safe token validation.
- AUTO INVALID/UNAVAILABLE/current-deadline stale stops cooperatively and never resumes; MANUAL ignores sensor health.
- External OFF during WATERING and external ON during SOAKING follow their exact deterministic accounting, cancellation, defensive-OFF, and escalation paths.
- All required runtime races yield one final session reason and one OFF operation.
- The corrected watchdog regression is exact: report at 10:00 arms 12:00; report at 11:59 arms 13:59; deliberately executing the old queued 12:00 callback no-ops, issues no OFF, emits no fault or terminal reason, preserves the 13:59 arm, and leaves WATERING active.

### Required tests / verification

- SR2-SR13, including exact SR13 old-token regression and both exact-boundary interleavings.
- MF1-MF5 and AC1-AC4.
- ER9-ER11 plus controller integration with SlotManager blocker/ownership tests.
- Scripted mock switch and valve tests for ON/OFF acknowledgement, transitional/unavailable states, position, retries, timeouts, delayed proof, and external interference.
- Deterministic task/timer races using futures/events and mocked time; no real sleeps.
- Verify no duplicate ON/session, no duplicate OFF sequence, and no stale callback side effect.

### Completed work

- `custom_components/moisture_loop/zone_controller.py` — `ActuatorAdapter` and `ZoneController`:
  - **ActuatorAdapter (§11.1):** switch/valve command adapters (`switch.turn_on/off`, `valve.open_valve/close_valve` with tagged HA `Context`); conservative assessment (unknown/unavailable/unrecognized/transitional never proven OFF; valve `closed` with position 0 or no position is OFF; nonzero position — even with terminal `closed` — is potentially flowing); `is_terminal_on` separates acknowledgement (terminal on/open only) from conservative potentially-flowing (`opening` blocks but never confirms).
  - **ZoneController:** one zone transition lock; every normalized event decided by the pure core under it, side effects executed from the Decision's action list. One session-owner background task is the only normal ON caller and normal OFF owner (§22.1): callbacks commit terminations through `decide()` and wake it. One shared idempotent OFF-operation future per exit (§11.3): first caller creates it, joiners await it, up to three attempts with the confirm-timeout each (HA-timer based, no real sleeps), unconfirmed completion dispatches `OffNotConfirmed`; a completed-confirmed operation short-circuits further assurance only while the actuator still reads proven OFF (a re-flowing actuator gets a fresh defensive operation — the external-ON-during-SOAKING case).
  - §11.2 ON sequence with the verified write-ahead gate: persist intent (verified), arm watchdog no later than ON, §18.5 pre-ON freshness re-check under the lock (expired -> never issue ON, stale/OFF-assurance path), issue ON, persist `pulse_commanded_at_utc` immediately after the call; ON acknowledgement from the actuator listener (terminal state only) arms the absolute pulse/manual deadline; every persist failure fails closed (`RESTORED_FROM_UNSAFE_STATE`, no ON, defensive OFF where not proven off).
  - Absolute-deadline timers (`async_track_point_in_time`) for pulse/manual/soak/grace/on-confirm plus the token-carrying watchdog arm (best-effort cancellation; correctness from token validation in the pure core); stale-timer housekeeping on state exits and confirmation.
  - Moisture adapter sink under the lock; actuator listener classifying own-acknowledgement vs external ON/OFF vs unavailability by phase; SlotManager integration (request/queue/decline, grants re-dispatching `SlotGranted` or the queued manual request with its duration, recorded under the lock before the wait task can run); §19.3/§19.4 accounting (per-growth daily charge split at HA-local midnights, lazy rollover, `last_session_end` on every closure), §23.2 summary building from `final_session`; event emission hooks (payloads finalized in Slice 11).
- `tests/test_zone_controller.py` (54 tests) with scripted mock switch AND valve (ack/silent/error behaviors), frozen time via pytest-freezer + `async_fire_time_changed`, deterministic settle loops — no real sleeps.

### Remaining work

None at this layer. Startup/reload orchestration (which events to feed for persisted sessions) is Slice 8; event payload finalization/ordering proofs are Slice 11.

### Tests actually run

All on 2026-08-21, HA 2025.9.0 environment: **510 passed, 1 skipped; 100.00% branch coverage on all seven modules** (`zone_controller.py`: 560 stmts, 174 branches, 0 missed). Pure environment: 401 passed, 3 skipped (HA suites self-skip). `ruff check`/`format` PASS. Highlights against the mandated groups:

- **SR2-SR13 controller portions:** full pulse->soak->recheck->target session (exact runtime/daily accounting, one start and one finish event); SR5 freshness expiry stops flowing AUTO at the deadline and never resumes; SR6 identical `state_reported` extends from its own timestamp (token generation+1); the exact SR13 regression — deliberately executed stale token callback no-ops with zero actions/fault/OFF and the newer arm preserved; SR8 INVALID/UNAVAILABLE immediate specific paths; SR9 manual runs through unavailable and invalid reports to its bounded deadline; SR12 boundary semantics from Slice 6/3 remain in force (§18.1 pre-ON re-check proven by injected slow persistence: ON never issued, `SENSOR_STALE`).
- **MF1-MF5:** T40 retained-fault manual with no event churn (no duplicate fault_set, no fault_cleared while running), MF4 recovery finish-then-clear ordering, MF5 actuator fault supersedes with the sensor fault retained as secondary and manual subsequently refused, clamped manual arms the effective deadline exactly (1799 s still watering, 1800 s finished).
- **AC1-AC4:** Stop and Disable each produce exactly one OFF sequence and reason; Stop-then-pulse-expiry yields one reason/one OFF/one finish; AC4 three silent OFF attempts -> `ACTUATOR_OFF_TIMEOUT` with keyed blocker, open accounting (no session_finished), then hours-later observed OFF closes accounting at the later timestamp (runtime 3690 s), removes only the matching blocker, and leaves the acknowledgement-required fault latched; clear_fault refused before OFF proof and accepted after (T44/T43).
- **ER9-ER11 + slot integration:** external OFF mid-pulse closes accounting at the observed time with the defensive OFF still issued; external ON during SOAKING counter-commanded (T33) and escalation on unproven OFF (T34 with blocker retained); interference during an in-flight OFF joins the same operation (no second sequence); external ON in IDLE respected without OFF while blocking evaluation until proven OFF (T54/T58); blocked evaluations queue and start on blocker removal; queued manual re-issues with its duration on the grant.
- **Valve:** transitional `opening` never confirms ON; `closing` never proves OFF; T6 only after terminal `closed`+position-0 proof; the full §11.1 assessment matrix unit-tested.
- **Failure injection:** write-ahead gate (persist failure -> no ON), post-ON anchor persist failure, mid-session persist failure with flowing actuator (fail-closed + forced OFF), ON/OFF service exceptions (attempts continue per §11.3), OFF-operation internal error resolves the shared future False.
- **No duplicates:** report bursts during WATERING never re-ON (one session_started); at most one ON per pulse and one OFF operation per exit asserted throughout.

### Decisions / implementation notes

- T6 releases the slot; the qualifying recheck's `RequestSlot` joins the queue tail. This implements §21's "release and later requeue at the tail" without a soaking zone holding or being re-offered the slot it cannot use (an immediate tail-requeue self-grant would block other dry zones for the whole soak).
- Own-command vs external classification is phase-based (own acknowledgement only while WATERING with a commanded-unconfirmed session and no OFF in flight; OFF proof during an active OFF operation is consumed by the operation), which is deterministic under the zone lock without trusting context objects.
- Session-owner/slot-wait tasks are HA background tasks; short-lived event dispatches are tracked tasks. `assert`s in the controller mark invariants guaranteed by the pure core (every closure carries a reason; session_finished only after a summary exists) and are coverage-excluded like the pure layer's.
- Windows test-harness detail: `asyncio.wait_for` never times out under frozen time, so all waiting uses HA timers; teardown uses direct cancellation.

### Deviations from specification

None. (The T6 slot-release refinement above preserves §21's semantics — at most one integration-commanded flowing zone, tail-fair interleaving — and is recorded here for review visibility.)

### Blockers

None.

## Slice 8 - Startup, reload, reconfiguration, and shutdown lifecycle

### Status

`[~] Spec.4 remediation required (historically complete under spec.3 on 2026-08-21)`

### Objective

Implement entry/process lifecycle orchestration, startup safety reconciliation, crash recovery, and trusted-SOAKING adoption without ever resuming WATERING.

### Specification references

- §§5.1, 5.5, 23.3-23.5, 24, 25, 26, and 37-38.
- T19-T21, T37-T39, T48-T53.
- PI12-PI20 and LC3-LC12 in §39.2.
- Invariants I11-I19, I24-I26, I29, I31; acceptance criteria §45.9, §45.12-45.19, §45.22-45.23.

### Scope

- First setup ordering through Store identity, verified new-run persistence, configuration validation, passive actuator subscription, all-actuator snapshot/re-read reconciliation, trusted-SOAKING adoption, and only then runtime activation.
- Persisted WATERING recovery for found-ON, found-OFF, and unknown/unavailable/transitional actuators with no pulse resume.
- Trusted persisted SOAKING checks, current-run owner rebase/read-back, original session/timing preservation, offline deadline handling, and untrusted termination.
- Clean/unclean run detection and once-only `EVENT_HOMEASSISTANT_STOP` handling.
- Graceful full shutdown, generic entry unload/reload, subentry reconfiguration/deletion preparation, setup failure, listener/platform teardown, and bounded cancellation fallback.
- Correct `HOME_ASSISTANT_SHUTDOWN`, `CONFIG_RELOAD`, `CONFIG_CHANGED`, and `RESTART_RECOVERY` outcomes.

### Out of scope

- UI config-flow forms, public entities/actions, Repairs/diagnostics presentation, packaging, or physical shutdown timing proof.
- Marking entry reload/reconfigure/removal/setup failure as a clean process shutdown.
- Resuming a persisted WATERING pulse or continuing SOAKING across generic reload.

### Dependencies

- Slices 0-7 complete.

### Expected files

- `custom_components/moisture_loop/__init__.py`
- Updates to `storage.py`, `zone_controller.py`, and `slot_manager.py` for lifecycle integration.
- `tests/test_lifecycle.py`
- Focused lifecycle additions to `tests/test_storage.py` and `tests/test_zone_controller.py`.

### Acceptance criteria

- No watering-capable listener, evaluation, controller, or slot grant activates before every §25.1 safety prerequisite completes.
- Every persisted WATERING path terminates/reconciles conservatively and never resumes.
- Trusted SOAKING continues only after every §25.3 guard and verified owner rebase; untrusted or failed rebase never activates watering.
- Two consecutive clean run adoptions remain trusted; an unclean intermediate run, fingerprint change, bad timing/structure/OFF state, or write failure prevents continuation.
- Full shutdown stops WATERING, honestly persists safety outcomes, preserves only eligible SOAKING, and marks clean last.
- Generic reload and subentry change terminate using distinct specified reasons and schedule no duplicate reload.
- Setup failure commands no ON and performs minimal defensive reconciliation where required.

### Required tests / verification

- PI12-PI20 and LC3-LC12.
- Found-ON/found-OFF/unknown startup tests, including open accounting and blocker retention.
- Run A -> clean Run B -> clean Run C SOAKING adoption and Run B crash rejection.
- Generic reload, reconfigure preparation, deletion preparation, full-stop, teardown timeout, and setup-failure tests.
- Subscribe-before-snapshot/re-read interleaving test with grants disabled.
- Manual verification of lifecycle logs/state in a local HA harness; real shutdown timing remains Slice 13 item 4.

### Completed work

- `custom_components/moisture_loop/runtime.py` — `EntryRuntime` plus module-level `async_setup`/`async_setup_entry`/`async_unload_entry` and `zone_config_from_subentry`; `custom_components/moisture_loop/__init__.py` is a thin HA-import-free delegator using module `__getattr__` (see notes).
- **Startup (§25.1 exact order):** §23.5 matrix handling (first-install transaction with flag update only after verified Store state; interrupted-initialization flag completion; integrity-loss reconstruction with detection-day budget exhaustion and blocked modes) -> §23.3 run protocol (new UUID4 active run ID persisted/verified; previous IDs retained for trust checks; write failure raises ConfigEntryNotReady after §24.4 minimal defensive reconciliation) -> subentry config validation -> passive per-actuator listeners installed BEFORE the snapshot, feeding keyed blockers only -> snapshot/classification, `actuator_not_proven_off` population, persisted-state reconciliation -> post-reconciliation re-read releasing proven-off keys (exact-key) -> passive listeners replaced by the controllers' own and only then `async_enable_grants`.
- **Persisted WATERING (§25.2):** never resumed; found-ON/OFF/UNPROVEN routed to the pure T48/T49 decisions through the controller (defensive OFF, keyed blocker, conservative intent-anchored estimation).
- **Trusted SOAKING (§25.3/§23.3):** all trust checks in the lifecycle (previous clean run, owner match, structural validity incl. `recheck==soak<=grace` and `off<=soak`, exact fingerprint, actuator available+proven OFF); verified owner rebase persisted via the storage primitive BEFORE controller activation; adoption dispatches T50; offline-expired deadlines re-check the current observation once then take the §18.4 explicit fault (SENSOR_STALE for a pre-deadline-only report; SENSOR_UNAVAILABLE for an absent sensor); untrusted -> T51.
- **Shutdown (§24.1):** once-only stop handler (re-entry guarded, unsubscribed on unload) — grants disabled, WATERING cooperatively stopped as HOME_ASSISTANT_SHUTDOWN with a bounded real-time OFF budget and forced-cancellation + best-effort-OFF fallback, SOAKING persisted unchanged (T37), resting zones persisted, and clean marking last (a failed clean marking logs and leaves the run unclean — the safe crash-equivalent).
- **Generic reload (§24.2):** WATERING and SOAKING terminate as CONFIG_RELOAD (OFF awaited for watering), run IDs never touched, never marked clean. **Reconfigure/delete preparation (§24.3):** CONFIG_CHANGED with OFF awaited; deletion uses the same path and cannot clear blockers.
- `tests/test_lifecycle.py` (42 tests).

### Remaining work

None at this layer. The config-flow invocation of `prepare_reconfigure` + the one `async_update_reload_and_abort` call is Slice 9; real shutdown timing is §46 item 4.

### Tests actually run

All on 2026-08-21. HA 2025.9.0 environment: **551 passed, 1 skipped; 100.00% branch coverage on all eight modules** (`runtime.py`: 263 stmts, 96 branches). Pure environment: 401 passed, 4 skipped. `ruff check`/`format` PASS. Highlights:

- PI12 (found ON: defensive OFF, intent->confirmation estimate >= downtime, RESTART_RECOVERY, never resumed, zero new ON), PI13 (found OFF: intent->reconciliation 45 min, never the scheduled 5-min end), PI14 (unproven: OFF attempts, keyed blocker, T49 ACTUATOR_OFF_TIMEOUT with blocker retained), PI15 (2-day downtime: 172800 s charged, today's budget exhausted, G-DAY refuses AUTO).
- LC3 (reconfigure CONFIG_CHANGED for WATERING and SOAKING; generic reload CONFIG_RELOAD with run IDs unchanged and never clean), LC4 (shutdown stops WATERING with one OFF, preserves SOAKING, marks clean only after safety persistence; resting zones persisted; fallback path with silent and raising OFF services), LC5/LC6 (Run A -> clean Run B -> clean Run C adoption chain with owner rebased each time), LC7 (crashed Run B: Run C refuses, RESTART_RECOVERY), LC8 (fingerprint change refuses before any rebase; the terminated session is persisted cleared), LC9 (rebase write failure -> ConfigEntryNotReady, grants never enabled, zero ON), LC10 (adopted session equals the original except owner), LC11 (offline-expired soak with only a pre-deadline report -> SENSOR_STALE; grace-remaining variant waits and a fresh at/after-deadline report completes TARGET_REACHED; absent-sensor variant -> the §18.4 explicit UNAVAILABLE path), LC12 (setup failure after readable config attempts defensive OFF and never arms watering).
- PI1/PI2/PI6/PI7 lifecycle completions (flag update ordering, interrupted-init adoption, initial-write failure leaving initialized=false with re-runnable first install).
- ER6/ER12 lifecycle: startup external ON respected without OFF, blocker before any grant, dry evaluation refused, proven OFF releasing exactly this zone's keys; passive-listener window events land in the keyed set before grants exist; unknown startup actuator adds `actuator_not_proven_off`.
- Once-only stop handler; module-level setup/unload API; non-zone subentries ignored; session-structure validation matrix.

### Decisions / implementation notes

- **Package init split (documented prerequisite):** `__init__.py` importing homeassistant would make the pure domain layer unimportable in the no-homeassistant environment, defeating the §37 boundary proof. The lifecycle therefore lives in `runtime.py` (the §37 architecture names EntryRuntime as its own component; §38's layout is proposed) and `__init__.py` lazily delegates the HA entry points via module `__getattr__` — `hasattr(component, "async_setup_entry")` still resolves for HA's loader.
- **Moisture listeners at step 6 vs step 8:** controllers attach (and their listeners arm) during reconciliation, but watering capability is gated by SlotManager grants, which are enabled only at step 8 after every prerequisite; pre-activation evaluations can only record guard refusals or queue. The ER12/LC tests prove no ON and no grant occur before reconciliation completes. The passive-to-controller listener replacement overlaps (attach first, unsubscribe passive after), so there is no observation gap.
- Startup external-ON is routed through the controller's T54/T55 bookkeeping so the external flag and keyed blocker stay consistent and later proven OFF releases via T58/T59; a fresh terminal-OFF observation also releases this zone's startup `actuator_not_proven_off` key (exact-key, idempotent).
- The shutdown OFF budget is wall-clock (`asyncio.wait` on the shared OFF future) with the §46-item-4 tuning pending; the bounded fallback cancels the owner task and makes one best-effort OFF call.

### Deviations from specification

None (the two ordering equivalences above are implementation notes with test evidence, not semantic changes).

### Blockers

None.

## Slice 9 - Config flow and zone subentries

### Status

`[~] Spec.4 remediation required; specification blocker resolved`

> **Current-spec note:** the original Objective, references, Scope/Out of scope, Dependencies, Acceptance criteria, Required tests, Completed work, Tests actually run, implementation notes, and Deviations below preserve the spec.3 implementation record. The spec.3 reload-helper/no-listener design is superseded by approved spec.4 and is not a current requirement or conformance claim; the updated Remaining work and Blockers are current.

### Objective

Implement the single-controller configuration flow and safe zone-subentry add, reconfigure, and delete experience on Home Assistant 2025.9.0.

### Specification references

- §§5.1, 5.3, 7-9, 24.3, 29-30, 37-38, and 42.
- LC2-LC3 and HA1-HA2 in §39.2.
- Invariants I20, I24-I26, I29; acceptance criteria §45.1, §45.15, §45.21-45.23.

### Scope

- One top-level controller config entry with immutable generation UUID, `runtime_store_initialized=false`, and `single_config_entry` behaviour.
- Zone `ConfigSubentryFlow` add/reconfigure/delete flows and one zone device per subentry.
- All §9 bounds, strict thresholds, entity existence/domain checks, valve feature requirements, duplicate-actuator refusal, case-insensitive unique zone names, and shared-sensor warning.
- Selector filtering for supported sensors and switch/valve actuators, with backend validation authoritative.
- Safe runtime `prepare_reconfigure`/deletion integration and the 2025.9.0 `ConfigSubentryFlow.async_update_reload_and_abort(..., reload_even_if_entry_is_unchanged=False)` path exactly once.
- No options flow; enabled remains runtime state.

### Out of scope

- Controller behaviour beyond invoking the already-implemented safety-preparation contract.
- Public watering actions/entities, Repairs/diagnostics, release packaging, or reopening the 2025.9.0 floor.
- A config-entry update listener or 2025.7/2025.8 compatibility implementation.

### Dependencies

- Slices 0-8 complete.

### Expected files

- `custom_components/moisture_loop/config_flow.py`
- Config-flow strings/translations in `strings.json` and `translations/en.json`.
- `tests/test_config_flow.py`
- Manifest metadata only if strictly required for harness discovery; final manifest ownership remains Slice 12.

### Acceptance criteria

- The UI creates exactly one controller and supports add/reconfigure/delete for zone subentries.
- All schema bounds, entity/domain/feature checks, duplicate rules, and shared-sensor warning match the specification.
- Reconfiguration compares proposed data before unnecessary pre-termination, safely prepares changed data, calls the subentry helper once, and has no update listener.
- Deletion cannot erase unresolved actuator safety blockers or runtime evidence before safety is established.
- Config-entry generation/initialized identity is created exactly as specified and never regenerated on Store absence.

### Required tests / verification

- Full valid/invalid field boundary matrix and strict-threshold tests.
- Duplicate name/actuator, shared sensor, missing entity, wrong domain, and insufficient-valve-feature tests.
- Single-entry, add/reconfigure/unchanged/delete, one-reload, and no-update-listener tests.
- Entity/device/subentry attribution tests in the HA 2025.9.0 harness.
- HA1 exact signature verification for the subentry update/reload helper.

### Completed work

- `custom_components/moisture_loop/config_flow.py`:
  - Top-level `MoistureLoopConfigFlow` (VERSION 1 / MINOR 1): creates the single controller entry with an immutable random UUID4 `runtime_store_generation_id` and `runtime_store_initialized=false` (§23.1, I29); in-flow single-instance abort as defense-in-depth alongside `single_config_entry`; `async_get_supported_subentry_types` exposing one `zone` `ConfigSubentryFlow`.
  - `ZoneSubentryFlow` with the three §29 steps (identity/entities, thresholds/timing, safety limits) for add and reconfigure; entity selectors filter sensors and switch/valve actuators while **backend validation stays authoritative** (§5.3): entity existence, domain shape, valve OPEN+CLOSE feature requirement (position-only valves refused), case-insensitive unique zone names, duplicate-actuator refusal across zones, strict `start < target`, and the full §9 bound matrix through the pure `ZoneConfig.validation_errors()` — catching cross-field violations (e.g., session limit below pulse) that per-field selectors cannot. Shared sensors warn (description placeholder) without blocking (§9).
  - Reconfigure: proposed data is normalized and compared first; unchanged submissions skip pre-termination and reload entirely; changed data calls the loaded runtime's `async_prepare_reconfigure` (§24.3 CONFIG_CHANGED termination) and then `async_update_reload_and_abort(..., reload_even_if_entry_is_unchanged=False)` exactly once. No options flow; no config-entry update listener (asserted empty).
  - Zone-add flows schedule exactly one entry reload themselves (no update listener may exist per §5.1/the helper's own contract, and core adds subentries without reloading), so the running entry adopts the new zone.
- `custom_components/moisture_loop/manifest.json` (harness-discovery necessity per this slice's expected files; final ownership stays Slice 12): domain, helper/calculated/single_config_entry/config_flow, version 0.1.0, documentation/issue_tracker/codeowners.
- `strings.json` and `translations/en.json`: flow steps, field labels, and translated error keys.
- `tests/test_config_flow.py` (23 tests).

### Remaining work

The specification issue is resolved by spec.4, but implementation conformance is incomplete. After explicit authorization, this slice must integrate with the entry-owned update listener/reconciler, use `async_update_and_abort`, remove add/flow-owned reload scheduling and incompatible reload-helper semantics, apply durable-identity/same-record/A -> B validation, and prove the actual HA 2025.9 native websocket deletion path plus safe reconciliation. Entity/device/subentry attribution tests implemented under Slice 10 remain historical spec.3 evidence.

### Tests actually run

All on 2026-08-21. HA 2025.9.0 environment: **574 passed, 1 skipped; 100.00% branch coverage on all nine modules** including `config_flow.py`. Pure environment: 401 passed, 5 skipped. `ruff check`/`format` PASS. Highlights:

- End-to-end controller creation through the real flow machinery, with real setup completing the §23.5 first-install transaction (generation matches the Store; flag flipped only after the verified write); second-entry abort; a removed-and-recreated entry gets a fresh generation.
- Zone add: full 3-step flow creating the subentry (typed/normalized data, integer-second durations) with exactly one scheduled reload; valve-with-features accepted; identity error matrix (empty/overlong name, missing sensor/actuator); wrong-domain rejection at the backend (bypassing selector filtering); position-only valve refusal; case-insensitive duplicate name and duplicate actuator refusal; shared-sensor warning that does not block; strict threshold-ordering boundary (40.0/40.0 refused, 39.9/40.0 accepted); selector range enforcement (`InvalidData`) plus backend cross-field violation (`invalid_configuration`).
- Reconfigure: changed data -> `async_prepare_reconfigure(subentry_id)` awaited exactly once BEFORE the update, one reload scheduled by the 2025.9.0 helper (HA1 signature exercised for real), data updated, abort `reconfigure_successful`, `update_listeners` empty; unchanged submission -> no termination and no reload; reconfigure works with an unloaded runtime; validation parity with add (including threshold and cross-field errors in the reconfigure steps).

### Decisions / implementation notes

- Core 2025.9 adds subentries without reloading the entry and forbids update listeners in combination with the reload helper; the add flow therefore schedules the single reload itself. Deterministic ordering holds because the flow manager attaches the subentry synchronously after the step returns, before the scheduled task runs.
- The §9 UI presents duration fields in seconds (number selectors with the exact bounds); §46 item 1 may refine presentation (e.g., duration selectors) without touching validation.

### Deviations from specification

None in implemented behaviour.

### Blockers

- **Specification blocker:** resolved by approved `0.1.0-spec.4`. Home Assistant still has no supported pre-delete hook, but spec.4 no longer requires one; the supported design is post-removal update-listener reconciliation plus the authoritative mapping/snapshot final-ON fence.
- **Implementation status:** remediation has not started and is not authorized. Slice 9 cannot become `[x]` until the Stage 3-5 implementation dependencies are complete and the actual HA 2025.9 websocket deletion, reconciliation, and reload-ownership tests pass.

## Slice 10 - Home Assistant entities and actions

### Status

`[~] Spec.4 remediation required (historically complete under spec.3 on 2026-08-21)`

### Objective

Expose the specification-defined per-zone status/control entities and integration-level validated actions without bypassing controller safety.

### Specification references

- Action lifecycle/validation §5.3; UX §8; entity model §28; actions §31; architecture §§37-38.
- LC1-LC2 in §39.2.
- Invariants I20, I25, I27; acceptance criteria §45.21.

### Scope

- Sensors: `status`, `watering_runtime_today`, `last_session`, and `next_eligible`.
- Binary sensors: `watering`, `problem`, and `needs_water` with exact availability/overlay semantics.
- Controls: `enabled` switch, `stop`, `evaluate_now`, and `clear_fault` buttons.
- Integration actions: `start_manual_watering`, `stop_watering`, `evaluate_zone`, and `clear_fault`.
- Register actions once from integration-level `async_setup`, keep them discoverable while entries are unloaded, and resolve exactly one zone `device_id` through backend checks.
- Nested device-selector integration filter, translated `ServiceValidationError` cases, stable unique IDs, entity naming/translation keys, and zone-device/subentry attribution.
- Bounded manual-action duration validation/clamping and guarded controller routing.

### Out of scope

- New safety decisions in entity/action code, entity-ID/config-entry-ID substitution for required device targets, an unbounded manual-start button, events/Repairs/diagnostics/logging, or packaging.
- Allowing `needs_water`, Evaluate, or any UI control to bypass pure guards.

### Dependencies

- Slices 0-9 complete.

### Expected files

- `custom_components/moisture_loop/services.py`
- `custom_components/moisture_loop/entity.py`
- `custom_components/moisture_loop/sensor.py`
- `custom_components/moisture_loop/binary_sensor.py`
- `custom_components/moisture_loop/switch.py`
- `custom_components/moisture_loop/button.py`
- `custom_components/moisture_loop/services.yaml`
- Action/entity strings and translations.
- `tests/test_services.py` and `tests/test_entities.py`

### Acceptance criteria

- Every §28 entity exists with exact data, availability, naming, unique-ID, and device/subentry semantics.
- Actions register once in `async_setup`, remain present with zero loaded entries, and are not duplicated across reloads.
- Backend target resolution rejects missing, multiple, wrong-integration, ambiguous, deleted, unloaded, or unavailable runtime targets with translated validation errors.
- Manual requests remain finite and observe all non-sensor guards; Stop/Evaluate/Clear Fault use existing validated controller paths.
- Informational entities cannot authorize water or hide retained/manual faults.

### Required tests / verification

- LC1-LC2.
- Entity creation, unique ID, device/subentry attribution, state/attribute, availability, enable/disable, and retained-fault tests.
- Action registration across zero/one/reloaded entries and complete invalid-target/error translation matrix.
- Manual duration/clamping/refusal routing tests and guard-bypass negative tests.
- HA 2025.9.0 harness verification of nested device-selector configuration.

### Completed work

- `entity.py`: base zone entity — `{subentry_id}_{key}` unique IDs, `has_entity_name=True`, translation keys, zone `DeviceInfo` with `(moisture_loop, subentry_id)` identifiers, no polling (controller listener push), no `via_device`.
- `sensor.py` (§28.1): `status` (enum of the five states with the full attribute set: mode, cycle, session runtime + estimate flag/reason, `sensor_fresh_until_utc`, active/retained/secondary fault, moisture value/classification/report time, external actuator ON, waiting-for-slot, sorted zone/reason blocker list), `watering_runtime_today` (duration, seconds), `last_session` (timestamp with the complete §23.2 summary attributes), `next_eligible` (derived min-interval timestamp; unknown without history).
- `binary_sensor.py` (§28.2): `watering` (ON while the actuator may be flowing: WATERING, respected external ON, observed ON, OFF-unconfirmed open accounting), `problem` (any active/retained/secondary fault), `needs_water` (ON only on VALID+fresh `< start`; unavailable otherwise — never falsely OFF; informational only, I27).
- `switch.py`/`button.py` (§28.3): `enabled` runtime switch; `stop`, `evaluate_now`, `clear_fault` buttons; deliberately no manual-start button. All controls route through the validated controller paths.
- `services.py` + `services.yaml` (§5.3, §31): four actions registered once from integration-level `async_setup` (idempotent; never removed on unload); nested device-selector integration filter in `services.yaml` with `multiple: false`; authoritative backend resolution (device exists -> exactly one `(DOMAIN, subentry_id)` identifier -> belongs to the Moisture Loop entry -> subentry still present -> entry LOADED -> controller present) raising translated `ServiceValidationError`s; pure guard refusals translated per case (disabled, invalid duration, active session, blocking fault, actuator not ready, daily exhausted, occupied resource; slot-queueing is a wait, not a refusal); `clear_fault` surfaces T44 refusals.
- Runtime integration: platform forwarding after §25.1 reconciliation; controller listener push updates; observation seeded at attach from the stored report; the §16 trigger set completed (15-minute fallback scan and HA-local midnight evaluation, unsubscribed at unload).
- `strings.json`/`translations/en.json` extended with entity names, action descriptions, and exception messages.
- `tests/test_entities.py` (13) and `tests/test_services.py` (26), both end-to-end through the real flows/platforms.

### Remaining work

None at this layer. Event payload finalization and Repairs are Slice 11.

### Tests actually run

All on 2026-08-21. HA 2025.9.0 environment: **613 passed, 1 skipped; 100.00% branch coverage on all fifteen modules**. Pure environment: 401 passed, 7 skipped. `ruff check`/`format` PASS. Highlights:

- Entity creation matrix (11 entities per zone) with stable unique IDs; device/subentry attribution proven in the registries (device identifiers, `config_entries_subentries`, per-entity `config_subentry_id`).
- Status/state semantics through a real session (idle -> watering with mode/cycle/freshness attributes -> runtime 300 s -> target completion summary incl. moisture before/after and reason); `next_eligible` unknown without history and set after; `needs_water` exact semantics (off at 33, on at 29.9, unavailable on sensor loss — never falsely off, and its guard holds even when queried directly); `watering` ON for external flow with the blocker list visible in status attributes.
- Controls: enabled switch round trip (disable -> DISABLED, enable -> IDLE), stop button (single OFF, USER_STOP summary), evaluate button refusing above-start (nothing runs), clear-fault button no-op safety.
- LC1: all four actions exist with zero loaded entries, survive unload (rejecting with `entry_not_loaded`), and reloads never duplicate registration (double registration is a no-op). LC2: unknown device, wrong-integration device, wrong-entry impostor device carrying our identifier, deleted subentry with a stale device, unloaded entry, and missing-controller (`zone_not_ready`).
- Manual action: bounded end-to-end run via the service; clamp to manual max; invalid durations (0, -5) refused through the pure guard translation; refusals for disabled, active session, blocking actuator fault (built by real mid-pulse actuator loss), exhausted daily budget (two full manual sessions), and occupied water resource; unknown-guard fallback translation.
- Interoperability regression captured: forwarding the real switch platform registers HA's own switch services, so scripted actuator doubles in tests use the valve domain; the zone-add reload is deferred one loop pass so the flow manager attaches the subentry before the eager reload task starts (proven by the entity end-to-end tests).

### Decisions / implementation notes

- The 15-minute fallback scan and midnight rollover (§16 triggers 4-5) were completed here as part of wiring entity-visible behaviour; the scan re-normalizes the stored report (never manufacturing freshness) and flows through the same decision paths.
- `status` exposes the SlotManager snapshot (owner/queue/sorted blockers), satisfying the §28.1 blocker attribute without giving entities any authority.

### Deviations from specification

None.

### Blockers

Spec.4 remediation is required for non-`ACTIVE`/dirty runtime refusal and schema-2 identity/lifecycle presentation. The former Slice 9 specification question is resolved; its implementation remediation remains a prerequisite.

## Slice 11 - Repairs, diagnostics, events, and logging

### Status

`[~] Spec.4 remediation required (historically complete under spec.3 on 2026-08-21)`

### Objective

Implement the specified operational evidence, fault visibility, support diagnostics, and safety-appropriate logging.

### Specification references

- Fault/completion model §26; events §32; logging/diagnostics §33; Repairs §34; examples §35; architecture §§37-38; failure analysis §40.
- Relevant event-order tests MF3-MF5, delayed-closure AC4, and lifecycle/persistence fault cases in §39.2.
- Acceptance criteria §45.5, §45.8-45.11, §45.13-45.21, and §45.25.

### Scope

- Repairs: `zone_sensor_missing`, `zone_actuator_missing`, `actuator_off_unconfirmed`, and `runtime_store_integrity_lost` at their specified severities and conditions.
- CRITICAL actuator-safety issue behaviour and acknowledgement/clear conditions from §26.
- Config-entry diagnostics with standard redaction, Store/run/adoption integrity results, normalized per-zone/controller/resource state, runtime estimation, open OFF operation/accounting state, and the last 50 transitions.
- `session_started`, `session_finished`, `fault_set`, and `fault_cleared` events with exact fields, replacement context, delayed finish, and manual-recovery ordering.
- Logging at the DEBUG/INFO/WARNING/ERROR levels defined in §33.1, with CRITICAL represented as a Repair plus ERROR log.
- Translated validation/Repair text and safe diagnostic output.

### Out of scope

- New controller decisions, new fault/completion codes, pulse-level bus events, credentials, cloud export, release packaging, or prototype validation claims.
- Using diagnostics, Recorder, logs, or entity presentation as safety authority.

### Dependencies

- Slices 0-10 complete.

### Expected files

- `custom_components/moisture_loop/diagnostics.py`
- `custom_components/moisture_loop/repairs.py`
- Event/logging integration updates in existing controller/runtime modules.
- Strings/translations for Repairs and validation errors.
- `tests/test_repairs.py` plus diagnostics/event/logging tests under `tests/`.

### Acceptance criteria

- Every specified Repair uses a supported severity and is created/cleared only under its normative condition.
- `ACTUATOR_OFF_TIMEOUT` produces the CRITICAL Repair, ERROR log, retained blocker, and continued accounting until proven OFF.
- Diagnostics contain all §33.2 information, distinguish measured/estimated runtime, and safely redact or shorten identifiers.
- Every session emits one start and exactly one finish only after accounting closes; every session has one reason.
- Manual sensor-fault event order and actuator-fault replacement semantics match §32 exactly without fault-event churn.
- Safety-relevant outcomes are never DEBUG-only and no pulse-level bus-event noise is introduced.

### Required tests / verification

- Repair create/update/clear/refusal tests for every issue and severity.
- Diagnostics snapshot/redaction tests for normal, sensor-fault, actuator-fault, integrity-loss, open-accounting, and trusted-SOAKING states.
- Event payload/count/order tests, including delayed OFF proof and manual recovery/override paths.
- Log capture tests for the §33.1 severity matrix.
- hassfest validation of translations and Repairs/action metadata where applicable.

### Completed work

- `repairs.py` (§34): `actuator_off_unconfirmed` (the only `IssueSeverity.CRITICAL` — true panic), `zone_sensor_missing`/`zone_actuator_missing` (ERROR), `runtime_store_integrity_lost` (ERROR); none fixable-flow (acknowledgement goes through the validated `clear_fault`/reconfigure paths, which delete the issues). Issue lifecycle driven from the runtime's event wrapper (fault_set/fault_cleared) plus creation at integrity reconstruction; the entry-level integrity issue clears only when no zone retains the fault.
- `diagnostics.py` (§33.2): HA version and manifest classification; store flags/setup classification/schema/revision/short run ID/previous-clean/soaking adoptions; SlotManager owner/queue/sorted blockers; per-zone config, state, faults, normalized observation with `reported_at_utc`, live freshness deadline, actuator classification, external-ON, full session anchors incl. pending termination and estimation metadata, OFF-operation state, daily split charge, last session end; merged last-50 transition ring; raw versioned store after standard redaction (`async_redact_data` on the generation and run UUIDs; the current run ID is hash-shortened). Recorder is never consulted.
- **Events (§32) finalized:** the runtime emit wrapper enriches every event with the common identity (subentry `zone_id`, `zone_name`, `device_id`, `mode`, `session_id` where applicable); `session_finished` carries reason, runtime + estimation metadata, cycles, moisture before/after, requested/effective manual duration and clamp reasons.
- **Logging (§33.1):** decision-level DEBUG for per-observation/pulse noise; INFO for session start/success, fault auto-clear, external-flow add/release; WARNING for constrained completions, external interference, sensor-fault terminations, crash reconciliation; ERROR for actuator/config/integrity faults and failed setup; ACTUATOR_OFF_TIMEOUT as CRITICAL Repair + ERROR log. Implemented in the controller's `_record_and_log`, which also feeds the per-zone transition ring (deque of 50).
- §26.1 completion: `CONFIGURATION_INVALID` now clears on the post-reconfigure reload when both configured entities exist again (fault cleared, state IDLE, Repairs deleted, INFO log); it persists if the entity is still missing. Repairs strings added to `strings.json`/`translations/en.json`.
- `tests/test_repairs.py` (18 tests).

### Remaining work

None. hassfest validation of translations/metadata is a Slice 12 gate.

### Tests actually run

All on 2026-08-21. HA 2025.9.0 environment: **631 passed, 1 skipped; 100.00% branch coverage on all seventeen modules** (2884 statements, 936 branches, zero missed). Pure environment: 401 passed, 8 skipped. `ruff check`/`format` PASS. Highlights:

- Repairs: full CRITICAL lifecycle for `actuator_off_unconfirmed` (created on unproven OFF with the keyed blocker; retained after observed OFF until acknowledgement; deleted on `clear_fault`); `zone_sensor_missing` and `zone_actuator_missing` ERROR issues on registry removal; integrity issue at reconstruction and its acknowledgement-driven clearing; configuration-fault clearing after a reconfigure-reload with the entity restored, and persistence when still missing.
- Events: identity/summary payload assertions on start/finish (device ID resolved from the registry); MF3/MF4 ordering end-to-end (single fault_set, no clear on manual start, finish-before-clear on recovery, no churn through WATERING); AC4 single deferred finish only after delayed OFF proof closes accounting.
- Diagnostics: content matrix (manifest/classification/store/run/slot/zone/session anchors/actuator classification/measured-vs-estimated) plus redaction proof (generation UUID never in clear text) and the transition ring (T1/T17 present, ≤50, ordered).
- Logging: INFO session start and success (manual_complete), WARNING sensor-fault termination and constrained completion, ERROR for the OFF-unproven panic, and per-observation refusals staying DEBUG.

### Decisions / implementation notes

- The Slice 9 `[?]` gap surfaced a companion behaviour implemented here: since reconfiguration is the §26.1 clearing mechanism for CONFIGURATION_INVALID and reconfigure works via reload, the reload path itself performs the clearing check (both entities exist -> clear); no update listener involved.
- The transition ring lives per controller (50 each) and diagnostics merges and caps the newest 50 across zones.

### Deviations from specification

None.

### Blockers

Spec.4 remediation is required for exact-record tombstone/identity/reconciliation Repairs, fix flows, diagnostics, events, and logging. The former Slice 9 specification question is resolved; its implementation remediation remains a prerequisite.

## Slice 12 - Distribution and documentation

### Status

`[~] Spec.4 remediation and existing release gates required` — implementation artifacts produced under spec.3 remain, but a post-remediation documentation/distribution pass is required; the supported-current HA harness and GitHub-hosted hassfest/HACS executions remain outstanding.

### Objective

Complete a distributable, documented HACS custom integration and run the full automated release gates without claiming prototype evidence that has not been obtained.

### Specification references

- Manifest/HACS research §§5.4, 5.6; name/domain §7; proposed layout §38.
- Testing/release jobs §§39.1 and 39.3; HACS/distribution §41; versioning §42; documentation §43.
- Full automated v0.1 release gates in §45, especially §45.23-45.28.

### Scope

- Final `manifest.json` with `integration_type: helper`, `iot_class: calculated`, `single_config_entry: true`, `config_flow: true`, required custom keys, version, and minimum-compatible runtime decisions.
- Root `hacs.json` declaring `homeassistant: "2025.9.0"` and current HACS metadata.
- README, user setup/configuration/operation/safety/troubleshooting/action documentation, local-only/privacy statement, license, translations, services/actions documentation, icons, and local brand preparation.
- CI release gates for full tests, coverage, mandatory HA 2025.9.0, supported-current HA, HA1 contract checks, hassfest, and HACS validation.
- Release/version consistency and dependency/network audit.
- Documentation of all §43 subjects and clear separation of remaining §46 prototype validations.

### Out of scope

- Altering control architecture/safety behaviour, implementing deferred §44 features, publishing a release/default-HACS submission unless separately authorized, or marking §46 validations complete.
- Treating local brand files as completion of the centralized `home-assistant/brands` requirement.

### Dependencies

- Implementations exist through Slice 11, and the dated Slice 10/11 spec.3 tests remain valid historical evidence. The current prerequisite chain is incomplete because Spec.4 Remediation Stages 1-7 have not been authorized, implemented, or tested.

### Expected files

- `custom_components/moisture_loop/manifest.json`
- `hacs.json`
- `README.md`, `LICENSE`, and supporting user/action documentation.
- `custom_components/moisture_loop/services.yaml`, `strings.json`, `icons.json`, and `translations/en.json` finalization.
- `custom_components/moisture_loop/brand/icon.png` where supported.
- `.github/workflows/` release-quality workflow finalization.

### Acceptance criteria

- Manifest and HACS metadata match the specified domain, classification, single-entry model, release version, and Home Assistant 2025.9.0 floor.
- All §43 documentation topics are accurate and do not weaken or reinterpret the specification.
- Full automated suite passes with 100% branch coverage for `state_machine.py` and at least 90% overall.
- Exact HA 2025.9.0 source-contract verification and harness job pass; supported-current job passes separately where required.
- hassfest and current HACS validation pass without ignored failures.
- All 59 transitions retain table/implementation/test parity and all 37 invariants have passing evidence at their applicable automated layers.
- Dependency/network audit confirms local-only operation and no Recorder safety dependency.
- Remaining prototype items are still visibly incomplete and do not block an honest `READY WITH PROTOTYPE VALIDATIONS` implementation status.

### Required tests / verification

- Run and record the full pytest suite with branch/overall coverage.
- Run and record lint, formatting, hassfest, HACS validation, HA1 contract checks, HA 2025.9.0 harness, and supported-current harness.
- Validate manifest/HACS/version/translation/action metadata consistency.
- Mechanically audit T1-T59 and I1-I37 traceability, including all 134 unique normative named behavioural test IDs.
- Audit packaged contents, local-only dependencies, Recorder independence, documentation links, and clean install instructions.
- Render/check brand and documentation presentation locally where possible; real presentation/default-inclusion evidence remains Slice 13 item 7.

### Completed work

- `custom_components/moisture_loop/manifest.json` finalized: `integration_type: helper`, `iot_class: calculated`, `single_config_entry: true`, `config_flow: true`, `version: 0.1.0`, empty `requirements` (local-only), documentation/issue_tracker/codeowners; hassfest key ordering (domain, name, then alphabetical) verified.
- Root `hacs.json` declaring `homeassistant: "2025.9.0"`; `README.md` covering every §43 subject (closed-loop purpose and non-goals, exact hysteresis/equality, pulse-soak-report rationale, unchanged reports and sensor cadence, the AUTO watchdog vs post-soak grace distinction, all limits and conservative crash estimates, manual watering from sensor faults with refusals, external-actuator/shared-resource rules, Store identity/recovery/shutdown/reload/reconfigure/no-resume behaviour, the 2025.9.0 minimum, the hardware-failsafe recommendation, action examples with device+duration, diagnostics/Repairs/events/troubleshooting, and the local-only privacy statement — plus the known Slice 9 deletion-reload limitation); `LICENSE` (GPL-3.0-only); `icons.json` for every entity and action; generated `brand/icon.png` (256x256 PNG for custom-repository presentation; the centralized `home-assistant/brands` submission remains §46 item 7).
- CI release gates finalized in `.github/workflows/ci.yml` since Slice 0 (mandatory 2025.9.0 job with HA1, supported-current job, hassfest, HACS Action) — their existence-gating now activates because manifest/hacs.json exist.
- The I1-I31 traceability matrix updated from future-slice placeholders to the real, now-existing test evidence and mechanically re-verified.

### Remaining work

- Complete the post-remediation documentation/distribution pass after Spec.4 Remediation Stages 1-7, including removal of the documented spec.3 deletion limitation and current I1-I37/134-ID traceability.
- Run and record the supported-current HA harness separately from the HA 2025.9.0 harness. The pinned intended environment is `pytest-homeassistant-custom-component==0.13.356` / `homeassistant==2026.8.2`, but no execution result or test count is currently recorded.
- Execute hassfest and HACS Action in GitHub CI (see Blockers).
- Complete Slice 9 implementation remediation and the full integrated spec.4 test evidence before treating the release/gating chain as ready.
- Release publication and any HACS default-store submission remain separately authorized (§41).

### Tests actually run

All on 2026-08-21 (local machine):

- **Full HA 2025.9.0 suite: 631 passed, 1 skipped; 100.00% branch coverage across all seventeen integration modules (2884 statements, 936 branches).** Gates re-run explicitly: `coverage report --include="*/state_machine.py" --fail-under=100` -> PASS (526/316, 0 missed); `coverage report --fail-under=90` -> PASS (100.00%).
- Pure suite: 401 passed, 8 skipped (no homeassistant installed). `ruff check` / `ruff format --check` -> PASS.
- HA1: `scripts/check_ha_contract.py --expect 2025.9.0` -> PASS (all 11 §5.1 API contract checks against the exact pinned release).
- Mechanical audits -> PASS: exactly T1-T59 represented with expected destinations (`TestTransitionTable`); all 31 invariants mapped to passing named evidence (`TestInvariantTraceability`, now with zero deferred placeholders).
- Dependency/network audit -> PASS: `requirements: []`; grep over the integration source finds no aiohttp/requests/urllib/websocket usage, no recorder import, no cloud/telemetry/API-key references (the single textual hit is the diagnostics docstring stating Recorder is not used). Local-only (I28) and no-Recorder-safety-dependency confirmed.
- Metadata consistency -> PASS: manifest/hacs/version/translations/icons all parse and agree; strings/en.json in sync.

The supported-current HA harness was **not run**: no exact execution command, pass/fail result, or test count is recorded. The configured pinned environment alone is not test evidence.

### Decisions / implementation notes

- The `venv-ha` local harness runs the exact 2025.9.0 release, so "release gates" here means every automated §45 gate except the two GitHub-hosted actions.
- Historical note: the current README documents the spec.3 Slice 9 limitation (UI zone deletion applies at the next reload). Approved spec.4 resolves the architecture; the README must be corrected only after implementation remediation makes that behaviour true.

### Deviations from specification

None.

### Blockers

- hassfest and HACS Action still need to execute in CI. The code was committed and pushed to `main` on 2026-08-21 — but to the self-hosted remote `https://git.lukestanbury.com/luke/moisture-loop.git` (Gitea/Forgejo), not GitHub. The `.github/workflows/ci.yml` gates run there only if Gitea Actions is enabled (it consumes GitHub-compatible workflows); alternatively, mirror the repository to GitHub. Note also that HACS custom-repository installation requires a GitHub-hosted repository, so distribution per §41 ultimately needs a GitHub presence. A green hassfest + HACS Action run completes this slice.
- The separately required supported-current HA harness has not been run. Until an exact environment/version, exact command, pass/fail result, and test count are recorded, this Slice 12 gate remains incomplete.
- Spec.4 implementation remediation and its full test/traceability evidence are incomplete. Slice 9's specification question is resolved, but its implementation and dependent Slice 12 documentation/distribution remediation remain release blockers.

## Slice 13 - Prototype validations

### Status

`[ ] Not started`

### Objective

Gather the real Home Assistant, deployment, timing, hardware, queue-scale, sensor-cadence, and presentation evidence intentionally deferred by the approved specification. These validations may refine presentation or documented defaults only where §46 permits; they are not opportunities to redesign controller behaviour.

### Specification references

- Exact prototype-validation list in §46.
- Test-evidence boundary in §39.1 and the implementation-readiness verdict.
- Related acceptance gates in §45 remain authoritative.

### Scope

The exact current §46 validation list is:

1. **HA 2025.9+ native subentry lifecycle and UI/UX:** practically validate create-controller-then-Add-zone, add/reconfigure, and the actual native UI/websocket Delete path; per-subentry device attribution/action selection; active AUTO deletion; active MANUAL deletion where practical; SOAKING deletion; a real actuator ON dispatch racing deletion; real entity/device registry cleanup while the runtime safety object survives; tombstone persistence/diagnostic/Repair visibility; restart after deletion; exact same-record delete/re-add; and A -> B replacement with retained A hazard plus zone-history continuity. This item may refine presentation/timing only, not weaken the fixed final-gate/tombstone architecture.
2. **Valve hardware matrix:** test at least one physical valve and templates for `opening`, `closing`, `open`, `closed`, availability, and position semantics; the conservative contract remains fixed.
3. **Entity rename tracking:** validate `async_track_entity_registry_updated_event` auto-fixup. If unreliable, ship Repair-and-reconfigure rather than guessing.
4. **Shutdown OFF budget:** measure cooperative OFF completion within HA's real stop window and tune the bounded fallback interval; never weaken startup reconciliation.
5. **Serialized queue scale:** validate FIFO latency/visibility with approximately ten simultaneously dry zones.
6. **Initial sensor cadence/default:** validate the two-hour `sensor_max_age` default against deployment sensors and adjust the default only, not freshness semantics.
7. **HACS/brand presentation:** validate local brand presentation on supported HA 2025.9+ and complete the required centralized `home-assistant/brands` submission before seeking HACS default inclusion, without changing runtime behaviour.

### Out of scope

- Reopening the source-resolved API floor, Store atomicity, report mechanics, action lifecycle, manifest classification, selector API, Repairs severity, or any settled watering/safety decision.
- Marking any item complete from mocks, offline unit tests, code inspection, or CI alone when real HA/hardware evidence is required.
- Publishing or submitting externally without separate user authorization.

### Dependencies

- Slices 0-12 complete and a working release-candidate integration available.
- Appropriate real Home Assistant 2025.9+ environments, physical/test actuators, representative sensors, and any required publication authority available for the relevant item.

### Expected files

- `PROGRESS.md` validation records and session-log entries.
- Focused validation evidence/checklists under repository documentation if authorized and useful.
- Presentation/default/documentation adjustments only where §46 expressly allows them.
- No architecture or safety-code change unless a separate specification revision is explicitly authorized first.

### Acceptance criteria

- Each of the seven §46 items has dated, reproducible evidence from the required real HA, hardware, scale, cadence, or presentation context.
- Limitations, device/environment versions, timings, observations, failures, and follow-up actions are recorded exactly.
- No item is marked complete from mocks alone.
- Any result implying a behavioural contradiction is marked `[?] Requires specification review` and blocks completion; it is not silently resolved in code.
- Any permitted presentation/default tuning remains within the explicit §46 boundary and passes the full Slice 12 regression gates afterward.

### Required tests / verification

- Real HA 2025.9+ UI walkthrough for controller creation, zone add/reconfigure/delete, device attribution, and action target selection.
- Physical valve/template state, availability, and position matrix with observed acknowledgement/OFF evidence.
- Real entity-registry rename trial and verified auto-fixup or Repair-and-reconfigure outcome.
- Measured graceful-shutdown OFF timing in the real HA stop window, including bounded fallback evidence.
- Approximately ten-zone simultaneously-dry FIFO latency/visibility exercise.
- Representative deployment-sensor cadence study against the two-hour default.
- Local HACS/brand presentation check and, only when separately authorized, centralized brand/default-inclusion submission evidence.
- Re-run affected automated release gates after any permitted adjustment.

### Completed work

None.

### Remaining work

Perform and document all seven exact §46 prototype validations using real implementation/platform/hardware evidence as applicable.

### Tests actually run

None.

### Decisions / implementation notes

None.

### Deviations from specification

None.

### Blockers

None.

## Implementation Session Log

### 2026-08-21 - Slices 0 through 12 (single session)

Authorized work:
- User instruction "implement as per progress.md", recorded as authorization to implement in strict slice order.

Completed:
- Slice 0: repository/quality foundation (pyproject, pinned pure + HA 2025.9.0 + supported-current environments, CI workflows with the mandatory 2025.9.0 job, HA1 contract-check script, smoke/audit tests, DEVELOPMENT.md).
- Slice 1: pure domain models (`const.py`, `models.py`) with the full enum/fault/reason vocabulary, §9 bounds, §12.2 session context, transition input/result structures.
- Slice 2: complete pure state machine (`state_machine.py`) implementing T1-T59 with the two-phase commit/finalize execution model.
- Slice 3: exhaustive table-driven suite — mechanical T1-T59 parity, boundary/equality/watchdog/race/manual matrices, I1-I31 traceability, 100% branch coverage of `state_machine.py`.
- Slice 4: `SafetyStore` (§23.5 matrix, verified atomic revisioned writes, run-ID protocol, integrity reconstruction), §23.2 schema serializers, §19.3 DST-safe accounting, config fingerprint; PI1-PI11, PI15-PI20 evidence. Local HA 2025.9.0 harness established (uv Python 3.13.12 + phacc 0.13.277) with documented Windows-only accommodations.
- Slice 5: pure-asyncio `SlotManager` (FIFO ownership, keyed blockers, startup gating) with manager-level ER coverage.
- Slice 6: moisture adapter (`classify_moisture`, `MoistureAdapter`) with the real §39.1 `state_reported` reproduction.
- Slice 7: `ActuatorAdapter` + `ZoneController` (session-owner task, one idempotent OFF future, verified write-ahead ON gate, pre-ON freshness re-check, absolute timers, watchdog tokens, external interference, accounting) with SR/MF/AC/ER controller evidence.
- Slice 8: `EntryRuntime` lifecycle (`runtime.py` + lazy `__init__.py`): §25.1 startup ordering, PI12-PI15 recovery, LC3-LC12 incl. the Run A->B->C adoption chain, once-only stop handler, reload/reconfigure/setup-failure.
- Slice 9: config flow + zone subentries (controller identity creation, 3-step zone flows, full validation matrix, §24.3 reconfigure with the 2025.9.0 helper exactly once, no update listener). `[?]` recorded: core 2025.9 UI subentry deletion has no integration hook.
- Slice 10: entities (11 per zone with device/subentry attribution), integration-level actions with authoritative backend resolution and translated errors; §16 fallback-scan and midnight triggers completed.
- Slice 11: Repairs (§34 severities incl. the CRITICAL panic), §33.2 diagnostics with redaction and the 50-transition ring, §32 event payloads/ordering, §33.1 logging levels; CONFIGURATION_INVALID clears via reconfigure-reload.
- Slice 12 (in progress): manifest/hacs.json/README/LICENSE/icons/brand icon finalized; all locally runnable §45 gates re-run and green; hassfest/HACS Action execution pending a GitHub push.

Files changed:
- `custom_components/moisture_loop/`: `__init__.py`, `runtime.py`, `const.py`, `models.py`, `state_machine.py`, `storage.py`, `slot_manager.py`, `zone_controller.py`, `config_flow.py`, `entity.py`, `sensor.py`, `binary_sensor.py`, `switch.py`, `button.py`, `services.py`, `services.yaml`, `diagnostics.py`, `repairs.py`, `manifest.json`, `strings.json`, `icons.json`, `translations/en.json`, `brand/icon.png`.
- `tests/`: `conftest.py`, `test_foundation.py`, `test_models.py`, `test_state_machine.py`, `test_storage_pure.py`, `test_storage.py`, `test_slot_manager.py`, `test_state_reported.py`, `test_zone_controller.py`, `test_lifecycle.py`, `test_config_flow.py`, `test_entities.py`, `test_services.py`, `test_repairs.py`.
- Root: `pyproject.toml`, `requirements_test*.txt`, `.github/workflows/ci.yml`, `scripts/check_ha_contract.py`, `DEVELOPMENT.md`, `README.md`, `LICENSE`, `hacs.json`, `.gitignore`.

Tests run:
- `.venv-ha` (Python 3.13.12, homeassistant==2025.9.0): `pytest tests/ --cov --cov-branch` -> PASS: 631 passed, 1 skipped; 100.00% branch coverage on all 17 modules (2884 stmts, 936 branches).
- `.venv` (Python 3.14.6, no homeassistant): `pytest` -> PASS: 401 passed, 8 skipped.
- `coverage report --include="*/state_machine.py" --fail-under=100` -> PASS; `coverage report --fail-under=90` -> PASS (100.00%).
- `ruff check .` / `ruff format --check .` -> PASS.
- `scripts/check_ha_contract.py --expect 2025.9.0` -> PASS (11/11 §5.1 APIs).
- Mechanical T1-T59 and I1-I31 audits -> PASS; dependency/network/Recorder audit -> PASS; manifest/hacs/translation consistency -> PASS.

Open issues:
- `[?]` Slice 9: no core hook for UI subentry deletion on 2025.9.0 (specification review; intersects §46 item 1).
- Slice 12: hassfest + HACS Action must run in CI. The repository was committed and pushed to main on the self-hosted remote (git.lukestanbury.com/luke/moisture-loop) on 2026-08-21; the workflows need Gitea Actions enabled there or a GitHub mirror, and HACS distribution itself requires GitHub hosting.
- Slice 13: all seven §46 prototype validations remain — they require a real HA 2025.9+ deployment, physical valve hardware, ~10-zone scale, deployment sensors, and brand submission authority, none of which exist on this development machine.

PROGRESS.md updated:
- yes

### 2026-08-22 - Progress-status review

Authorized work:
- Review and correct `PROGRESS.md` only; no implementation, specification, or prototype work authorized.

Completed:
- Changed Slice 9 from `[x] Complete` to `[?] Requires specification review` and recorded its deletion acceptance criteria as incomplete.
- Updated Current Position and Progress Summary to preserve the completed Slice 10/11 implementation records while making the Slice 9 release/gating blocker explicit.
- Recorded that the required supported-current HA harness has not been run and added it to Slice 12 Remaining Work and Blockers.
- Set the current authorized slice to `None`; further implementation or prototype work requires explicit user authorization after review.

Files changed:
- `PROGRESS.md` only.

Tests run:
- None (documentation-only status correction).

Open issues:
- Slice 9 UI subentry deletion requires specification review.
- Slice 12 lacks a supported-current HA harness result and GitHub-hosted hassfest/HACS results.

PROGRESS.md updated:
- yes

### 2026-08-22 - Spec.4 progress reconciliation

Authorized work:
- Documentation/tracking reconciliation only after approval of `0.1.0-spec.4`; one editorial acceptance-criterion correction was authorized. No implementation, remediation, prototype validation, publication, architecture change, or spec.5 work was authorized.

Completed:
- Corrected only §45.27's stale test-range reference from AR1-AR10 to AR1-AR17 while retaining spec.4, 59 transitions, 37 invariants, Store schema 2, five controller states, and the Home Assistant 2025.9.0 minimum.
- Reconciled current metadata and traceability to spec.4, I1-I37, T1-T59, `(safety_record_id, reason)`, Store schema 2, and the 134-ID normative test inventory.
- Preserved dated spec.3 implementation/test records while marking Slices 0, 1, 3, 4, 5, and 7-12 as requiring spec.4 remediation; retained Slices 2 and 6 as unaffected within their documented scopes.
- Recorded that Slice 9's specification blocker is resolved but its listener/reconciliation/config-flow/native-deletion implementation remediation is incomplete.
- Added the ordered eight-stage spec.4 implementation remediation plan and kept Current authorized slice `None`.
- Preserved Slice 12's supported-current HA and GitHub-hosted hassfest/HACS gates, and left Slice 13 not started with every real §46 validation outstanding.

Files changed:
- `SPECIFICATION.md`
- `PROGRESS.md`

Tests run:
- None (documentation-only reconciliation). A mechanical §39.2 inventory scan found 134 matched IDs, 134 unique IDs, and zero duplicates; this is not behavioural test execution.

Open issues:
- No spec.4 remediation stage is authorized, implemented, or tested.
- Supported-current Home Assistant, GitHub-hosted hassfest/HACS, and every §46 prototype validation remain outstanding.

PROGRESS.md updated:
- yes

### 2026-08-22 - Spec.4 Remediation Stage 1

Authorized work:
- The user explicitly authorized **Spec.4 Remediation Stage 1 only**: canonical models and strict verified runtime Store schema-1 -> schema-2 migration. Stages 2-8, Slice 13, publication, and specification edits were explicitly out of scope.

Completed:
- Changed the current runtime Store format to schema `2` while retaining a read-only schema-`1` Store wrapper and the exact strict historical schema-1 parser solely for migration.
- Added frozen canonical authorities: `SafetyRecord` (one mutable record per durable actuator lineage), `ZoneHistory`, `ZoneRuntime`, `ActuatorIdentity`, `SensorIdentity`, `AppliedEntityIdentity`, `AppliedConfigurationShadow`, `NormalizedZoneSettings`, `IdentityIncident`, `PersistedSession`, `AccountingContribution`, and `ZoneDailyRuntime`.
- Added exact lifecycle `ACTIVE`/`DELETE_PENDING`/`RETIRED`, identity status `registry_confirmed`/`registry_unavailable`/`missing`/`conflict`, possible-flow ownership, stable safety-lineage/history/contribution IDs, blocker ownership, actuator-fault/acknowledgement authority, and strict deterministic serialization/cross-reference validation.
- Kept the five `ControllerState` values and T1-T59 unchanged. `SafetyRecord` contains no enabled/state/sensor/session authority; those logical-zone fields live only in `zone_history.zone_runtime`.
- Implemented pure deterministic contribution-ID deduplication and conservative aggregate merging. Conflicting reuse of one contribution ID is rejected; known distinct contributions remain; unresolved aggregate evidence is added conservatively.
- Implemented strict schema-1 -> schema-2 migration: the old map key becomes `safety_record_id`; stable UUID5 lineage/history/contribution IDs are deterministic; configured records accept caller-supplied normalized identity/shadow facts and become `ACTIVE`; Store-only records become unresolved `DELETE_PENDING` tombstones with no invented Registry UUID/entity identity, retained history/session evidence, `actuator_not_proven_off`, possible `integration_off_unconfirmed`, and a durable migration identity incident.
- Migration moves sessions under `zone_runtime` with `owner_safety_record_id`, preserves the complete historical `SessionContext`, daily/interval fields, summaries, estimates, run IDs, and revision lineage, and explicitly splits actuator versus sensor/configuration primary/secondary faults. Two simultaneous schema-1 actuator faults are rejected as unrepresentable rather than weakened.
- Migration increments `store_revision`, writes schema 2 with `atomic_writes=True`, reloads through a fresh same-key Store, verifies schema/generation/revision/full serialized payload, and adopts only the verified object. Save, fresh-read, malformed/tampered payload, and generation failures remain fail closed.
- A genuine first install now creates verified schema 2 at revision 1 with matching generation, null run IDs, and empty records/histories. Existing schema 2 loads idempotently and is never remigrated. Future, malformed, missing initialized, and mismatched-generation Stores cannot become a clean watering budget.
- Preserved the independent initialized-flag and run-ID protocols. Integrity-loss reconstruction now creates unresolved schema-2 actuator safety evidence with the current-day budget exhausted.
- Added a temporary, explicitly non-authoritative compatibility seam: `StoreData.zones` projects canonical schema-2 data to historical `ZoneRecord`, and `SafetyStore.async_update_zone` may update only an already-existing canonical record/history. It cannot manufacture a clean identityless schema-2 record; first-install runtime callers therefore fail closed until Stages 2/3 materialize and consume canonical records.
- No reconciliation coordinator, blocker re-keying, A -> B orchestration, ON-race handling, config-flow change, entity/action/Repair/diagnostic change, integrated spec.4 suite, distribution work, or prototype validation was implemented.

Named/focused evidence implemented:
- PI21: configured schema-1 migration, ownership split, preservation, revision increment, fresh reload.
- PI22: Store-only unresolved tombstone migration with durable evidence and no guessed identity.
- PI23: atomic migration plus injected save, fresh-read, revision/payload tamper, and non-adoption failures.
- PI27/TB11 Stage-1 persistence portion: `RETIRED` tombstone survives run writes/reload and is never automatically purged.
- TB7: malformed schema-1 data and ambiguous two-actuator-fault ownership fail closed.
- Relevant PI1-PI20 storage/run evidence retained and adapted: first/interrupted initialization, missing/corrupt/future/generation cases, atomic/read-back failures, previous-revision retention, monotonic serialized writes, run A -> B -> C cleanliness, unverified run-ID refusal, conservative integrity reconstruction, and concurrent canonical-record compatibility writes.
- Additional focused tests cover schema-2 round trips, exact lifecycle vocabulary, retained lifecycle round trips, immutable shadows, identity statuses/OFF metadata, stable IDs, primary/secondary actuator/sensor/configuration splitting, strict enum/field/timestamp/finite-number handling, missing history/session-owner/source cross-references, duplicate contribution IDs, conservative merge, historical-value preservation, existing-schema-2 idempotence, and no identityless compatibility creation.
- PI24-PI26 were not claimed; their live exact-identity/reactivation/coordinator portions remain Stage 3.

Files changed:
- `custom_components/moisture_loop/const.py`
- `custom_components/moisture_loop/models.py`
- `custom_components/moisture_loop/storage.py`
- `tests/test_models.py`
- `tests/test_storage_pure.py`
- `tests/test_storage.py`
- `PROGRESS.md`

Tests run:
- Pure environment: Windows, Python 3.14.5, no Home Assistant. `py -3.14 -m pytest tests/test_models.py tests/test_storage_pure.py tests/test_state_machine.py tests/test_foundation.py -q --tb=short` -> PASS: 391 passed, 0 failed, 0 skipped (warning-only pytest/cache noise; 0.91 s).
- HA environment: Windows, Python 3.13.13, Home Assistant 2025.9.0, `pytest-homeassistant-custom-component` 0.13.277, pytest 8.4.1. `.\.venv-ha-stage1\Scripts\python.exe -m pytest tests/test_storage.py -q --tb=short` -> PASS: 31 passed, 0 failed, 0 skipped (2 harness/cache warnings; 0.72 s).
- Focused Stage-1/regression coverage: `.\.venv-ha-stage1\Scripts\python.exe -m pytest tests/test_models.py tests/test_storage_pure.py tests/test_storage.py tests/test_state_machine.py tests/test_foundation.py -q --tb=short --cov=custom_components.moisture_loop.const --cov=custom_components.moisture_loop.models --cov=custom_components.moisture_loop.storage --cov=custom_components.moisture_loop.state_machine --cov-branch --cov-report=term-missing` -> PASS: 421 passed, 0 failed, 1 skipped (the deliberate pure-boundary proof skips when HA is installed), 2 warnings; affected-module branch coverage 92.39%; `const.py` 100.00%, `models.py` 87.91%, `storage.py` 92.27%, `state_machine.py` 100.00% (7.03 s).
- Skip audit: the same focused suite with `-rs` -> PASS before the final duplicate-ID regression was added: 420 passed, 1 skipped; skip reason: the foundation boundary proof intentionally runs only in the pure environment. The final coverage command above contains the additional passing regression and the same single collected skip.
- Ruff 0.16.4: `uvx --from ruff==0.16.4 ruff check custom_components tests scripts` -> PASS; `uvx --from ruff==0.16.4 ruff format --check custom_components tests scripts` -> PASS, 32 files already formatted.
- Broad inventory only: `.\.venv-ha-stage1\Scripts\python.exe -m pytest -q --tb=no` -> expected downstream non-green result: 555 passed, 90 failed, 1 skipped, 1 teardown error, 3 warnings (12.52 s). Failures are confined to historical runtime/lifecycle/entity/service/Repair/controller suites that start from an empty schema-2 first install and still expect `async_update_zone` to create spec.3 zone records. The seam intentionally refuses that unsafe identityless creation; Stages 2/3 must create/consume canonical records, and Stage 6 later owns surface remediation. This result is not treated as a Stage-1 failure or as integrated spec.4 evidence.

Local test-environment notes:
- The repository's existing `.venv`/`.venv-ha` launchers referenced unavailable interpreters, so an ignored `.venv-ha-stage1` was created from `requirements_test_ha.txt` for verification only.
- Windows harness startup required the same local-only accommodations as the historical environment: `pycares==4.4.0` for the `aiodns` compatibility issue and an untracked no-op Unix `resource` shim. Project requirements and production source were not changed for these accommodations.

Open issues:
- No Stage-1 specification ambiguity or blocker was found.
- Stages 2-8 remain unimplemented/unverified. The broad-suite failures above are the honest downstream boundary: Stage 2 owns safety-record resource/blocker integration and history continuity; Stage 3 owns canonical record materialization/reconciliation/runtime consumption; later stages own their explicitly assigned runtime and presentation work.
- Slices 1 and 4 remain `[~]` because Stage-1 completion does not complete their Stage-2/3 obligations.
- Stage 2 is technically unblocked by the persistence primitives but is not authorized.
- Slice 13 remains not started; no automated result is claimed as §46 prototype evidence.

Authorization closeout:
- Current authorized slice returned to `None`. No Stage 2 authorization is implied.
- `SPECIFICATION.md` was not changed.
- Historical spec.3 session/test records were preserved without rewriting.

PROGRESS.md updated:
- yes

Future sessions must append entries in this format:

```markdown
### YYYY-MM-DD - Slice N

Authorized work:
- ...

Completed:
- ...

Files changed:
- ...

Tests run:
- `command` -> PASS/FAIL

Open issues:
- ...

PROGRESS.md updated:
- yes
```
