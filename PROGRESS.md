# SoilSync Implementation Progress

This document tracks implementation work against the approved `SPECIFICATION.md` version `0.1.0-spec.4`, whose architectural-review verdict is **READY WITH PROTOTYPE VALIDATIONS**.

> **Source-of-truth boundary:** `SPECIFICATION.md` is authoritative for architecture, safety behaviour, state-machine behaviour, persistence behaviour, Home Assistant integration behaviour, lifecycle behaviour, terminology, acceptance criteria, and prototype validations. `PROGRESS.md` is authoritative only for implementation status, slice status, work completed, work remaining, tests actually run, implementation blockers, implementation notes, and deviations requiring review. `PROGRESS.md` must never override, weaken, reinterpret, or silently amend `SPECIFICATION.md`. If implementation appears to require contradicting the specification, record `[?] Requires specification review` under the affected slice and stop that work until the specification is explicitly reviewed.

## Current Position

- Current authorized work: `None`; the 2026-08-24 Slice 13 Phase A continuation closed `[~] Partial`. Phase B remains explicitly unauthorized and `[ ] Not started`.
- Canonical identity: `SoilSync`; Home Assistant domain `soilsync`; integration path `custom_components/soilsync/`; public repository `https://github.com/embersas/soilsync`.
- Specification version: `0.1.0-spec.4`
- Historical implementation baseline: `Implementation and test records produced against spec.3 remain valid evidence of the work actually performed. Spec.4 Remediation Stages 1-8 and Slices 0-12 are complete; the historical records below remain preserved.`
- Current spec.4 conformance: `Spec.4 Remediation Stages 1-8 and the nomenclature-only SoilSync canonical rename are complete. Exact Home Assistant 2025.9.0 and supported-current 2026.8.3 each pass 838 tests with the one deliberate pure-boundary skip; pure passes 436/436. Executed traceability remains 134/134 normative IDs, I1-I37, and T1-T59; state_machine.py remains 100% branch. Canonical rename content SHA 46783d2900fd42a13666eb13d8fe78c623456164 passed all six GitHub-hosted jobs at embersas/soilsync.`
- Slice 9 specification status: `Resolved by approved spec.4 and completed Stages 5 and 7. Core's native add/reconfigure/delete mutations feed the existing entry listener/reconciler; actual HA 2025.9 websocket deletion is proven for IDLE, AUTO WATERING, MANUAL WATERING, SOAKING, and rapid multi-zone deletion; registry cleanup preserves canonical safety evidence; delete-only reconciliation performs zero reloads.`
- Next implementation work: `Only the unfinished Phase A items and the separately authorized Phase B physical-water items listed under Slice 13 remain. No release/submission or specification stage is authorized.`
- Release gates: `All six GitHub-hosted jobs passed canonical rename content SHA 46783d2900fd42a13666eb13d8fe78c623456164 in run 32705144394 at embersas/soilsync: lint/format, pure, HA 2025.9.0, HA 2026.8.3, hassfest, and HACS. The documentation-only tracking closeout commit containing this record receives the same exact-SHA run, reported in the final handoff. No GitHub Release, HACS default-store submission, or Brands submission has occurred.`
- Slice 13: `[~] Partial. Prior live HA/HACS baseline evidence and the 82.525-minute deployed-sensor cadence sample are preserved. Unfinished work is formally divided below into Phase A non-water live validation and Phase B physical-water validation. The Phase A continuation is partial; Phase B is not started.`
- Overall status: `Implementation and automated distribution validation are complete. Slice 13 remains partial until every applicable Phase A item and the separately authorized Phase B physical-water items are complete. No synthetic runtime result will be described as physical evidence, and no prototype absence is recorded as a pass.`

On 2026-08-22 the user explicitly authorized and completed Spec.4 Remediation Stages 1, 2, and 3 in sequence. On 2026-08-23 the user explicitly authorized and completed Spec.4 Remediation Stages 4, 5, 6, 7, and 8, including privacy sanitization, self-hosted history replacement, first public GitHub publication, and exact-final-SHA hosted CI completion. Later on 2026-08-23 the user explicitly authorized Slice 13 prototype validation only, using GPT-5.6 Sol with extra-high reasoning. That run closed partial at the required UI/operator and physical-safety checkpoints and returned authorization to `None`. On 2026-08-24 the user explicitly authorized the canonical pre-release rename to SoilSync; that rename completed without resuming Slice 13 and returned authorization to `None`. The 2026-08-21 instruction "implement as per progress.md" remains recorded only as the historical authorization under which the spec.3 implementation was produced.

> **Development-name history:** Before the 2026-08-24 canonical rename, SoilSync was developed as **Moisture Loop** with domain/package `moisture_loop` and repository slug `moisture-loop`. Occurrences of those names in dated session logs, old commands, old file lists, old URLs, and the first partial prototype observations below are retained only as historical evidence. They are not current installation, domain, package, service, event, Store, CI, or repository instructions.

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
| 0 | Repository and quality foundation | [x] |
| 1 | Pure domain models | [x] |
| 2 | Pure state machine | [x] |
| 3 | State-machine and invariant test suite | [x] |
| 4 | Persistence and run-integrity layer | [x] |
| 5 | Global SlotManager and resource blockers | [x] |
| 6 | Home Assistant moisture sensor adapter | [x] |
| 7 | Zone runtime controller | [x] |
| 8 | Startup, reload, reconfiguration, and shutdown lifecycle | [x] |
| 9 | Config flow and zone subentries | [x] |
| 10 | Home Assistant entities and actions | [x] |
| 11 | Repairs, diagnostics, events, and logging | [x] |
| 12 | Distribution and documentation | [x] Exact public SHA passed all six GitHub-hosted jobs |
| 13 | Prototype validations | [~] Partial; Phase A non-water validation partial, Phase B not started |

Slices 0-12 are `[x]`. Slice 0 has reproducible pure, mandatory-minimum, and supported-current environments plus six non-optional CI jobs. Slice 12 closed when public SHA `43f24b12fc162412b534851b9c1b3762ca57cd98` passed all six hosted jobs. Slice 13 is `[~]`: the dated live evidence below is retained, but no mock, harness, or absent hardware is treated as a prototype pass.

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

- **Normative named tests specified:** 134 expected, 134 mechanically discovered from §39.2, 134 unique, 134 mapped, and 134 with actually executed passing evidence; zero missing, duplicate, extra, malformed, or unresolved IDs.
- **Tests currently implemented:** every SR1-SR13, PI1-PI27, MF1-MF5, AC1-AC4, ER1-ER12, LC1-LC13, ND1-ND17, TB1-TB12, AR1-AR17, RC1-RC12, and HA1-HA2 is classified `FULLY IMPLEMENTED AND PASSING`. No current normative ID remains partial, future, focused-only, manager-level-only, expected-only, skipped, or xfailed.
- **Tests actually run/passing:** the final 2026-08-23 no-Home-Assistant pure inventory passed 436 with 0 skips. Exact HA 2025.9.0 and supported-current HA 2026.8.3 each passed 838 with 1 deliberate pure-boundary skip, 0 failures, and 0 errors. The executed-JUnit checker proves 134/134 named IDs, I1-I37, and T1-T59 against both HA reports. Mandatory overall branch coverage is 92.74% with `state_machine.py` at 100.00%; supported-current overall branch coverage is 92.63%. Historical 2026-08-21 and Stage 1-6 totals remain unchanged below.

## Spec.4 Remediation Assessment

This assessment compares the approved spec.4 requirements with the dated spec.3 baseline and current remediation state. Stages 1-8 implement and prove Store schema 2, canonical `safety_records` plus independent `zone_histories[*].zone_runtime`, exact `safety_record_id` blockers, fail-closed reconciliation/reload admission, conservative history handoff without hazard transfer, the entry-wide coordinator/final command envelope, native config-subentry flows, schema-2 entities/actions, exact-record Repairs, diagnostics, deleted-safe events, documentation, supported-current compatibility, distribution metadata, and exact-public-SHA hosted gates. Live controller/session/accounting writes use explicit schema-2 record/history IDs without a `ZoneRecord` projection. Historical schema-1 types/parsers remain migration-only; obsolete runtime/test compatibility projections were removed. Slice 13 now has partial live evidence but remains incomplete.

| Slice | Current assessment | Actual spec.4 impact |
|---:|---|---|
| 0 | `[x] Stage 8 quality/current-HA foundation complete` | Reproducible pure, exact HA 2025.9.0, and exact supported-current HA 2026.8.3 environments pass; HA1/HA2, traceability, coverage, source audits, lint, formatting, and all six hosted CI jobs are current. |
| 1 | `[x]` | Canonical identity/ownership models and conservative history continuity are fully consumed and evidenced without a current schema-1 projection. |
| 2 | `[x]` | The pure five-state T1-T59 decision semantics are unchanged. Reconciliation must dispatch the broadened T21/T39 trigger, but no new pure transition/state is required. |
| 3 | `[x]` | Mechanical executed-evidence traceability covers all 134 named IDs and I1-I37; T1-T59 implementation/table/diagram/test parity and 100% branch coverage pass. |
| 4 | `[x]` | Schema 2/migration, exact-record writes, startup union, tombstones, reactivation, A -> B history handoff, canonical live persistence, integrity reconstruction, and delayed accounting recovery are fully evidenced. |
| 5 | `[x]` | SlotManager exact-record blockers, the reconciliation barrier, startup restore, FIFO semantics, and independent blocker release pass integrated evidence. |
| 6 | `[x]` | Entity-filtered changed/unchanged report delivery, normalization, timestamp, and freshness semantics remain normative. Persistent sensor identity and reconciliation handoff are assigned to Slices 1/4/8; real rename validation remains Slice 13. |
| 7 | `[x]` | Controllers use canonical record/history persistence, one OFF future, the final no-yield ON fence, deterministic watchdog/manual/accounting behavior, and retained observation-only ownership; all integrated groups pass. |
| 8 | `[x]` | Listener/coordinator/startup union, lifecycle materialization, exact reactivation, A -> B, reload, shutdown, delete races, and restart reconstruction are fully evidenced. |
| 9 | `[x]` | Config flow uses `async_update_and_abort`, owns no reload/application state, enforces durable identity, and native HA deletion passes IDLE/AUTO/MANUAL/SOAKING/rapid-delete evidence with zero delete-only reload. |
| 10 | `[x]` | Schema-2 entities/actions and all lifecycle/reconciliation refusal surfaces pass final traceability. |
| 11 | `[x]` | Exact-record Repairs, incidents, diagnostics, deleted-safe events, delayed closure, and logging pass final traceability. |
| 12 | `[x] Exact-public-SHA hosted gates complete` | README/developer docs and distribution metadata are spec.4-current; HA 2025.9.0 and 2026.8.3, traceability, package, local-only, Recorder, metadata, hosted hassfest, and hosted HACS gates pass SHA `43f24b12fc162412b534851b9c1b3762ca57cd98`. |
| 13 | `[~] Partial live evidence` | Real HA/HACS baseline and deployed-sensor cadence evidence exist; full UI, physical valve, Registry rename, shutdown, ten-zone, longer cadence, and HACS presentation obligations remain incomplete. Existing mocks and harness tests do not satisfy them. |

## Spec.4 Implementation Remediation Plan

Stages 1-8 were explicitly authorized in sequence and are complete. Stage 8 included privacy history rewriting, self-hosted history replacement, first public GitHub publication, and exact-final-SHA hosted CI; all six hosted jobs passed the exact public candidate. Slice 13 was later explicitly authorized and closed `[~]` with the dated live evidence below. Current authorization is `None`. A later stage may be marked complete only after its named evidence is implemented and actually run.

### Stage 1 - Canonical models and Store schema-1 -> schema-2 migration

- **Status:** `[x] Complete on 2026-08-22`; authorization returned to `None` after the focused model, migration, Store, regression, lint, formatting, and coverage gates passed.

- **Objective:** introduce the approved ownership model: one canonical safety record per durable actuator lineage, independent zone histories with `zone_runtime`, durable identities/applied shadows/lifecycles/contribution IDs, strict schema-1 parsing, and atomic verified schema-2 migration without dropping any schema-1 fact.
- **Affected existing slices/files:** Slices 1 and 4; `const.py`, `models.py`, `storage.py`, `tests/test_models.py`, `tests/test_storage_pure.py`, and `tests/test_storage.py`.
- **Specification sections:** §§6, 12.4, 19.3-19.5, 23, 25.2-25.5, 42; I20, I23-I24, I29, I31, I33-I35, I37.
- **Required named tests:** PI21-PI23, PI27, TB7, and TB11; retain and rerun PI1-PI20.
- **Prerequisite stages:** none.
- **Completion evidence:** schema-1 preservation/migration and malformed/write/read-back failure cases pass; schema-2 round trips show correct single-authority field ownership; no grant or watering-capable runtime can use unverified migrated data. Full identity reactivation tests PI24-PI26 close in Stage 3.

### Stage 2 - Safety-record blocker identity and zone-history continuity

- **Status:** `[x] Complete on 2026-08-22`; authorization returned to `None` after exact-key persistence, admission, history-continuity, pure/HA regression, lint, formatting, coverage, and broad-inventory gates ran.

- **Objective:** re-key all hazards to `(safety_record_id, reason)`, add the reconciliation admission barrier to SlotManager, and implement deterministic contribution deduplication/conservative merge plus exact A/B hazard separation.
- **Affected existing slices/files:** Slices 1, 4, and 5; `models.py`, `storage.py`, `slot_manager.py`, controller/runtime call sites, `sensor.py`, and their focused tests.
- **Specification sections:** §§6, 11.4, 19.5, 21-22, 23.2, 24.4, 25.5; I18-I21, I23, I33, I35-I37.
- **Required named tests:** ER1-ER12, TB1-TB4, AR2-AR10, and AR17; exact-key portions are repeated end-to-end in Stage 7.
- **Prerequisite stages:** Stage 1.
- **Completion evidence:** snapshots and tests expose only safety-record blocker keys; one record/reason cannot clear another; dirty/reconciling/failed admission prevents grants; A-owned hazards stay A-owned while zone budget/interval continuity is conservatively verified.

### Stage 3 - Configuration reconciliation coordinator and runtime lifecycle

- **Status:** `[x] Complete on 2026-08-22`; authorization returned to `None` after focused lifecycle/reconciliation/controller/Store regressions, teardown reproduction, coverage, lint, formatting, diff, and broad-inventory gates ran.

- **Objective:** register the entry update listener before grants, normalize immutable applied shadows, serialize/coalesce latest-snapshot reconciliation, materialize `ACTIVE`/`DELETE_PENDING`/`RETIRED`, reconcile current-config + Store union at startup, safely reactivate the exact same record, execute A -> B handoff, and coordinate unload/reload/shutdown without stale publication.
- **Affected existing slices/files:** Slices 4, 5, 8, and 9; `__init__.py`, `runtime.py`, the spec-aligned reconciliation component, `models.py`, `storage.py`, `slot_manager.py`, and lifecycle/reconciliation/storage tests.
- **Specification sections:** §§5.1, 12.4, 22.4, 23.2-23.5, 24, 25, 30, 37; I18-I19, I26, I32-I37.
- **Required named tests:** PI24-PI27, LC13, ND1-ND3, ND6, ND13-ND16, TB5-TB11, AR1-AR17, and RC5-RC12.
- **Prerequisite stages:** Stages 1-2.
- **Completion evidence:** actual add/change/remove snapshots are classified and published only at the latest verified generation; Store-only implicit tombstones block grants; exact UUID re-add mutates one record; A -> B preserves A hazards and logical-zone state/budget rules; listener/Store/reload/supersession failures remain fail closed.

### Stage 4 - Final pre-ON gate and delete/in-flight compensation

- **Status:** `[x] Complete on 2026-08-23`; authorization returned to `None` after deterministic switch/valve gate and race tests, controller/reconciliation/lifecycle regressions, canonical persistence checks, affected-module coverage, lint, formatting, diff, and broad-inventory gates ran.

- **Objective:** place the complete authoritative live-configuration gate after all preparatory awaits, create the no-suspension dispatch boundary and in-memory possible-flow ownership, recheck immediately after ON returns/raises, and route every deletion race through one OFF/accounting operation with no resurrection.
- **Affected existing slices/files:** Slices 7 and 8; `zone_controller.py`, `runtime.py`/reconciliation interfaces, `slot_manager.py`, `storage.py`, and controller/lifecycle/deletion race tests.
- **Specification sections:** §§11.2-11.3, 13, 18.1, 22.1-22.3, 23.4, 24.4, 25; I15-I19, I22, I32-I34, I36-I37.
- **Required named tests:** ND4-ND12, ND17, RC1-RC6, and AC1-AC4; rerun SR5-SR13 and MF1-MF5 to prove watchdog/manual behaviour is unchanged.
- **Prerequisite stages:** Stages 1-3.
- **Completion evidence:** deterministic future/event interleavings prove no post-mismatch ON, durable intent covers every crash window, in-flight calls compensate immediately, and each outcome has one terminal reason, one idempotent OFF, honest accounting, retained blockers, and no future pulse/session resurrection.

### Stage 5 - Config flows and reconciler-owned reload application

- **Status:** `[x] Complete on 2026-08-23`; authorization returned to `None` after config-flow/native websocket deletion, identity, reload coalescing/failure, Stage-3/4 regression, HA1/source audit, coverage, lint, formatting, diff, and broad-inventory gates ran.

- **Objective:** retain pre-mutation quiescence where applicable, replace `async_update_reload_and_abort` with `async_update_and_abort`, remove add/flow-owned reload scheduling, validate durable identity/same-record/A -> B conflicts, and make the reconciler the sole zero-or-one reload owner.
- **Affected existing slices/files:** Slices 0, 8, and 9; `config_flow.py`, `runtime.py`/reconciliation component, `scripts/check_ha_contract.py`, strings/translations, and `tests/test_config_flow.py`/lifecycle tests.
- **Specification sections:** §§5.1, 9, 24.3-24.5, 29-30, 39.1; I26, I32-I36.
- **Required named tests:** LC3, LC13, ND1-ND2, AR1, AR5-AR6, AR11-AR16, RC7-RC8, and HA1.
- **Prerequisite stages:** Stages 1-4.
- **Completion evidence:** source/runtime checks prove the approved helper/listener pairing; add/reconfigure/delete bursts have one application owner; actual native removal supplies the post-removal mapping; delete-only work does not reload; a stable mixed batch schedules at most one supported reload after durable safety handoff.

### Stage 6 - Entities, actions, Repairs, diagnostics, events, and logging

- **Status:** `[x] Complete on 2026-08-23`; authorization returned to `None` after focused surface/tombstone/identity/reconciliation/event tests, Stage-3/4/5 regressions, broad HA 2025.9 inventory, branch coverage, lint, formatting, JSON consistency, HA contract, and diff gates passed.

- **Objective:** reject actions/entities against deleted, non-`ACTIVE`, dirty, failed, or unavailable runtime; expose safety/lineage/history/lifecycle/barrier/merge facts; implement exact-record tombstone Repairs and fix flow; and keep deleted-zone events independent of removed device IDs.
- **Affected existing slices/files:** Slices 10 and 11; `services.py`, `entity.py`, `sensor.py`, `binary_sensor.py`, `switch.py`, `button.py`, `repairs.py`, `diagnostics.py`, event/logging integration, strings/translations/icons, and surface tests.
- **Specification sections:** §§5.3, 26.3, 28, 31-34, 37; I25, I27, I32-I37.
- **Required named tests:** LC1-LC2, ND14, ND16-ND17, TB12, AR14, and RC9-RC11, plus the existing MF3-MF5 and AC4 event-order regressions.
- **Prerequisite stages:** Stages 1-5.
- **Completion evidence:** translated refusal tests cover non-ACTIVE/dirty runtime; exact-record fix flows reject stale/cross-record/unproven-OFF acknowledgement; diagnostics/events identify the owning safety record without inventing a device; registry cleanup cannot destroy safety ownership.

### Stage 7 - Full HA 2025.9 behavioural suite and I1-I37 traceability

- **Status:** `[x] Complete on 2026-08-23`; authorization returned to `None` after exact 134-ID executed-evidence traceability, I1-I37 and T1-T59 parity, compatibility cleanup, pure/HA suites, native deletion/race/integrity/surface regressions, source audits, coverage, lint, formatting, and diff gates passed.

- **Objective:** implement and run the complete approved named-test set against the integrated schema-2 architecture, including the real HA 2025.9 websocket removal route and registry cleanup, while retaining pure-state-machine and coverage guarantees.
- **Affected existing slices/files:** Slices 0 and 3-11; all existing tests plus spec.4 reconciliation/deletion test modules and the HA contract checker.
- **Specification sections:** §§14-15, 27, 39, 45; T1-T59 and I1-I37.
- **Required named tests:** all 134 unique IDs: SR1-SR13, PI1-PI27, MF1-MF5, AC1-AC4, ER1-ER12, LC1-LC13, ND1-ND17, TB1-TB12, AR1-AR17, RC1-RC12, and HA1-HA2.
- **Prerequisite stages:** Stages 1-6.
- **Completion evidence:** exact commands, environment/Core versions, counts, failures, coverage, T1-T59 parity, and I1-I37 mapping are recorded; native deletion uses `config_entries/subentries/delete`; no real sleeps; no mock result is claimed as §46 evidence.

### Stage 8 - Post-remediation documentation, supported-current HA, and distribution CI

- **Status:** `[x] Complete on 2026-08-23`; local/current-HA work, privacy sanitization, public publication, and all six exact-SHA GitHub-hosted jobs pass. Public SHA `43f24b12fc162412b534851b9c1b3762ca57cd98` is the validated candidate. No release or external store/Brands submission occurred.

- **Objective:** align user/developer documentation with safe native deletion and schema 2, then execute the separately pinned supported-current HA job and GitHub-hosted hassfest/HACS release gates without publishing.
- **Affected existing slices/files:** Slices 0 and 12; `README.md`, `DEVELOPMENT.md`, manifest/HACS metadata if accuracy changes are required, `.github/workflows/ci.yml`, `scripts/check_ha_contract.py`, and tracking/release documentation.
- **Specification sections:** §§39.1, 41-43, 45-46.
- **Required named tests:** HA1-HA2 and the full 134-ID suite as the release regression; hassfest and HACS Action are additional distribution gates, not behavioural test IDs.
- **Prerequisite stages:** Stage 7.
- **Completion evidence:** supported-current HA version/command/count is recorded; mandatory 2025.9.0 remains green; GitHub-hosted lint/format, pure, both HA jobs, hassfest, and HACS Action passed exact SHA `43f24b12fc162412b534851b9c1b3762ca57cd98`; docs no longer describe the spec.3 deletion limitation. Slice 13 remained separate and was later explicitly authorized.

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

`[x] Complete (current spec.4 quality/current-HA foundation evidenced by Stage 8 on 2026-08-23; historical spec.3 record preserved below)`

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
- `requirements_test_ha_current.txt`: Stage 8 superseded the planning pin with exact `homeassistant==2026.8.3` plus `pytest-homeassistant-custom-component==0.13.357`; the harness independently pins that exact Core release and requires Python >=3.14.2.
- `.github/workflows/ci.yml`: six non-optional jobs: `lint`, explicit no-HA `test-pure`, mandatory exact `test-ha-2025-9-0`, exact `test-ha-current`, `hassfest`, and `hacs`. The distribution jobs no longer contain existence skips.
- `scripts/check_ha_contract.py`: HA1 execution path — verifies, inside the exactly pinned HA environment, every §5.1 normative API: `ConfigSubentryFlow.async_update_reload_and_abort(..., reload_even_if_entry_is_unchanged)`, `ConfigEntry.runtime_data`/`ConfigSubentry`, state change/report/entity-registry event helpers, `State.last_reported`, `Store(atomic_writes=...)`, nested `DeviceSelectorConfig.filter`, `IssueSeverity` WARNING/ERROR/CRITICAL, `ValveEntityFeature` OPEN/CLOSE, `EVENT_HOMEASSISTANT_STOP`, `ServiceValidationError`.
- `tests/conftest.py` (minimal, HA-import-free) and `tests/test_foundation.py` (toolchain smoke, mandatory-job presence check, HA1 script presence, AST-based no-homeassistant-import audit of the pure layer).
- `DEVELOPMENT.md`: environments, bootstrap, and all local validation commands for later slices; test-module conventions (`pytest.importorskip("homeassistant")` for HA suites).
- `.gitignore`.
- Stage 8 clean-environment verification: pure Python 3.14.5 passed 436/436 with Home Assistant absent; HA 2025.9.0/Python 3.13.13 passed 838 with the one documented skip and 92.74% overall branch; HA 2026.8.3/Python 3.14.5 Linux passed 838 with the same skip and 92.63% overall branch. Both HA1/HA2 environments passed, and `state_machine.py` remained 100% branch on the mandatory suite.

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

`[x] Complete (current spec.4 scope evidenced by Stage 7 on 2026-08-23; historical spec.3 record preserved below)`

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

`[x] Complete (current spec.4 T1-T59/I1-I37/134-ID scope evidenced by Stage 7 on 2026-08-23; historical spec.3 record preserved below)`

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

`[x] Complete (current spec.4 scope evidenced by Stage 7 on 2026-08-23; historical spec.3 record preserved below)`

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

`[x] Complete (current spec.4 scope evidenced by Stage 7 on 2026-08-23; historical spec.3 record preserved below)`

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

`[x] Complete (current spec.4 scope evidenced by Stage 7 on 2026-08-23; historical spec.3 record preserved below)`

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

`[x] Complete (current spec.4 scope evidenced by Stage 7 on 2026-08-23; historical spec.3 record preserved below)`

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

`[x] Complete (current spec.4 scope evidenced by Stage 7 on 2026-08-23; historical spec.3 blocker record preserved below)`

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

Stage 5 completed the current config-flow/reload-ownership remediation: the flow uses `async_update_and_abort`, add/reconfigure schedule no flow-owned reload, the existing entry listener/reconciler applies all Core mutations, durable identity/same-record/rename/A -> B conflicts are validated without duplicating reconciliation, and actual HA 2025.9 native websocket deletion proves safe IDLE/AUTO-WATERING tombstoning plus registry cleanup with no delete-only reload. Stage 7 still owns complete 134-ID/native-route traceability. Entity/device/subentry attribution tests implemented under Slice 10 remain historical spec.3 evidence pending that audit.

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

`[x] Complete (current spec.4 scope evidenced by Stage 7 on 2026-08-23; historical spec.3 record preserved below)`

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

`[x] Complete (current spec.4 scope evidenced by Stage 7 on 2026-08-23; historical spec.3 record preserved below)`

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

`[x] Complete` — Stage 8 documentation, supported-current HA, metadata, CI, package, local-only/Recorder, traceability, local hassfest, privacy sanitization, and repository hygiene work pass. Public SHA `43f24b12fc162412b534851b9c1b3762ca57cd98` passed all six GitHub-hosted jobs.

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

- Implementations and current automated evidence exist through Slice 11; Spec.4 Remediation Stages 1-8 are complete and the exact public candidate passed its hosted release gates.

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
- Stage 8 replaced the historical README limitation with the implemented spec.4 native deletion/tombstone, add/reconfigure, safety, action, Repair, diagnostics, local-only, minimum-version, and Slice-13-boundary documentation. `DEVELOPMENT.md` and `CLAUDE.md` now describe the two-HA-environment policy and current commands.
- Current metadata passes JSON/YAML/key parity and local hassfest: manifest `0.1.0`, helper/calculated/single-entry/config-flow classification, empty requirements, HACS floor `2025.9.0`, synchronized services/strings/en/icons, and a 256x256 RGBA local icon. Current HACS schema no longer supports the historical `render_readme` key, which was removed.
- Stage 8 current HA evidence is exact `homeassistant==2026.8.3`, Python 3.14.5 Linux, `pytest-homeassistant-custom-component==0.13.357`, pytest 9.0.3, pytest-cov 7.1.0, and coverage 7.15.2: 838 passed, 0 failed, 1 documented skip, 0 errors, 92.63% overall branch. Mandatory HA 2025.9.0 remains 838/0/1/0 at 92.74% overall branch and 100% `state_machine.py`; pure remains 436/436 with no skip. Traceability is 134/134, 37/37, and 59/59 in both HA report checks.

### Remaining work

- None within Slice 12. Release publication and any HACS default-store or centralized-brand submission remain separately authorized (§41/§46) and were not begun.

### Tests actually run

All on 2026-08-21 (local machine):

- **Full HA 2025.9.0 suite: 631 passed, 1 skipped; 100.00% branch coverage across all seventeen integration modules (2884 statements, 936 branches).** Gates re-run explicitly: `coverage report --include="*/state_machine.py" --fail-under=100` -> PASS (526/316, 0 missed); `coverage report --fail-under=90` -> PASS (100.00%).
- Pure suite: 401 passed, 8 skipped (no homeassistant installed). `ruff check` / `ruff format --check` -> PASS.
- HA1: `scripts/check_ha_contract.py --expect 2025.9.0` -> PASS (all 11 §5.1 API contract checks against the exact pinned release).
- Mechanical audits -> PASS: exactly T1-T59 represented with expected destinations (`TestTransitionTable`); all 31 invariants mapped to passing named evidence (`TestInvariantTraceability`, now with zero deferred placeholders).
- Dependency/network audit -> PASS: `requirements: []`; grep over the integration source finds no aiohttp/requests/urllib/websocket usage, no recorder import, no cloud/telemetry/API-key references (the single textual hit is the diagnostics docstring stating Recorder is not used). Local-only (I28) and no-Recorder-safety-dependency confirmed.
- Metadata consistency -> PASS: manifest/hacs/version/translations/icons all parse and agree; strings/en.json in sync.

Historical 2026-08-21 statement: the supported-current HA harness was **not run** in that session. This is superseded by the Stage 8 exact HA 2026.8.3 execution evidence above and in the Stage 8 session log; the historical planning pin alone was never treated as evidence.

On 2026-08-23 GitHub workflow run `32630108774` passed all six jobs for exact public SHA `43f24b12fc162412b534851b9c1b3762ca57cd98`: lint/format, pure, HA 2025.9.0, HA 2026.8.3, hassfest, and HACS.

### Decisions / implementation notes

- The `venv-ha` local harness runs the exact 2025.9.0 release, so "release gates" here means every automated §45 gate except the two GitHub-hosted actions.
- Historical note from 2026-08-21: the then-current README documented the spec.3 Slice 9 limitation (UI zone deletion applied at the next reload). Stage 8 removed that limitation only after Stages 5 and 7 proved native deletion and safety reconciliation.

### Deviations from specification

None.

### Blockers

None. Official local hassfest passes (`Integrations: 1`, `Invalid integrations: 0`) and the hosted HACS/hassfest jobs passed the exact public candidate.

## Slice 13 - Prototype validations

### Status

`[~] Partial — Phase A non-water live validation is partial; Phase B physical-water validation is [ ] Not started`

### Phase split

#### Phase A - Non-water live validation

`[~] Partial`

Phase A contains only live validation that requires no actual irrigation water
flow:

- **A1. HACS custom-repository installation and presentation:** add the public
  SoilSync repository through real HACS, install it, restart when required,
  and verify the installed component and startup result.
- **A2. Real SoilSync Home Assistant UI/UX lifecycle:** use isolated synthetic
  sensor/actuator entities where an actuator is required; validate controller
  and zone creation, entities, actions, reconfigure, diagnostics, native
  deletion/re-add, reload/restart survival, and safely observable Repairs.
- **A3. Real Entity Registry rename and durable identity continuity:** rename a
  temporary synthetic SoilSync sensor or actuator through the supported real
  Registry UI, verify the Registry UUID plus `safety_record_id`,
  `safety_lineage_id`, and `zone_history_id` continuity, then restore the
  original entity ID and verify restoration.
- **A4. Approximately ten simultaneously-dry live zones:** create about ten
  unique live synthetic moisture entities and ten independently observable
  synthetic actuators in the real HA runtime. Validate serialization, FIFO
  admission, queue visibility, fairness/no starvation, pulse/soak/recheck,
  cancellation, and cleanup.
- **A5. Deployment sensor cadence and live SoilSync freshness:** use the one
  real deployed moisture sensor read-only, paired only with a synthetic
  actuator, to extend cadence evidence and validate changed/unchanged report,
  `state_reported`, and SoilSync `fresh_until` behavior.
- **A6. Final non-water HACS/integration presentation review:** inspect the
  HACS card, README, icon, name, description, version, integration search,
  Devices & services, device/entities/actions, diagnostics, Repairs where
  observed, links, and current UI terminology.

Phase A safety and evidence rules:

- Physical valve OPEN commands are forbidden.
- No physical irrigation hardware may be energised. This includes physical
  `switch.turn_on`, physical `valve.open_valve`, a SoilSync manual request
  targeting physical equipment, or any script/automation known to energise
  irrigation.
- Shutdown during active flow is not part of Phase A.
- The approximately ten-zone scheduler/load test does not require purchasing
  ten physical moisture sensors. Section 46 permits real live Home Assistant
  synthetic entities for this scale/load validation.
- Live synthetic entities are real Home Assistant runtime evidence, but they
  are not physical sensor or valve evidence.

#### Phase B - Physical-water validation

`[ ] Not started`

Phase B contains only:

- **B1. Physical valve state/availability/position/external-interference
  matrix.**
- **B2. Actual active-flow Home Assistant/container shutdown and measured
  shutdown-to-proven-OFF timing.**

Phase B requires known-safe physical irrigation hardware, actual physical
flow, an explicit operator water checkpoint, a manual stop/fallback, and a
separate authorization/run. It must not begin during Phase A.

#### Future multi-zone deployment

- Approximately six potential physical irrigation zones currently exist.
- Only one physical soil-moisture sensor is currently installed.
- Additional per-zone moisture sensors are planned but have not yet been
  purchased.
- The architecture remains one soil-moisture sensor per independently
  controlled real physical irrigation zone. The single installed sensor must
  not be configured as the permanent control sensor for all six zones.
- Purchasing the additional sensors is not a prerequisite for Phase A.

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

- Slices 0-12 complete and current SoilSync SHA `f4229cfe040d5542ae5acbfc3510ffe7cb922f4f` available.
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

- The user explicitly authorized **Slice 13 prototype validation only**, using GPT-5.6 Sol with extra-high reasoning. No later stage, release, submission, version bump, tag, or specification change was authorized.
- The mandatory pre-live review was completed: `SPECIFICATION.md` `0.1.0-spec.4` (including §46), `PROGRESS.md`, `README.md`, `DEVELOPMENT.md`, the current public repository, and local git/remotes were read or inspected before live-system work.
- Live baseline: Home Assistant Core `2026.7.2`, Home Assistant Container on Docker with host networking; HACS `2.0.5`; Moisture Loop was not installed and had no config entry; candidate version `0.1.0`, SHA `43f24b12fc162412b534851b9c1b3762ca57cd98`; a recent full HA backup was confirmed. The private LAN address and credentials are not recorded.
- Reachability was proved on the configured HA endpoint; the frontend returned HTTP 200 and the unauthenticated API correctly returned 401. A configured trusted-network auth flow correctly refused this workstation (`not_allowed`), so authentication was not bypassed. Legitimate SSH/Docker host control was available separately.
- Read-only live inventory identified one deployed valve, separate deployed irrigation switches, a representative deployed Zigbee/MQTT soil sensor, and unrelated irrigation automations/scripts. Every candidate irrigation actuator was unavailable. No actuator command was issued, no automation was disabled, and the physical-water checkpoint was never reached.
- The operator confirmed through the real HA UI that HACS 2.0.5 and its Custom repositories dialog were available. No controllable browser session was available to Codex. The next one-step instruction—to add `https://github.com/embersas/moisture-loop` as category Integration—did not produce an operator result before closeout; live HACS storage and `custom_components` still showed no Moisture Loop repository/install.
- A seven-day live Recorder cadence query and an 82.525-minute read-only MQTT observation were completed for the deployed soil sensor. Recorder showed 198 rows, 196 numeric changed rows, two availability rows, and 193 within-availability intervals (median 870.742 s, p90 5012.61 s, maximum 79464.4 s). Direct observation captured 20 messages in eight bursts; burst-gap median was 994.638 s and maximum 1116.047 s, with six unchanged-value transitions and two approximately 30-second gaps. Because the direct observation was shorter than the two-hour default, the default was not declared validated and was not changed.
- Structured public-safe evidence for each item is in `PROTOTYPE_VALIDATION.md`.

| §46 item | Result | Evidence class | Live result |
|---|---|---|---|
| 1. UI/UX lifecycle | `BLOCKED` | `NOT VALIDATED` | Real HACS UI was reachable, but no Moisture Loop installation/controller/zone/action/delete/Repair/diagnostic/reload/restart UI lifecycle was run. HACS navigation is not substituted for integration UI evidence. |
| 2. Physical valve matrix | `BLOCKED` | `NOT VALIDATED` | All identified physical candidates unavailable; no physical state sequence, interference test, or OFF proof. |
| 3. Entity Registry rename | `BLOCKED` | `NOT VALIDATED` | No configured prototype zone, so supported real Registry rename/restore and identity continuity were not run. |
| 4. Shutdown OFF timing | `BLOCKED` | `NOT VALIDATED` | Real container-control path exists, but safe active physical flow could not be established; no T0-T4 timings. |
| 5. Approximately ten dry zones | `BLOCKED` | `NOT VALIDATED` | Integration not installed; no temporary live synthetic entities/zones were created and no FIFO/fairness result exists. |
| 6. Deployment sensor cadence | `PARTIAL` | `LIVE PHYSICAL` | Multiple live changed and unchanged reports measured, but direct continuous observation did not exceed the two-hour default. |
| 7. HACS/brand presentation | `PARTIAL` | `LIVE HOME ASSISTANT` | HACS/custom-repository capability confirmed; repository card/install/version/icon/README/restart presentation not observed. No default-store or Brands submission occurred. |
- No live/physical implementation defect was discovered. The unavailable hardware and incomplete operator/UI steps are evidence gaps, not product defects or specification contradictions.
- Cleanup: watering was never started; physical actuators remained uncommanded/unavailable; no helper, prototype zone, Registry rename, automation disable, restart, or shutdown was performed; the bounded observer was stopped and its exact temporary log removed; HA remained in normal operation with no test-only Moisture Loop blocker/fault because Moisture Loop was never installed.

### Remaining work

- **Phase A:** complete A1 HACS custom-repository add/install/restart; A2 the
  real SoilSync UI/UX lifecycle with mechanically verified synthetic
  actuators; A3 the real Registry rename/identity-continuity/restore trial; A4
  the approximately ten-zone live synthetic FIFO/serialization/fairness test
  and cleanup; A5 a direct continuous sensor window exceeding two hours plus
  live SoilSync `state_reported`/`fresh_until` handling through a synthetic
  actuator; and A6 the final installed HACS/Devices & services/stale-name
  presentation review.
- **Phase B B1:** physical valve state/availability/position/external-
  interference matrix on known-safe hardware after a new authorization and
  explicit operator water checkpoint.
- **Phase B B2:** actual active-flow HA/container shutdown and measured
  shutdown-to-proven-OFF timing after a new authorization and explicit
  operator water checkpoint.

### Tests actually run

- Read-only live endpoint checks: TCP 8123 reachable; frontend HTTP 200; unauthenticated API HTTP 401.
- Read-only live HA/container/component/config-entry/Entity Registry/device/Recorder/automation/HACS/backup inventory.
- Public/local git comparison: local `HEAD`, `origin/main`, and `github/main` all `43f24b12fc162412b534851b9c1b3762ca57cd98` at baseline; public workflow run `32630108774` had six successful jobs.
- Seven-day Recorder cadence query and 82.525-minute direct read-only MQTT observation, summarized above.
- No production/test/config code changed, so the established automated suites were not gratuitously rerun. Documentation-only evidence changes pass `git diff --check` at closeout.

### Decisions / implementation notes

- The physical valve candidate's implementation reports no position support; a future physical result cannot be claimed as position evidence. §46's template cases and any unavailable-hardware limitation must be reported separately.
- Real Docker host control is available, but it is not treated as shutdown evidence without the actual active-flow shutdown test.
- Recorder history is observational cadence evidence only and remains no SoilSync runtime safety dependency.
- No successful single hardware sample would justify weakening blockers, the final ON fence, durable identity, OFF proof, Store persistence, or conservative accounting.

### Deviations from specification

None. No live result contradicted `0.1.0-spec.4`; `SPECIFICATION.md` remained unchanged.

### Blockers

- UI/operator evidence stopped after opening HACS Custom repositories; browser automation was unavailable and the instructed repository-add result was not returned.
- Every identified irrigation actuator was unavailable, so safe hardware identity/availability, manual fallback, operator water confirmation, physical valve semantics, and real shutdown OFF timing remain blocked.
- Integration setup was therefore absent, blocking the real Registry rename and ten-zone live scale exercise in this run.
- The direct cadence window was shorter than the two-hour default and is retained only as partial evidence.
- Current authorized slice returned to `None` at closeout.

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

## Session Log — 2026-08-23 (Spec.4 Remediation Stage 7)

Authorized work:
- The user explicitly authorized **Spec.4 Remediation Stage 7 only**, using GPT-5.6 Sol with extra-high reasoning: the integrated HA 2025.9.0 behavioural suite, exact 134-ID traceability, I1-I37/T1-T59 parity, compatibility-seam audit/cleanup, and narrowly necessary fixes for unambiguous spec.4 defects. Stage 8, supported-current HA execution, README/distribution remediation, GitHub hassfest/HACS execution, publication, and Slice 13 remained out of scope and were not begun.

Traceability implementation and result:
- Added `tests/traceability_manifest.py`, a checked mapping from every normative §39.2 ID to one or more substantive pytest nodes and an explicit `pure` or `ha-2025.9.0` environment. One test supports multiple IDs only where its assertions prove each mapped obligation; multi-layer requirements map to multiple nodes.
- Added `tests/test_traceability.py`, which mechanically parses §39.2 and §27, rejects malformed/duplicate/missing/unknown/extra IDs, detects duplicate manifest dictionary keys through AST, verifies every mapped node exists, checks exact I1-I37/component/normative-ID/evidence coverage, checks exact T1-T59 evidence, rejects xfails/unexpected skips, and rejects behavioural wall-clock sleeps.
- Added `scripts/check_traceability.py`, which consumes the independent pure and HA pytest JUnit reports and requires every mapped node to have actually executed and passed in its declared environment. It also provides direct lookup such as `--show AR14`, `--show I37`, and `--show T25`.
- Final normative result: expected 134; discovered 134; unique 134; mapped 134; passing 134; missing `[]`; duplicate `[]`; unresolved `[]`. Every group is fully implemented and passing: SR 13/13, PI 27/27, MF 5/5, AC 4/4, ER 12/12, LC 13/13, ND 17/17, TB 12/12, AR 17/17, RC 12/12, HA 2/2. No ID remains partial/future/focused-only/expected-only.
- Final invariant result: expected 37; mapped 37; fully evidenced 37; unresolved `[]`. The machine check rejects missing, duplicate, unknown, empty-evidence, nonexistent-test, and unknown-normative-ID references.
- Final transition result: specification rows 59; implementation IDs 59; tested IDs 59; missing `[]`; duplicate formal rows `[]`; T60+ additions `[]`; destination/reason/fault/diagram mismatches `[]`. The table parser, production AST inventory, §15 diagram inventory, canonical destination semantics, and all 59 parameterized executable rows agree.

Compatibility-seam audit and disposition:
- **Removed — historical-test/dead projection:** `StoreData.zones`; no second mutable schema-1-shaped view remains on canonical Store data.
- **Retained migration-only:** `ZoneRecord`, `Schema1StoreData`, their strict serializers/parsers, `MigrationRecordContext`, and `migrate_schema1_to_schema2`. Production references are confined to `models.py` and `storage.py`; tests reference them only in dedicated schema-1 parser/migration coverage. The exact schema-1 parser and PI21-PI23/TB7 regressions remain green.
- **Removed — historical-test/dead mutation seam:** `SafetyStore.async_update_zone`.
- **Removed — historical-test/dead mutation seam:** `SafetyStore.async_update_record_runtime` and its internal compatibility updater.
- **Removed — historical-test/dead construction seam:** controller `build_record`.
- **Removed — obsolete optional projections:** `ZoneRuntime.to_legacy_record`, Store `legacy_record_for`, the ambiguous zone-ID `async_rebase_soaking_owner`, and legacy optional arguments to `ZoneController.async_attach`.
- **Retained for a current justified reason:** canonical `SafetyStore.async_rebase_soaking_owner_for_record(safety_record_id, ...)`, which is the exact-record verified owner rebase required for trusted SOAKING adoption; it is not a schema-1 projection.
- Lifecycle and ordinary schema-2 Store fixtures were converted to construct `SafetyRecord`/`ZoneHistory` directly; schema-1 migration is no longer used as test convenience. Current watering-capable runtime uses no `ZoneRecord`, `StoreData.zones`, identityless compatibility record, schema-1 mutation helper, or second persisted authority.

Integrated architecture audit:
- Canonical persistence authority is schema-2 `SafetyRecord` plus `ZoneHistory.zone_runtime`; active runtime writes name both stable IDs and read-back verify the complete payload before dependent action.
- Source/call-path audit proves every production blocker add/remove uses `(safety_record_id, reason)`. Logical `zone_id` remains permitted only for FIFO/current logical-zone ownership; no physical hazard keys use zone/subentry identity.
- `SafetyRecord` owns actuator identity/hazards/fault/acknowledgement/possible flow. `ZoneHistory.zone_runtime` owns enabled/current state/current sensor/current zone fault/current session. Retained B operational state never overrides the current logical zone during A -> B; current valid/unavailable/invalid sensor variants and retained-B WATERING closure all pass.
- Same-record reactivation now directly proves exact Registry UUID, stable record/lineage/history, unchanged blocker key, one Repair, daily runtime/minimum interval, acknowledgement, open accounting, fresh sensor/config state, and no WATERING/SOAKING resume. Delayed exact OFF closes accounting while acknowledgement remains.
- A -> B integrated evidence proves A-owned blockers/possible flow/fault/acknowledgement/accounting/Repair remain separate; retained/new/conflicting B resolves independently; continuing zone history keeps enabled/budget/interval and conservative contribution merge; B historical operational state never leaks; B cannot clear A and A may globally block B.
- Foundation AST/source audits prove one normal idempotent controller OFF operation/future covers normal pulse, Stop, Disable, faults, deletion, reconfigure, reload, unload, shutdown, ON exceptions, interference, and delayed proof. Startup's one defensive OFF is the specified recovery path, not a competing normal session OFF implementation.
- Stage-4 switch/valve suite proves AUTO first/continuation and MANUAL use the final membership/fingerprint/generation/lifecycle/admission/blocker/slot gate after preparatory awaits, establish possible-flow intent, have no yield from authorization to dispatch initiation, immediately recheck the result, and converge through shared OFF on mismatch/exception.

Native HA 2025.9 deletion and named regressions:
- Actual supported Core websocket `config_entries/subentries/delete` tests pass for IDLE, AUTO WATERING, MANUAL WATERING, SOAKING, and rapid two-zone deletion. Public `entry.subentries` changes before listener work; no integration pre-delete hook exists; update reconciliation sees the post-removal mapping; final ON rejects removed membership; delete-only reload count is zero; controller/device/entity cleanup cannot erase the canonical record/history; tombstone, delayed accounting/events, and exact re-add remain valid.
- SR13 exact regression passes: 10:00 report arms 12:00; 11:59 report creates the authoritative 13:59 arm; deliberate execution of the stale 12:00 callback produces zero OFF/fault/reason and leaves WATERING active. Both exact-boundary report/watchdog orderings also pass.
- MANUAL, accounting, persistence/integrity, reconciliation/reload, config-flow, entity/action, Repair/diagnostic/event/logging, same-record, A -> B, and all RC1-RC12 race/failure groups pass. RC5 and RC6 now have direct delete-vs-reload and delete-vs-shutdown/restart tests rather than inferred evidence from separate scenarios.

Implementation defects found and fixed:
- **CONFIGURATION_INVALID clearing durability:** the Repair could be deleted after only an in-memory controller change. Clearing now first performs an exact canonical schema-2 Store reconciliation/read-back verification, then removes the Repair.
- **Exact same-record open-accounting reactivation:** the reconciler treated continuity as requiring the old subentry ID and rejected exact-UUID delete/re-add with unresolved conservative accounting. It now recognizes exact retained-record reactivation only when no different current prior exists, preserves the session/accounting and blocker owner, and freshly derives current operational/sensor state so old WATERING/SOAKING does not resume. A -> retained B remains a distinct path and still closes B's historical operational session before handoff.
- **Post-restart delayed OFF for an unresolved tombstone:** schema 2 deliberately omits live-only `pending_termination_reason`; a retained `ACTUATOR_OFF_TIMEOUT` session could reattach without reconstructing T15's superseding reason, causing an assertion on later OFF. Startup now deterministically restores `ACTUATOR_FAULT` from the canonical fault before any current or tombstoned controller attaches, so delayed OFF closes accounting exactly once.
- No specification contradiction, T1-T59 semantic change, private-API workaround, fail-closed weakening, or specification review was required.

Skip, race, source, and dependency audits:
- The only skip is `tests/test_models.py::TestPureBoundary::test_importing_models_does_not_import_homeassistant` in the HA-installed suite. It is non-normative and the identical node passes in the mandatory no-Home-Assistant pure suite. Pure skips: none. Normative skips: none. Xfails: none.
- The AST race audit permits only `await asyncio.sleep(0)` as deterministic event-loop yielding. No behavioral test uses real time sleeps; any HA/plugin timeout is infrastructure protection, not ordering evidence.
- Production private-API audit passes with no `_async_update_entry`, `_async_save_and_notify`, `_async_dispatch`, private config-entry signal, `SIGNAL_CONFIG_ENTRY_CHANGED`, Core delete hook patch, websocket interception, frontend deletion replacement, private storage probing, or private registry safety mutation.
- Local-only/Recorder AST audit passes: no cloud/telemetry/API-key/outbound runtime dependency and no `recorder` import/query/reconstruction path. The runtime Store is the safety persistence source.

Environment:
- Windows; HA harness Python 3.13.13; `homeassistant==2025.9.0`; `pytest==8.4.1`; `pytest-homeassistant-custom-component==0.13.277`; `pytest-cov==6.2.1`; `coverage==7.10.0`.
- Mandatory pure environment: `C:\Python314\python.exe`, Python 3.14.5, pytest 8.3.3, no `homeassistant` installed.
- Lint/format tool: `ruff==0.16.4` through `uvx`.

Tests actually run:
- Mandatory pure suite: `C:\Python314\python.exe -m pytest tests\test_models.py tests\test_storage_pure.py tests\test_state_machine.py tests\test_foundation.py tests\test_slot_manager.py tests\test_traceability.py -q --tb=short --junitxml=.stage7-evidence\pure-final.xml -o cache_dir=.pytest-cache-stage7-pure-final --basetemp=.pytest-temp-stage7-pure-final` -> PASS: 436 passed, 0 failed, 0 skipped, 0 errors (5.45 s); warning-only Python 3.14/pytest-asyncio deprecations.
- Full exact-minimum HA suite and coverage: `.venv-ha-stage1\Scripts\python.exe -m pytest tests -q --tb=short --junitxml=.stage7-evidence\ha-final.xml -o cache_dir=.pytest-cache-stage7-ha-final --basetemp=.pytest-temp-stage7-ha-final --cov=custom_components.moisture_loop --cov-branch --cov-report=term-missing --cov-fail-under=90` -> PASS: 838 passed, 0 failed, 1 deliberate pure-boundary skip, 0 errors, 1 warning (38.80 s); 92.74% total branch coverage.
- Executed traceability: `.venv-ha-stage1\Scripts\python.exe scripts\check_traceability.py --pure-report .stage7-evidence\pure-final.xml --ha-report .stage7-evidence\ha-final.xml` -> PASS: 134/134 normative IDs passing, 37/37 invariants passing, 59/59 transitions tested; pure skips `[]`; HA skip exactly the documented boundary node.
- Native deletion: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_config_flow.py::TestNativeSubentryDeletion -q --tb=short -o cache_dir=.pytest-cache-stage7-native-delete --basetemp=.pytest-temp-stage7-native-delete` -> PASS: 5 passed, 0 failed/skipped/errors (0.50 s).
- Stage-4 command fence/races: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_stage4_on_gate.py -q --tb=short -o cache_dir=.pytest-cache-stage7-stage4 --basetemp=.pytest-temp-stage7-stage4` -> PASS: 94 passed, 0 failed/skipped/errors (4.19 s).
- Reconciliation/reload/lifecycle/config flow: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_config_flow.py tests\test_reconciliation.py tests\test_lifecycle.py -q --tb=short -o cache_dir=.pytest-cache-stage7-reconcile --basetemp=.pytest-temp-stage7-reconcile` -> PASS: 104 passed, 0 failed/skipped/errors (4.08 s). Final lifecycle including direct RC5/RC6: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_lifecycle.py -q --tb=short -o cache_dir=.pytest-cache-stage7-lifecycle-final --basetemp=.pytest-temp-stage7-lifecycle-final` -> PASS: 44 passed.
- Schema-1 migration plus Store integrity: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_storage_pure.py tests\test_storage.py -q --tb=short -o cache_dir=.pytest-cache-stage7-store-integrity --basetemp=.pytest-temp-stage7-store-integrity` -> PASS: 100 passed, 0 failed/skipped/errors (1.42 s).
- Entities/actions/Repairs/diagnostics/events: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_entities.py tests\test_services.py tests\test_repairs.py -q --tb=short -o cache_dir=.pytest-cache-stage7-presentation --basetemp=.pytest-temp-stage7-presentation` -> PASS: 83 passed, 0 failed/skipped/errors (4.97 s).
- HA1/HA2: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_ha_contract.py -q --tb=short -o cache_dir=.pytest-cache-stage7-ha-contract --basetemp=.pytest-temp-stage7-ha-contract` -> PASS: 2 passed. HA1 direct source audit: `.venv-ha-stage1\Scripts\python.exe scripts\check_ha_contract.py --expect 2025.9.0` -> PASS: all 12 public minimum-release checks. HA2 confirms the exact 2025.9.0 harness/pins and separate supported-current job contract; actual supported-current execution remains Stage 8 and was not run.
- Private/local/Recorder/compatibility/skip/no-sleep/traceability audits: `C:\Python314\python.exe -m pytest tests\test_foundation.py tests\test_traceability.py -q --tb=short -o cache_dir=.pytest-cache-stage7-audits --basetemp=.pytest-temp-stage7-audits` -> PASS: 17 passed, 0 failed/skipped/errors (4.16 s).
- Explicit coverage gates: `.venv-ha-stage1\Scripts\python.exe -m coverage report --include="*\state_machine.py" --fail-under=100` -> PASS: 100.00%; `.venv-ha-stage1\Scripts\python.exe -m coverage report --fail-under=90` -> PASS: 92.74%.
- Final coverage by required architecture module: `models.py` 87.52%; `storage.py` 88.11%; `slot_manager.py` 100.00%; `state_machine.py` 100.00%; `reconciliation.py` 91.52%; `runtime.py` 89.73%; `zone_controller.py` 94.66%; `config_flow.py` 98.61%; `services.py` 100.00%; `repairs.py` 90.20%; `diagnostics.py` 96.74%.
- Final quality commands are recorded after this log once the `PROGRESS.md` edit itself is checked. JSON/translation files were not touched in Stage 7, so no Stage-7 structural JSON rerun was applicable.

Files changed:
- `PROGRESS.md`
- `custom_components/moisture_loop/models.py`
- `custom_components/moisture_loop/runtime.py`
- `custom_components/moisture_loop/storage.py`
- `custom_components/moisture_loop/zone_controller.py`
- `scripts/check_ha_contract.py`
- `scripts/check_traceability.py`
- `tests/test_config_flow.py`
- `tests/test_foundation.py`
- `tests/test_ha_contract.py`
- `tests/test_lifecycle.py`
- `tests/test_reconciliation.py`
- `tests/test_repairs.py`
- `tests/test_stage4_on_gate.py`
- `tests/test_state_machine.py`
- `tests/test_storage.py`
- `tests/test_traceability.py`
- `tests/test_zone_controller.py`
- `tests/traceability_manifest.py`

Slice status reconciliation:
- Slices 1 and 3-5 and 7-11 changed from `[~]` to `[x]` because their current spec.4 implementation scope and all required behavioural evidence now pass. Slices 2 and 6 remain `[x]` and passed integrated regression.
- Slice 0 remains `[~]`: Stage 7 completed minimum-HA/source/quality evidence, but Stage 8 still owns supported-current HA and final CI/release evidence.
- Slice 12 remains `[~]`: Stage 8 documentation/distribution/current-HA/hassfest/HACS gates are outstanding.
- Slice 13 remains `[ ]`: all seven §46 real UI/hardware/timing/scale/sensor/brand validations are unstarted; no harness result is claimed as prototype evidence.

Remaining work and authorization closeout:
- Stage 8 remains technically unblocked but not authorized: run the separately pinned supported-current HA harness, perform the post-remediation README/developer/distribution accuracy pass, and execute/record GitHub-hosted hassfest and HACS Action release gates without publishing unless separately authorized.
- Slice 13 remains unstarted: real HA UI/UX, physical valve matrix, registry rename, actual shutdown timing, approximately ten-zone scale, deployment sensor cadence, and HACS/brand presentation validations remain.
- Current authorized slice returned to `None`. Stage 8 is not automatically authorized. No Stage-8 work, supported-current run, external push/mirror/submission/publication, or Slice-13 work occurred.
- `SPECIFICATION.md` remains unchanged at `0.1.0-spec.4`; no spec.5 was created and no specification review was required.
- Final quality gates after the `PROGRESS.md` update: `uvx --from ruff==0.16.4 ruff check .` -> PASS; `uvx --from ruff==0.16.4 ruff format --check .` -> PASS (`45 files already formatted`); `git diff --check` -> PASS with warning-only Git LF-to-CRLF notices for the Windows working tree.

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
- Teardown-error reproduction/classification (performed before any Stage 2 implementation change): the broad command was rerun with `--tb=short` and reproduced the same 555 passed, 90 failed, 1 skipped, and 1 error. The sole error is `tests/test_services.py::TestManualAction::test_manual_refused_for_blocking_fault` during the HA `hass` fixture teardown. An isolated `-vv --tb=long` run reproduced the test-body mismatch (`session_active` instead of the historical `fault_blocks_manual`) and the teardown `AssertionError` at `state_machine.py::_close_open_accounting` (`session.pending_termination_reason is None`). This is not a Stage-1 model, Store, or compatibility-seam defect: `SafetyStore.async_update_zone` correctly emits the documented `StoreWriteVerificationError` before manufacturing identityless schema-2 authority. The unchanged spec.3 controller first installs its proposed session in memory, then its generic persistence-failure handler moves to `FAULT` while retaining that uncommitted session without a termination reason; the test's subsequent `unavailable -> closed` actuator change routes that impossible downstream state through delayed-accounting closure. Stage 3 replaces the empty-Store runtime materialization/consumption path and Stage 6 replaces the service-surface expectation. No suppression, xfail, skip, ignore rule, or implementation workaround was added.

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

### 2026-08-22 - Spec.4 Remediation Stage 2

Authorized work:
- The user required reproduction and ownership classification of the Stage-1 broad-inventory teardown error before any implementation change, then authorized continuation when it proved to be the expected downstream spec.3 runtime path. This authorized **Spec.4 Remediation Stage 2** only: exact safety-record blocker identity, SlotManager reconciliation admission, and conservative zone-history continuity. Stages 3-8, Slice 13, publication, and specification edits remained out of scope.

Prerequisite teardown classification:
- Reran the broad HA 2025.9.0 inventory with traceback enabled before modifying implementation code: 555 passed, 90 failed, 1 skipped, and the same single teardown error.
- Isolated `tests/test_services.py::TestManualAction::test_manual_refused_for_blocking_fault`; its body expected the historical `fault_blocks_manual` refusal but received `session_active`, then HA teardown surfaced `AssertionError` in `state_machine.py::_close_open_accounting` because `session.pending_termination_reason` was null.
- Classified this as the expected downstream spec.3 runtime/materialization path, not a Stage-1 model, Store, or compatibility-seam defect. The Stage-1 seam correctly refuses identityless creation; unchanged controller code installs a proposed session before that write, then its generic persistence-failure handler retains the uncommitted session in FAULT. The later test-driven actuator `unavailable -> closed` observation reaches a delayed-accounting precondition that the downstream path violated.
- No suppression, xfail, skip, ignore rule, exception swallowing, or implementation workaround was added. The exact classification was added to the Stage-1 remediation session before Stage-2 implementation began.

Completed:
- Re-keyed the SlotManager blocker API and every controller/runtime hazard call site to explicit `(safety_record_id, BlockerReason)` ownership while retaining zone/subentry IDs solely for FIFO request/slot ownership.
- Added a controller `safety_record_id` distinct from `zone_id`; migrated/current records resolve by current subentry first and unique legacy metadata second. The temporary no-record fallback remains live-only and fail closed until Stage 3 materializes every configured canonical record; it does not create Store authority.
- Added exact durable blocker writes on `SafetyStore`. Adds become live before persistence and remain live if persistence fails; removals become visible and can trigger a grant only after exact-record write/read-back verification. Idempotent same-value writes do not increment the revision.
- Rebuilt every persisted record blocker into SlotManager before startup grant enablement. An OFF/removal event for B cannot clear A or another reason, and persisted failure cannot create a grant window.
- Added immutable reconciliation admission state (`dirty`, `reconciling`, `failed`) to SlotManager. Each state independently blocks new grants; lifecycle grant enablement remains separate; clearing the barrier never clears a keyed blocker or disturbs a current owner.
- Changed SlotManager snapshots and the currently touched blocker projections in sensor/diagnostics from `zone_id` labels to `safety_record_id`, and exposed reconciliation/admission state in diagnostics.
- Added pure `merge_zone_history_continuity`: it preserves the continuing history's identity, current-subentry audit metadata, and exact `zone_runtime`; deduplicates identical contribution IDs; retains known distinct contributions; conservatively adds unresolved aggregates; keeps the later active local-day counter when dates differ; and takes the latest applicable interval anchors without importing retained B operational state.
- Added a serialized, read-back-verified Store history handoff for a quiesced retained record. It rejects ACTIVE or unresolved-session sources, requires exactly one source-history owner, merges budget/interval evidence, appends the old history ID as audit metadata, repoints only that exact retained record, and leaves all A/B blocker, possible-flow, fault, acknowledgement, identity, and lifecycle fields unchanged.
- Preserved T1-T59 and the pure state-machine implementation unchanged. No configuration coordinator, record materialization, live add/change/remove orchestration, same-record reactivation, final ON gate, config-flow change, or full surface remediation was implemented.

Named/focused evidence implemented:
- ER1-ER12 Stage-2 manager/call-site portions: exact durable keys, FIFO/owner separation, multiple records/reasons, startup reconstruction, persistence failures, adversarial grants, and a controller whose zone ID differs from its safety-record ID.
- TB1-TB4 Stage-2 exact-key persistence portions: exact record/reason add/remove, independent retention, idempotence, read-back reload, and no cross-record clearing.
- AR2-AR10 and AR17 Stage-2 model/Store portions: A/B hazard fields remain exclusively on their source records while known/unresolved budget contributions merge conservatively, current-day runtime cannot reset, latest minimum-interval evidence wins, and retained B `zone_runtime` does not replace the continuing logical-zone authority.
- Full coordinator/runtime/end-to-end repetitions of those named IDs remain assigned to Stages 3 and 7 and are not claimed here.

Files changed:
- `custom_components/moisture_loop/models.py`
- `custom_components/moisture_loop/storage.py`
- `custom_components/moisture_loop/slot_manager.py`
- `custom_components/moisture_loop/runtime.py`
- `custom_components/moisture_loop/zone_controller.py`
- `custom_components/moisture_loop/sensor.py`
- `custom_components/moisture_loop/diagnostics.py`
- `tests/test_slot_manager.py`
- `tests/test_storage_pure.py`
- `tests/test_storage.py`
- `tests/test_zone_controller.py`
- `tests/test_entities.py`
- `PROGRESS.md`

Tests run:
- Pre-change broad reproduction: `.\.venv-ha-stage1\Scripts\python.exe -m pytest -q --tb=short` -> expected downstream non-green result: 555 passed, 90 failed, 1 skipped, 1 teardown error, 3 warnings (14.47 s); exact teardown test/error as classified above.
- Isolated pre-change reproduction: `.\.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_services.py::TestManualAction::test_manual_refused_for_blocking_fault -vv --tb=long` -> expected downstream result: 1 failed plus the one teardown error; exact `session_active` body mismatch and `_close_open_accounting` assertion captured.
- Pure Python 3.14.5: `py -3.14 -m pytest tests/test_models.py tests/test_storage_pure.py tests/test_state_machine.py tests/test_foundation.py tests/test_slot_manager.py -q --tb=short` -> PASS: 423 passed, 0 failed, 0 skipped (warning-only Python 3.14/pytest-asyncio deprecation noise; 1.08 s).
- Focused HA 2025.9.0 regression: `.\.venv-ha-stage1\Scripts\python.exe -m pytest tests/test_models.py tests/test_storage_pure.py tests/test_storage.py tests/test_state_machine.py tests/test_foundation.py tests/test_slot_manager.py tests/test_zone_controller.py::TestExternalInterference::test_stage2_blocker_uses_safety_record_not_zone_id tests/test_lifecycle.py::TestRuntimeEdges::test_passive_listener_window -q --tb=short` -> PASS: 458 passed, 0 failed, 1 skipped; the skip is the deliberate pure-boundary proof in an HA-installed environment (5.67 s).
- Focused coverage: the same focused HA command with branch coverage for `const.py`, `models.py`, `storage.py`, `state_machine.py`, and `slot_manager.py` -> PASS: 458 passed, 1 skipped; combined affected-module branch coverage 92.25%; `const.py` 100.00%, `models.py` 87.53%, `storage.py` 89.04%, `state_machine.py` 100.00%, `slot_manager.py` 100.00% (8.12 s).
- Ruff 0.16.4: `uvx --from ruff==0.16.4 ruff check custom_components tests scripts` -> PASS; `uvx --from ruff==0.16.4 ruff format --check custom_components tests scripts` -> PASS, 32 files formatted.
- Post-change broad inventory: `.\.venv-ha-stage1\Scripts\python.exe -m pytest -q --tb=no` -> expected downstream non-green result: 570 passed, 90 failed, 1 skipped, the same 1 classified teardown error, 2 warnings (12.81 s). The 15 new Stage-2 tests account for the pass-count increase; no historical passing test regressed and the teardown path was neither masked nor changed.

Open issues:
- No Stage-2 specification ambiguity or blocker was found.
- Stage 3 must replace the temporary no-record compatibility fallback by creating/resolving canonical records before controllers, own the update listener/generations/barrier flags, reconcile the config+Store union, and orchestrate live same-record/A -> B lifecycle handoffs using the verified Stage-2 primitives.
- Stage 7 must repeat ER/TB/AR exact-key behaviour end to end. The focused Stage-2 portions are not claimed as complete integrated spec.4 evidence.
- The classified downstream teardown error remains intentionally visible until Stage 3 materializes/consumes canonical runtime records and Stage 6 updates the service-surface expectation. It was not suppressed or ignored.
- Slice 13 remains not started; no automated result is claimed as §46 prototype evidence.

Authorization closeout:
- Current authorized slice returned to `None`. No Stage 3 authorization is implied.
- `SPECIFICATION.md` was not changed.
- Historical spec.3 session/test records were preserved without rewriting.

PROGRESS.md updated:
- yes

### 2026-08-22 - Spec.4 Remediation Stage 3

Authorized work:
- The user explicitly authorized **Spec.4 Remediation Stage 3 only**: configuration reconciliation coordinator and runtime lifecycle. Stages 4-8, Slice 13, publication, external submission, specification edits, and the Stage-5 config-flow helper/reload conversion remained out of scope.

Completed architecture:
- Registered exactly one supported `ConfigEntry.add_update_listener` before grants can be enabled and placed its unsubscribe under `entry.async_on_unload`. The listener synchronously captures an immutable public-`entry.subentries` snapshot/generation, marks dirty, and closes the existing Stage-2 SlotManager barrier before returning the reconciliation coroutine; it retains no mutable `ConfigSubentry` authority and relies on no private Core dispatcher.
- Added `ConfigurationReconciliationCoordinator`, the one entry-wide serialized mutator. It owns monotonic observed/applied generations and immutable entry/zone snapshots, deterministic complete/zone fingerprints, dirty/reconciling/failed state, one active worker, equivalent-notification coalescing, re-read-after-await, supersession counting, latest-snapshot-only publication, bounded failure, and stop-time publication revocation. A stale generation may persist conservative evidence but cannot publish, detach latest ownership, mark clean, or reopen admission.
- Consumed the Stage-2 reconciliation barrier directly. Dirty, reconciling, failed, unload, reload, and shutdown ownership synchronously prevent new grants; clearing the configuration fence preserves exact keyed blockers and does not destroy an existing slot owner.
- Replaced current-subentries-only setup with one verified current-config plus persisted-Store union. Every configured zone receives a canonical schema-2 safety record and zone history before controller construction; Store-only records are implicit tombstones, restore exact blockers/evidence before grants, resolve Entity Registry UUIDs conservatively, remain observation/accounting objects where necessary, and are never current AUTO/MANUAL-eligible controllers.
- Added canonical configured-record resolution: exact Registry UUID or unambiguous current mapping reuses the existing record; a conflict-free genuinely new actuator creates one verified record/history; textual reuse, missing state/identity after deletion, or conflicting Registry UUID fails closed and persists an identity incident/blocker where possible. Normal configured controllers no longer use the temporary no-record fallback.
- Materialized `ACTIVE`, `DELETE_PENDING`, and `RETIRED` durably. Native removal is discovered from the current public mapping, quiesces the old binding, revokes future requests/timers, dispatches `CONFIG_CHANGED` for WATERING/SOAKING, persists the immutable old applied shadow/hazard state before detachment, retains unresolved exact-actuator observation/accounting, and retires only after permitted terminal-OFF/no-open-evidence conditions.
- Implemented exact same-actuator delete/re-add and rename by Registry UUID: the same `safety_record_id`, `safety_lineage_id`, and continuing `zone_history_id` are reused; prior subentry metadata is retained; budget, latest interval, enabled state, exact blockers, possible-flow ownership, fault/acknowledgement, session/accounting evidence, and current history survive without copy/re-key/reset. The newly applied sensor/config is re-evaluated and entity-ID reuse under a different UUID fails closed.
- Implemented live A -> B orchestration using the Stage-2 continuity helper. A is quiesced and retained with its exact record, blocker/fault/acknowledgement/possible-flow/open-accounting ownership. B resolves independently as exact-retained, genuinely new, or conflict. The continuing zone history keeps enabled state, current-day budget/contributions, latest interval, and freshly evaluated current sensor/config state; retained B operational state does not replace it. A evidence is never copied to or clearable by B. Interrupted Store sessions on displaced A or retained B are reconciled against their exact actuator before B may adopt the history.
- Changed runtime/controller ownership to explicit subentry -> safety record -> zone history -> lifecycle/applied shadow/controller bindings. `ZoneController` now requires a verified canonical record, persists through the exact-record Store API, exposes Stage-4 snapshot/lifecycle metadata, and becomes observation/OFF/accounting-only when retained; it cannot evaluate, manually start, queue, or accept a late slot grant. No Stage-4 no-suspension final-ON critical region or in-flight service-call compensation was implemented.
- Reload/unload/shutdown close admission and stop coordinator publication first. Generic reload retains existing `CONFIG_RELOAD` session termination and run-ID semantics; unload safely joins/supersedes reconciliation and detaches current/retained controllers without erasing Store evidence; HA shutdown owns the existing clean-run/OFF budget and a stopped coordinator cannot reopen admission.
- Removed the runtime no-record lookup fallback and the unused pre-canonical passive-listener shim. Defensive run-write failure reconciliation now iterates canonical safety records, including Registry-resolvable Store-only WATERING evidence.

Named/focused evidence implemented:
- PI24-PI26 Stage-3 portions: exact UUID delete/re-add/rename reuses one record/lineage/history; blockers are not re-keyed; budget and interval persist; same text/different UUID is rejected. PI27's configured canonical materialization/startup-union portion was rerun; Stage 7 still owns complete normative traceability.
- LC13 Stage-3 portion: exactly one public update listener, unload-owned unsubscribe, native public add/update/removal observation, and listener-compatible runtime reconciliation. Stage-5 reload-helper ownership remains unclaimed.
- ND1-ND3, ND6, ND13-ND16 Stage-3 portions: logical tombstone discovery, CONFIG_CHANGED WATERING closure, no session resurrection, retained evidence, Store crash-window recovery, listener/coordinator failure, stop-time publication fencing, and immutable ownership. ND4-ND5, ND7-ND12, ND17 final-ON/in-flight portions remain Stage 4.
- TB5-TB11 Stage-3 lifecycle portions: implicit tombstones, exact record/history retention, identity resolution/failure, no current eligibility, and durable blocker restoration. Stage 6/7 presentation and complete traceability portions remain.
- AR1-AR17 Stage-3 orchestration portions: A retention, independent B resolution, exact retained-record reuse path, conservative continuing history, disabled-state continuity, current sensor/config re-evaluation, no retained-B operational leakage, and exact A blocker independence. Stage-4 final-ON race portions and Stage-7 complete matrices remain unclaimed.
- RC5-RC12 Stage-3 portions: immutable in-place update protection, one worker, add/update/delete coalescing, repeated notification no-op joining, stale publication rejection, Store/listener failure closure, and unload/shutdown supersession. RC1-RC6 portions that require the Stage-4 final dispatch fence remain explicitly unclaimed.

Classified teardown regression:
- `tests/test_services.py::TestManualAction::test_manual_refused_for_blocking_fault` now passes in isolation with no teardown error. Canonical record/history ownership exists before the controller proposes a session, so the former identityless Store failure/uncommitted-session path no longer exists. The final broad inventory also has zero errors. The classification is **eliminated**, not suppressed, skipped, xfailed, or reassigned.

Compatibility seams remaining:
- `StoreData.zones`, `ZoneRecord`, and `SafetyStore.async_update_zone` remain non-serialized/exact-record compatibility projections for historical tests and the remaining controller/surface conversion. Runtime materialization, blocker ownership, and controller construction no longer depend on identityless creation. Stage 4 owns the remaining controller persistence conversion needed alongside final-ON work; Stage 7 owns final historical-test seam removal/audit.
- `async_prepare_reconfigure`/`async_prepare_delete`, `config_flow.py` add-owned reload scheduling, and `async_update_reload_and_abort` remain unchanged as the documented Stage-5 seam. Stage 3 did not create a second reload owner.
- Existing entity/action/Repair/diagnostic schema-1-shaped expectations remain Stage 6. The two final broad failures are exactly in entity blocker presentation and diagnostics schema-version presentation.

Files changed:
- `custom_components/moisture_loop/reconciliation.py` (new)
- `custom_components/moisture_loop/runtime.py`
- `custom_components/moisture_loop/slot_manager.py`
- `custom_components/moisture_loop/storage.py`
- `custom_components/moisture_loop/zone_controller.py`
- `tests/test_reconciliation.py` (new)
- `tests/test_config_flow.py`
- `tests/test_lifecycle.py`
- `tests/test_services.py`
- `tests/test_zone_controller.py`
- `PROGRESS.md`

Environment:
- Windows; HA harness Python 3.13.13; `homeassistant==2025.9.0`; `pytest==8.4.1`; `pytest-homeassistant-custom-component==0.13.277`; `pytest-cov==6.2.1`; `coverage==7.10.0`.
- Pure environment Python 3.14.5. Lint/format tool `ruff==0.16.4`.

Tests run:
- Iterative red/green evidence was retained rather than hidden: the first `tests\test_zone_controller.py -q --tb=short` run after enforcing canonical construction produced 2 passed, 6 failed, and 46 setup errors until the test harness materialized canonical records; its rerun passed 54. The first `tests\test_lifecycle.py -q --tb=short` run produced 19 passed/22 failed because the historical helper still constructed schema-1-shaped `StoreData`; after migrating that fixture, a genuine same-actuator persisted-session rejection was exposed and fixed, followed by 24 passed/17 failed, 38 passed/3 failed, 40 passed/1 failed, and then green inclusion in the 52- and 137-test focused runs. The first `tests\test_services.py -q --tb=short` rerun produced 25 passed/1 stale noncanonical test failure and then passed in the combined focused suite. New `tests\test_reconciliation.py` progressed from 2 passed/3 failed to 5, 9, 11, and 14 passed as synchronous-listener, native mutation, A -> B, tombstone, identity, and failure cases were completed. The first post-implementation broad run produced 673 passed/3 failed/1 skipped/0 errors; the Stage-3 config-listener expectation was corrected, leaving the final 674/2/1/0 inventory below. All implementation-owned failures were investigated and fixed; none was suppressed.
- Pure model/Store/state-machine/SlotManager regression: `py -3.14 -m pytest tests\test_models.py tests\test_storage_pure.py tests\test_state_machine.py tests\test_foundation.py tests\test_slot_manager.py -q --tb=short` -> PASS: 423 passed, 0 failed, 0 skipped; warning-only Python 3.14/pytest-asyncio deprecation noise (1.02 s).
- Stage-1/2 model/state/SlotManager/Store HA regression: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_models.py tests\test_state_machine.py tests\test_slot_manager.py tests\test_storage.py -q --tb=short` -> PASS: 386 passed, 0 failed, 1 deliberate pure-boundary skip (4.24 s).
- Focused Stage-3/controller/lifecycle/service regression: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_zone_controller.py tests\test_reconciliation.py tests\test_lifecycle.py tests\test_services.py -q --tb=short` -> PASS: 137 passed, 0 failed, 0 skipped (6.21 s).
- Classified teardown rerun: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_services.py::TestManualAction::test_manual_refused_for_blocking_fault -vv --tb=long` -> PASS: 1 passed, 0 failed, 0 errors (0.32 s).
- Focused affected-module branch coverage: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_models.py tests\test_storage_pure.py tests\test_storage.py tests\test_state_machine.py tests\test_foundation.py tests\test_slot_manager.py tests\test_zone_controller.py tests\test_lifecycle.py tests\test_reconciliation.py tests\test_services.py -q --tb=short --cov=custom_components.moisture_loop.const --cov=custom_components.moisture_loop.models --cov=custom_components.moisture_loop.storage --cov=custom_components.moisture_loop.state_machine --cov=custom_components.moisture_loop.slot_manager --cov=custom_components.moisture_loop.zone_controller --cov=custom_components.moisture_loop.runtime --cov=custom_components.moisture_loop.reconciliation --cov-branch --cov-report=term` -> PASS: 593 passed, 0 failed, 1 deliberate pure-boundary skip; combined affected-module coverage 91.67%; `reconciliation.py` 90.06%, `runtime.py` 85.92%, `storage.py` 89.64%, `zone_controller.py` 96.49%, `models.py` 87.66%, `const.py` 100%, `slot_manager.py` 100%, `state_machine.py` 100% (16.13 s).
- Explicit coverage gates: `.venv-ha-stage1\Scripts\python.exe -m coverage report --include="*/state_machine.py" --fail-under=100` -> PASS: 100.00%; `.venv-ha-stage1\Scripts\python.exe -m coverage report --include="*/slot_manager.py" --fail-under=100` -> PASS: 100.00%; `.venv-ha-stage1\Scripts\python.exe -m coverage report --fail-under=90` -> PASS: 91.67%.
- Final broad HA 2025.9.0 inventory: `.venv-ha-stage1\Scripts\python.exe -m pytest -q --tb=no` -> expected later-stage non-green result: 674 passed, 2 failed, 1 deliberate pure-boundary skip, 0 errors, 3 warnings (13.19 s). Remaining failures: Stage 4 = 0; Stage 5 = 0; Stage 6 = 2 (`tests/test_entities.py::TestBinarySensors::test_watering_on_for_external_flow`, stale subentry-ID blocker presentation expectation; `tests/test_repairs.py::TestDiagnostics::test_diagnostics_content_and_redaction`, stale schema-1 diagnostics expectation); Stage 7/test-only = 0; genuine unexpected defect = 0. Stages 4/5 are not implied complete merely because no current historical test fails there.
- Tool/version evidence: `.venv-ha-stage1\Scripts\python.exe -c "import importlib.metadata as m, sys; ..."` -> Python 3.13.13, Home Assistant 2025.9.0, pytest 8.4.1, pytest-homeassistant-custom-component 0.13.277, pytest-cov 6.2.1, coverage 7.10.0; `py -3.14 --version` -> Python 3.14.5; `uvx --from ruff==0.16.4 ruff --version` -> ruff 0.16.4.
- Quality gates: `uvx --from ruff==0.16.4 ruff check .` -> PASS; `uvx --from ruff==0.16.4 ruff format --check .` -> PASS (40 files already formatted); `git diff --check` -> PASS with warning-only Git LF-to-CRLF notices for existing Windows working-tree normalization.

Open issues / remaining remediation:
- No Stage-3 specification ambiguity, STOP condition, or implementation blocker was found. `SPECIFICATION.md` was unchanged.
- Stage 4 remains entirely unauthorised/unimplemented for the complete final pre-ON membership/fingerprint/generation/lifecycle fence, no-suspension dispatch region, in-flight marker, post-call recheck, and compensation. Stage 3 only exposes the immutable snapshot/generation/lifecycle/canonical ownership data it needs.
- Stage 5 config-flow helper and sole reload-application ownership, Stage 6 entity/action/Repair/diagnostic/event remediation, Stage 7 full 134-ID/I1-I37 evidence, Stage 8 supported-current/distribution work, and Slice 13 prototypes remain unauthorised/unimplemented or unverified as assigned.
- Stage 4 is technically unblocked by the Stage-3 interfaces and lifecycle ownership, but is not automatically authorized.

Authorization closeout:
- Current authorized slice returned to `None`. No Stage 4 authorization is implied.
- `SPECIFICATION.md` was not changed; no spec.5 was created.
- Historical spec.3 and Stage-1/2 records were preserved without rewriting.

PROGRESS.md updated:
- yes

### 2026-08-23 - Spec.4 Remediation Stage 4

Authorized work:
- The user explicitly authorized **Spec.4 Remediation Stage 4 only**: final pre-ON gate and delete/in-flight compensation, using GPT-5.6 Sol with extra-high reasoning. Stages 5-8, Slice 13, publication/external submission, specification edits, spec.5, Stage-5 config-flow/reload-helper conversion, and Stage-6 surface remediation remained out of scope.

Completed final authorization envelope:
- Added one entry-owned synchronous `authorize_on`/`recheck_on_authorization` API and immutable, single-attempt authorization token. The final gate runs in `_perform_on` after FIFO/slot admission and the verified `pulse_intent_at_utc` Store write/read-back, while the controller owns its command transition domain. AUTO T1, MANUAL T40, and each T25 continuation pulse converge on this same path.
- Every gate evaluation freshly normalizes current public `entry.subentries` and verifies: current subentry membership; current normalized zone fingerprint against the immutable applied shadow; complete fresh/applied/observed entry snapshot fingerprints; exact observed/applied generation; process/coordinator/SlotManager admission not stopping, dirty, reconciling, failed, or closed; binding/controller lifecycle exactly `ACTIVE` and neither quiescing, detaching, persistence-failed, nor terminal; exact binding/controller/Store `safety_record_id`, `zone_history_id`, applied shadow, actuator identity, and durable intent/session owner; the current logical-zone slot owner; an empty exact keyed blocker set; authoritative daily/session/freshness/manual/budget/state-machine guards; and a synchronous fresh HA actuator assessment that is available, proven OFF, and not observed ON before dispatch.
- Tokens bind the exact subentry, safety record, zone history, session, command attempt, applied generation, normalized zone fingerprint, and entry snapshot fingerprint. They are registered once, consumed immediately, cannot authorize another attempt/pulse, and are retired after command reconciliation. Post-call logic always re-reads live authority; the token is never treated as continuing permission.

Dispatch and possible-flow ownership:
- After a successful final gate, `_perform_on` synchronously creates the exact `InFlightOnCommand` marker (`safety_record_id`, `zone_history_id`, session, attempt, token, HA Context, dispatch instant), publishes it, synchronously releases the controller lock, and directly awaits `ActuatorAdapter.async_turn_on`. There is no `await`, task creation, callback scheduling, listener yield, or event-loop suspension between authorization, marker publication, and entering the HA service-call coroutine.
- Verified against the supported Home Assistant 2025.9.0 `ServiceRegistry.async_call` path: its synchronous prefix validates the handler, constructs/fires the service-call event, creates the execution coroutine, and enters the blocking service execution at its first await. A deterministic `call_soon` test proves the controlled service handler records `dispatch_started` before deletion can become visible on the next loop turn. This resolves the Python coroutine-boundary question without private APIs or invented semantics.
- The marker remains authoritative while switch `turn_on` or valve `open_valve` is slow, returns, raises, or is cancelled. Only a terminal ON/open state carrying the exact marker Context is recorded as the integration acknowledgement; genuine external state changes are not misclassified.

Immediate post-call recheck and compensation:
- On ON return or raise, before any further await, the controller records returned/raised/cancelled outcome, completion/error time, possible commanded anchor, and observed acknowledgement in memory; rebuilds current public configuration; rechecks fingerprint, snapshot/generation, lifecycle/admission/canonical ownership, slot/blocker, and ordinary guards; and synchronously commits the applicable first terminal state.
- Missing/mismatched/superseded/failed/stopping authority forbids normal WATERING continuation and requests `CONFIG_CHANGED` only when no earlier terminal reason owns the session. A still-valid service exception remains an uncertain actuator-ON fault using the existing ON timeout/fault semantics. Cancellation after marker publication is likewise uncertain. No exception is interpreted as proof that hardware stayed OFF.
- On mismatch/error, the first await is the existing shared idempotent OFF operation. There is no tombstone/command persistence await before OFF begins. Authority is checked again after reacquiring the controller lock, after commanded-anchor persistence, and after acknowledgement persistence so deletion in each narrow window cannot arm or continue a normal pulse.
- First-terminal arbitration remains deterministic: Stop, Disable, sensor/freshness fault, reload, or shutdown already synchronously accepted through the controller transition domain remains the session reason; later deletion still revokes eligibility, tombstones, and joins OFF. If deletion/configuration invalidation is accepted first, later terminal callbacks no-op. No duplicate `session_finished` is emitted.

Shared OFF, accounting, and lifecycle convergence:
- Compensation, normal pulse exit, Stop, Disable, sensor/actuator fault, external interference, generic unload/reload, native deletion, HA shutdown, service error, and cancellation all use `begin_off_operation`/the same published future and background operation. A completed unconfirmed three-attempt operation cannot be restarted as a second sequence; later exact OFF observation alone closes its evidence. Lifecycle code contains no independent actuator OFF call.
- Lifecycle waiting now distinguishes ON-dispatch completion from a deliberately open unconfirmed session. Reconciliation waits the in-flight service return/cancellation, joins the same OFF future, and may publish `DELETE_PENDING` after that exact future durably resolves unconfirmed without discarding the live observation/accounting owner. Shutdown budget exhaustion cancels the session owner into the same compensation operation and persists unconfirmed evidence rather than starting another OFF implementation.
- `pulse_intent_at_utc` remains verified before the gate and therefore spans crash-before-ON and dispatch-before-command-persistence windows conservatively. Possible flow is anchored from intent/dispatch; commanded/confirmed flow closes at exact OFF; delayed/unconfirmed OFF keeps the contribution/session, exact `(safety_record_id, integration_off_unconfirmed)` blocker, possible-flow owner, and global slot open. A later exact OFF persists closure at the observed timestamp, clears only that matching record/reason, then releases the slot. Deletion never erases current-day runtime, minimum interval, zone history, or actuator hazard ownership.
- New-pulse setup clears the prior pulse's OFF proof/timestamp so a later AUTO pulse cannot accept stale physical evidence. Quiescing cancels pulse/soak/manual/watchdog timers and pending requests; retained controllers reject evaluation/manual start/late grants. Explicit stale pulse deadline, stale watchdog token, and late slot grant tests prove no tombstoned resurrection.

Canonical persistence conversion:
- Added `SafetyStore.async_update_controller_runtime` with explicit `safety_record_id` and `zone_history_id`. Live command/session/logical-state/daily writes directly replace the exact schema-2 `ZoneHistory.zone_runtime`/daily authority and the exact `SafetyRecord` possible-flow/actuator-fault authority, followed by the existing atomic verified write/read-back. `ZoneController._persist_locked` and runtime resting-state persistence use this API.
- Normal watering-capable controller persistence no longer creates or updates authority through `ZoneRecord`, `StoreData.zones`, `SafetyStore.async_update_zone`, or `SafetyStore.async_update_record_runtime`. Focused tests monkeypatch the legacy update methods to fail and complete a live watering session successfully through the canonical API.

Named/focused evidence implemented:
- ND4-ND5 and ND7: AUTO and MANUAL deletion during possible/confirmed flow perform one OFF, never resume, and retain a sensor-only MANUAL fault overlay/history where applicable.
- ND8-ND10: deletion before intent produces no session/ON; deletion after verified intent produces zero-flow `CONFIG_CHANGED`; next-turn instrumentation proves no event-loop yield between the gate and dispatch initiation.
- ND11-ND12: native websocket deletion and fingerprint/generation/lifecycle changes while switch/valve ON is blocked, service success/raise after deletion, return-before-command-write, deletion during commanded/acknowledgement persistence, forced cancellation, and restart from intent-only evidence remain conservative and never continue normally.
- ND17: deletion interleavings retain exact blockers, slot, open accounting, record/history ownership, one terminal reason, one OFF future, and stale callback/grant suppression. The Stage-4 portions are implemented; Stage 7 still owns the complete normative matrix/traceability claim.
- RC1-RC6 applicable portions: watchdog/sensor, Stop, Disable, external-state, generic reload/unload, full shutdown, zero-budget cancellation, and native deletion races preserve first-terminal ownership and one OFF. Reconciliation dirty/reconciling/failed/stopping/superseded authority fails closed before or during dispatch.
- AC1-AC4, SR5-SR13, MF1-MF5, exact-key controller tests, external-flow/off/interference tests, Stage-3 tombstone/reactivation/reconciliation tests, and Stage-1/2 model/Store/SlotManager tests were rerun. This is focused Stage-4 evidence, not a claim that Stage 7's full 134-ID mapping is complete.

Files changed:
- `custom_components/moisture_loop/reconciliation.py`
- `custom_components/moisture_loop/runtime.py`
- `custom_components/moisture_loop/storage.py`
- `custom_components/moisture_loop/zone_controller.py`
- `tests/test_lifecycle.py`
- `tests/test_reconciliation.py`
- `tests/test_stage4_on_gate.py` (new)
- `tests/test_zone_controller.py`
- `PROGRESS.md`

Environment:
- Windows; HA harness Python 3.13.13; `homeassistant==2025.9.0`; `pytest==8.4.1`; `pytest-homeassistant-custom-component==0.13.277`; `pytest-cov==6.2.1`; `coverage==7.10.0`; `ruff==0.16.4`.

Tests run:
- Focused Stage-4 deterministic switch/valve race suite: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_stage4_on_gate.py -q --tb=short` -> PASS: 92 passed, 0 failed, 0 skipped (4.64 s).
- Stage-3/4 controller/reconciliation/lifecycle regression: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_stage4_on_gate.py tests\test_zone_controller.py tests\test_reconciliation.py tests\test_lifecycle.py -q --tb=short` -> PASS: 205 passed, 0 failed, 0 skipped (8.20 s).
- Pure/state/SlotManager and Stage-1/2 Store regression: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_models.py tests\test_state_machine.py tests\test_slot_manager.py tests\test_storage_pure.py tests\test_storage.py -q --tb=short` -> PASS: 452 passed, 0 failed, 1 deliberate pure-boundary skip (5.10 s).
- Focused affected-module branch coverage: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_models.py tests\test_state_machine.py tests\test_slot_manager.py tests\test_storage_pure.py tests\test_storage.py tests\test_reconciliation.py tests\test_stage4_on_gate.py tests\test_zone_controller.py tests\test_lifecycle.py --cov=custom_components.moisture_loop.storage --cov=custom_components.moisture_loop.state_machine --cov=custom_components.moisture_loop.slot_manager --cov=custom_components.moisture_loop.zone_controller --cov=custom_components.moisture_loop.runtime --cov=custom_components.moisture_loop.reconciliation --cov-branch --cov-report=term-missing -q --tb=short` -> PASS: 657 passed, 0 failed, 1 deliberate pure-boundary skip; combined 91.99%; `reconciliation.py` 91.13%, `runtime.py` 87.13%, `storage.py` 89.15%, `zone_controller.py` 91.32%, `slot_manager.py` 100.00%, `state_machine.py` 100.00% (19.95 s).
- Explicit coverage gates: `.venv-ha-stage1\Scripts\python.exe -m coverage report --include="*/state_machine.py" --fail-under=100` -> PASS: 100.00%; `.venv-ha-stage1\Scripts\python.exe -m coverage report --include="*/slot_manager.py" --fail-under=100` -> PASS: 100.00%; `.venv-ha-stage1\Scripts\python.exe -m coverage report --fail-under=90` -> PASS: 91.99%.
- Final broad HA 2025.9.0 inventory: `.venv-ha-stage1\Scripts\python.exe -m pytest tests -q --tb=short` -> expected later-stage non-green result: 768 passed, 2 failed, 1 deliberate pure-boundary skip, 0 errors, 3 warnings (17.90 s). Remaining failures: Stage 5 = 0; Stage 6 = 2 (`tests/test_entities.py::TestBinarySensors::test_watering_on_for_external_flow`, stale subentry-ID expectation rather than canonical `safety_record_id`; `tests/test_repairs.py::TestDiagnostics::test_diagnostics_content_and_redaction`, stale schema-1 diagnostics expectation); Stage 7/test-only = 0; genuine unexpected defect = 0. Stage 4 owns no remaining failure or teardown error.
- Post-format controller regression: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_zone_controller.py -q --tb=short` -> PASS: 57 passed, 0 failed, 0 skipped (2.82 s).
- Tool/version evidence: `.venv-ha-stage1\Scripts\python.exe -c "import importlib.metadata as m, sys; ..."` -> Python 3.13.13, Home Assistant 2025.9.0, pytest 8.4.1, pytest-homeassistant-custom-component 0.13.277, pytest-cov 6.2.1, coverage 7.10.0; `uvx --from ruff==0.16.4 ruff --version` -> ruff 0.16.4.
- Quality gates: `uvx --from ruff==0.16.4 ruff check .` -> PASS; `uvx --from ruff==0.16.4 ruff format --check .` -> PASS; `git diff --check` -> PASS with warning-only Git LF-to-CRLF notices for existing Windows working-tree normalization.
- Expected warning-only environment noise: pytest-homeassistant-custom-component's no-current-event-loop deprecation and an inaccessible pre-existing `.pytest_cache` path; neither produces a test error or changes safety evidence.

Compatibility seams remaining:
- `StoreData.zones`, `ZoneRecord`, `SafetyStore.async_update_zone`, `SafetyStore.async_update_record_runtime`, controller `build_record`, and optional legacy attach projections remain for schema migration, historical tests, and untouched compatibility consumers. They are not authority for the normal live watering command/session/accounting path. Stage 7 owns their final historical seam removal/audit.
- `async_prepare_reconfigure`/`async_prepare_delete`, config-flow add-owned reload scheduling, `async_update_reload_and_abort`, and flow helper ownership remain unchanged for Stage 5. No competing reload owner was added.
- Entity/action/Repair/diagnostic/event presentation remediation remains Stage 6; the two broad failures are intentionally unchanged surface expectations.
- Full 134-ID/I1-I37 traceability and complete native deletion/registry-cleanup inventory remain Stage 7; supported-current HA/distribution evidence remains Stage 8; all §46 Slice-13 prototypes remain unstarted.

Open issues / remaining remediation:
- No Stage-4 specification ambiguity, STOP condition, implementation blocker, T1-T59 change, or need for a second OFF path was found. `state_machine.py` and `SPECIFICATION.md` were unchanged; no spec.5 was created.
- Stage 5 is technically unblocked by the final command fence but remains unauthorised/unimplemented. Stages 6-8 remain unauthorised/unimplemented or unverified as assigned, and Slice 13 remains not started.

Authorization closeout:
- Current authorized slice returned to `None`. Stage 5 is not automatically authorized.
- `SPECIFICATION.md` was not changed; no spec.5 was created.
- Historical spec.3 and Stage-1/2/3 records were preserved without rewriting.

PROGRESS.md updated:
- yes

### 2026-08-23 - Spec.4 Remediation Stage 5

Authorized work:
- The user explicitly authorized **Spec.4 Remediation Stage 5 only**: native config-subentry flows and reconciler-owned reload application, using GPT-5.6 Sol with high reasoning. Stages 6-8, Slice 13, publication/external submission, specification edits, and spec.5 remained out of scope.

Completed config-flow and application ownership:
- Removed production use of `ConfigSubentryFlow.async_update_reload_and_abort` and every add-flow `async_schedule_reload` call. Changed reconfiguration validates/normalizes the complete candidate, cooperatively prepares a loaded old runtime through `async_prepare_reconfigure`, then calls the exact HA 2025.9 public `ConfigSubentryFlow.async_update_and_abort(entry, subentry, title=..., data=...)`. An equivalent normalized submission aborts successfully without Core mutation, preparation, observed-generation advance, session termination, or reload.
- Preserved exactly one entry-owned `ConfigEntry.add_update_listener`, registered before grants and removed through `entry.async_on_unload`. Core add/reconfigure/delete mutation reaches that listener, the Stage-3 coordinator, durable latest-snapshot reconciliation, and only then optional platform reconstruction. Config flow creates no listener, publishes no applied runtime, creates no canonical record, transfers no history/hazard, clears no blocker, and schedules no reload.
- Reduced pre-mutation preparation to cooperative old-runtime quiescence only. WATERING/SOAKING use the existing `CONFIG_CHANGED` path and complete the shared OFF safety preparation before mutation; unloaded/absent runtime data performs no invented partial reconciliation.

Reconciler-owned reload policy:
- Added one `stable_batch_requires_reload` policy. Initial setup establishes the platform snapshot without reload; pure deletion schedules zero reloads; any added subentry or materially changed fingerprint schedules one supported `ConfigEntries.async_reload(entry_id)` only after the latest durable safety handoff has published. Runtime-only optimization is not used where the current platform architecture binds entities to setup-time controller objects.
- Reload state is generation/fingerprint-bound, coalesced behind the serialized worker, and included in final-ON admission. A newer observation suppresses an obsolete not-yet-started reload and makes the latest stable snapshot the only decision owner. Equivalent post-reload notifications recognize the stable applied platform snapshot and cannot loop. Unload/shutdown cancels a stale pending request.
- False/raised/cancelled reload leaves coordinator/SlotManager admission failed/closed, retains Store/tombstone/blocker evidence, records the error, and does not retry indefinitely for an equivalent fingerprint. No reload can clear safety evidence.

Native deletion and identity:
- Exercised Home Assistant 2025.9.0's unmodified websocket/backend route `config_entries/subentries/delete` against the installed listener/reconciler for IDLE and AUTO WATERING zones. Core mapping removal is visible when websocket success returns; the immediate Stage-4 membership authority rejects a fresh ON before asynchronous reconciliation completes; active flow joins the shared OFF operation; the listener tombstones/retires the canonical record; Core removes subentry-attributed device/entity registry objects; the safety record persists; and delete-only reconciliation performs no whole-entry reload. No integration pre-delete callback, frontend/websocket interception, or private registry hook exists.
- Add/reconfigure duplicate checks compare Entity Registry UUIDs first. A current active UUID duplicate is refused; an exact retained UUID is accepted for Stage-3 same-record reactivation; a renamed entity ID resolving to the same UUID remains the same actuator; textual entity-ID reuse by another UUID or ambiguous retained evidence fails with translated `actuator_identity_conflict`; shared sensor remains warning-only.
- A -> B flow validation checks B and active/retained conflicts, quiesces old A when material, and performs only the Core mutation. The existing reconciler retains A evidence, independently resolves/reuses exact retained B, merges the continuing zone history, and fails closed on conflict. Flow code creates no B record and never discards a tombstone.

HA1 and production source contract:
- `scripts/check_ha_contract.py` now verifies HA 2025.9.0's exact `ConfigSubentryFlow.async_update_and_abort` parameter set, `ConfigEntry.add_update_listener`, `ConfigEntry.async_on_unload`, public `ConfigEntry.subentries`, and the supported `ConfigEntries.async_reload(entry_id)`, while retaining all still-valid minimum-release checks.
- The foundation AST/source audit rejects production uses of `async_update_reload_and_abort`, `_async_update_entry`, `_async_save_and_notify`, `_async_dispatch`, `SIGNAL_CONFIG_ENTRY_CHANGED`, `async_dispatcher_send_internal`, and equivalent private/manual dispatch seams. Direct source search found none.

Named/focused evidence implemented:
- Applicable Stage-5 portions of LC3, LC13, ND1-ND2, AR1, AR5-AR6, AR11-AR16, RC7-RC8, and HA1: supported update helper/listener pairing, loaded/unloaded/no-op reconfigure, native deletion and registry cleanup, duplicate/exact-retained/rename/entity-ID reuse/A -> B identity handling, latest-batch serialization, reload coalescing/stale suppression/no-loop/failure, and Stage-4 membership/compensation through a real delete mutation.
- This is focused Stage-5 evidence only. It does not claim Stage 7's complete 134-ID/I1-I37 mapping.

Files changed:
- `custom_components/moisture_loop/config_flow.py`
- `custom_components/moisture_loop/reconciliation.py`
- `custom_components/moisture_loop/runtime.py`
- `custom_components/moisture_loop/strings.json`
- `custom_components/moisture_loop/translations/en.json`
- `scripts/check_ha_contract.py`
- `tests/test_config_flow.py`
- `tests/test_foundation.py`
- `tests/test_lifecycle.py`
- `tests/test_reconciliation.py`
- `PROGRESS.md`

Environment:
- Windows; HA harness Python 3.13.13; `homeassistant==2025.9.0`; `pytest==8.4.1`; `pytest-homeassistant-custom-component==0.13.277`; `pytest-cov==6.2.1`; `coverage==7.10.0`.
- Pure environment Python 3.14.5 with pytest 8.3.3. Lint/format tool `ruff==0.16.4` through `uvx`.

Tests run:
- Pure regression: `py -3.14 -m pytest tests\test_models.py tests\test_storage_pure.py tests\test_state_machine.py tests\test_foundation.py tests\test_slot_manager.py -q --tb=short` -> PASS: 424 passed, 0 failed, 0 skipped; warning-only Python 3.14/pytest-asyncio deprecations (1.20 s).
- Stage-1/2 Store/SlotManager HA regression: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_models.py tests\test_state_machine.py tests\test_slot_manager.py tests\test_storage_pure.py tests\test_storage.py -q --tb=short` -> PASS: 452 passed, 0 failed, 1 deliberate pure-boundary skip (4.34 s).
- Complete config-flow/reconciliation/lifecycle regression: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_config_flow.py tests\test_reconciliation.py tests\test_lifecycle.py -q --tb=short` -> PASS: 95 passed, 0 failed, 0 skipped (3.47 s). This includes add, loaded/unloaded changed/no-op reconfigure, durable identity/A -> B, rapid add/reconfigure/delete, reload policy, and actual native deletion.
- Stage-3 reconciliation and Stage-4 final-ON regression: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_reconciliation.py tests\test_stage4_on_gate.py tests\test_zone_controller.py tests\test_lifecycle.py -q --tb=short` -> PASS: 210 passed, 0 failed, 0 skipped (8.02 s).
- Actual native websocket deletion focused rerun: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_config_flow.py::TestNativeSubentryDeletion -q --tb=short` -> PASS: 2 passed, 0 failed, 0 skipped (0.34 s). The immediately preceding test-only run exposed a misspelled test class reference (1 passed/1 failed); it was corrected without a production change before this green rerun.
- Focused affected-module branch coverage: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_models.py tests\test_state_machine.py tests\test_slot_manager.py tests\test_storage_pure.py tests\test_storage.py tests\test_reconciliation.py tests\test_stage4_on_gate.py tests\test_zone_controller.py tests\test_lifecycle.py tests\test_config_flow.py --cov=custom_components.moisture_loop.state_machine --cov=custom_components.moisture_loop.slot_manager --cov=custom_components.moisture_loop.storage --cov=custom_components.moisture_loop.reconciliation --cov=custom_components.moisture_loop.runtime --cov=custom_components.moisture_loop.config_flow --cov=custom_components.moisture_loop.zone_controller --cov-branch --cov-report=term-missing -q --tb=short` -> PASS: 696 passed, 0 failed, 1 deliberate pure-boundary skip; combined 93.01%; `config_flow.py` 98.61%, `reconciliation.py` 91.52%, `runtime.py` 87.30%, `storage.py` 89.15%, `zone_controller.py` 93.19%, `slot_manager.py` 100.00%, `state_machine.py` 100.00% (21.37 s).
- HA1: `.venv-ha-stage1\Scripts\python.exe scripts\check_ha_contract.py --expect 2025.9.0` -> PASS: all 11 minimum-release checks.
- Final broad HA 2025.9.0 inventory: `.venv-ha-stage1\Scripts\python.exe -m pytest tests -q --tb=no` -> expected later-stage non-green result: 785 passed, 2 failed, 1 deliberate pure-boundary skip, 0 errors, 3 warnings (17.73 s). Stage 5 = 0 failures; Stage 6 = 2 (`tests/test_entities.py::TestBinarySensors::test_watering_on_for_external_flow`, stale subentry-ID expectation rather than canonical `safety_record_id`; `tests/test_repairs.py::TestDiagnostics::test_diagnostics_content_and_redaction`, stale schema-1 diagnostics expectation); Stage 7/test-only = 0; genuine unexpected defect = 0.
- Tool/version and quality gates: `uvx ruff --version` -> ruff 0.16.4; `uvx ruff check .` -> PASS; `uvx ruff format --check .` -> PASS; `git diff --check` -> PASS. A final post-`PROGRESS.md` rerun is recorded below if its file count differs.
- Expected warning-only environment noise: pytest-homeassistant-custom-component's no-current-event-loop deprecation and an inaccessible pre-existing `.pytest_cache` path; neither produces a test error or changes safety evidence.

Compatibility seams remaining:
- `StoreData.zones`, `ZoneRecord`, `SafetyStore.async_update_zone`, `SafetyStore.async_update_record_runtime`, controller `build_record`, and optional legacy attach projections remain for schema migration, historical tests, and untouched compatibility consumers. They are not authority for normal live application/command/session/accounting. Stage 7 owns their final historical seam removal/audit.
- Entity/action/Repair/diagnostic/event presentation remediation remains Stage 6; the two broad failures remain unchanged and classified there.
- Full 134-ID/I1-I37 traceability remains Stage 7; supported-current HA/distribution/documentation work remains Stage 8; all §46 Slice-13 prototype validations remain unstarted.

Open issues / remaining remediation:
- No Stage-5 specification ambiguity, STOP condition, implementation blocker, private-API need, T1-T59 change, Stage-4 weakening, or need for spec.5 was found. `SPECIFICATION.md` was unchanged.
- Stage 6 is technically unblocked by the completed flow/reload architecture but remains unauthorised/unimplemented. Stages 7-8 remain unauthorised/unimplemented or unverified as assigned, and Slice 13 remains not started.

Authorization closeout:
- Current authorized slice returned to `None`. Stage 6 is not automatically authorized.
- `SPECIFICATION.md` was not changed; no spec.5 was created.
- Historical spec.3 and Stage-1/2/3/4 records were preserved without rewriting.

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

### 2026-08-23 - Spec.4 Remediation Stage 6

Authorized work:
- The user explicitly authorized **Spec.4 Remediation Stage 6 only**: entities, actions, Repairs, diagnostics, events, and logging, using GPT-5.6 Sol with high reasoning. Stage 7's complete 134-ID/I1-I37 traceability and compatibility-seam audit, Stage 8 documentation/distribution/supported-current HA work, Slice 13 prototypes, external publication, specification edits, and spec.5 remained out of scope.

Completed entity/runtime and action behavior:
- Added one entry-runtime presentation/action authority check over the canonical `SafetyRecord`, `ZoneHistory`, current binding/subentry membership, `ACTIVE` lifecycle, runtime eligibility, coordinator generations/state, reload state, SlotManager admission, and unload/shutdown state. Normal controls refuse translated `zone_not_active`, `reconciliation_busy`, or `reconciliation_failed` errors instead of silently queuing/no-oping; status/history entities remain presentation-only, while controls/`needs_water` become unavailable behind the same barrier and direct control calls fail visibly.
- Strengthened backend target resolution from exactly one HA `device_id` through the Moisture Loop identifier, owning config entry/subentry attribution, loaded entry, current controller, exact canonical active runtime, and reconciliation admission. A public safety-record ID is not accepted as a zone-device substitute. Manual duration rejects non-finite input and retains the complete Stage-4/pure-guard path; sensor-only manual behavior remains allowed, while actuator/configuration/integrity faults and every final-gate guard remain blocking.
- Converted entity presentation to schema-2 authority. Status exposes lifecycle, safety record/lineage/history, actuator identity/incident, exact blocker keys, possible-flow ownership, accounting/session estimation, current observation/fault overlay, and reconciliation generation/admission state. Runtime-today, last-session, next-eligible, enabled, watering, problem, and needs-water read their normative zone-history/runtime versus actuator-record owners. The external-flow watering sensor now uses canonical `safety_record_id` blockers.

Completed Repairs and tombstone handling:
- Re-keyed retained actuator/identity Repairs as the supported issue-ID encoding of `(config_entry_id, safety_record_id, issue_type)`. `ACTUATOR_OFF_TIMEOUT` remains `CRITICAL` and fixable only through a new entry-level exact-record flow; delete, RETIRED state, exact same-actuator re-add, and A -> B replacement do not re-key, duplicate, transfer, or clear A's issue.
- The flow captures entry, record, lineage, and issue type, then re-resolves the loaded entry and exact current Store record at confirmation. It rejects stale lineage/record, wrong entry, changed/non-acknowledgeable fault, unresolved identity, remaining blockers/possible-flow/session accounting, and unproven live OFF. A detached RETIRED record clears only through a new verified Store API after all exact evidence is closed; an active/retained controller clears through its existing state-machine path. Later OFF removes exact flow/accounting evidence but leaves the acknowledgement Repair until this explicit flow completes.
- Added exact-record missing/migration-unresolved and identity-conflict ERROR issues without unsafe adoption behavior, plus an entry-level ERROR reconciliation incident that persists while admission is failed and clears only after a later authoritative stable reconciliation succeeds. Recovery does not touch unrelated record blockers/faults. Current logical `CONFIGURATION_INVALID` entity-missing Repairs remain zone/configuration owned.

Completed diagnostics, events, and logging:
- Rebuilt diagnostics from Store schema 2. Entry output includes HA/manifest classification, schema/revision, shortened generation/run/fingerprints, setup integrity result, observed/applied generations, dirty/reconciling/failed/reload/supersession/error/admission state, and exact SlotManager ownership. Active-zone output combines the exact record, zone history/runtime, applied shadow, durable identities, fault authorities, observation, possible flow, session/accounting/daily contribution data, and OFF operation. `retained_tombstones` is Store-driven and requires no current subentry, controller, device, or entity. Raw Store generation/run fields remain standard-redacted and fingerprint/registry display uses shortened diagnostic forms where appropriate.
- Event emitters now close over the exact `safety_record_id` and add safety lineage/history/lifecycle ownership from the current Store record. Deleted-zone fault/finish/clear events do not require or invent a removed `device_id`; delayed OFF closes accounting and emits exactly one finish. Stage-6 testing exposed and fixed a duplicate delayed finish caused by materializing a second retained observer for a live-bound displaced session; the reconciler now transfers the existing exact controller instead.
- Added WARNING lifecycle/tombstone retention logs, INFO exact-record reactivation/retirement and reconciliation-recovery logs, and ERROR identity/reconciliation incident logs. Existing session, sensor/constrained, external-flow/interference, persistence, and `ACTUATOR_OFF_TIMEOUT` severity philosophy remains intact; the timeout is still ERROR plus CRITICAL Repair.

Known Stage-6 failures resolved:
- `tests/test_entities.py::TestBinarySensors::test_watering_on_for_external_flow` -> PASS with the expected canonical `safety_record_id` blocker key and current possible-flow semantics.
- `tests/test_repairs.py::TestDiagnostics::test_diagnostics_content_and_redaction` -> PASS with Store schema 2, active record/history/runtime content, and generation/run redaction.
- No Stage-6-owned broad failure, teardown error, Stage-7/test-only failure, or genuine unexpected defect remains.

Named/focused evidence implemented:
- Applicable Stage-6 portions of LC1-LC2, ND14, ND16-ND17, TB12, AR14, and RC9-RC11: once-only services with zero entries, exact device/backend resolution, non-ACTIVE and reconciliation-barrier refusal, native registry-cleanup tolerance, exact tombstone diagnostics/Repair identity, same-record continuity, A -> B issue separation, reconciliation failure/recovery presentation, and deleted-safe exactly-once event ownership.
- MF3-MF5 and AC4 were explicitly rerun; manual sensor-fault retention/recovery/order, actuator-fault supersession/refusal, delayed exact OFF closure, accounting, blocker removal, and acknowledgement separation remain green. This is focused Stage-6 evidence, not the Stage-7 complete 134-ID/I1-I37 traceability claim.

Files changed:
- `custom_components/moisture_loop/binary_sensor.py`
- `custom_components/moisture_loop/button.py`
- `custom_components/moisture_loop/diagnostics.py`
- `custom_components/moisture_loop/entity.py`
- `custom_components/moisture_loop/repairs.py`
- `custom_components/moisture_loop/runtime.py`
- `custom_components/moisture_loop/sensor.py`
- `custom_components/moisture_loop/services.py`
- `custom_components/moisture_loop/storage.py`
- `custom_components/moisture_loop/strings.json`
- `custom_components/moisture_loop/switch.py`
- `custom_components/moisture_loop/translations/en.json`
- `tests/test_entities.py`
- `tests/test_reconciliation.py`
- `tests/test_repairs.py`
- `tests/test_services.py`
- `PROGRESS.md`

Environment:
- Windows; HA harness Python 3.13.13; `homeassistant==2025.9.0`; `pytest==8.4.1`; `pytest-homeassistant-custom-component==0.13.277`; `pytest-cov==6.2.1`; `coverage==7.10.0`.
- Pure environment Python 3.14.5 with pytest 8.3.3. Lint/format tool `ruff==0.16.4` through `uvx`.

Tests run:
- Baseline known failures before implementation: `.venv-ha-stage1\Scripts\python.exe -m pytest tests/test_entities.py::TestBinarySensors::test_watering_on_for_external_flow tests/test_repairs.py::TestDiagnostics::test_diagnostics_content_and_redaction -q` -> expected FAIL: 2 failed, 0 passed; exactly the two recorded Stage-6 failures.
- Final known-failure rerun: `.venv-ha-stage1\Scripts\python.exe -m pytest tests/test_entities.py::TestBinarySensors::test_watering_on_for_external_flow tests/test_repairs.py::TestDiagnostics::test_diagnostics_content_and_redaction -q -o cache_dir=.pytest-cache-stage6-known-final --basetemp=.pytest-temp-stage6-known-final` -> PASS: 2 passed, 0 failed, 0 skipped (0.34 s).
- Pure regression: `C:\Python314\python.exe -m pytest tests\test_models.py tests\test_storage_pure.py tests\test_state_machine.py tests\test_foundation.py tests\test_slot_manager.py -q --tb=short -o cache_dir=.pytest-cache-stage6-pure --basetemp=.pytest-temp-stage6-pure` -> PASS: 424 passed, 0 failed, 0 skipped (1.13 s); warning-only Python 3.14/pytest-asyncio deprecations.
- Store/SlotManager regression: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_models.py tests\test_state_machine.py tests\test_slot_manager.py tests\test_storage_pure.py tests\test_storage.py -q --tb=short -o cache_dir=.pytest-cache-stage6-store --basetemp=.pytest-temp-stage6-store` -> PASS: 452 passed, 0 failed, 1 deliberate pure-boundary skip (4.38 s).
- Stage-3 reconciliation and Stage-5 config-flow/native-delete regression: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_config_flow.py tests\test_reconciliation.py tests\test_lifecycle.py -q --tb=short -o cache_dir=.pytest-cache-stage6-stage35 --basetemp=.pytest-temp-stage6-stage35` -> PASS: 95 passed, 0 failed, 0 skipped (3.40 s).
- Stage-4 final-ON/controller plus Repair/event regression: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_stage4_on_gate.py tests\test_zone_controller.py tests\test_repairs.py -q --tb=short -o cache_dir=.pytest-cache-stage6-stage4 --basetemp=.pytest-temp-stage6-stage4` -> PASS: 171 passed, 0 failed, 0 skipped (7.01 s).
- Final complete Stage-6 entity/action/Repair/diagnostic/reconciliation focus: `.venv-ha-stage1\Scripts\python.exe -m pytest tests/test_entities.py tests/test_services.py tests/test_repairs.py tests/test_reconciliation.py -q -o cache_dir=.pytest-cache-stage6-focused-final --basetemp=.pytest-temp-stage6-focused-final` -> PASS: 102 passed, 0 failed, 0 skipped (5.02 s).
- Explicit MF3-MF5 and AC4: `.venv-ha-stage1\Scripts\python.exe -m pytest tests\test_zone_controller.py::TestManual::test_manual_from_sensor_fault_returns_to_fault tests\test_zone_controller.py::TestManual::test_manual_recovery_clears_after_finish tests\test_zone_controller.py::TestManual::test_mf5_actuator_fault_supersedes_mid_manual tests\test_zone_controller.py::TestTerminationRaces::test_ac4_off_timeout_delayed_proof_closes_later -q --tb=short -o cache_dir=.pytest-cache-stage6-mf-ac --basetemp=.pytest-temp-stage6-mf-ac` -> PASS: 4 passed, 0 failed, 0 skipped (0.54 s).
- Final broad HA 2025.9.0 inventory: `.venv-ha-stage1\Scripts\python.exe -m pytest tests -q --tb=no -o cache_dir=.pytest-cache-stage6-broad-final2 --basetemp=.pytest-temp-stage6-broad-final2` -> PASS: 813 passed, 0 failed, 1 deliberate pure-boundary skip, 0 errors (18.40 s). Remaining Stage 7/test-only failures: 0. Genuine unexpected defects: 0.
- Final affected-module branch coverage: `.venv-ha-stage1\Scripts\python.exe -m pytest tests -q --tb=short -o cache_dir=.pytest-cache-stage6-coverage-final2 --basetemp=.pytest-temp-stage6-coverage-final2 --cov=custom_components.moisture_loop.state_machine --cov=custom_components.moisture_loop.storage --cov=custom_components.moisture_loop.reconciliation --cov=custom_components.moisture_loop.runtime --cov=custom_components.moisture_loop.zone_controller --cov=custom_components.moisture_loop.entity --cov=custom_components.moisture_loop.sensor --cov=custom_components.moisture_loop.binary_sensor --cov=custom_components.moisture_loop.switch --cov=custom_components.moisture_loop.button --cov=custom_components.moisture_loop.services --cov=custom_components.moisture_loop.repairs --cov=custom_components.moisture_loop.diagnostics --cov-branch --cov-report=term` -> PASS: 813 passed, 0 failed, 1 deliberate skip; combined 92.93%; `state_machine.py` 100.00%, `services.py` 100.00%, `sensor.py` 100.00%, `entity.py` 100.00%, `button.py` 100.00%, `switch.py` 100.00%, `diagnostics.py` 96.74%, `zone_controller.py` 94.91%, `binary_sensor.py` 92.86%, `reconciliation.py` 91.52%, `repairs.py` 90.20%, `runtime.py` 87.47%, and `storage.py` 86.71% (28.31 s).
- HA1/source contract: `.venv-ha-stage1\Scripts\python.exe scripts\check_ha_contract.py --expect 2025.9.0` -> PASS: all 11 minimum-release checks.
- JSON consistency: `C:\Python314\python.exe -c "import json,pathlib; a=json.loads(pathlib.Path('custom_components/moisture_loop/strings.json').read_text()); b=json.loads(pathlib.Path('custom_components/moisture_loop/translations/en.json').read_text()); print('JSON_SYNC', a == b)"` -> PASS: `JSON_SYNC True`.
- Quality gates after all source/test edits: `uvx --from ruff==0.16.4 ruff check .` -> PASS; `uvx --from ruff==0.16.4 ruff format --check .` -> PASS (41 files formatted); `git diff --check` -> PASS with warning-only Git LF-to-CRLF notices. A final post-`PROGRESS.md` check is recorded by the completion handoff.
- Expected warning-only environment noise: pytest-homeassistant-custom-component's no-current-event-loop deprecation and occasional inaccessible cache-path warnings under the workspace mount; neither produced a test error or changed safety evidence.

Compatibility seams remaining:
- `StoreData.zones`, `ZoneRecord`, `SafetyStore.async_update_zone`, `SafetyStore.async_update_record_runtime`, controller `build_record`, and optional legacy attach/projection paths remain for schema migration, historical tests, and compatibility consumers. Current entities/actions/Repairs/diagnostics/events do not treat them as authority. Stage 7 owns the final compatibility-seam and integrated traceability audit; no Stage-7 cleanup was performed for tidiness.

Open issues / remaining remediation:
- No Stage-6 specification ambiguity, STOP condition, implementation blocker, private-API need, T1-T59 change, Stage-4 weakening, or need for spec.5 was found. `SPECIFICATION.md` was unchanged.
- Stage 7 full 134-ID/I1-I37 traceability and compatibility audit remains unimplemented/unverified; Stage 8 supported-current HA/distribution/documentation work remains unimplemented/unverified; Slice 13 remains not started. Stage 7 is technically unblocked by Stage 6 but is not automatically authorized.

Authorization closeout:
- Current authorized slice returned to `None`. Stage 7 is not automatically authorized.
- `SPECIFICATION.md` was not changed; no spec.5 was created; no external publication/release/push/mirror/submission occurred.
- Historical spec.3 and Stage-1/2/3/4/5 records were preserved without rewriting.

PROGRESS.md updated:
- yes

## Final Closeout — 2026-08-23 (Spec.4 Remediation Stage 7)

- This closeout is the current record. The Stage-6 session log immediately above is preserved as historical evidence and does not supersede the completed Stage-7 session log earlier in this file.
- Stage 7 result: complete. Normative evidence is 134/134 IDs mapped and passing, I1-I37 is 37/37 mapped and passing, and T1-T59 is 59/59 implemented and tested with zero missing, duplicate, or semantic mismatches.
- Final suites: pure Python 3.14.5 = 436 passed, 0 failed, 0 skipped, 0 errors; HA 2025.9.0 on Python 3.13.13 = 838 passed, 0 failed, 1 non-normative pure-boundary skip, 0 errors. Overall branch coverage is 92.74%; `state_machine.py` branch coverage is 100%.
- Final repository gates after all edits: `uvx --from ruff==0.16.4 ruff check .` -> PASS; `uvx --from ruff==0.16.4 ruff format --check .` -> PASS (45 files already formatted); `git diff --check` -> PASS with warning-only Git LF-to-CRLF notices; `SPECIFICATION.md` -> unchanged.
- Current authorized slice: `None`. Stage 8 is technically unblocked but not authorized or begun. Slice 13 remains `[ ]` and unstarted.

## Session Log — 2026-08-23 (Spec.4 Remediation Stage 8)

### Authorization and result

- The user explicitly authorized **Spec.4 Remediation Stage 8 only**, using GPT-5.6 Sol with high reasoning. `SPECIFICATION.md`, `PROGRESS.md`, and `HOME_ASSISTANT_SUBENTRY_DELETION_INVESTIGATION.md` were read completely before any edit, followed by the workflow, documentation, metadata, requirements, scripts, repository, remotes, and CI audits.
- **Status: `[~] Blocked`.** All authorized local documentation, supported-current, mandatory-minimum, pure, traceability, metadata, package, and distribution-preflight work passes. Stage 8 cannot be marked complete because no GitHub-hosted hassfest or HACS Action result exists for the exact final commit/state, and obtaining those results requires an unauthorized external repository creation/mirror/push/workflow action.
- No STOP-condition contradiction, T1-T59 change, fail-closed weakening, minimum-version change, architecture redesign, spec.5 work, publication, submission, remote alteration, or Slice 13 work occurred. Current authorized slice returned to `None`.

### Supported-current identity and environment

- Current stable Core was established, not guessed: official Home Assistant Core GitHub release `2026.8.3` is non-draft/non-prerelease and was published 2026-08-21; PyPI's `homeassistant` index also identifies `2026.8.3`, uploaded 2026-08-21, not yanked, with `Requires-Python >=3.14.2`.
- Current PyPI metadata identifies `pytest-homeassistant-custom-component==0.13.357` as the latest harness; its dependency metadata pins `homeassistant==2026.8.3`, `pytest==9.0.3`, `pytest-cov==7.1.0`, and `coverage==7.15.2` exactly and requires Python >=3.14.
- Reproducible pin: `requirements_test_ha_current.txt` now contains direct `homeassistant==2026.8.3` and `pytest-homeassistant-custom-component==0.13.357` pins. The mandatory `requirements_test_ha.txt` remains unchanged at harness `0.13.277` / exact HA `2025.9.0`.
- A clean Windows Python 3.14.5 environment installed the exact dependency set, but the current harness imports POSIX `fcntl` at pytest-plugin startup on Windows. This was classified as a test-harness/platform issue. Final supported-current execution used a clean `python:3.14.5-slim` Linux container (`Linux 6.6.114.1-microsoft-standard-WSL2 x86_64`, glibc 2.41), independent of the HA 2025.9 environment.

### Tests and quality actually run

- Supported-current bootstrap/contract: `docker run --rm --mount "type=bind,source=$repoPath,target=/workspace" --mount "type=bind,source=$stage8Evidence,target=/evidence" -w /workspace python:3.14.5-slim sh -lc 'python -m pip install --disable-pip-version-check --requirement requirements_test_ha_current.txt && python scripts/check_ha_contract.py --expect 2026.8.3 && ...'` -> exact versions above; all 12 HA public-contract checks passed.
- Final supported-current full suite: `docker exec -e COVERAGE_FILE=/tmp/.coverage-current-clean moisture-loop-stage8-current python -m pytest tests -q --tb=short --junitxml=/evidence/ha-current-release-clean.xml -o cache_dir=/tmp/cache-current-release-clean --basetemp=/tmp/temp-current-release-clean --cov=custom_components.moisture_loop --cov-branch --cov-report=term` -> **838 passed, 0 failed, 1 skipped, 0 errors in 118.57 s; 92.63% overall branch coverage**. `state_machine.py` also reported 100%, though exact percentage parity is required only on the minimum suite.
- Mandatory full regression: `.venv-ha-stage1\Scripts\python.exe -m pytest tests -q --tb=short --junitxml="$env:TEMP\moisture-loop-stage8\ha-min-release-final.xml" -o cache_dir="$env:TEMP\moisture-loop-stage8\cache-min-release-final" --basetemp="$env:TEMP\moisture-loop-stage8\temp-min-release-final" --cov=custom_components.moisture_loop --cov-branch --cov-report=term --cov-fail-under=90` -> **838 passed, 0 failed, 1 skipped, 0 errors, 1 harness deprecation warning in 39.71 s; 92.74% overall branch; `state_machine.py` 100.00% branch**. Environment: Windows 11, Python 3.13.13, HA 2025.9.0, harness 0.13.277, pytest 8.4.1, pytest-cov 6.2.1, coverage 7.10.0.
- Pure clean environment: `uv venv --python 3.14.5 --seed .venv-pure-stage8`; `.venv-pure-stage8\Scripts\python.exe -m pip install --requirement requirements_test.txt`; `pip show homeassistant` -> not found; `.venv-pure-stage8\Scripts\python.exe -m pytest tests/test_models.py tests/test_storage_pure.py tests/test_state_machine.py tests/test_foundation.py tests/test_slot_manager.py tests/test_traceability.py -q --tb=short --junitxml="$env:TEMP\moisture-loop-stage8\pure-final.xml" -o cache_dir=... --basetemp=... --cov=custom_components.moisture_loop.models --cov=custom_components.moisture_loop.state_machine --cov=custom_components.moisture_loop.slot_manager --cov-branch --cov-report=term-missing` -> **436 passed, 0 failed, 0 skipped, 0 errors; `state_machine.py` 100.00% branch**. Warning-only Python 3.14 event-loop-policy deprecations were non-behavioural.
- HA1/HA2: `...python.exe -m pytest tests/test_ha_contract.py -q --tb=short` -> 2 passed on HA 2025.9.0 and 2 passed on HA 2026.8.3. Direct `scripts/check_ha_contract.py --expect <version>` passed all 12 checks in both environments.
- Focused native-delete/final-ON/Store/actions/entities/Repairs/diagnostics regression: `pytest -q --tb=short tests/test_config_flow.py::TestNativeSubentryDeletion tests/test_stage4_on_gate.py tests/test_storage.py tests/test_storage_pure.py tests/test_services.py tests/test_entities.py tests/test_repairs.py` -> 282 passed on HA 2025.9.0 and 282 passed on HA 2026.8.3.
- Final executed traceability, run once with the mandatory JUnit and once with the current JUnit: `scripts/check_traceability.py --pure-report <pure-final.xml> --ha-report <ha-report.xml>` -> **134/134 normative IDs, 37/37 invariants, 59/59 transitions** on each pairing. Skip audit: pure `[]`; each HA report contains only `TestPureBoundary::test_importing_models_does_not_import_homeassistant`, which passes in pure.
- Quality: `.venv-pure-stage8\Scripts\ruff.exe check .` -> pass; `ruff format --check .` -> all files formatted; `git diff --check` -> pass with warning-only LF-to-CRLF notices. JSON parsing, YAML parsing, strings/en equality, four service/action/icon-key parity, manifest/HACS assertions, and 256x256 RGBA PNG validation all pass.

### Compatibility findings and remediation

- HA 2026.8.3 initially produced six failures because older integration test doubles did not propagate `ServiceCall.context` into simulated state changes, and current HA no longer includes the controller's deliberate background session task in `async_block_till_done()`. This was classified as test-harness-only compatibility. The doubles now model real entity services by preserving context, and the native-delete test waits for actuator acknowledgement instead of depending on harness task-draining policy. No production runtime Python changed.
- Current hassfest rejected the fixable `actuator_off_unconfirmed` issue because a fixable issue translation now permits `description` or `fix_flow`, not both. The redundant top-level description was removed while the detailed safety/acknowledgement text remains in the fix flow and README. Both HA suites and local hassfest pass afterward.

### Documentation, metadata, CI, and release audit

- `README.md` now documents implemented spec.4 native deletion/tombstones, immediate no-ON authority, safe active-session termination, same-actuator re-add history, independent A -> B hazards, native add/reconfigure/no-op behavior, all four device-targeted actions, manual clamps/refusals, Repairs/diagnostics, exact thresholds/report/freshness behavior, Store/restart/shutdown safety, local-only/privacy, hardware failsafes, Home Assistant 2025.9.0 or later, and the seven still-unstarted Slice 13 items. The spec.3 delete-after-reload limitation is gone.
- `DEVELOPMENT.md` now gives exact clean-environment, full-suite, coverage, traceability, HA1/HA2, focused-regression, metadata, Ruff, hassfest, HACS, and six-job CI instructions. `CLAUDE.md` no longer claims a greenfield/2025.7 project.
- Manifest remains version `0.1.0`, domain/name correct, helper/calculated/local-only, config flow/single entry true, requirements empty, and key ordering accepted by current hassfest. `hacs.json` retains minimum `2025.9.0` and drops unsupported `render_readme`. Services, strings, `translations/en.json`, and icons synchronize all four actions; fix-flow errors remain present. Specification version remains `0.1.0-spec.4`; `SPECIFICATION.md` has no diff.
- CI now has required independent `lint`, explicit pure, mandatory HA 2025.9.0, exact HA 2026.8.3/Python 3.14, hassfest, and HACS jobs. Current action forms are `home-assistant/actions/hassfest@master` and `hacs/action@main`; neither distribution job has an existence skip or ignored validation.
- Official local hassfest: `docker run --rm --mount "type=bind,source=$repoPath,target=/github/workspace" ghcr.io/home-assistant/hassfest` -> **PASS: Integrations 1; Invalid integrations 0**. Official local HACS Action container invocation reached its mandatory remote preflight and stopped with **`No GitHub token found`**; this is not recorded as a HACS validation pass.
- Tracked release-content audit: 59 tracked files, 24 integration files, no tracked venv/cache/JUnit/coverage/storage/secret/temp/migration artifact, license and README present, and only the integration directory is the HACS payload. The diagnostics source filename is expected, not a diagnostics dump. Runtime source has no cloud/outbound HTTP/telemetry/API-key dependency, Recorder import/safety reconstruction, or direct `.storage` filesystem manipulation; pure AST/import tests pass.

### Repository hosting and external gate

- `git remote -v`: only `origin https://git.lukestanbury.com/luke/moisture-loop.git` for fetch/push. No remote was altered. There is no GitHub remote. Public GitHub checks for `lukestanbury/moisture_loop` and `lukestanbury/moisture-loop` returned 404.
- Audited pre-Stage-8 `HEAD` was `ee6df21f6ac07fd13e4d29a9329c5ee755b59338`; the then-observed `origin/main` was `7cad715008888a542da1ee583e1be7a0f0bd35a4`. A later user message explicitly authorized commit/push to the existing remote, and Stage 8 content commit `b2a9a8474e5d4ba219c87b4c1c5b64746901bb25` was pushed successfully. There is still no GitHub commit or workflow result for this state.
- Current official HACS guidance requires a public GitHub repository for a custom repository. Manifest documentation/issue URLs target the intended GitHub repository but currently return 404. Repository creation/mirroring/push, release publication, HACS submission, and brands submission were explicitly unauthorized and were not performed.

### Slice and authorization reconciliation

- Slice 0 -> `[x]`: all quality-foundation and supported-current obligations assigned to it are now complete and reproducible.
- Slice 12 -> `[~]`: every local/current-HA/documentation gate passes, but exact-final-commit GitHub-hosted hassfest and HACS Action evidence is mandatory and unavailable; the declared GitHub documentation/issue targets also cannot resolve until hosting exists.
- Slice 13 -> `[ ]`: all seven §46 real UI/UX, physical valve, real registry rename, physical shutdown timing, ten-zone scale, deployment cadence, and HACS/central-brand presentation validations remain unstarted.
- Files changed in Stage 8: `.github/workflows/ci.yml`, `.gitignore`, `CLAUDE.md`, `DEVELOPMENT.md`, `README.md`, `custom_components/moisture_loop/strings.json`, `custom_components/moisture_loop/translations/en.json`, `hacs.json`, `requirements_test_ha_current.txt`, `tests/test_config_flow.py`, `tests/test_entities.py`, `tests/test_ha_contract.py`, and `PROGRESS.md`.
- Current authorized slice: `None`. `SPECIFICATION.md` remained unchanged. Stage 8 is not complete. The subsequently authorized commit/push to existing self-hosted `origin` occurred; no GitHub repository/mirror, release/publication/submission, or Slice 13 action was taken.

### Post-closeout git handoff

- After the Stage 8 response, the user explicitly authorized `commit & push`.
- Commit `b2a9a8474e5d4ba219c87b4c1c5b64746901bb25` (`Complete spec.4 remediation stage 8 local gates`) was created and pushed from `main` to the existing self-hosted `origin/main`; remote verification returned the same hash.
- This tracking correction is a follow-up commit on the same existing remote. It does not create GitHub-hosted hassfest/HACS evidence, alter remotes, publish a release, submit to HACS/brands, or begin Slice 13.

## Publication Closeout Candidate — 2026-08-23 (Spec.4 Remediation Stage 8)

### Authorization and privacy decision

- The user explicitly authorized the remaining Stage 8 history-sanitization, repository-hygiene, first-publication, self-hosted-history-replacement, and hosted-CI gates. No release, release tag, HACS default-store submission, Brands submission, specification change, or Slice 13 work is authorized.
- The verified GitHub identity is account `embersas`, account ID `30363137`; the resulting ID-based noreply identity is `embersas <30363137+embersas@users.noreply.github.com>`. Repository-local Git configuration uses this identity for all future authors and committers.
- A private pre-rewrite recovery bundle was created outside the repository at `%LOCALAPPDATA%\MoistureLoopBackups\moisture-loop-before-publication-8c92341e5c7a.bundle` and successfully verified. It is a private recovery artifact and must never be published.
- `git-filter-repo` (`a40bce548d2c`) rewrote every one of the 13 reachable commits. Mechanical comparison with the recovery bundle proves commit count, tree/content, full messages, author dates, committer dates, and parent topology were preserved; only author/committer names and email metadata changed as intended. The sole reachable author and committer identity is now the verified `embersas` noreply identity.
- Refs were inventoried before and after rewriting. The active repository has only local `main`; it has no tags, stashes, notes, abandoned branches, filter-repo original refs, or backup refs. Original history is absent from active refs and will not be pushed. Self-hosted `origin` remains `https://git.lukestanbury.com/luke/moisture-loop.git`; its `main` will be replaced only with the verified sanitized final history by an explicit lease-guarded force update.
- Full email-shaped-string audits found historical private addresses only in commit author/committer metadata. Commit messages, tags/notes, current tracked content, and every historical tracked-file version contain no email address. After rewriting, the only email-shaped string in reachable commit metadata is the intentional verified GitHub noreply address.
- Pre-rewrite Gitleaks full-history scanning and targeted credential/private-key/token/storage/database scans detected zero secrets. The rewritten exact final candidate must receive the same zero-finding full-history and targeted scans after its normal closeout commit and before either publication push.

### Hygiene, metadata, and local evidence

- `.gitignore` now precisely covers Python/build artifacts, all project virtual-environment variants, pytest caches/temp directories, coverage outputs, Stage evidence and root JUnit results, tool caches, local environment files while preserving `.env.example`, IDE/OS files, and generated logs/temp files. It does not ignore tests, scripts, CI, documentation, integration code, or metadata.
- `git ls-files`, status, ignored-status, and `git check-ignore` audits confirm all 59 intended tracked files remain public candidates, including the complete `tests/` tree and traceability/migration evidence. Actual local environments, pytest/cache directories, coverage files, Stage evidence, and JUnit artifacts are ignored; no unwanted generated artifact is tracked.
- Public metadata targets `https://github.com/embersas/moisture-loop` and its `/issues` tracker. The manifest domain remains `moisture_loop`; HACS minimum Home Assistant remains `2025.9.0`; README installation wording describes manual or HACS custom-repository installation and does not claim default-store inclusion.
- Final pre-publication execution remains green: pure Python 3.14.5 = 436 passed, 0 skipped; mandatory HA 2025.9.0/Python 3.13.13 = 838 passed, 1 documented pure-boundary skip, 92.74% overall branch and 100% `state_machine.py`; supported-current HA 2026.8.3/Python 3.14.5/harness 0.13.357 = 838 passed, the same one skip, 92.63% overall branch and 100% `state_machine.py`. Both direct HA API contract checks pass.
- The first hosted bootstrap exposed two repository/CI compatibility issues without changing integration behaviour: console-script `pytest` did not place the checkout root on `sys.path`, and newly released `pycares` 5.x removed result-type attributes imported by HA 2025.9.0. CI now invokes `python -m pytest`, and the mandatory environment pins compatible `pycares==4.11.0` (which still satisfies `aiodns>=4.9`). A clean Linux Python 3.13.15/HA 2025.9.0 environment then passed the 12 direct contracts and the full 838/1 suite at 92.74% overall branch/100% `state_machine.py`; pure `python -m pytest` remained 436/436. All hosted gates remain pending the new exact final SHA.
- The next mandatory hosted run collected and executed the full suite but exposed nondeterministic delivery in the event-ordering test fixture: its undecorated synchronous listener was eligible for executor dispatch, so two sequentially fired events could be observed out of order. Marking the capture listener with Home Assistant's public `@callback` contract keeps the test on the event loop and verifies the integration's actual fire order deterministically; production behaviour and the ordering assertion are unchanged. All six hosted gates remain pending the new exact final SHA.
- Executed traceability remains 134/134 normative IDs, 37/37 invariants, and 59/59 transitions. Ruff lint/format, diff, JSON/YAML, metadata parity, package-content, local-only/Recorder, and official local hassfest gates must remain green at the final candidate.

### Publication boundary

- Public target: `embersas/moisture-loop`, with self-hosted `origin` preserved and GitHub added only as second remote `github`. Publish only sanitized `main`; never mirror arbitrary refs or the private recovery bundle.
- `PROGRESS.md` deliberately records all hosted gates as pending the exact final candidate SHA. The final response will carry the exact SHA, GitHub workflow/run evidence, and public URL checks so no post-validation tracking commit invalidates the evidence.
- Slice 0 remains `[x]`. Slice 12 becomes `[x]` only if the exact final SHA passes all six hosted jobs and the public/security checks; until then it remains `[~]`. Slice 13 remains `[ ]` and unstarted.
- Current authorized slice: `None`. `SPECIFICATION.md` remains unchanged at `0.1.0-spec.4`.

## Session Log — 2026-08-23 (Slice 13 prototype validation)

### Authorization and completed automated baseline

- The user explicitly authorized Slice 13 only, using GPT-5.6 Sol with extra-high reasoning. The required specification, progress, user/developer documentation, public repository, and local git/remotes were reviewed completely before any live action.
- The public closeout preceding this run is SHA `43f24b12fc162412b534851b9c1b3762ca57cd98`. Local `HEAD`, `origin/main`, and `github/main` matched it at the baseline. GitHub workflow run `32630108774` passed lint/format, pure, HA 2025.9.0, HA 2026.8.3, hassfest, and HACS, closing Slice 12 `[x]`.

### Live environment and evidence

- Live deployment: Home Assistant Core `2026.7.2`, Home Assistant Container on Docker host networking, HACS `2.0.5`, legitimate authenticated operator UI plus SSH/Docker host control. A recent full HA backup was confirmed. No credential or private LAN address is recorded.
- Moisture Loop `0.1.0` was not installed and had no config entry. The operator opened HACS Custom repositories, but the instructed repository-add result was not returned before closeout; live HACS/component inventory remained absent. Item 1 is `BLOCKED`, `NOT VALIDATED`; item 7 is `PARTIAL`, `LIVE HOME ASSISTANT`. HACS navigation is not treated as Moisture Loop lifecycle evidence.
- Physical inventory identified deployed valve/switch irrigation hardware but every candidate was unavailable. No hardware was commanded, the physical-water checkpoint was not reached, and the physical valve matrix and shutdown timing are `BLOCKED`, `NOT VALIDATED`. The real Docker shutdown path exists but is not evidence without the actual active-flow test.
- With no integration/zone setup, the real Entity Registry rename and ten-zone scale exercise are `BLOCKED`, `NOT VALIDATED`; no temporary HA helper or zone was created.
- Deployed-sensor cadence is `PARTIAL`, `LIVE PHYSICAL`: seven days of Recorder changed-state/availability history plus 82.525 minutes of direct read-only MQTT observation. The direct sample captured 20 messages/eight bursts, median burst gap 994.638 s, maximum 1116.047 s, and six unchanged-value transitions. Because it did not continuously exceed the two-hour default, no default change or complete validation is claimed.
- No implementation defect or specification contradiction was found. Production/test/config code did not change, so existing automated suites were not rerun. Only `PROTOTYPE_VALIDATION.md` and this progress record changed locally.

### Cleanup and closeout

- Watering was never started; physical actuators remained uncommanded and unavailable.
- No temporary live helper/zone, Registry rename, automation disable, shutdown, or restart existed to revert. The read-only cadence observer was stopped and its exact temporary log removed. HA remained in normal operation with no test-only Moisture Loop blocker/fault.
- No HACS default-store submission, Brands submission, GitHub Release, version bump, release tag, or specification edit occurred.
- Slice 13 remains `[~]` because the exact §46 completion rule requires all seven live/physical items. Current authorized slice returned to `None`.

## Session Log — 2026-08-24 (SoilSync canonical pre-release rename)

### Authorization, baseline, and collision checks

- The user selected the final product identity **SoilSync**, Home Assistant domain `soilsync`, package `custom_components/soilsync/`, and public repository `embersas/soilsync`. This is a pre-release canonical rename only; Slice 13 is paused and remains `[~] Partial`.
- The requested pre-rename SHA `43f24b12fc162412b534851b9c1b3762ca57cd98` was verified as the immediate parent of the actual starting `main` SHA `bbfeee2e18bfa478c79bc41faa7555f7933c9ec6`. The latter is the normal forward commit that preserves the first partial Slice 13 observations in `PROTOTYPE_VALIDATION.md` and `PROGRESS.md`; local `main`, self-hosted `origin/main`, and `github/main` all matched it before this rename.
- `soilsync` matches Home Assistant's integration-domain syntax. No local `custom_components/soilsync/` existed before the rename, GitHub had no `embersas/soilsync` repository, and current Home Assistant Core had neither a `homeassistant/components/soilsync` path nor an exact `soilsync` domain result. No technical collision was found.
- The pre-edit tracked-file inventory found 103 exact `Moisture Loop`, 293 exact `moisture_loop`, and 22 exact `moisture-loop` occurrences across 47 files; uppercase and all-lowercase display-name variants were absent. The inventory covered source, tests, metadata, CI, traceability tooling, current documentation, specification, progress, and prototype evidence before transformation.

### Canonical source and documentation rename

- Git moved the sole integration directory from `custom_components/moisture_loop/` to `custom_components/soilsync/`; no legacy alias package or dual-domain registration was retained. All active imports, patch targets, constants, config-flow registration, task/logger namespaces, domain-derived device identifiers, Repair ownership, diagnostics module references, services, and events now use `soilsync`.
- The integration-owned Store key changed mechanically from `moisture_loop.<entry_id>` to `soilsync.<entry_id>` through the existing `f"{DOMAIN}.{entry_id}"` construction. Store schema remains 2 and its schema, serialization, durable UUID, SafetyRecord, ZoneHistory, blocker, accounting, tombstone, restart, shutdown, delete, and reconfigure semantics are unchanged. No deployed-domain migration or compatibility shim was added because the integration is unreleased and was not installed on the prototype.
- Manifest/HACS metadata, strings, English translations, icons metadata, README, development instructions, source audits, coverage targets, and all four action examples now use SoilSync/`soilsync` and `https://github.com/embersas/soilsync`. Version remains `0.1.0`; the Home Assistant floor remains `2025.9.0`; the supported-current evidence pin remains `2026.8.3`.
- `SPECIFICATION.md` remains `0.1.0-spec.4`. Its edits are strictly the authorized canonical product/domain/path/service/event/repository nomenclature replacement; SR1-SR13, PI1-PI27, MF1-MF5, AC1-AC4, ER1-ER12, LC1-LC13, ND1-ND17, TB1-TB12, AR1-AR17, RC1-RC12, HA1-HA2, I1-I37, T1-T59, thresholds, defaults, states, persistence, lifecycle, and safety semantics received zero behavioural amendment.
- A mechanical comparison of the complete active source/test/script/CI tree before and after rename, with only the old/new product and namespace tokens normalized, found zero mismatches. The PNG brand asset has the identical Git blob. This proves the five-state model, AUTO hysteresis, pulse/soak/recheck, freshness watchdog, manual semantics, blockers/serialization/final ON fence, durable identities/history, deletion/tombstones/reconfigure, restart/shutdown safety, accounting, Repairs, and diagnostics logic were not changed under the rename.
- The post-rename active-scope audit has zero occurrences of the development names. Current tracked historical occurrences are intentionally confined to this file and `PROTOTYPE_VALIDATION.md`: dated commands, old paths/URLs, old Store/domain evidence, publication history, and the true observation that the candidate then called Moisture Loop was not installed. They are covered by the explicit development-name history notice and are not current instructions.

### Local rename validation

- Pure/no-HA Python 3.14.5: **436 passed, 0 failed, 0 skipped, 0 errors**; Home Assistant absent; `state_machine.py` 100.00% branch.
- Mandatory HA 2025.9.0/Python 3.13.13: direct HA contract check **12/12**; full suite **838 passed, 0 failed, 1 documented pure-boundary skip, 0 errors**; 92.74% overall branch and `state_machine.py` 100.00% branch.
- Supported-current HA 2026.8.3/Python 3.14.5: direct HA contract check **12/12**; Linux full suite **838 passed, 0 failed, 1 documented pure-boundary skip, 0 errors**; 92.63% overall branch and `state_machine.py` 100.00% branch. The established Stage 8 exact pin was deliberately preserved.
- Executed traceability remains **134/134 normative IDs, 37/37 invariants, and 59/59 transitions** with no new or missing ID and only the established HA-environment pure-boundary skip.
- Ruff check, Ruff format check, `git diff --check`, JSON/YAML validation, strings/translation and service/icon parity, manifest domain/path/version checks, and the official local hassfest container all pass. Hassfest reports one integration and zero invalid integrations. HACS-compatible local metadata/preflight is canonical; the mandatory official HACS result remains the GitHub-hosted exact-SHA job.
- The public repository rename, remotes, forward push, exact-final-SHA six-job GitHub Actions run, public rendering checks, and final authorization closeout are intentionally recorded after those operations. No tag, GitHub Release, HACS default submission, Brands submission, or Slice 13 prototype action is part of this rename.

### Repository rename and hosted closeout

- After local gates were green, normal forward commit `46783d2900fd42a13666eb13d8fe78c623456164` (`Rename Moisture Loop to SoilSync`) was created with author and committer `embersas <30363137+embersas@users.noreply.github.com>` before either hosted repository was renamed. No public history was rewritten and no tag was created.
- GitHub renamed `embersas/moisture-loop` in place to the public `embersas/soilsync` repository. It retains default branch `main` and enabled Issues. Its description is `Closed-loop soil moisture and drip irrigation controller for Home Assistant`; its topics are `home-assistant`, `hacs`, `irrigation`, `drip-irrigation`, `soil-moisture`, `watering`, `garden-irrigation`, `smart-irrigation`, and `home-automation`.
- Legitimate authenticated administrator access was available on the private self-hosted service, and `luke/moisture-loop` was safely renamed in place to private `luke/soilsync`. No repository was deleted, recreated, or split. Local remotes are now `origin https://git.lukestanbury.com/luke/soilsync.git` and `github https://github.com/embersas/soilsync.git`.
- Commit `46783d2900fd42a13666eb13d8fe78c623456164` was pushed as a fast-forward to both `origin/main` and `github/main`; both remote refs and local `HEAD` matched exactly. GitHub Actions run `32705144394` completed successfully for that exact SHA: lint/format, pure, HA 2025.9.0, HA 2026.8.3 supported-current, hassfest, and HACS all passed.
- Public checks confirm the SoilSync README, manifest (`name: SoilSync`, `domain: soilsync`, version `0.1.0`), `custom_components/soilsync/` directory, and Issues URL resolve from the renamed repository; the active old component directory is absent. GitHub's redirect from the old repository URL is a hosting redirect only, not an active product identifier.
- This documentation-only tracking closeout commit records the completed external operations and returns current authorization to `None`. Its exact SHA and second six-job hosted result are carried in the final handoff so no further tracking commit invalidates that evidence.
- No GitHub Release, release tag, HACS default-store submission, Brands submission, integration-version bump, Store-schema bump, compatibility shim, or prototype action occurred. Slice 13 remains `[~] Partial` with its prior observations intact and no new validation claim.

## Session Log — 2026-08-24 (Slice 13 Phase A continuation)

### Authorization and phase split

- The user explicitly authorized only SoilSync Slice 13 Phase A non-water
  validation, using GPT-5.6 Sol with extra-high reasoning. Phase B physical
  water, releases, tags, version changes, HACS default-store/Brands
  submissions, and specification changes were not authorized.
- Before live mutation, `SPECIFICATION.md` including §46, this complete
  progress ledger, `PROTOTYPE_VALIDATION.md`, `README.md`, `DEVELOPMENT.md`,
  the relevant config-flow/subentry/entity/action/Registry/report/slot/
  reconciliation/diagnostic/Repair source, Git state/remotes/HEAD, and safe
  live reachability were reviewed.
- Unfinished Slice 13 work is now formally divided into Phase A A1-A6 and
  Phase B B1-B2. The six-potential-physical-zone/one-installed-sensor reality
  and one-sensor-per-real-zone architecture are explicit. Additional sensor
  purchases are not a Phase A prerequisite.

### Live Phase A result

- Current repository state before documentation edits was clean at
  `f4229cfe040d5542ae5acbfc3510ffe7cb922f4f`; both remotes and canonical
  identity were verified. No production or test code changed.
- The local Home Assistant Container test instance remained reachable: the
  frontend returned HTTP 200, the unauthenticated API correctly returned HTTP
  401, and HA plus the previously documented host-control network paths were
  reachable. No credential was requested, displayed, stored, or committed.
- Direct browser control was attempted through the supported browser runtime
  and no browser was available. Following the operator-interaction rule, one
  precise real-HACS step was requested: add the SoilSync public URL as an
  Integration custom repository and report exactly what appeared. No result
  arrived before closeout, so repository acceptance/install/restart and all
  dependent A2-A4 work remain blocked rather than inferred.
- Anonymous read-only MQTT connection reached the live broker but was refused
  as `Not authorized`, as expected. No credentials were sought and no new
  message/report evidence was captured. The truthful direct physical sample
  therefore remains the preserved 4951.476 s / 82.525 min, 20-message,
  eight-burst result from 2026-08-23; no elapsed time was fabricated.
- A1 is BLOCKED; A2 is BLOCKED; A3 is BLOCKED; A4 is BLOCKED; A5 is PARTIAL;
  A6 is PARTIAL. Detailed public-safe procedures, observations, evidence
  classes, and cleanup are in `PROTOTYPE_VALIDATION.md`.
- Source review noted no live defect because no installed runtime was
  exercised. Registry rename remains a real prototype obligation; source
  inspection is not substituted for its outcome. No specification
  contradiction was observed.

### Safety, cleanup, and closeout

- Zero physical irrigation ON/open commands occurred. Physical valves,
  irrigation switches, and unrelated irrigation automations/scripts remained
  untouched.
- No synthetic helper, test actuator, SoilSync config entry, temporary zone,
  scale zone, Registry rename, test fault, Repair, restart, or shutdown was
  created, so no runtime cleanup was required.
- Phase A closes `[~] Partial`. Phase B remains `[ ] Not started`, specifically
  B1 physical valve matrix and B2 active-flow shutdown OFF timing.
- Only `PROGRESS.md` and `PROTOTYPE_VALIDATION.md` changed. Established test
  suites were not gratuitously rerun; documentation diff checks are the
  applicable closeout gate. `SPECIFICATION.md` remains unchanged.
- Current authorization returned to `None`.
