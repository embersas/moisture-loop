# Moisture Loop prototype-validation evidence

This document is the development evidence ledger for the seven real-world
prototype validations required by `SPECIFICATION.md` §46. Automated tests,
mocks, and source inspection are supporting context only and are never counted
as prototype evidence here.

The live host, credentials, full Entity Registry identifiers, and household
entity names are intentionally omitted from this public document. Exact local
identifiers are retained only for the duration of the operator-controlled test
where they are needed for before/after comparison.

## Evidence classes

- `LIVE PHYSICAL`: observed on deployed physical equipment.
- `LIVE HOME ASSISTANT`: observed in the real Home Assistant deployment.
- `LIVE HOME ASSISTANT WITH SYNTHETIC TEST ENTITIES`: observed in the real
  deployment using isolated temporary Home Assistant entities.
- `NOT VALIDATED`: the required live or physical observation does not yet
  exist.

## Environment baseline

| Field | Evidence |
|---|---|
| Validation date | 2026-08-23 (Australia/Brisbane) |
| Home Assistant | Core 2026.7.2, Home Assistant Container on Docker with host networking |
| Moisture Loop candidate | 0.1.0 at `43f24b12fc162412b534851b9c1b3762ca57cd98` |
| Candidate installation at baseline | Not installed; no duplicate `custom_components/moisture_loop` directory and no config entry |
| HACS | 2.0.5; the operator confirmed the real Custom repositories dialog is available |
| Backup | A recent full Home Assistant backup predating the prototype work was confirmed |
| Access | Authenticated operator UI plus legitimate SSH/Docker host control; no credential is recorded here |
| Public-source baseline | Public `main` and the local candidate were the same SHA; all six GitHub-hosted checks passed that SHA |

Read-only inventory found one deployed valve entity, deployed irrigation
switch entities, and a deployed soil-moisture sensor. Every identified
irrigation actuator was unavailable at the inventory time. No actuator command
was issued and no physical-flow checkpoint has yet been passed.

## 1. Real Home Assistant UI/UX lifecycle

| Field | Record |
|---|---|
| Date/time | Began 2026-08-23 |
| HA / candidate | HA 2026.7.2; Moisture Loop 0.1.0 candidate SHA above |
| Entities/hardware | None created yet |
| Preconditions | Real HA frontend reachable; HACS 2.0.5 available; no pre-existing Moisture Loop installation |
| Procedure | Operator opened HACS Integrations and its Custom repositories dialog in the authenticated real UI. The operator was then asked to add the public repository as category Integration and report the visible result. No controllable in-app or Chrome browser session was available to Codex. |
| Observed result | HACS version and Custom repositories availability were confirmed by the operator. The repository-add result was not provided before run closeout, and read-only live inventory confirmed the repository/component remained absent. No API or harness observation is substituted for the remaining UI lifecycle. |
| Evidence references | Operator observation; live component/config-entry inventory |
| Status | `BLOCKED` |
| Evidence class | `NOT VALIDATED` |
| Cleanup | No HA configuration or watering change had been made at this checkpoint. |

The controller/zone lifecycle, validation errors, actions, native deletion,
tombstone/Repair visibility, diagnostics, reload, restart, same-actuator
re-add, A-to-B replacement, and active-flow deletion cases remain unvalidated.

## 2. Physical valve matrix

| Field | Record |
|---|---|
| Date/time | Inventory 2026-08-23 |
| HA / candidate | HA 2026.7.2; candidate not installed at inventory time |
| Entities/hardware | One deployed `valve` entity and separate deployed irrigation `switch` entities, identifiers generalized |
| Preconditions | Physical identity, safe zone, manual shutoff, interference controls, and operator water checkpoint are required before any ON command |
| Procedure | Read-only Entity Registry, device, Recorder-state, and automation-reference inventory only |
| Observed result | All identified irrigation actuator candidates were unavailable. Existing unrelated irrigation automations/scripts were identified and remained unchanged. No physical state sequence or OFF proof was attempted. |
| Timestamps | Latest inventory on 2026-08-23; historical unavailable observations were present in Recorder |
| Evidence references | Live Entity Registry/device/Recorder inventory |
| Status | `BLOCKED` |
| Evidence class | `NOT VALIDATED` |
| Cleanup | No command, water flow, automation change, or test state to revert |

The physical `opening`/`open`/`closing`/`closed`, position, availability,
delayed acknowledgement, ownership, external-interference, and blocker matrix
remains outstanding. A physical switch result, if later obtained, will be
reported separately and will not be claimed as valve-position evidence.

## 3. Real Entity Registry rename

| Field | Record |
|---|---|
| Date/time | Not run |
| HA / candidate | HA 2026.7.2; candidate not installed at inventory time |
| Entities/hardware | A safe live test entity will be selected after zone creation |
| Preconditions | Installed/configured integration and complete before-state identity/lineage/history capture |
| Procedure | Pending supported real Entity Registry rename and reverse rename |
| Observed result | No mocked or file-edited Registry evidence is accepted |
| Status | `BLOCKED` pending integration setup |
| Evidence class | `NOT VALIDATED` |
| Cleanup | None required yet |

## 4. Real shutdown OFF timing

| Field | Record |
|---|---|
| Date/time | Host-control inventory 2026-08-23; flow test not run |
| HA / candidate | HA Container 2026.7.2; candidate not installed at inventory time |
| Entities/hardware | Known-safe physical irrigation actuator not yet established |
| Preconditions | Available physical actuator, manual water fallback, unrelated-automation control, synchronized observation, and explicit physical-flow checkpoint |
| Procedure | Verified legitimate Docker-host control exists; did not substitute an integration reload or container inspection for the required real shutdown test |
| Observed result | The actual deployment shutdown path is available, but no active physical flow can safely be established while all candidate actuators are unavailable. No T0-T4 timing exists yet. |
| Status | `BLOCKED` |
| Evidence class | `NOT VALIDATED` |
| Cleanup | No shutdown and no water command occurred |

## 5. Approximately ten simultaneously-dry zones

| Field | Record |
|---|---|
| Date/time | Not run |
| HA / candidate | HA 2026.7.2; candidate not installed at inventory time |
| Entities/hardware | Planned isolated live-HA template sensors and ten unique synthetic actuators |
| Preconditions | Installed integration and temporary entities isolated from household automation |
| Procedure | Pending ten-zone FIFO/slot/fairness exercise in live HA |
| Observed result | No mock or automated scheduler result is accepted as this evidence |
| Status | `BLOCKED` pending integration setup |
| Evidence class | `NOT VALIDATED` |
| Cleanup | No temporary scale entities created yet |

## 6. Deployment sensor cadence/default

| Field | Record |
|---|---|
| Date/time | Historical window and live observation begun 2026-08-23 |
| HA / candidate | HA 2026.7.2; Moisture Loop candidate default `sensor_max_age` is two hours |
| Entities/hardware | Deployed Zigbee/MQTT soil-moisture sensor; entity identifier generalized |
| Preconditions | Sensor available with numeric percentage state; runtime remains independent of Recorder |
| Procedure | Queried seven days of live Recorder history for changed-state/availability evidence, then subscribed read-only to the sensor's existing Zigbee2MQTT report topic to observe unchanged reports that Recorder history cannot prove. The direct observer was stopped at closeout because the remaining UI checkpoint was not completed. |
| Observed result | Recorder: 198 rows, 196 numeric changed rows, two availability rows, 193 within-availability intervals; median 870.742 s, p90 5012.61 s, longest observed within an availability segment 79464.4 s. Recorder had no consecutive equal numeric rows. Direct observation ran for 4951.476 s (82.525 min), captured 20 MQTT messages in eight report bursts, and included six consecutive unchanged-soil transitions. Burst-gap median was 994.638 s and maximum was 1116.047 s; two rapid gaps were about 30 s. Observed soil values were 31% and 30%. |
| Timestamps | Direct observer began 2026-08-23 09:37:07.168Z; first burst 09:40:07.487Z; last burst ended 10:59:38.644Z |
| Evidence references | Live Recorder database and credential-redacted read-only MQTT observation |
| Status | `PARTIAL` |
| Evidence class | `LIVE PHYSICAL` |
| Cleanup | Observer process was stopped and its exact temporary host log removed after summary extraction |

No default change is justified by this sample. The direct sample shows normal
unchanged reports and an observed maximum burst gap far below two hours, while
the Recorder history shows that changed-state rows alone can be separated by
more than two hours. A continuous direct observation longer than the two-hour
default is still required before declaring the item complete.

## 7. HACS/brand presentation

| Field | Record |
|---|---|
| Date/time | Began 2026-08-23 |
| HA / candidate | HA 2026.7.2; HACS 2.0.5; candidate SHA above |
| Entities/hardware | Real HACS frontend and public repository |
| Preconditions | No pre-existing Moisture Loop directory/config entry; custom repositories supported |
| Procedure | Operator opened the real HACS Custom repositories dialog and was asked to add the public repository as category Integration. Codex had no controllable browser session. |
| Observed result | Custom-repository capability is confirmed. At closeout, read-only live HACS storage still did not contain the repository and the component directory was absent; card presentation, README/icon/version, download/install/update, restart, and post-restart discovery were therefore not observed. |
| Evidence references | Operator UI observation; read-only HACS/component inventory |
| Status | `PARTIAL` |
| Evidence class | `LIVE HOME ASSISTANT` |
| Cleanup | Nothing installed or changed at this checkpoint |

No HACS default-store submission, `home-assistant/brands` submission, GitHub
Release, version bump, or release tag has occurred. Centralized Brands
submission remains outside this Slice 13 authorization.

## Current cleanup inventory

- No watering command has been sent; physical actuators remain uncommanded.
- No temporary zone, helper, Entity Registry rename, or automation disable has
  yet been created.
- The bounded, read-only cadence observer was stopped and its temporary host
  log was removed after extracting the aggregate evidence above.
- Home Assistant remains in normal operation.

## Current slice verdict

`[~] PARTIAL` — live HA/HACS baseline evidence and an initial deployed-sensor
observation exist, but none of the seven §46 items is complete yet. Physical
items remain gated by actuator availability, safe hardware identification, and
the mandatory operator water checkpoint.
