# MoistureLoop

Soil moisture-driven irrigation for Home Assistant.

MoistureLoop pairs one soil-moisture sensor with one `switch` or `valve`
actuator per zone for closed-loop drip irrigation and watering. It waters in
bounded pulses, waits for water to redistribute through the soil, then requires
a fresh report made at or after the soak ends before deciding whether to pulse
again. Measured moisture is the automatic feedback signal; this is not a timer,
weather, or evapotranspiration controller.

> Requires Home Assistant 2025.9.0 or later. Older releases are not supported.

The integration is local-only and hardware-agnostic. It has no cloud account,
telemetry, API key, outbound network dependency, or Recorder safety dependency.

## How automatic watering works

Each zone has exactly one sensor and one actuator:

1. A new AUTO session can start only from `IDLE`, with the zone enabled, when
   the latest report is valid and fresh and `moisture < start_threshold`.
2. One complete pulse must fit the cycle, session, and current-day limits.
3. The actuator is closed and proven OFF, then the full soak runs.
4. Continuation or completion requires a valid, fresh report timestamped at or
   after the soak deadline. Below target, another whole pulse may run; at or
   above target, the session completes.

The comparisons are exact:

- `moisture == start_threshold` does not start a new AUTO session.
- An active AUTO session continues only while `moisture < target_threshold`.
- `moisture == target_threshold` completes the session.
- A report exactly at the soak deadline qualifies; an earlier report does not.
- A report exactly on the freshness boundary is fresh.

When an upstream integration writes an unchanged reading to Home Assistant,
Home Assistant can expose it through the entity-filtered `state_reported` path
and MoistureLoop treats it as a genuine report. Some integrations suppress
unchanged source updates before they become Home Assistant state writes;
MoistureLoop cannot treat those invisible source messages as fresh reports. A
fallback scan never invents a new report timestamp.

### Freshness and watchdogs

AUTO watering remains dependent on a current sensor report while water is
flowing. If the sensor becomes invalid or unavailable, the session stops and
the actuator follows the shared OFF path. If reports go silent, watering stops
when the newest valid report reaches its configured maximum age. A newer valid
report, changed or unchanged, replaces that deadline.

SOAKING uses a separate rule: a report before the soak ends may update the UI
but cannot decide the session. After the soak, MoistureLoop waits for a
qualifying report for at most one sensor-freshness window, then faults stale.

### Sensor freshness compatibility

MoistureLoop measures freshness from the report timestamp Home Assistant exposes.
The default Sensor Report Maximum Age is a conservative, configurable two
hours. During healthy operation, the selected moisture entity must produce Home
Assistant state writes often enough to remain within that limit, including
during long periods when the measured moisture does not change. MoistureLoop can
use changed reports and unchanged reports that Home Assistant actually exposes,
but it cannot infer a physical heartbeat that the upstream integration hides.
Polling or scanning the entity does not substitute for a report.

For MQTT-backed sensors, Home Assistant's MQTT sensor normally has
`force_update: false`. If unchanged MQTT payloads are suppressed and do not
advance the moisture entity's report timestamp, configure the MQTT entity or
source so healthy unchanged reports produce Home Assistant state writes. Where
appropriate, `force_update: true` is one way to do this; it is not a MoistureLoop
requirement or a universal recommendation. Consider the source update rate and
system impact before forcing every update. See the official
[Home Assistant MQTT Sensor documentation](https://www.home-assistant.io/integrations/sensor.mqtt/).

## Safety model

- Watering commands are globally serialized: at most one integration-commanded
  zone flows at a time.
- An actuator observed or conservatively believed to be flowing blocks every
  new integration ON, including flow started outside MoistureLoop.
- External flow outside a session is respected and is not counter-commanded;
  it blocks the shared resource until that exact actuator is proven OFF.
- Every AUTO pulse must fit in full. No partial trailing pulse is used to spend
  the last part of a budget.
- Manual watering is finite and clamped by its request, the configured manual
  maximum, session maximum, and remaining current-day budget.
- Every created session resets the minimum interval for later AUTO starts.
- WATERING never resumes after restart, crash, reload, or reconfiguration.
- Unknown watering duration is conservatively overestimated and charged to the
  affected HA-local calendar day or days.
- Safety state is written atomically and read back before an ON command. A
  missing, corrupt, future-version, or mismatched initialized Store blocks both
  AUTO and MANUAL, exhausts the detection day's budget, and raises a Repair.
- Home Assistant shutdown and entry unload close admission first and route
  possible flow through the same idempotent OFF operation. Full-process
  shutdown is owned by exactly one Home Assistant Stage-1 shutdown job, which
  Core runs and awaits while it can still write and verify safety state; a run
  is recorded as clean only after every required OFF and verified write
  succeeded.

Software cannot close mechanically failed hardware. Use a valve with a hardware
maximum runtime, a master valve, or another independent physical failsafe. If
OFF cannot be proven, MoistureLoop raises a critical Repair, retains the global
blocker, and continues conservative accounting until exact OFF evidence exists.

## Installation

The public source and documentation repository is
[`embersas/moisture-loop`](https://github.com/embersas/moisture-loop), and
problems can be reported through its
[issue tracker](https://github.com/embersas/moisture-loop/issues).

MoistureLoop is not included in the HACS default store. It can be installed as
a HACS custom repository:

1. Open HACS → Integrations → ⋮ → Custom repositories.
2. Add `https://github.com/embersas/moisture-loop` as category Integration.
3. Install MoistureLoop and restart Home Assistant.

For manual development installation, copy
`custom_components/moisture_loop/` into the Home Assistant
`config/custom_components/` directory and restart Home Assistant.

## Configure zones

1. Settings → Devices & services → Add integration → MoistureLoop.
2. Create the single controller entry.
3. On that entry, choose Add zone and select the name, sensor, actuator,
   thresholds, pulse/soak timing, and safety limits.

Each native config subentry becomes one zone device. The configured sensor must
produce a finite number from 0 through 100. A `switch` uses ON/OFF. A `valve`
must support both open and close; position-only valves are unsupported.
`opening`, `closing`, unknown, unavailable, and a nonzero reported position are
never proof of OFF.

| Setting | Default | Allowed range |
|---|---:|---:|
| Start threshold | 30% | 1–99; strictly below target |
| Target threshold | 40% | 2–100; strictly above start |
| Pulse duration | 5 min | 30 s–30 min |
| Soak duration | 20 min | 1 min–4 h |
| Maximum cycles | 4 | 1–20 |
| Maximum session runtime | 30 min | pulse duration–4 h |
| Maximum daily runtime | 60 min | pulse duration–12 h |
| Minimum AUTO session interval | 6 h | 15 min–7 d |
| Sensor report maximum age | 2 h | 5 min–24 h |
| Actuator confirmation timeout | 30 s | 5 s–5 min |
| Manual maximum duration | 30 min | 1 min–2 h |

Defaults are conservative starting points, not agronomic advice. Calibrate for
the soil, emitters, probe placement, and sensor cadence in the deployment.

### Add and reconfigure behavior

Zone creation uses Home Assistant's native subentry flow. An unchanged
reconfigure is a no-op. A changed reconfigure safely quiesces an active old
session before the new configuration is applied. Users do not need to manually
reload after add, reconfigure, or delete; configuration-flow code does not own
watering safety or reload semantics.

When the durable actuator is unchanged, its retained safety and irrigation
history continue. When actuator A is replaced by actuator B, A's possible-flow
evidence, blockers, accounting, faults, and acknowledgement remain independently
owned by A. The logical zone's conservative daily budget and minimum interval
continue onto B; B cannot clear or inherit A's actuator hazard.

### Delete a zone

A zone can be deleted through Home Assistant's normal UI or API. Core removes
the configuration subentry through its native path. From that visible removal,
MoistureLoop rejects every new ON for the zone and safely terminates an active
AUTO, MANUAL, or SOAKING session in the background. No manual reload is needed.

The zone device and entities disappear, but runtime safety evidence may remain
internally as a retained tombstone. This is deliberate:

- unresolved actuator flow, blockers, accounting, faults, and Repairs survive;
- deleting a zone never means unresolved physical-flow evidence was erased;
- delete/re-add of the same durable actuator may reuse the same retained safety
  lineage, daily runtime, minimum interval, and acknowledgement history;
- a deleted-zone Repair remains available at entry level even without the old
  zone device;
- retired tombstones are not automatically purged in v0.1.

## Entities

Each active zone exposes status, current-day watering runtime, last-session and
next-eligible sensors; watering, problem, and needs-water binary sensors; an
enabled switch; and Stop, Evaluate now, and Clear fault buttons. `needs_water`
is informational and never bypasses an AUTO guard. There is no manual-start
button because a safe manual request requires an explicit duration.

## Actions

All four actions require exactly one current MoistureLoop zone `device_id`.
Targets are checked again in the backend. Deleted, unloaded, non-active,
reconciling, failed, or otherwise unsafe runtimes are refused.

| Action | Required data | Behavior |
|---|---|---|
| `moisture_loop.start_manual_watering` | `device_id`, `duration` in seconds | Starts one explicit bounded run; may clamp or refuse it. |
| `moisture_loop.stop_watering` | `device_id` | Cooperatively stops an active session; no-op when inactive. |
| `moisture_loop.evaluate_zone` | `device_id` | Runs normal AUTO evaluation and bypasses no guard. |
| `moisture_loop.clear_fault` | `device_id` | Clears only when that fault's safety condition permits it. |

Example matching `services.yaml`:

```yaml
action: moisture_loop.start_manual_watering
data:
  device_id: abc123...  # MoistureLoop zone device
  duration: 600         # requested seconds
```

MANUAL may ignore only `SENSOR_UNAVAILABLE`, `SENSOR_STALE`, and
`SENSOR_INVALID`. Sensor changes do not stop the bounded run. It is refused for
actuator unavailable/ON-timeout/OFF-timeout faults, invalid configuration,
restored unsafe Store state, a disabled zone, an active session, an actuator
not proven OFF, an occupied global water resource, reconciliation restrictions,
an invalid duration, or an exhausted daily budget.

## Repairs, diagnostics, and recovery

Repairs cover missing current sensors or actuators, unresolved tombstone
actuators, durable identity conflicts, configuration reconciliation failure,
runtime Store integrity loss, and unconfirmed OFF. The unconfirmed-OFF Repair
is critical. Exact OFF evidence releases only that actuator's blocker and
closes its accounting; acknowledgement remains separate and cannot clear a
different retained record.

Download diagnostics from the MoistureLoop config entry. They include Store
schema/run integrity, configuration-application state, active and retained
safety records, durable identities, blockers, sessions/accounting, current
observations, and recent transitions with identifiers redacted or shortened as
appropriate.

Do not delete files from `.storage` and do not manually edit Store data. Restore
the exact entity identity, prove the physical actuator OFF, reconfigure the zone,
or use the offered Repair flow as instructed. If watering refuses to start,
check sensor freshness, actuator OFF/availability, Repairs, daily budget,
minimum interval, and external flow before trying again.

### Troubleshooting `SENSOR_STALE`

First inspect the moisture entity's `last_reported` timestamp and, where
possible, compare it with the upstream integration or physical device's actual
reporting cadence. A stale fault can mean either that the sensor genuinely
stopped reporting or that source reports continued while unchanged updates were
suppressed before reaching the Home Assistant entity. If the source remains
healthy but `last_reported` does not advance, correct the upstream entity
configuration instead of treating a larger MoistureLoop timeout as the first fix.
For MQTT sensors, `force_update: true` is one possible integration-specific
remedy, not a general requirement. A different Sensor Report Maximum Age remains
available within the configured range when the sensor's legitimate observable
cadence requires it.

The integration also emits `moisture_loop_session_started`,
`moisture_loop_session_finished`, `moisture_loop_fault_set`, and
`moisture_loop_fault_cleared` events.

## Known limitations and validation status

v0.1 intentionally has no weather/ET input, calendar scheduling, flow meter,
leak measurement, tank interlock, shared-pump model beyond global serialization,
multi-sensor/multi-actuator zone, stuck-sensor detection, adaptive learning, or
unbounded manual watering.

Automated mocked-time implementation evidence is not physical deployment
validation. Status of the seven SPECIFICATION.md §46 / Slice 13 validations:

1. Real Home Assistant UI/UX lifecycle validation — **validated** on a live
   Home Assistant deployment using synthetic actuators.
2. A physical valve state/availability/position matrix — **validated / PASS**
   on real irrigation hardware exposed as a Home Assistant `valve`, with the
   remaining transitional/position/availability cases covered by clearly
   labelled synthetic entities.
3. A real entity-registry rename trial — **validated** live, including rename
   during an active session, reload and restart while renamed, and restore.
4. Measured physical shutdown OFF timing — **validated / PASS**. A first trial
   on 2026-08-26 was stopped by finding B2-1, a lifecycle defect in the
   then-current specification; `0.1.0-spec.5` moved full-process shutdown
   ownership to a single Home Assistant Stage-1 shutdown job. On the corrected
   implementation, a physical active-flow trial proved shutdown-path terminal
   valve CLOSED 1.36 s after a normal external container stop — inside both the
   8-second internal budget and the 10-second external stop window — with
   runtime measured rather than estimated and the run recorded clean.
5. Approximately ten simultaneously dry zones in a deployment-scale exercise —
   **validated** live with ten synthetic zones.
6. Deployment sensor-cadence/default validation — **validated / PASS**. A clean
   2.9974-hour window showed that physical cadence supports the two-hour horizon
   while the tested default MQTT-to-Home Assistant entity presentation can
   suppress unchanged writes. The compatibility requirement is documented and
   the conservative two-hour default is retained.
7. HACS/brand presentation — **validated** for custom-repository install and
   presentation; the centralized `home-assistant/brands` submission is
   deliberately not made.

All seven prototype validations now have live evidence, including both
water-carrying ones. `PROTOTYPE_VALIDATION.md` is the evidence ledger for all of
the above, including the one failed attempt that is retained unchanged as
historical evidence. Validation on this deployment is not a guarantee for other
hardware, and the centralized brand submission remains deliberately unmade.

Centralized brand submission, HACS default-store submission, and public release
publication are not implied by the local icon or this repository metadata.

## License

MoistureLoop software is licensed under the GNU General Public License version 3
only (`GPL-3.0-only`); see [LICENSE](LICENSE). Distributed modifications and
derivative works are subject to the applicable GPL requirements.

### Name and branding

The GPL licence applies to the software code. The MoistureLoop name, logo, and
official project branding are addressed separately in
[TRADEMARKS.md](TRADEMARKS.md). Forks and derivative distributions must not
falsely imply that they are official MoistureLoop releases or are endorsed by the
official project.
