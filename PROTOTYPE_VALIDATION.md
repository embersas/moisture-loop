# SoilSync prototype-validation evidence

This is the public evidence ledger for the real-world prototype validations
required by `SPECIFICATION.md` §46. Automated tests, mocks, and source
inspection are supporting context only and are never counted as live or
physical evidence.

The live host, credentials, complete Registry UUIDs, household entity names,
and MQTT details are intentionally omitted. Exact private identifiers are kept
only for the duration of a test that needs them.

## Evidence classes

- `LIVE PHYSICAL`: observed from deployed physical equipment.
- `LIVE HOME ASSISTANT`: observed in the real Home Assistant deployment.
- `LIVE HOME ASSISTANT WITH SYNTHETIC TEST ENTITIES`: observed in the real
  deployment using isolated temporary entities that cannot control physical
  irrigation.
- `NOT VALIDATED`: the required live or physical observation does not exist.

# Slice 13

## Environment baseline

| Field | Evidence |
|---|---|
| Initial validation date | 2026-08-23 (Australia/Brisbane) |
| Phase A continuation date | 2026-08-24 (Australia/Brisbane) |
| Home Assistant | Core 2026.7.2 observed in the initial run; Home Assistant Container on Docker with host networking |
| HACS | 2.0.5 observed in the initial run; real Custom repositories UI confirmed |
| SoilSync candidate | Version 0.1.0; current source SHA `f4229cfe040d5542ae5acbfc3510ffe7cb922f4f` |
| Installation baseline | SoilSync was not installed and had no config entry in the initial run |
| Phase A reachability | Local Home Assistant Container test instance frontend returned HTTP 200; unauthenticated API returned HTTP 401; HA and previously documented host-control ports were reachable |
| Interactive access | Existing browser control was unavailable; one precise HACS operator step was requested, but no result arrived before closeout |
| Credentials | No credential was requested, exposed, stored, or committed |
| Public source | `https://github.com/embersas/soilsync`; current local HEAD and expected final SHA match |

The Phase A continuation issued no physical irrigation command. A direct
read-only MQTT attempt without credentials was refused as `Not authorized`,
as expected; it supplied no sensor evidence and is not added to the cadence
duration.

## Phase A - Non-water live validation

Phase A forbids every command that could energise physical irrigation. All
actuator testing must use source-verified synthetic entities. A live synthetic
test is real Home Assistant runtime evidence, but it is not physical
sensor/valve evidence.

### A1 HACS installation

| Field | Record |
|---|---|
| Date/time | Initial UI observation 2026-08-23; continuation checkpoint 2026-08-24 |
| HA / HACS / SoilSync | HA 2026.7.2 previously observed; HACS 2.0.5 previously observed; SoilSync 0.1.0 at `f4229cfe040d5542ae5acbfc3510ffe7cb922f4f` |
| Entities used | None |
| Procedure | Initial run: operator opened real HACS Custom repositories. Continuation: direct browser control was attempted and found unavailable; operator was instructed to add `https://github.com/embersas/soilsync` as category Integration and report the exact result before installation. |
| Actual observations | The live frontend is reachable. No repository-add result was returned. Repository acceptance, SoilSync card, description, links, version, README, artwork, download, installed files, restart requirement, restart, and startup logs were not observed. |
| Evidence class | `LIVE HOME ASSISTANT` for the prior HACS UI/reachability observations; installation itself `NOT VALIDATED` |
| Status | `BLOCKED` |
| Cleanup | No repository/install/restart change was observed or needs reversal. |

A successful custom-repository installation would prove public-repository HACS
compatibility and live presentation only. It would not prove HACS default-store
acceptance, pre-add discoverability, or Home Assistant Brands acceptance.

### A2 UI/UX lifecycle

| Field | Record |
|---|---|
| Date/time | 2026-08-24 |
| HA / SoilSync | HA 2026.7.2 previously observed; SoilSync 0.1.0 source SHA above; not installed |
| Entities used | None; no synthetic actuator was created |
| Procedure | Reviewed the production config-subentry, entity, action, diagnostics, and Repair paths before live work. Live setup was gated on A1 so no actuator-bearing zone could be created. |
| Actual observations | Controller creation, first zone, selectors, validations, device/entity attribution, thresholds, pulse/soak, actions, synthetic manual watering, Stop, Evaluate, Clear fault, reconfigure, diagnostics, reload, native deletion/re-add, Repairs, and restart survival were not exercised. |
| Evidence class | `NOT VALIDATED` |
| Status | `BLOCKED` by incomplete A1/authenticated UI checkpoint |
| Cleanup | No helper, zone, fault, Repair, reload, or restart existed to clean up. |

No physical actuator entity was selected or commanded. Display names alone
would not be accepted as proof that a future synthetic actuator is safe; its
implementation/source must be mechanically verified before manual watering.

### A3 Entity Registry rename

| Field | Record |
|---|---|
| Date/time | 2026-08-24 |
| HA / SoilSync | HA 2026.7.2 previously observed; SoilSync 0.1.0 source SHA above; not installed |
| Entities used | None |
| Procedure | Reviewed the Registry-first identity and `async_track_entity_registry_updated_event` paths. Planned test requires a temporary synthetic entity, complete before-state capture, supported Registry rename, reload/reconciliation check, and reverse rename. |
| Actual observations | No live Registry rename occurred. Therefore no before/after Registry UUID, subentry, `safety_record_id`, `safety_lineage_id`, `zone_history_id`, blocker, or history continuity result exists. |
| Evidence class | `NOT VALIDATED` |
| Status | `BLOCKED` by incomplete A1/A2 setup |
| Cleanup | No rename existed to restore. |

Source review alone is not treated as a pass. The live trial remains necessary
because the moisture adapter currently instruments rename events while durable
runtime reconciliation is Registry-first.

### A4 Ten-zone live synthetic test

| Field | Record |
|---|---|
| Date/time | 2026-08-24 |
| HA / SoilSync | HA 2026.7.2 previously observed; SoilSync 0.1.0 source SHA above; not installed |
| Exact zone count | 0 created; target remains approximately 10 |
| Entity type | Planned: ten unique synthetic percentage sensors and ten unique independently observable synthetic switch/valve entities that cannot control physical equipment |
| Synthetic vs physical | Planned evidence class is synthetic live HA only; no physical hardware is required or permitted |
| Procedure | Confirmed from §46 that this is scheduler/load validation and may use live synthetic entities. Reviewed SlotManager FIFO, blocker, owner, and reconciliation-admission behavior before live work. |
| Actual observations | No live dry-zone queue, FIFO order, serialization, pulse/soak/recheck, fairness, starvation, limits, cancellation, queued-zone reconfigure/delete, or diagnostic visibility was exercised. |
| FIFO/order | Not observed |
| Serialization | Not observed |
| Fairness/starvation | Not observed |
| Evidence class | `NOT VALIDATED` |
| Status | `BLOCKED` by incomplete A1/A2 setup |
| Cleanup | No temporary scale entities or zones were created. |

Purchasing ten physical moisture sensors is not a prerequisite for A4. The
deployment architecture nevertheless remains one physical sensor per
independently controlled real physical zone.

### A5 Sensor cadence/freshness

| Field | Record |
|---|---|
| Date/time | Historical and direct observation on 2026-08-23; continuation access check 2026-08-24 |
| HA / SoilSync | HA 2026.7.2; SoilSync default `sensor_max_age` two hours; candidate not installed |
| Physical sensor type | One deployed wireless soil-moisture percentage sensor reporting through an existing MQTT-backed path |
| Entities used | One real moisture sensor read-only; no SoilSync zone or synthetic actuator was created |
| Procedure | Initial run: seven-day Recorder query plus direct read-only MQTT observation. Continuation: tested read-only broker access without credentials; the broker refused it, so no new messages were captured. No credentials were requested or exposed. |
| Actual observations | Recorder: 198 rows, 196 numeric changed rows, two availability rows, 193 within-availability intervals. Direct MQTT: 4951.476 s (82.525 min), 20 messages in eight bursts, six unchanged-soil transitions, and two approximately 30-second gaps. |
| Typical interval | Direct median burst gap 994.638 s (about 16.58 min); Recorder median within-availability changed-state interval 870.742 s |
| Maximum observed normal interval | Direct maximum burst gap 1116.047 s (about 18.60 min). Recorder changed-state intervals are not raw-report cadence and included a maximum 79464.4 s. |
| Unchanged reports | Directly observed in six consecutive unchanged-soil transitions |
| `state_changed` behavior | Recorder supplied changed-state/availability history only; it did not prove unchanged report delivery |
| `state_reported` behavior | Not observed in the live HA runtime because authenticated event access and an installed SoilSync zone were unavailable |
| SoilSync freshness | Not observed live; no real-sensor/synthetic-actuator SoilSync zone existed, so `fresh_until`, watchdog extension, and false-stale behavior remain unvalidated |
| Two-hour conclusion | No default change is justified. The direct continuous window did not exceed two hours, so the two-hour default is not yet validated. |
| Evidence classes | Cadence/source side: `LIVE PHYSICAL`; live SoilSync handling: `NOT VALIDATED` |
| Status | `PARTIAL` |
| Cleanup | Initial observer stopped and temporary exact log removed; continuation created no observer artifact. The physical sensor was unchanged. |

No time from the refused connection attempt is added to the direct observation
period. The truthful total direct physical observation remains 82.525 minutes.

### A6 HACS/presentation

| Field | Record |
|---|---|
| Date/time | Initial observation 2026-08-23; continuation 2026-08-24 |
| HA / HACS / SoilSync | HA 2026.7.2 and HACS 2.0.5 previously observed; SoilSync 0.1.0 source SHA above |
| Entities used | None |
| Procedure | Prior operator inspection confirmed real HACS and Custom repositories UI. Continuation verified endpoint reachability and requested the repository-add step; current source/README/manifest terminology was also reviewed as supporting context only. |
| Actual observations | HACS card, README rendering, icon, name, description, version, repository links, integration search, Devices & services, device/entity/action presentation, diagnostics, Repairs, and live stale-name audit were not observed after installation because installation did not occur. |
| Evidence class | `LIVE HOME ASSISTANT` for prior HACS capability; SoilSync presentation `NOT VALIDATED` |
| Status | `PARTIAL` |
| Cleanup | No presentation/install state was changed. |

No HACS default-store submission, Home Assistant Brands submission, GitHub
Release, version bump, or release tag occurred.

## Phase B - Physical-water validation

Phase B requires known-safe physical irrigation hardware, actual flow, an
explicit operator water checkpoint, manual stop/fallback, and separate
authorization. It was not authorized or started in this run.

### B1 Physical valve matrix

| Field | Record |
|---|---|
| Prior context | Initial read-only inventory found one deployed valve and separate irrigation switch entities; all identified candidates were unavailable. Existing unrelated irrigation automations/scripts were left unchanged. |
| Required future evidence | Physical `opening`/`open`/`closing`/`closed`, availability, position, acknowledgement, ownership, external interference, blocker behavior, and exact OFF proof on known-safe hardware |
| Evidence class | `NOT VALIDATED` |
| Status | `[ ] Not started` |
| Cleanup | No physical command or configuration change occurred. |

### B2 Active-flow shutdown OFF timing

| Field | Record |
|---|---|
| Prior context | Legitimate Docker host-control path was previously confirmed, but no safe active physical flow was established and no T0-T4 timing exists. |
| Required future evidence | SoilSync-owned physical flow, actual HA/container shutdown, measured shutdown-to-proven-OFF timing, bounded fallback, restart, and no-resume behavior |
| Evidence class | `NOT VALIDATED` |
| Status | `[ ] Not started` |
| Cleanup | No shutdown, restart, or physical water command occurred. |

## Current cleanup inventory

- Zero physical irrigation ON/open commands were issued.
- Physical irrigation hardware and unrelated automations/scripts were
  untouched.
- No temporary synthetic helper, actuator, scale zone, SoilSync config entry,
  Registry rename, test fault, or Repair was created.
- The prior bounded observer remains stopped and its exact temporary log
  remains removed.
- Home Assistant's frontend remained reachable; no SoilSync-related live
  change was made that could affect normal operation.

## Current slice verdict

`[~] PARTIAL` — the formal Phase A/Phase B split is recorded and Phase A was
begun with safe live reachability, browser/operator, source-safety, and MQTT
access checks. A1-A4 remain blocked by the unavailable authenticated UI result,
A5 remains partial with the preserved 82.525-minute physical sample, and A6
remains partial. Phase B is `[ ] Not started`.
