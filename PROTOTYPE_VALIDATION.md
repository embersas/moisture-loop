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
| Phase A live-execution date | 2026-08-24; all times below are UTC as reported by the live instance |
| Phase A remediation date | 2026-08-25 (Australia/Brisbane); live-instance UTC timestamps below run 2026-08-24T22:57Z to 2026-08-24T23:35Z |
| Home Assistant | Core 2026.7.2 observed live; Home Assistant Container on Docker with host networking |
| HACS | 2.0.5 confirmed live from the HACS `hacs/info` websocket command |
| SoilSync candidate | Version 0.1.0; source SHA `dcf9036165b02c443e5cc8a5eddf0741676ffe65` |
| Installed artefact | HACS reported `installed_version` `dcf9036` at `/config/custom_components/soilsync`, matching the baseline SHA prefix |
| Interactive access | Local Chrome 151 driven over the DevTools protocol by `playwright-core` in a dedicated browser profile |
| Credentials | The operator performed one interactive Home Assistant sign-in in that browser window. No long-lived access token was requested. No cookie, token, or credential was read, printed, stored, or committed |
| Public source | `https://github.com/embersas/soilsync`; remote `main` matched the local HEAD |

Screenshots and raw diagnostics captured during this run are kept locally under
the git-ignored `evidence/slice13-phaseA/` directory and are referenced by name
below. They are deliberately not committed: they contain household entity
names.

The Phase A run issued no physical irrigation command. Every actuator commanded
by SoilSync during Phase A was a temporary Home Assistant `template` switch
whose only configured `turn_on`/`turn_off` actions target a dedicated
`input_boolean` helper.

## Synthetic actuator safety verification

Display names were not accepted as proof. Non-physical scope was established
two independent ways before any SoilSync ON command:

1. **Configuration evidence.** Each `switch.soilsync_test_valve_NN` was read
   back from the live config store through its own options flow. Every one is
   `platform: template`, has no device, and carries exactly:
   `value_template` reading `input_boolean.soilsync_test_valve_backing_NN`,
   `turn_on` = `input_boolean.turn_on` targeting that same helper, and
   `turn_off` = `input_boolean.turn_off` targeting that same helper.
2. **Empirical evidence.** With SoilSync not yet configured, a full snapshot of
   all 1700 live entity states was taken, `switch.turn_on` was called on
   `switch.soilsync_test_valve_01`, and the snapshot was retaken. The only
   causally related changes were the template switch itself and its backing
   `input_boolean`. The subsequent `switch.turn_off` diff contained exactly
   those two entities and nothing else.

Ten synthetic percentage moisture sensors were published through the Home
Assistant States API as `sensor.soilsync_test_moisture_NN`
(`device_class: humidity`, unit `%`). They exist only in the state machine, so
they are not Entity Registry entries and do not survive a restart; that
limitation is stated wherever it matters below.

## Phase A - Non-water live validation

Phase A forbids every command that could energise physical irrigation. All
actuator testing used the source-verified synthetic entities above. A live
synthetic test is real Home Assistant runtime evidence, but it is not physical
sensor/valve evidence.

### A1 HACS installation

| Field | Record |
|---|---|
| Date/time | 2026-08-24, approximately 09:10-09:18 UTC |
| HA / HACS / SoilSync | HA 2026.7.2; HACS 2.0.5; SoilSync 0.1.0 at `dcf9036` |
| Entities used | None |
| Procedure | Drove the real HACS panel in the browser: overflow menu, **Custom repositories**, entered `https://github.com/embersas/soilsync`, selected type **Integration**, pressed **Add**, opened the resulting card, pressed **Download**, confirmed, then restarted Home Assistant and re-read live state. |
| Repository acceptance | Accepted. The Custom repositories list immediately showed `SoilSync — embersas/soilsync (integration)` |
| Card presentation | Name `SoilSync`; description `Closed-loop soil moisture and drip irrigation controller for Home Assistant`; type `Integration`; author `embersas`; 0 stars; 0 open issues |
| README | Rendered in full inside the HACS card, including headings, bullet lists, and inline code spans |
| Repository link | Resolved; the card is populated from the live GitHub repository |
| Artwork | The HACS repository list showed `icon not available`, because HACS resolves list artwork from the centralized `home-assistant/brands` CDN and SoilSync is deliberately not submitted there. The integration's own local brand icon does render inside Home Assistant (see A6) |
| Version presentation | The download dialog stated `Commit dcf9036 will be downloaded` and `When downloaded, this will be located in '/config/custom_components/soilsync'`, matching the exact baseline SHA prefix and the expected path |
| Restart requirement | Presented correctly in the download dialog, and additionally raised as a real Home Assistant Repair `hacs / restart_required` at severity `warning` |
| Download result | Succeeded. HACS reported `installed: true`, `installed_version: dcf9036`, `available_version: dcf9036`, `local_path: /config/custom_components/soilsync`, `status: pending-restart` |
| Restart | `homeassistant.restart` issued 09:17:32 UTC; the HTTP API answered again 5.1 s later; Home Assistant returned to `RUNNING` on 2026.7.2 |
| Post-restart state | HACS `status` became `installed`; the `restart_required` Repair cleared automatically |
| Startup errors | None. The live system log contained zero SoilSync-related entries; the only errors present were pre-existing and unrelated to this integration |
| Evidence class | `LIVE HOME ASSISTANT` |
| Status | `PASS` |
| Cleanup | SoilSync is intentionally left installed. The custom repository entry remains registered in HACS |

A successful custom-repository installation proves public-repository HACS
compatibility, real HACS presentation, and installability. It does not prove
HACS default-store acceptance, default-store search discoverability, or Home
Assistant Brands acceptance. No such submission was made.

### A2 UI/UX lifecycle

| Field | Record |
|---|---|
| Date/time | 2026-08-24, approximately 09:24-09:56 UTC |
| HA / SoilSync | HA 2026.7.2; SoilSync 0.1.0 at `dcf9036`, installed through HACS |
| Entities used | Ten synthetic percentage moisture sensors, eleven synthetic template switches with their backing `input_boolean` helpers, and one real read-only moisture sensor. No physical actuator was ever selected or commanded |
| Integration search | `Settings > Devices & services > Add integration`, typed `SoilSync`. Exactly one result: **SoilSync (Helper)**, rendered with the SoilSync brand droplet icon and the orange custom-integration badge |
| Config entry creation | The flow opened with the translated step text `Create the SoilSync controller. Add irrigation zones afterwards with 'Add zone'.` and a single **Submit**. Submitting created one entry titled `SoilSync`, state `loaded`, `single_config_entry` honoured, supporting subentry type `zone` with `supports_reconfigure: true`. Because the manifest declares `integration_type: helper`, Home Assistant correctly routed the flow back to the Helpers page |
| Action registration | `soilsync.start_manual_watering`, `soilsync.stop_watering`, `soilsync.evaluate_zone`, `soilsync.clear_fault` all registered once at integration level |
| First zone creation | Created entirely through the graphical UI. Step 1 `Zone identity` (`Zone name`, `Soil-moisture sensor`, `Irrigation actuator (switch or valve)`), step 2 `Thresholds and timing`, step 3 `Safety limits`, all with correct translated labels, units, and step descriptions |
| Sensor selector | Filtered to the `sensor` domain; offered the synthetic moisture sensors |
| Actuator selector | Filtered to `switch`/`valve` only; offered only the synthetic template switches |
| Validation errors | Deliberately set target threshold equal to start threshold. The flow refused to advance and rendered the translated field error `The target threshold must be strictly greater than the start threshold.` Correcting the value allowed the flow to continue |
| Zone subentry | Created as subentry type `zone`, titled from the zone name |
| Device creation | One device per zone, carrying identifier `(soilsync, <subentry_id>)` and attributed to the owning entry and subentry |
| Entity creation and naming | Exactly 11 entities per zone: 4 sensors (`status`, `watering_runtime_today`, `last_session`, `next_eligible`), 3 binary sensors (`watering`, `problem`, `needs_water`), 1 switch (`enabled`), 3 buttons (`stop`, `evaluate_now`, `clear_fault`). All use `has_entity_name` device-prefixed friendly names, e.g. `SoilSync Test Zone 01 Status` |
| Availability/state presentation | `status` presented the enum `idle` with the full documented attribute set, including `safety_record_id`, `safety_lineage_id`, `zone_history_id`, `actuator_identity_status`, `moisture`, `moisture_classification`, `moisture_reported_at_utc`, blockers, and the live reconciliation block |
| Enabling/disabling | `switch.<zone>_enabled` off drove `status` to `disabled`; on returned it to `idle` |
| Threshold and pulse/soak settings | Accepted and applied; the applied values are visible in diagnostics as the zone's normalized applied shadow |
| `evaluate_zone` | Accepted. With moisture above the start threshold it correctly started no session |
| `start_manual_watering` | Accepted against a synthetic actuator. The zone entered `watering` with `mode: manual`, `possible_flow_owner: integration`, the synthetic switch turned `on`, and `binary_sensor.<zone>_watering` turned `on` |
| `stop_watering` | Cooperative stop completed within one sample (under 3 s): synthetic switch `off`, watering binary sensor `off`, zone back to `idle` |
| `clear_fault` | Invoked on a zone with no active fault; accepted without raising, and no fault was invented |
| Buttons | `stop` and `evaluate_now` button presses both routed through the validated controller paths without error |
| Unchanged reconfigure | Re-submitted a zone's reconfigure flow with byte-identical values. Result: `abort` with reason `reconfigure_successful`, and the zone's applied generation and config fingerprint were unchanged - a true no-op |
| Changed reconfigure | Changed one threshold. The zone's `config_fingerprint_short` moved from `2d93413f8771` to `c4710da886fa`, the reconciliation barrier converged (`dirty: false`, `failed: false`, `admission_open: true`), and reverting restored the original fingerprint exactly |
| Diagnostics | `Download diagnostics` content retrieved from the documented config-entry diagnostics endpoint. It contains `store` (`schema_version: 2`, `setup_classification: initialized_ok`, redacted generation id), `reconciliation`, `slot_manager`, per-zone applied shadow and runtime, `retained_tombstones`, and `recent_transitions` with transition IDs |
| Reload | Exercised twice through the documented reload path. A healthy reload returned `require_restart: false` and all zones returned to `idle` with identical durable identity |
| Native delete | Performed through the native websocket `config_entries/subentries/delete` command, which §46 item 1 names explicitly. Devices fell 11 to 10 and SoilSync entities fell 121 to 110; the zone's device and all 11 entities were removed immediately |
| Tombstone | The deleted zone was retained in the Store as a tombstone with `lifecycle: retired`, `active_subentry_id: null`, the deleted subentry id appended to `previous_subentry_ids`, and its `safety_record_id`, `safety_lineage_id`, and `zone_history_id` all unchanged |
| Exact same-record re-add | Re-adding the identical zone (same name, same synthetic sensor, same synthetic actuator) reactivated the same canonical record: identical `safety_record_id`, `safety_lineage_id`, and `zone_history_id`, `lifecycle` back to `active`, tombstone count back to zero, device and entity counts restored to 11/121, with no duplicate device, entity, or safety record |
| Repairs | A real SoilSync Repair was raised and rendered during this run: `Actuator identity conflict for SoilSync Test Zone 01`, severity `Error`, attributed `by SoilSync`, with the SoilSync brand icon. See A3 |
| Restart survival | See the note below |
| Evidence class | `LIVE HOME ASSISTANT WITH SYNTHETIC TEST ENTITIES` |
| Status | `PASS` for every item above |
| Cleanup | Recorded in the cleanup inventory |

Zone 01 was created step by step through the graphical UI, including the
deliberate validation-error round trip. The remaining zones were created
through the same three-step subentry config flow driven over the documented
config-flow HTTP API rather than by synthesising mouse events, purely for
speed; the backend flow, validation, and resulting state are identical.

### A3 Entity Registry rename

| Field | Record |
|---|---|
| Date/time | Rename 2026-08-24 09:38:53 UTC; restore 09:46:49 UTC |
| HA / SoilSync | HA 2026.7.2; SoilSync 0.1.0 at `dcf9036` |
| Entity used | One temporary synthetic template switch acting as `SoilSync Test Zone 01`'s actuator |
| Procedure | Captured full before-state, performed a supported Entity Registry rename in the real Home Assistant UI (entity settings dialog, Entity ID field, **Update**), re-read live state, reloaded the entry, then restored the original entity ID through the same UI dialog and reloaded again |
| Before identity | `entity_id switch.soilsync_test_valve_01`; Registry UUID `3581c639…`; zone `safety_record_id 1bc49e2f…`, `safety_lineage_id a10657ed…`, `zone_history_id 546a4c06…`; `actuator_identity_status registry_confirmed`; no blockers, no fault, no identity incident |
| After identity | `entity_id switch.soilsync_registry_rename_test`; Registry UUID unchanged `3581c639…`; `safety_record_id`, `safety_lineage_id`, and `zone_history_id` all **unchanged**; `actuator_identity_status` still `registry_confirmed`; no duplicate SafetyRecord, no duplicate device, no duplicate entity (device count 2, SoilSync entity count 22 before and after); no duplicated blocker or fault |
| `safety_record_id` | `1bc49e2f…` before, during, and after. Never re-keyed |
| `safety_lineage_id` | `a10657ed…` before, during, and after |
| `zone_history_id` | `546a4c06…` before, during, and after |
| Restore result | Restoring the original entity ID and reloading returned the entry to `loaded`, both zones to `idle`, identical `safety_record_id`/`safety_lineage_id`/`zone_history_id`, `registry_confirmed` identity, no fault, no incident, 2 devices and 22 entities with no duplicates. A subsequent bounded manual watering against the restored synthetic actuator ran and stopped normally, proving full functional recovery |
| Evidence class | `LIVE HOME ASSISTANT WITH SYNTHETIC TEST ENTITIES` |
| Status | `PASS` after remediation - durable identity retention passed here, and the two rename findings raised below were fixed and re-validated live on 2026-08-25 (see **A3 remediation re-validation**) |
| Cleanup | The rename was fully reversed; the original entity ID is in place |

Durable identity is the part §46 item 3 most cares about, and it held
completely: the Registry UUID remained the equivalence key and no safety
history was reset, merged, or duplicated by a textual entity-ID change.

Two live behaviours were observed that source review alone would not have
surfaced. Both are recorded as findings, not as fixes, because §46 item 3 is
still an open prototype validation whose outcome decides the design.

**Finding A3-1 - an actuator rename is not tracked at runtime, and silently
disables ON authorization entry-wide while the entry stays loaded.**
`async_track_entity_registry_updated_event` is installed only by the moisture
adapter (`zone_controller.py`), so an actuator rename produces no runtime
reaction. It nevertheless changes the computed entry snapshot: the immutable
snapshot builder resolves each configured actuator by entity ID
(`registry.async_get(config.actuator)`), which returns `None` once the
configured entity ID no longer exists, so the zone and entry snapshot
fingerprints change while the applied and observed snapshots keep the
pre-rename value. Nothing re-runs reconciliation, because an Entity Registry
rename does not raise a config-entry update.

Observed consequence: the final live ON gate failed the single predicate
`current_entry_snapshot_matches` with `configuration_authority_valid: false`,
so every manual start was admitted to `WATERING` (T3) and then terminated
about 40 ms later as `OffConfirmed` (T21) with reason `config_changed`. This
was reproduced twice. Critically it affected **both** zones, including the
second zone whose own sensor and actuator were untouched. While the entry
remained loaded, the zone reported no fault, no blocker, no identity incident,
and `admission_open: true`, and no Repair was raised. The behaviour is
fail-closed and therefore safe, but it is silent and entry-wide.

**Finding A3-2 - after a reload while renamed, the whole config entry fails to
set up.** Reloading with the rename still in place put the entry into
`setup_retry` with reason
`ReconciliationError: identity conflict for <zone-01 subentry>: records ['1bc49e2f…']`,
made every zone entity in the entry `unavailable`, and raised the SoilSync
Repair `actuator_identity_conflict` at severity `error`, naming the zone, the
short record/lineage/registry ids, and the stale entity ID. Raising an
exact-record Repair and authorising no water is what §39 TB8 prescribes for a
missing actuator, and it is the "Repair-and-reconfigure" fallback that §46
item 3 explicitly permits. What is not settled by spec.4 is that the failure is
**entry-wide** rather than confined to the affected zone, so healthy zones stop
working too; the documented remedy, reconfiguring the zone onto the new entity
ID, was not exercised from that state and its availability while the entry is
in `setup_retry` is untested here.

The `actuator_identity_conflict` Repair issue also remained listed after the
entity ID was restored and the entry reloaded cleanly, i.e. it did not
auto-clear on recovery.

No production or test code was changed in response to either finding **in the
2026-08-24 run**. Both were carried to specification review rather than patched,
because choosing between runtime rename fix-up, a narrower per-zone failure, and
an explicit Repair-and-reconfigure flow appeared to be the §46 item 3 decision.

**Superseded 2026-08-25.** The complete spec.4 review recorded under
*Remediation* below found that §23.2 item 1, §25.1.1, §35.11, §40 and I35
already determine the required behaviour without any new semantics: a different
current entity ID for the same durable Entity Registry UUID *is* the same
actuator. Both findings are therefore implementation defects, not open
behavioural questions. The original text above is retained unchanged as the
historical record of what was observed and why the original caution was taken;
the method of that caution was correct, only the conclusion that spec.4 was
insufficient was later disproved.

### A3 remediation re-validation

Re-validated live on 2026-08-25 against the fixed candidate, using one
registry-backed synthetic template switch (`switch.soilsync_f1_valve`,
Registry UUID `c314f72e…`) as `SoilSync F1 Zone`'s actuator.

| Field | Record |
|---|---|
| Rename performed | Supported Entity Registry rename `switch.soilsync_f1_valve` -> `switch.soilsync_f1_valve_renamed`, executed **during an active bounded synthetic MANUAL session** |
| Registry UUID | `c314f72e…` before, during and after. Never re-keyed |
| `safety_record_id` | `bdcb2d97…` unchanged |
| `safety_lineage_id` | `474abd29…` unchanged |
| `zone_history_id` | `9de33327…` unchanged |
| Runtime addressing | Followed the rename: `actuator_identity.last_known_entity_id` became `switch.soilsync_f1_valve_renamed`; the subentry keeps its durable configured reference `switch.soilsync_f1_valve` |
| Identity status | `registry_confirmed` throughout; `identity_incident` `null` |
| Fingerprints | Zone `config_fingerprint` `2597cad0` and entry snapshot `b03c1aab` **unchanged**, so the rename was not processed as a configuration change |
| Session behaviour | Controller stayed `watering` with `possible_flow_owner: integration`; no `CONFIG_CHANGED`; the session later ended normally as `user_stop` (39.87 s, measured, not estimated) |
| Repairs | None at any point |
| Post-rename watering | A further bounded synthetic manual session ran and completed `manual_complete` (45.01 s measured) against the renamed entity |
| Reload while renamed | Entry returned `loaded`; same record/lineage/history/UUID; no `actuator_identity_conflict`; daily runtime 816.40 s and `last_session_end` preserved |
| Restart while renamed | Full container restart; startup resolved the same Registry UUID, kept all durable IDs, and preserved the daily budget and interval |
| Restore | The original entity ID was restored and verified: addressing returned to `switch.soilsync_f1_valve` with every durable ID and the accumulated 861.41 s budget unchanged |
| Evidence class | `LIVE HOME ASSISTANT WITH SYNTHETIC TEST ENTITIES` |
| Status | `PASS` |

§46 item 3 is therefore answered: `async_track_entity_registry_updated_event`
auto-fix-up **is** reliable for this purpose when the candidate is verified
against the stored durable UUID before any addressing changes. The specified
Repair-and-reconfigure fallback is retained for every case that cannot be
verified that way, and both of those cases were exercised live and in the
automated suite.

### A4 Ten-zone live synthetic test

§46 item 5 asks only to "validate FIFO latency/visibility with approximately
ten simultaneously dry zones". It does not require ten physical zones, so live
synthetic entities are permitted and this item is not blocked.

| Field | Record |
|---|---|
| Date/time | 2026-08-24; all ten sensors driven below their start threshold at 10:03:58 UTC as recorded by SoilSync itself |
| HA / SoilSync | HA 2026.7.2; SoilSync 0.1.0 at `dcf9036` |
| Exact zone count | **10** simultaneously dry SoilSync zones |
| Entity type | 10 unique synthetic percentage moisture sensors and 10 unique, independently observable synthetic template switches. Every zone had its own dedicated actuator; no actuator was shared |
| Synthetic vs physical | 10 synthetic actuators, **0** physical irrigation actuators. An eleventh zone bound to the one real physical moisture sensor was present but deliberately configured with a start threshold below the current reading so it could not open a session and could not perturb the queue |
| Zone settings | start 40 %, target 45 %, pulse 30 s, soak 60 s, max cycles 20, max session runtime 3600 s, max daily runtime 3600 s, minimum session interval 900 s, sensor max age 7200 s, actuator confirmation timeout 30 s |
| Trigger | All ten synthetic sensors were published to 35 % concurrently in a single batch. SoilSync recorded the resulting report time for zone 01 as `2026-08-24T10:03:58.609766+00:00` |
| Admission order | `01 -> 02 -> 03 -> 05 -> 04 -> 06 -> 07 -> 08 -> 09 -> 10`. Order follows request arrival, not zone number: zone 05's report was processed before zone 04's, and the queue served them in exactly that arrival order |
| FIFO | Held exactly. Every zone was granted once, in arrival order, with no reordering and no queue jumping |
| Serialization | Held absolutely. Across 359 samples taken at 2-second resolution spanning the whole run, the maximum number of synthetic actuators simultaneously ON was **1**, and the number of samples with more than one ON was **0** |
| No duplicate grants | Each of the ten zones received exactly one grant in the round; per-zone grant count was 1 for all ten |
| No forbidden parallel ON | Confirmed by the overlap check above and by every zone's `possible_flow_owner`, which was non-null for the single owner only |
| Pulse | Every zone ran a complete 30-second pulse. SoilSync's own session summaries report `runtime_s` between 30.003564 s and 30.008786 s with `runtime_estimated: false` and `runtime_estimation_reason: none` - measured, not estimated |
| Queue progression | Consecutive pulse-OFF times recorded by SoilSync were 10:04:28, 10:04:58, 10:05:28, 10:05:58, 10:06:28, 10:06:58, 10:07:28, 10:07:59, 10:08:29, 10:08:59. The handoff interval is a consistent 30 s (one 31 s), i.e. the next zone was granted essentially immediately on the previous zone's proven OFF, with no idle gap |
| Eventual service / no starvation | All 10 of 10 zones were served within a single round. Total time from the simultaneous dry trigger to the last zone's proven OFF was approximately 301 s, i.e. about 30.1 s per zone with negligible scheduling overhead |
| Soak | After its pulse each zone entered `soaking` and correctly **did not** advance. With no new sensor report available, all ten zones held in `soaking` for over six minutes rather than inventing a post-soak reading. This is the specified rule that continuation requires a real report timestamped at or after the soak deadline, and that a fallback scan never manufactures a report timestamp |
| Recheck | Publishing a qualifying report at 50 % (at or above the 45 % target) completed all ten sessions promptly and cleanly |
| Completion | All ten sessions ended with reason `target_reached`, mode `auto`, 1 cycle, `moisture_before: 35`, `moisture_after: 50`, and all ten zones returned to `idle` with every actuator `off` |
| State presentation | Queued zones correctly showed `waiting_for_slot: true` while remaining `idle`; the owner showed `watering` with `possible_flow_owner: integration`; `next_eligible` was set to each zone's session end plus the configured 900 s minimum interval, exactly |
| Diagnostics | The `slot_manager` block exposed live `owner`, `queue`, keyed `blockers`, `grants_enabled`, the reconciliation barrier flags, and `admission_open` throughout |
| Cancellation/reconfigure/delete of a queued zone | Not exercised during the ten-zone round itself. The equivalent behaviours were exercised separately in A2 (unchanged reconfigure no-op, changed reconfigure, native delete, exact same-record re-add) on idle zones |
| Evidence class | `LIVE HOME ASSISTANT WITH SYNTHETIC TEST ENTITIES` |
| Status | `PASS` |
| Cleanup | All ten zones and the config entry that owned them were removed; see the cleanup inventory |

This is real Home Assistant runtime evidence for global serialization, FIFO
fairness, pulse/soak/recheck, and queue visibility at ten-zone scale. It is not
physical valve evidence.

### A5 Sensor cadence/freshness

| Field | Record |
|---|---|
| Date/time | Historical and direct MQTT observation 2026-08-23; live SoilSync observation 2026-08-24 from 09:35:27 UTC |
| HA / SoilSync | HA 2026.7.2; SoilSync 0.1.0 at `dcf9036`, installed and running |
| Real sensor generic type | One deployed wireless soil-moisture percentage sensor delivered through the existing MQTT integration. Confirmed live from the Entity Registry: `platform: mqtt`, `device_class: moisture`, unit `%`, `state_class: measurement` |
| Entities used | The one real physical moisture sensor, read-only, plus one synthetic non-physical actuator. The physical sensor was never reconfigured or written to |
| Prototype zone | A real SoilSync zone was created pairing the physical moisture sensor with a synthetic template switch, proving the intended end-to-end path with zero irrigation risk |
| Preserved prior evidence | Unchanged and not superseded: 4951.476 s / 82.525 min of direct MQTT observation, 20 messages in eight bursts, direct median burst gap 994.638 s (16.58 min), maximum observed normal direct burst gap 1116.047 s (18.60 min), six consecutive directly observed unchanged-soil transitions, Recorder changed-state median 870.742 s |
| New continuous live observation | A polling observer sampled the physical sensor's `last_reported` every 10 s from 09:35:27.723 UTC to 11:00:25.162 UTC without interruption: **5097.439 s / 84.957 min**, 506 polls, 3 transient errors (all during the two deliberate restarts). This exceeds the previously documented 82.525 min direct sample, so the direct-observation record is extended. Because the poller watches `last_reported`, which advances on unchanged re-reports as well as changed ones, an interval with no `last_reported` movement is genuine radio silence, not merely an absence of value changes |
| Report count in the new window | 3 new physical reports were captured: 09:53:44 (43 %), 10:17:29 (`unknown`), 10:18:20 (43 %) |
| Clean measured interval | One clean sensor-to-sensor interval falls entirely inside the new window and outside any restart: 09:18:58 -> 09:53:44 = **2085.351 s (34.76 min)** |
| Relationship to the prior maximum | That single clean interval **exceeds** the previously documented maximum normal direct burst gap of 1116.047 s (18.60 min) by roughly 87 %. It is one sample, not a distribution |
| Window contamination, stated plainly | Two deliberate Home Assistant restarts were performed during this run (09:17 for the HACS installation, 10:16 for the restart-survival test). The 10:17:29 `unknown` row and the 10:18:20 `43` row are the MQTT entity repopulating after the second restart, not natural cadence. Intervals spanning those restarts are therefore **not** counted as cadence samples |
| Unchanged reports | **Not newly observed.** Every report captured in this window had `last_changed` equal to `last_reported`, so none was an unchanged re-report. The only direct evidence of unchanged reports remains the preserved 2026-08-23 MQTT observation of six consecutive unchanged-soil transitions. This is stated rather than inferred |
| `state_changed` behaviour | Observed live: each new physical report advanced `last_changed`, `last_updated`, and `last_reported` together, and SoilSync's zone attribute `moisture_reported_at_utc` tracked the physical sensor's `last_reported` exactly |
| `state_reported` behaviour | Not newly exercised against the physical sensor, because no unchanged physical re-report occurred inside the window. Home Assistant confirmed live that `state_reported` is an entity-filtered-only event stream - an unfiltered subscription is rejected with `Event filter is required for event state_reported` - which is consistent with the entity-filtered listener SoilSync installs |
| SoilSync freshness behaviour | **Validated live against the physical sensor.** A guarded AUTO evaluation on the physical-sensor zone opened a real AUTO session at 10:27:09 UTC, ran one complete 30.011 s pulse on the synthetic actuator (`runtime_estimated: false`), and entered `soaking`. Its `sensor_fresh_until_utc` was `2026-08-24T12:18:20.139374+00:00`, which is exactly the physical sensor's own `last_reported` of `10:18:20.139374` plus the configured 7200 s `sensor_max_age`. Freshness is therefore derived from the sensor's report time, never from scan or callback time |
| `fresh_until` on synthetic zones | The same identity held on synthetic zones: `sensor_fresh_until_utc` equalled `moisture_reported_at_utc` plus exactly 7200 s |
| Fresh/stale presentation | `moisture_classification` was presented live as `valid` while fresh, and as `unavailable`/`invalid` when a zone's sensor was absent after a restart. No zone was ever falsely presented as fresh |
| Longest directly observed silence | **2525.023 s / 42.084 min, and still open at closeout.** From the 10:18:20 report to the 11:00:25 end of observation the physical sensor produced no report of any kind. This is the single most important new cadence datum in this run: it exceeds the previously documented maximum normal direct burst gap of 1116.047 s (18.60 min) by roughly 126 %, and it was measured by continuous 10 s polling of `last_reported`, so it cannot be explained away as unchanged reports going unseen |
| Watchdog extension on a later report | **Not observed.** No second physical report arrived before closeout, so the freshness deadline was never seen to advance. `sensor_fresh_until_utc` correctly stayed pinned to the 10:18:20 report for the whole 42-minute silence, and the zone correctly remained `soaking` with `moisture_classification: valid` and no fault, because 42 min is well inside the configured 7200 s window. The extension-on-new-report path therefore remains unvalidated live |
| Conclusion on the two-hour default | **No change to the default is justified by this run, and none was made.** The 2026-08-23 direct sample (median 16.58 min, maximum normal 18.60 min) sits comfortably inside a two-hour window. This run is materially less comfortable: it produced one clean 34.76 min interval and one 42.08 min silence still open at closeout, both measured by continuous 10 s polling of `last_reported`, and both far above the previous maximum. Two observations at roughly a third of the window are not grounds to move a safety default, but they do weaken the earlier assumption that this sensor reports every 15-20 min, and they make the margin smaller than the prior evidence implied. The 24 h Recorder view additionally shows a maximum changed-state gap of 13473.8 s (3.74 h), which is **not** evidence of silence - Recorder records changed states, not reports - and must not be read as such. Deciding `sensor_max_age` under §46 item 6 needs a longer, restart-free, unchanged-report-aware sample than this run produced. The default remains 7200 s and this item stays open |
| Duration-dependent gap | The goal of at least one legitimate continuous observation exceeding the two-hour freshness default was **not** achieved and is not claimed. The achieved continuous window is 84.957 min and the longest single observed silence is 42.084 min. No elapsed time was fabricated, and the run was not extended by pretending an unattended period was observed. This specific duration-dependent part of A5 stays `PARTIAL` |
| Evidence classes | Physical cadence: `LIVE PHYSICAL`. SoilSync freshness handling driven by the physical sensor: `LIVE HOME ASSISTANT WITH SYNTHETIC TEST ENTITIES` (real sensor, synthetic actuator) |
| Status | `PARTIAL` |
| Cleanup | The physical sensor was never modified. The observer was stopped and the temporary freshness zone and its entry were removed |

No elapsed time was fabricated and no interval that crosses a restart was
counted as cadence.

The 2026-08-24 record above is preserved unchanged. The clean window it was
missing was obtained on 2026-08-25 and is recorded next; that continuation also
identified the platform mechanism that explains both runs.

### A5 continuation - 2026-08-25 clean window longer than two hours

| Field | Record |
|---|---|
| Date/time | 2026-08-25; all times UTC as reported by the live instance |
| HA / SoilSync | HA Core 2026.7.2, Home Assistant Container on Docker. SoilSync 0.1.0; all 24 files of the deployed `custom_components/soilsync` were MD5-compared against the local working tree at `3e4823c2358cd991d0cd0ff67c38b16d01e50158` and every file matched |
| Real sensor | The one deployed Zigbee soil-moisture probe, delivered by zigbee2mqtt through the MQTT integration. Entity Registry confirms `platform: mqtt`, `original_device_class: moisture`, unit `%`, `state_class: measurement`. It was read only: never written, renamed, reconfigured, or replaced |
| Synthetic actuators | Two `template` switches created through the supported template helper flow. Stored configuration read back from the live config store shows for each: `template_type: switch`, no device, `value_template` reading only its own dedicated `input_boolean`, and `turn_on`/`turn_off` consisting solely of `input_boolean.turn_on`/`input_boolean.turn_off` against that same helper. Empirically, a deliberate ON and OFF of one of them was diffed across 323 actionable and irrigation-matching entities and the only changes were the template switch itself and its own backing helper. Every real irrigation entity in the instance - the physical valve-domain entities, the entities belonging to the household's real irrigation integration, and every irrigation switch, script, and helper - was untouched, and none was in an energised state at any point in the run |
| Prototype zones | `A5 Observer Zone` (start 20 %, target 30 %) held the physical sensor's live 41-43 % comfortably **above** its start threshold for the whole window, so it never requested water. `A5 Watchdog Zone` (start 60 %, target 70 %, pulse 30 min, soak 60 s, `max_cycles` 1, `max_session_runtime` 1800 s, `max_daily_runtime` 1860 s) was configured to run exactly one AUTO pulse against the second synthetic switch |
| Observation layers | **A. Transport:** every zigbee2mqtt publish for the device, from the broker-independent zigbee2mqtt log, giving the device's own `last_seen` per message. No broker credential was used, requested, read, or stored. **B. HA state:** `state`, `last_changed`, `last_updated`, `last_reported`, availability. **C. HA events:** a temporary read-only custom component installed exactly the two supported entity-filtered listeners, `async_track_state_change_event` and `async_track_state_report_event`, on that one sensor, and appended every delivered event plus a 30 s read-only state sample to a JSONL file. It commanded nothing and created no entity. It was loaded by a restart **before** T0 and removed at closeout. **D. SoilSync:** live zone attributes, `sensor_fresh_until_utc`, `moisture_reported_at_utc`, `moisture_classification`, entry diagnostics, and the transition ring buffer, with `custom_components.soilsync` at DEBUG through the supported `logger.set_level` action |
| Unfiltered subscription | Re-confirmed from Core source that this is a platform property and not a SoilSync limitation: `websocket_api` exposes no `state_reported` subscription at all, and `subscribe_entities` listens to `EVENT_STATE_CHANGED` only. The entity-filtered listener that SoilSync installs is the supported path |
| T0 | `2026-08-25T02:58:00.464462Z` |
| T_end | `2026-08-25T05:57:51.238503Z` |
| Elapsed | **10790.773987 s = 179.8462 min = 2.9974 h**, exceeding the required 7200 s by 3590.773987 s |
| Window integrity | No Home Assistant restart, no integration reload, no entity rename, no sensor replacement, no manual mutation of the sensor state, and no synthetic write to the real sensor entity occurred between T0 and T_end. The container start at `02:45:54Z` is **before** T0 and the cleanup restart at `06:01:08Z` is **after** T_end, and container uptime spanned the whole window |
| Genuine device reports (transport) | 33 genuine publishes in 8 bursts, and **0** cached republishes. Burst-to-burst intervals n=7: min 131.238 s, median 1281.826 s, max 2406.275 s, mean 1015.958 s. Longest device silence 2405.146 s (40.09 min). The physical sensor was healthy and talking throughout |
| Reports Home Assistant actually saw | **2 `state_changed`, 0 `state_reported`.** `2026-08-25T03:31:04.478969Z` 43 -> 42 and `2026-08-25T05:03:45.260265Z` 42 -> 41. Interval between them **5560.781296 s (92.68 min)**. T0 to first HA-visible report 1984.015 s; last HA-visible report to T_end 3245.978 s |
| Restart repopulation excluded | The `02:47:04.027907Z` state that seeded the window is **not** counted as a genuine report. The transport log proves it: the device's own burst was at `02:46:00.149Z`-`02:46:01.320Z` while Home Assistant was still restarting, and the publish Home Assistant did receive, logged at `02:47:03`, carried the **stale** `last_seen` `02:46:01.320Z`, i.e. zigbee2mqtt replaying cached state. Both the genuine burst and the replay are recorded separately and neither is used as a cadence sample |
| Why no unchanged report reached Home Assistant | **Root cause identified, with primary evidence.** At `03:05:10` one MQTT message carried an unchanged `soil_moisture` and a changed temperature. The temperature entity's `last_reported` advanced to `03:05:10.651177Z`; the soil-moisture entity's `last_reported` did **not** move at all. Core source explains it exactly: `MqttEntity._message_callback` requests a state write only `if attributes is not None and self._attrs_have_changed(attrs_snapshot)`, and `_attrs_have_changed` returns true only when `_attr_force_update` is set or a tracked attribute actually changed. The MQTT sensor platform tracks `{_attr_native_value, _attr_last_reset, _expired}` and its `DEFAULT_FORCE_UPDATE` is `False`. So for this deployed sensor an identical value produces **no Home Assistant state write of any kind**: no `state_changed`, no `state_reported`, and no `last_reported` advance. A second unchanged burst at `03:07:31`-`03:07:32` reproduced it |
| Consequence for the earlier evidence | This corrects the reading of the preserved 2026-08-23 sample. The "six consecutive unchanged-soil transitions" observed there were unchanged **device** reports on the MQTT transport. With `force_update` false they never became Home Assistant reports, so they never refreshed `last_reported` and never refreshed SoilSync freshness. The earlier direct-MQTT cadence figures describe the device, not the signal SoilSync consumes |
| `state_reported` handling | Not exercised against this physical sensor, and now known to be **structurally impossible** for it rather than merely absent by chance. This is recorded as a platform fact, not as a SoilSync gap: `SPECIFICATION.md` §46 already removes `last_reported`/`state_reported` mechanics from the open-question list as conclusive from release source, and SoilSync's entity-filtered `async_track_state_report_event` listener remains installed and correct for sensors that do produce unchanged writes |
| Freshness derived from report time | At session start the watchdog zone's `sensor_fresh_until_utc` was `2026-08-25T04:47:04.027907Z` against `moisture_reported_at_utc` `2026-08-25T02:47:04.027907Z`: a delta of **exactly 7200.000000 s**. The session opened at `02:57:22Z`, ten minutes after that report, so the deadline was derived from the report timestamp and not from evaluation, callback, or scan time |
| Scan time never manufactures freshness | Two independent proofs. **Home Assistant:** 360 read-only samples over 10770.353 s produced only 3 distinct `last_reported` values, each held bit-for-bit constant across many reads - 66 reads spanning 1950.058 s, 186 reads spanning 5550.171 s, and 108 reads spanning 3210.121 s. **SoilSync:** the 15-minute fallback scan fired `T56` twice during the live AUTO pulse, at `03:11:03.873016Z` and `03:26:03.871704Z`, and `sensor_fresh_until_utc` read back over the supported API at `02:57:27Z`, `03:11:26Z` and `03:26:45Z` was the identical `2026-08-25T04:47:04.027907Z` every time. A scan produced a transition but moved the deadline by zero microseconds |
| Live AUTO pulse | One only, on the synthetic actuator. `T1 SlotGranted` `02:57:28.855023Z` -> `T6 OffConfirmed` `03:27:28.867616Z` = 1800.012593 s wall; SoilSync reported `session_runtime_s` 1800.00384 with `runtime_estimated: false`. `T23 SoakDeadlineReached` `03:28:28.867616Z`. The genuine `03:31:04` report then qualified as the post-soak report and closed the session at `T26` `03:31:04.483779Z` with reason `max_cycles`. Both synthetic switches and both backing helpers finished `off`. No fault, no Repair, no blocker |
| Freshness extension on a later report | **Still not observed live.** No Home Assistant-visible report occurred inside the 30-minute WATERING window - the first one arrived at `03:31:04`, 3.6 minutes after OFF, while the zone was already SOAKING - so `T56` was never seen to move a deadline forward. The cause is the same platform behaviour recorded above: over three hours the deployed sensor produced only two Home Assistant-visible reports, and a pulse is capped at 30 minutes by `SPECIFICATION.md` §9 |
| Evidence classes | Device cadence and transport: `LIVE PHYSICAL`. Home Assistant event and state behaviour: `LIVE HOME ASSISTANT`. SoilSync freshness driven by the physical sensor: `LIVE HOME ASSISTANT WITH SYNTHETIC TEST ENTITIES` |

#### Cadence corpus for the two-hour default

Three independent corpora, all excluding restart repopulation, integration
reload, browser reconnect, polling, and diagnostic reads:

| Corpus | Span | Device reports | Reports Home Assistant saw | Median HA-visible interval | Max HA-visible interval | Intervals over 7200 s |
|---|---|---|---|---|---|---|
| Clean window, 2026-08-25 | 2.9974 h | 33 publishes in 8 bursts | 2 | single interval | 5560.781 s (1.54 h) | 0 of 1 |
| Transport log, 2026-08-24/25 | 22.9 h | 513 publishes | 21 | 2446.0 s (40.8 min) | 16051.3 s (4.46 h) | 4 of 20 (20 %) |
| Home Assistant Recorder for that entity | 248.22 h (10.34 days) | not visible to Recorder | 342 numeric states | 751.7 s (12.5 min) | 79464.4 s (22.07 h) | **24 of 341 (7.0 %)** |

The device's own cadence is comfortable: median burst gap 1281.8 s in the clean
window, maximum observed device silence 2405.1 s (40.09 min), and a 54.88 min
maximum across the full 22.9 h transport corpus. The signal SoilSync can
actually see is not. The four transport-corpus gaps over two hours (7231 s,
8521 s, 12695 s, 16051 s) are all independently confirmed by the transport log
to be periods in which the device was publishing normally every few minutes, so
they are not device outages, radio loss, or battery failure.

#### Two-hour default assessment - `CONTRADICTED`

Against `SPECIFICATION.md` §46 item 6 the verdict from physical evidence is
**CONTRADICTED**, with one precise qualification.

- The contradiction is at the Home Assistant state-write layer, not at the
  device. This deployed sensor is healthy and reports every few minutes.
- `SPECIFICATION.md` §10.2 and §18 define staleness against `reported_at_utc`,
  which is Home Assistant `last_reported`. That is the only signal SoilSync can
  observe, and for this sensor it advances only on **value changes**.
- Measured against that signal, normal healthy operation exceeded
  `sensor_max_age = 2 h` on 7.0 % of intervals over 10.34 days, with a maximum
  of 22.07 h; and on 20 % of intervals in the 22.9 h stretch where the transport
  log independently proves the device never stopped talking.
- The clean >2 h window did not itself breach the default - its single
  HA-visible interval was 5560.781 s, 77.2 % of the 7200 s budget - but it
  reproduced the mechanism directly, and that interval is far above the
  device-level cadence.

**No default was changed and no freshness semantics were touched.** §46 item 6
permits adjusting the default only, and the authorisation for this run requires
stopping and reporting before any such change. The decision is therefore
referred, with these options recorded and deliberately not chosen:

1. Leave the default at 7200 s. It sits inside the configurable 5 min-24 h range
   of §9 and users calibrate per deployment; the failure mode is fail-closed - no
   automatic start, or a `SENSOR_STALE` termination of a flowing AUTO pulse -
   never an unsafe ON.
2. Document that MQTT-sourced moisture sensors should be published with
   `force_update: true`, which makes `_attrs_have_changed` return true
   unconditionally, restores the unchanged-write path, and would have turned this
   deployment's 21 Home Assistant-visible reports in 22.9 h into 513. That fixes
   the deployment rather than weakening the safety horizon, and it is the option
   that also restores the `state_reported` path §10.3 is written for.
3. Raise the default. This weakens the detection horizon for a sensor that has
   genuinely died, which is the property §40 relies on, and would need to be
   justified on its own terms rather than by one deployment.

This is a deployment-default and platform-integration finding. It is **not** a
SoilSync implementation defect: freshness is correctly derived from
`last_reported`, scans correctly never manufacture a report time, and the
entity-filtered `state_reported` listener is correctly installed. It is **not** a
specification contradiction: §46 item 6 exists precisely to receive this
evidence, and no normative rule, invariant, or transition is inconsistent with
what was observed.

Raw evidence for this continuation is kept under the git-ignored
`evidence/slice13-phaseA5/`: `a5observer.jsonl` (every entity-filtered event and
read-only sample), `z2m_transport.txt` (every device publish), `transitions.txt`
(the SoilSync transition ring buffer), and `A5_ANALYSIS.txt` (the computed
window, transport, and Recorder analyses).

No elapsed time was fabricated, no interval crossing a restart was counted as
cadence, and no unchanged report was invented.

#### A5 status after the continuation

`PASS` for §46 item 6. The item requires validating the two-hour default against
a deployment sensor and adjusting only the default. That validation is now
complete on a clean, restart-free, 2.9974 h continuous window plus a 10.34 day
Home Assistant corpus and a 22.9 h transport corpus: the default is
`CONTRADICTED` for this deployment, the mechanism is identified to Core source
level, and the decision is referred rather than taken. The one sub-observation
that remains unobtained live - a `T56` deadline advancing from a new physical
report, and a physical `state_reported` - is now known to be unobtainable from
this sensor while its MQTT publisher leaves `force_update` false, and both are
covered deterministically by the automated suite (`SR1`, `SR6`, `SR13`) and by
release-source behaviour that §46 already treats as conclusive.

#### Final A5 product decision - retain the two-hour default

The user made the outstanding product decision after reviewing the measured
result: `sensor_max_age` remains **7200 seconds / 2 hours**. A5 remains `PASS`.

- The physical sensor cadence itself comfortably supports the two-hour horizon:
  33 genuine publishes in 8 bursts during the clean window, with a median burst
  interval of approximately 1281.826 s and maximum device silence of
  approximately 2405.146 s / 40.09 min.
- The tested default MQTT-to-Home Assistant entity presentation does not support
  that horizon reliably. Unchanged transport reports were suppressed before
  becoming moisture-entity state writes, so Home Assistant's authoritative
  `last_reported` timestamp did not advance even while the device continued
  publishing normally.
- The measured assessment remains `CONTRADICTED`: physical cadence supports the
  two-hour horizon; the tested default MQTT-to-Home Assistant entity presentation
  does not. The product default is nevertheless retained because increasing it
  would mask missing observable heartbeat rather than correct it.
- The chosen mitigation is documentation and upstream entity configuration.
  The configured moisture entity must produce Home Assistant state writes often
  enough during healthy operation, including when its value is unchanged. For
  MQTT-backed sensors, `force_update: true` is one integration-specific example
  where appropriate, not a universal SoilSync requirement.
- SoilSync remains hardware agnostic. It does not consume MQTT directly, add an
  MQTT runtime dependency, or treat polling, fallback scans, or callback time as
  freshness. There is no runtime change and no specification change.

### A6 HACS/presentation

| Field | Record |
|---|---|
| Date/time | 2026-08-24, approximately 09:10-10:02 UTC |
| HA / HACS / SoilSync | HA 2026.7.2; HACS 2.0.5; SoilSync 0.1.0 at `dcf9036` |
| Entities used | None for the presentation audit itself |
| HACS card | After installation SoilSync is grouped under **Downloaded** in the HACS repository list, typed `Integration`. The HACS repository record reports `name: SoilSync`, `category: integration`, `domain: soilsync`, `installed: true`, `installed_version: dcf9036`, `homeassistant: 2025.9.0` from `hacs.json`, `local_path: /config/custom_components/soilsync`, `authors: ["@embersas"]` |
| README | Renders in full inside the HACS card: title, prose, requirement callout, headed sections, ordered and unordered lists, and inline code spans all display correctly |
| Icon | Two different results, and the difference is expected. Inside Home Assistant the local brand icon renders correctly: the SoilSync droplet appears in the Add-integration picker, on the integration page, and on the SoilSync Repair. In the HACS repository list the artwork shows `icon not available`, because that list resolves artwork from the centralized `home-assistant/brands` CDN and SoilSync is deliberately not submitted there |
| Name | `SoilSync` everywhere: HACS card, HACS custom-repository entry, integration picker (`SoilSync (Helper)`), integration page title, config entry title, device names, Repair attribution |
| Description | `Closed-loop soil moisture and drip irrigation controller for Home Assistant`, sourced from the public repository description |
| Version | `Version 0.1.0` shown on the integration page beside the `Custom integration` badge; HACS separately reports the installed commit `dcf9036` |
| Repository / issues links | `manifest.json` carries `documentation` and `issue_tracker` pointing at the public repository; the HACS card resolves against the live repository |
| Devices & services | The SoilSync integration page renders the brand icon, `Version 0.1.0`, the `Custom integration` badge, an **Add zone** action, aggregate device/entity counts, and one collapsible group per zone subentry labelled `Irrigation zone`, each with a Reconfigure control, an overflow menu, and its device with 11 entities |
| Actions | All four actions are registered and exposed with translated names and the documented `device_id` selector filtered to the `soilsync` integration |
| Diagnostics | Available from the integration page and from the documented endpoint; content is structured and redacts the runtime Store generation id |
| Repairs | A real SoilSync Repair rendered correctly with brand icon, translated title, `Error` severity, and `by SoilSync` attribution |
| Stale-name audit | Clean. Across all tracked repository files, the only file containing `Moisture Loop`/`moisture_loop`/`moisture-loop` is `PROGRESS.md`, which is the historical development record and is allowed to retain the old development name. No source file, `README.md`, `manifest.json`, `hacs.json`, `strings.json`, or translation contains it. In the live system: zero matching entity IDs or friendly names, all four action names are `soilsync`-correct, and the full diagnostics payload contains no occurrence |
| Evidence class | `LIVE HOME ASSISTANT` |
| Status | `PASS`, with the HACS-list artwork limitation recorded above as expected and out of scope |
| Cleanup | No presentation state needed reverting |

No HACS default-store submission, no `home-assistant/brands` submission, no
GitHub Release, no version bump, and no release tag occurred in this run.

## Findings carried to specification review

Phase A produced three live findings on 2026-08-24. None was patched in that
run. Each was recorded with its evidence and marked
`[?] Requires specification review` because resolving it appeared to require
choosing new Repair, blocker, or fault semantics rather than applying an
unambiguous spec.4 rule.

> **Reclassified 2026-08-25.** A complete re-review of `SPECIFICATION.md`
> `0.1.0-spec.4` found that all three are determined by rules that already
> exist. F1 is decided by §11.3 step 5 with §21; F2 by §23.2 item 1, §25.1.1,
> §35.11, §40 and I35; F3 is the reload/reconciliation manifestation of the
> same F2 resolution gap. All three are therefore **implementation defects
> against existing spec.4**, all three are now **RESOLVED**, and
> `SPECIFICATION.md` was not changed. The original finding text below is
> preserved verbatim; nothing about it is retracted. The 2026-08-24 caution was
> correct in method — the findings were genuinely ambiguous on the evidence then
> available, and no semantics were invented — and only the conclusion that
> spec.4 was insufficient did not survive the fuller review.

### F1 - restart during an active session can permanently block all watering

**Disposition: implementation defect against existing spec.4. RESOLVED
2026-08-25.** See *Remediation* below.

Reproduced on the live instance. A bounded manual session was started on a
synthetic zone and Home Assistant was restarted mid-pulse.

Startup recovery behaved correctly in every respect the specification names
explicitly: the interrupted pulse was **not** resumed, the actuator was driven
to OFF, the session was finalized as `restart_recovery` with
`runtime_estimated: true` and `runtime_estimation_reason: off_unconfirmed`,
runtime was charged conservatively
(`daily.runtime_s == conservative_unattributed_runtime_s == 112.676 s`),
accounting was closed, and every zone kept its exact
`safety_record_id`/`safety_lineage_id`/`zone_history_id` (11 of 11 identical
across the restart).

What did not happen is blocker removal. §11.4 step 5 states that on OFF
confirmation the corresponding `integration_off_unconfirmed` blocker is
removed. §25 states that a startup actuator "found ON" gets that blocker plus a
defensive OFF, and that if OFF cannot be confirmed the record latches
`ACTUATOR_OFF_TIMEOUT` with a CRITICAL Repair and open accounting. The live
result is a third state that neither branch describes: the blocker was retained
while `actuator_fault` stayed `null`, no Repair was raised,
`acknowledgement_required` stayed `false`, and `open_accounting` was `false` -
yet the runtime simultaneously reported `proven_off: true` and
`off_operation: {done: true, confirmed: true}`.

Because `SlotManager` refuses every grant while the blocker set is non-empty,
this silently disables watering for the whole config entry. Verified directly:
a manual start on a completely untouched zone was refused with
`Another configured actuator is or may be flowing`.

The blocker proved unrecoverable through every available path. It survived an
entry reload (it is persisted and restored); `clear_fault` did not clear it;
`evaluate_zone` did not clear it; and supplying fresh terminal OFF evidence for
the exact record - an external ON followed by an external OFF - correctly added
and then removed only the `external_flow` key while leaving
`integration_off_unconfirmed` in place. That last result is a positive
confirmation of the keyed per-record, per-reason independence §21 and ER8
require, and it isolates the defect precisely.

The mechanism is visible in `runtime.py::_reconcile_active_record`: on
`assessment.proven_off` it removes `ACTUATOR_NOT_PROVEN_OFF` and `EXTERNAL_FLOW`
but deliberately never `INTEGRATION_OFF_UNCONFIRMED`, and it only clears
`possible_flow_owner` when that blocker is already absent. The only removal
sites are the two session-termination transitions in `state_machine.py`, which
cannot fire for a record whose session no longer exists after a restart.

The trigger generalises beyond synthetic entities and is, if anything, more
likely with real hardware. The blocker is added because the actuator could not
be confirmed OFF at the moment startup recovery finalized the interrupted
session; the session summary records exactly that, with
`runtime_estimation_reason: off_unconfirmed`. A template switch is briefly
unavailable while it and its backing helper initialise after a restart. Real
MQTT, Zigbee, and Wi-Fi valves are routinely unavailable for far longer after a
Home Assistant restart, so they would hit the same window at least as often.

The behaviour is fail-closed and therefore safe: no unsafe ON is possible. It
is nevertheless an availability defect of real consequence, because Home
Assistant restarts are routine and a restart that interrupts any session leaves
the integration permanently unable to water with no fault, no Repair, and no
documented operator remedy.

### F2 - an actuator rename is untracked and silently invalidates the ON gate entry-wide

**Disposition: implementation defect against existing spec.4. RESOLVED
2026-08-25.** See A3, finding A3-1, and *Remediation* below.

### F3 - a rename that outlives a reload fails the entire entry, not just its zone

**Disposition: implementation consequence of F2, not an independent defect.
RESOLVED 2026-08-25.** Root-cause analysis showed one cause for both: the
immutable snapshot builder resolved the configured actuator by entity ID only.
F2 is that gap observed while the entry stays loaded; F3 is the same gap
observed after a reload, where the unresolvable reference additionally reaches
the identity-conflict classification. See A3, finding A3-2, and *Remediation*
below.

## Remediation - 2026-08-25

### Specification review

| Finding | Determining spec.4 rule | Classification |
|---|---|---|
| F1 | §11.3 step 5 ("on confirmation, persist `off_confirmed_at_utc`, close accounting, release the zone's slot, and remove only the corresponding `integration_off_unconfirmed` blocker") together with §21 ("Release of that blocker is allowed only when the actuator is observed terminal OFF/closed") and §25.2. T48 restart recovery finalizes on exactly that confirmed-OFF evidence, so the release is already required | Implementation defect |
| F2 | §6 ("Actuator durable identity … the last-known entity ID is resolution/display metadata"), §23.2 item 1 ("If that exact registry entry now has a renamed entity ID, it is the same actuator; update `last_known_entity_id` only after verified resolution"), §25.1.1 bullet 1, §35.11, §40 and I35. §14 T21/T39 fire on "configuration change termination (reconfigure or deletion reconciliation)", which a Registry rename is not | Implementation defect |
| F3 | Same rules as F2, plus §25.1.1's ordered resolution and §25.5 item 8 fail-closed rule for genuine ambiguity | Consequence of F2 |

`SPECIFICATION.md` was **not** changed. No new normative ID, invariant, or
transition was created; the totals remain 134 / 37 / 59.

### F1 root cause and fix

`state_machine.py::_startup_persisted_watering` adds
`AddBlocker(INTEGRATION_OFF_UNCONFIRMED)` for a startup actuator found ON or
unproven, and requests the defensive OFF. When that OFF confirms, the decision
lands on `_finalize_watering` (row T48). `_finalize_watering` persisted state,
released the slot and emitted `session_finished`, but — unlike
`_finalize_soaking_external` (T33) and `_close_open_accounting` — it never
emitted the matching `RemoveBlocker`. The key therefore outlived the exact
terminal-OFF proof that §11.3 step 5 says releases it, and because the session
was cleared at the same moment no later event could reach a removal site.

The fix adds `RemoveBlocker(BlockerReason.INTEGRATION_OFF_UNCONFIRMED)` to the
confirmed-OFF finalization in `_finalize_watering` and `_finalize_manual_complete`,
positioned exactly where `_close_open_accounting` already places it. Removal is
exact-key and idempotent, so unrelated reasons and other records are untouched,
T49's unproven-OFF branch still retains the key, and `ACTUATOR_OFF_TIMEOUT`
acknowledgement semantics are unchanged.

### F2/F3 root cause and fix

`runtime.py::_build_immutable_snapshot` resolved each configured entity with
`registry.async_get(config.actuator)` alone. After a rename that call returns
`None`, so the snapshot lost the durable UUID; the zone and entry fingerprints
moved, the §11.2 final gate failed `current_entry_snapshot_matches`
entry-wide (F2), and on reload `_same_actuator` and the textual-conflict check
classified the same record as an identity conflict, failing setup (F3).
`ActuatorAdapter` also installed no Entity Registry listener at all, so the
runtime never followed the rename.

The fix makes durable identity the resolution authority:

- resolution is UUID-first. A record's persisted `registry_entry_id` is honoured
  as a hint only while the subentry still stores the exact configured reference
  that produced it, so a genuine A -> B reconfiguration still resolves
  independently;
- `ImmutableZoneSnapshot` now separates the *configured* subentry reference
  (which alone enters `config_fingerprint`, making a rename a non-change) from
  the *current* addressable entity ID, which follows the verified rename and
  becomes `actuator_identity.last_known_entity_id` per §23.2 item 1;
- `ZoneController` installs `async_track_entity_registry_updated_event` for the
  actuator and wires the moisture adapter's existing rename hook. On a rename it
  verifies the candidate against the stored durable UUID, then re-points the
  adapter, the state listener and its configuration, subscribing to the new
  entity ID *before* unsubscribing the old one so no ON/OFF state change and no
  removal of the old state object is missed or misread;
- if the candidate does not resolve to the stored UUID, nothing is re-pointed
  and ordinary fail-closed reconciliation owns the outcome;
- a configured reference that has been taken over by a *different* durable
  identity while the stored one still exists is explicit ambiguity: the record
  and all candidates are retained, admission closes, and the exact-record
  `actuator_identity_conflict` Repair is raised (§23.2 item 3, §25.5 item 8);
- a resolved incident now clears its exact-record Repair even after a reload,
  which closes the 2026-08-24 observation that the conflict Repair did not
  auto-clear on recovery.

### Two further defects found by the remediation live run

Both were exposed by re-running the live rename with the fix in place, and both
are the same fail-closed family as F1 — a keyed blocker with no reachable
release path.

1. **`external_flow` on an integration-owned session.** The final actuator
   re-read in `_apply_configuration_snapshot` labelled any actuator observed ON
   as `external_flow`, without §11.4's "genuinely non-session IDLE or DISABLED"
   condition that `_reconcile_active_record` already applies. Reconciliation
   triggered by a rename during WATERING therefore relabelled the zone's own
   flow as external, and that key could not be released by this record's own OFF
   evidence. Observed live: after a normal `user_stop` with the actuator proven
   OFF, `external_flow` remained and `possible_flow_owner` stayed `external`.
   The branch is now guarded by the same session condition.
2. **`actuator_not_proven_off` released only on a transition.**
   `_async_actuator_change` released that key only when
   `assessment.proven_off and not previous.proven_off`. A key added while the
   actuator was momentarily unobservable — exactly the window a rename creates —
   could therefore survive indefinitely if no fresh OFF *transition* followed.
   §21 and §25.4 key the release on observed terminal OFF, not on a transition,
   so the removal is now performed on the evidence and the transition guard is
   retained only for the `ExternalActuatorOff` dispatch that genuinely needs it.

### F1 live regression - 2026-08-25

Two synthetic zones were created, each with its own source-verified template
switch backed only by an `input_boolean`, plus template moisture sensors.

| Step | Result |
|---|---|
| Active session | `SoilSync F1 Zone` bounded synthetic MANUAL session; `switch.soilsync_f1_valve` ON; store recorded `state: watering` with a live session |
| Unrelated blocker present | `switch.soilsync_f2_valve` was turned ON **externally** while its zone was IDLE, giving record `481718a1…` an `external_flow` key |
| Restart | `docker kill --signal=SIGKILL` followed by start, i.e. a genuinely unclean restart; the store came back with `last_clean_shutdown_run_id: null` |
| No resume | Controller `idle`, no session; `on_calls` unchanged; I13 held |
| Actuator OFF | `switch.soilsync_f1_valve` `off`, `proven_off: true` |
| Accounting | `restart_recovery`, `runtime_s 324.78`, `runtime_estimated: true`, `runtime_estimation_reason: off_unconfirmed`, `open_accounting: false`, `last_session_end_utc` set, daily runtime charged (cumulative 649.75 s over the two restart runs) |
| Blocker before | Added by startup recovery on record `bdcb2d97…` while the actuator was not proven OFF |
| Blocker after | **Removed.** `blocker_reasons: []`, `possible_flow_owner: null`, SlotManager blocker set free of that key, read back from the persisted Store |
| Unrelated blockers | Record `481718a1…` kept **both** `external_flow` and `actuator_not_proven_off`. One record's OFF evidence cleared nothing belonging to another record or reason |
| Subsequent grant | After the second actuator was proven OFF externally, both records cleared and a **new** bounded synthetic manual session was granted and ran normally on `SoilSync F1 Zone` |
| Faults / Repairs | None at any point; `actuator_fault: null`, zero SoilSync Repairs |
| Evidence class | `LIVE HOME ASSISTANT WITH SYNTHETIC TEST ENTITIES` |
| Status | `PASS` |

The transition ring buffer recorded the decisive event directly:
`OffConfirmed` at `23:05:22Z` with `reason: restart_recovery`, which is the T48
row the fix changes.

### F2 live regression - 2026-08-25

Recorded in full in **A3 remediation re-validation** above. `PASS`.

### F3 live regression - 2026-08-25

| Step | Result |
|---|---|
| Renamed state | `switch.soilsync_f1_valve_renamed` left in place; the subentry still stored `switch.soilsync_f1_valve` |
| Reload | Supported `config_entries/reload`. Entry returned `loaded`; **no** `setup_retry` |
| Repair state | No `actuator_identity_conflict`; zero SoilSync Repairs |
| Identity continuity | Same `safety_record_id` `bdcb2d97…`, `safety_lineage_id` `474abd29…`, `zone_history_id` `9de33327…`, Registry UUID `c314f72e…`, `registry_confirmed`, `identity_incident: null`; exactly two safety records, i.e. no second record was created |
| Budget/history | Daily runtime 816.40 s and `last_session_end_utc` preserved across the reload |
| Restart | Full container restart with the rename still in place: startup resolved the same Registry UUID from the durable record, kept every ID, preserved the budget, and a further bounded synthetic manual session ran to `manual_complete` (45.01 s measured) |
| Restore | Original entity ID restored and verified with all durable IDs and the accumulated budget intact |
| Evidence class | `LIVE HOME ASSISTANT WITH SYNTHETIC TEST ENTITIES` |
| Status | `PASS` |

### Remediation cleanup

- **Zero physical irrigation ON or open commands were issued.** Every SoilSync
  ON command targeted a temporary `template` switch whose stored configuration
  was read back from the live config store and contains only
  `input_boolean.turn_on`/`turn_off` against its own dedicated backing helper,
  with no device. Empirically, a full 1685-entity before/after state diff around
  a deliberate ON and OFF of that switch showed the switch and its backing
  helper as the only causally related changes; no irrigation entity of any
  domain changed.
- The one real physical moisture sensor was not used, referenced, or written to
  in the remediation run.
- Both synthetic zone subentries were deleted through the native supported
  websocket path and retired cleanly: both tombstones `retired`, no blockers, no
  faults, no acknowledgement requirement, no identity incidents.
- The SoilSync config entry, all four temporary `template` helper entries, and
  all three temporary input helpers were removed. Verified end state: 0 SoilSync
  config entries, 0 SoilSync devices, 0 SoilSync registry entities, 0 SoilSync
  Repairs, and no ON irrigation switch or valve anywhere in the instance.
- The Entity Registry rename was restored before cleanup and verified.
- Home Assistant is healthy. The only ERROR lines in the window belong to
  unrelated pre-existing integrations; SoilSync logged no error at all.
- SoilSync intentionally remains installed. The remediation candidate was
  deployed by replacing `/config/custom_components/soilsync` from the exact
  working tree (verified by matching MD5 sums). The previously installed HACS
  build is retained outside Home Assistant's integration scan path at
  `/opt/docker/homeassistant/soilsync-backups/` as a rollback copy; HACS still
  records the older commit, so a normal HACS update will restore its own
  bookkeeping once the fix is published.
- Runtime Store files for removed config entries remain in `.storage` as inert
  orphans, as they did before this run. They are referenced by no config entry,
  and this project does not hand-edit or delete Home Assistant `.storage` data.

## Phase B - Physical-water validation

Phase B requires known-safe physical irrigation hardware, actual flow, an
explicit operator water checkpoint, manual stop/fallback, and separate
authorization. B1 was authorized and attempted on 2026-08-25, then aborted and
marked blocked when the deployed controller's Home Assistant integration did
not expose a real actuator transition or confirm physical flow. B2 was not
authorized and remains not started.

### B1 Physical valve matrix

| Field | Record |
|---|---|
| Date/environment | 2026-08-25; Home Assistant Core 2026.7.2 `RUNNING`; SoilSync 0.1.0 candidate actuator adapter, manifest, and config flow byte-identical between the live container and local HEAD `275cf0aa83be1677223c92aef0d046f3bbd1ee13` |
| Physical actuator | Real Tuya four-channel irrigation controller, exposed by the Tuya integration as one literal HA `valve`; available, initial `closed`, `is_closed: true`, water device class, supported features 3 (OPEN/CLOSE), no `current_position` |
| Hardware failsafe | A sibling duration/countdown entity exposed 0-86400 s and read 0. HA accepted a request for 60 s while closed, but the entity remained 0 with no transition. No hardware timeout was therefore established or claimed |
| Operator checkpoint | `PROCEED B1 WATER` was received before any possible physical OPEN. The missing countdown materially changed the conditions, testing paused while still closed, and `PROCEED B1 WATER WITHOUT COUNTDOWN` was received before the first OPEN |
| Observer | Authenticated Home Assistant WebSocket `state_changed` observer connected and recording before command; REST used for service invocation support and independent terminal-state reads |
| T0 / service result | OPEN sent at `2026-08-25T08:31:25.131893Z` from proven `closed`; HA returned successful service acceptance at `08:31:26.410064Z` (1.278 s). Service acceptance is not terminal actuator acknowledgement |
| T1 / T2 | No actuator response, transitional state, or state-change event. No terminal `open`. The HA entity remained `closed` for the complete 30 s confirmation window |
| T3 / T5 | Safety CLOSE sent at `08:31:55.137240Z`; the first fallback call returned HTTP 200 and an independent read about 0.75 s later was `closed`, `is_closed: true`, with the unchanged pre-trial `last_changed` timestamp. A reinforcing CLOSE later produced the same result. This is terminal-closed HA evidence, not a measured physical-flow shutdown latency |
| Physical observation | The operator could not confirm that any outlet produced water. Actual water start and stop are therefore `NOT VALIDATED`; no `LIVE PHYSICAL` flow claim is made |
| SoilSync manual session | `NOT VALIDATED`; not started after the physical actuator failed to acknowledge OPEN |
| External physical flow | `NOT VALIDATED`; not attempted after abort |
| Transitional states / position | `NOT VALIDATED` live in B1. The deployed entity exposed neither transitions nor position, and the planned synthetic gap matrix was not started after the physical abort |
| Unknown / unavailable | Recorder showed natural availability interruptions only while the entity was closed; this did not validate physical flow semantics. No deliberate physical disconnect occurred |
| Confirmation timing | OPEN terminal confirmation timed out at the unchanged 30 s default. No physical ON or OFF latency exists because flow was not confirmed. This deployment evidence does not warrant changing SoilSync's default |
| Serialization | `NOT VALIDATED`; no confirmed physical flow existed to occupy the global slot |
| Defect classification | Deployment integration/hardware-exposure blocker, not a SoilSync defect and not a spec.4 contradiction |
| Evidence class | `LIVE HOME ASSISTANT` for registry/platform/service/state evidence; selected real hardware but physical water `NOT VALIDATED` |
| Status | `[!] Blocked` pending a confirmed-working HA integration for the physical controller, followed by a fresh B1 authorization/checkpoint |
| Cleanup | No second OPEN. Because physical flow could not be observed, the operator used the Tuya app fallback and confirmed the controller disabled/stopped. A final API read found the selected valve terminal `closed`, duration 0, zero open valves, zero SoilSync config entries, and HA healthy. The helper was off, both briefly paused automations were restored on, no SoilSync session/blocker/fault/accounting or synthetic entity existed, and the observer was stopped |

### B2 Active-flow shutdown OFF timing

| Field | Record |
|---|---|
| Prior context | A legitimate Docker host-control path was previously confirmed, but no safe active physical flow was established and no T0-T4 timing exists |
| Required future evidence | SoilSync-owned physical flow, actual HA/container shutdown, measured shutdown-to-proven-OFF timing, bounded fallback, restart, and no-resume behavior |
| Relationship to this run | The Phase A restart-survival test restarted Home Assistant during an active **synthetic** session. That is Phase A restart survival and is explicitly **not** B2 evidence: there was no physical flow and no shutdown-to-proven-OFF timing was measured on hardware |
| Evidence class | `NOT VALIDATED` |
| Status | `[ ] Not started` |
| Cleanup | No shutdown of physical irrigation, and no physical water command, occurred |

## Current cleanup inventory

- The 2026-08-25 B1 run issued exactly one direct HA OPEN service call to the
  selected physical valve after the two explicit operator authorizations. HA
  accepted the service but the entity never left `closed`, and the operator
  could not confirm water. No SoilSync physical ON command or session occurred.
- The B1 safety CLOSE and a reinforcing CLOSE were accepted and independently
  read terminal `closed`. Two potentially related automations were briefly
  paused before the attempted OPEN and restored to their original enabled
  state after abort; their helper remained off. The operator also used the Tuya
  app fallback and confirmed the physical controller disabled/stopped. A final
  read found the selected valve `closed`, zero open valves, and Home Assistant
  healthy.
- The one real physical moisture sensor was read only. It was never
  reconfigured, renamed, or written to.
- All synthetic watering was stopped. Every synthetic actuator finished `off`.
- The Entity Registry rename was fully restored to its original entity ID and
  verified.
- All temporary SoilSync zones, including the ten scale zones, were removed
  together with the SoilSync config entry that owned them, so no test-only
  safety record, tombstone, blocker, fault, or Repair remains in the runtime
  Store.
- The temporary synthetic helpers created for the run were removed at closeout.
- The live observer was stopped and left no artifact on the Home Assistant
  instance.
- Home Assistant remained healthy: entry state `loaded` whenever the
  integration was configured, and no SoilSync-related error in the system log
  other than the deliberately induced identity conflict recorded in A3.
- SoilSync intentionally remains installed through HACS, as permitted.

Verified end state at closeout, read back from the live instance:

| Check | Result |
|---|---|
| SoilSync config entries | 0 |
| SoilSync devices | 0 |
| SoilSync registry entities | 0 |
| Temporary `SoilSync Test Valve` template entries | 0 |
| Temporary backing `input_boolean` helpers | 0 |
| Temporary synthetic moisture sensor states | 0 |
| Open Repairs of any domain | 0 |
| Home Assistant | `RUNNING`, 2026.7.2 |
| HACS SoilSync | still `installed` at `dcf9036`, intentionally retained |
| Real physical moisture sensor | unchanged at 43 %, `last_reported` still its own 10:18:20 value, never written to |

The only remaining SoilSync-matching entity is `update.soilsync_update`, which
is HACS's own update entity for a downloaded repository. It is a normal
consequence of leaving SoilSync installed, not a test artifact, and it is
correct for it to exist.

### A5 continuation cleanup - 2026-08-25

- **Zero physical irrigation ON or open commands were issued.** The only ON
  command in the run was the single AUTO pulse and one deliberate proof ON/OFF,
  both against a `template` switch whose stored configuration targets nothing but
  its own dedicated `input_boolean`.
- The one real physical moisture sensor was read only for the entire run. It was
  never written to, renamed, reconfigured, or replaced, and no synthetic value was
  ever pushed to it.
- Both zone subentries were removed through the supported native websocket
  deletion path and retired cleanly; the log shows exactly the two expected
  `retained as retired after configuration removal` notices and nothing else.
- The SoilSync config entry, both temporary `template` switch entries, and both
  temporary `input_boolean` helpers were removed.
- `custom_components.soilsync` logging was returned to `warning` through the
  supported `logger.set_level` action.
- The temporary read-only observer component was deleted and its JSONL output
  moved off the Home Assistant instance. `configuration.yaml` was restored from
  the pre-run backup and verified **byte-identical** by MD5
  (`c914d27a80e6dba89a8808d75ac18757` both sides).
- One restart was performed after T_end to unload the observer. The system log
  after it contains **zero** `a5observer` references and zero SoilSync errors.

Verified end state, read back live at `2026-08-25T06:03:15Z`:

| Check | Result |
|---|---|
| Home Assistant | `RUNNING`, Core 2026.7.2 |
| SoilSync config entries | 0 |
| SoilSync devices | 0 |
| SoilSync registry entities | 0 |
| Temporary A5 `template` switch entries | 0 |
| Temporary A5 `input_boolean` helpers | 0 |
| Any entity matching the temporary A5 fixture | 0 |
| Open Repairs, all domains | 0 |
| Open SoilSync Repairs | 0 |
| Valves in `open` state | 0 |
| Irrigation-matching switches `on` | 0 |
| Real physical moisture sensor | unchanged at 41 %, never written to |
| Temporary observer component / its output file | removed from the instance |
| `configuration.yaml` | byte-identical to the pre-run backup |
| HACS SoilSync | still installed, intentionally retained |

The only remaining SoilSync-matching entity is `update.soilsync_update`, which is
HACS's own update entity for a downloaded repository. It is a normal consequence
of leaving SoilSync installed, not a test artifact.

Two `soilsync` rows dated 2026-08-24 remain in the stored
`repairs.issue_registry` file from the earlier remediation run. Both are
`is_persistent: false`, so Home Assistant does not restore them into the active
issue set across a restart; the live Repairs list read back after this run's
restart contains **0** issues in total. They are inert file residue, not open
Repairs.

## Current slice verdict

`[~] PARTIAL`.

**Phase A is complete.** A1, A2, A4, and A6 are `PASS` on live evidence. **A3 is
`PASS`**: durable Registry identity retention passed on 2026-08-24, and after the
2026-08-25 remediation the live rename, reload-while-renamed,
restart-while-renamed, post-rename watering, and restore cases all pass with
unchanged durable identity, no false `CONFIG_CHANGED`, and no Repair, so every
§46 item 3 requirement has live evidence. **A5 is now `PASS`**: the 2026-08-25
continuation obtained a clean, restart-free continuous window of 10790.773987 s
(2.9974 h) on the deployed physical sensor, proved live that SoilSync freshness
is derived from the genuine report timestamp plus exactly 7200 s and never from
scan, callback, or evaluation time, and settled the §46 item 6 default question
against a 10.34 day Home Assistant corpus and a 22.9 h transport corpus. That
assessment is `CONTRADICTED` for this deployment and the root cause is identified
to Core source level. The final product decision retains the 7200 s default and
uses documentation/upstream Home Assistant report visibility as the mitigation;
no SoilSync runtime or specification change was made.

Findings F1, F2, and F3 are `RESOLVED` as implementation defects against
existing spec.4, fixed, covered by deterministic automated regression, and
re-validated live. The 2026-08-25 A5 continuation produced no new SoilSync
defect and no specification contradiction.

Phase A therefore closes `[x] Complete`. B1 is `[!] Blocked` pending a
confirmed-working Home Assistant integration for the physical irrigation
controller and a fresh physical-water checkpoint. B2 remains `[ ] Not started`
and separately unauthorized. Phase B is blocked at B1, and Slice 13 remains
`[~] Partial`.
