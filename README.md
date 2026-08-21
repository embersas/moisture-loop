# Moisture Loop

**Closed-loop soil-moisture irrigation for Home Assistant.**

Moisture Loop is a hardware-agnostic Home Assistant custom integration that
waters each zone in bounded pulses driven by a real soil-moisture sensor.
Every pulse is followed by a full soak, and the next decision uses only a
sensor report made *at or after* the soak ends. It is not a timer, a weather
model, or an evapotranspiration calculator: measured soil moisture is the
authoritative automatic feedback signal, and every uncertainty fails toward
water OFF.

> **Requires Home Assistant 2025.9.0 or newer.** The integration uses the
> subentry-specific update-and-reload API introduced in that release; no
> older release is supported or claimed compatible.

## How it works

Each zone pairs exactly one moisture `sensor` with one `switch` or `valve`
actuator:

1. A new automatic session starts only when a **valid, fresh** moisture
   report is **strictly below** the start threshold (and every safety guard
   passes).
2. The zone waters one bounded **pulse**, then closes the valve and waits
   the full configured **soak** — water moves through soil slowly, so a
   reading taken right after closing means nothing yet.
3. After the soak, the next decision requires a report **timestamped at or
   after the soak deadline**. Below target: another whole pulse (if it fits
   every limit). At or above target: done.
4. Hysteresis is exact and asymmetric: start requires `moisture <
   start_threshold`; an active session continues while `moisture <
   target_threshold`; equality at the target completes.

### Safety model

- **Fail toward OFF.** A sensor that goes unavailable, invalid, or silent
  during automatic watering stops the pulse immediately. An interrupted
  watering pulse is **never resumed** after a restart, reload, or crash.
- **Hard limits.** Whole pulses must fit within the per-session and
  per-day runtime budgets; sessions are bounded by a cycle count and a
  minimum interval between automatic sessions.
- **Conservative accounting.** If Home Assistant crashes mid-pulse, the
  possible watering time is *overestimated* (from the persisted
  write-ahead intent through restart reconciliation) and fully charged to
  the daily budget — estimated runtime is labelled but never discounted.
- **One zone at a time.** Watering commands are globally serialized. Any
  configured actuator that is observed (or must conservatively be assumed)
  to be flowing — even when a person opened it by hand — blocks every new
  integration command until it is proven OFF.
- **Verified persistence.** Safety state is stored atomically with
  read-back verification before any valve is commanded ON; corrupted or
  missing history blocks all watering, exhausts the day's budget, and
  raises a Repair until acknowledged.
- **Manual watering is always bounded.** There is no unbounded ON anywhere
  in this integration. Manual runs require an explicit duration, clamped by
  the manual maximum, session maximum, and remaining daily budget.

**Hardware note:** software cannot close a mechanically stuck valve. Use a
hardware backstop (a valve with a built-in maximum runtime, or a master
valve) for defense in depth. If the actuator cannot be proven OFF, Moisture
Loop raises a **critical Repair** and keeps charging runtime until OFF is
observed.

## Installation

### HACS (custom repository)

1. HACS → Integrations → ⋮ → *Custom repositories*.
2. Add this repository with category **Integration**.
3. Install **Moisture Loop** and restart Home Assistant.

### Manual

Copy `custom_components/moisture_loop/` into your Home Assistant
`config/custom_components/` directory and restart.

## Configuration

Everything is configured in the UI:

1. **Settings → Devices & services → Add integration → Moisture Loop.**
   This creates the single controller entry.
2. On the Moisture Loop entry, choose **Add zone** and complete the three
   steps: identity (name, sensor, actuator), thresholds/timing, and safety
   limits.

Each zone appears as its own device with status, runtime, last-session,
needs-water, watering, problem, enable, stop, evaluate, and clear-fault
entities.

| Setting | Default | Range |
|---|---|---|
| Start threshold | 30 % | 1–99, strictly below target |
| Target threshold | 40 % | 2–100, strictly above start |
| Pulse duration | 5 min | 30 s – 30 min |
| Soak duration | 20 min | 1 min – 4 h |
| Max cycles per session | 4 | 1–20 |
| Max session runtime | 30 min | pulse – 4 h |
| Max daily runtime | 60 min | pulse – 12 h |
| Min automatic session interval | 6 h | 15 min – 7 d |
| Sensor report max age | 2 h | 5 min – 24 h |
| Actuator confirm timeout | 30 s | 5 s – 5 min |
| Manual max duration | 30 min | 1 min – 2 h |

The defaults are safe starting points, **not agronomic advice**. Calibrate
thresholds and timing from your own soil, emitters, probe placement, and
sensor behaviour. There are no universal moisture percentages for crops.

### Sensor requirements

Any `sensor` whose state is a finite number in `[0, 100]` works. Repeated
*identical* readings still count: Moisture Loop listens to Home Assistant's
`state_reported` events, so a sensor that reports the same value every few
minutes keeps its data fresh. A sensor that only pushes on change and stays
silent longer than the configured max age will stop automatic watering —
that is deliberate. Prefer sensors that report at least a few times per
freshness window.

### Valves

`valve` entities must support both open and close commands; position-only
valves are not supported. Transitional states (`opening`/`closing`) are
never treated as proof of the requested state, and a reported nonzero
position is conservatively treated as flowing.

## Actions

All actions target one **zone device** and validate everything in the
backend:

| Action | Fields | Notes |
|---|---|---|
| `moisture_loop.start_manual_watering` | `device_id`, `duration` (s) | Explicit, bounded manual run. Ignores sensor health but never actuator, configuration, integrity, or budget safety. |
| `moisture_loop.stop_watering` | `device_id` | Cooperative stop; no-op when idle. |
| `moisture_loop.evaluate_zone` | `device_id` | Runs a normal guarded evaluation; bypasses nothing. |
| `moisture_loop.clear_fault` | `device_id` | Clears/acknowledges a fault only when its safety condition is resolved. |

Example:

```yaml
service: moisture_loop.start_manual_watering
data:
  device_id: abc123...   # the zone device
  duration: 600
```

Manual watering is permitted during sensor-only faults (that is its
purpose) and refused for actuator, configuration, and integrity faults.

## Faults and recovery

| Fault | Blocks manual? | Clears |
|---|---|---|
| `sensor_unavailable` / `sensor_invalid` / `sensor_stale` | No | Automatically on a valid, fresh report |
| `actuator_unavailable` / `actuator_on_timeout` | Yes | Automatically once the actuator is available and observed OFF |
| `actuator_off_timeout` | Yes | Only by acknowledgement **after** OFF is observed (critical Repair) |
| `configuration_invalid` | Yes | By reconfiguring the zone |
| `restored_from_unsafe_state` | Yes | By acknowledgement after actuators are proven OFF; the detection day's budget stays exhausted |

## Events

`moisture_loop_session_started`, `moisture_loop_session_finished`,
`moisture_loop_fault_set`, and `moisture_loop_fault_cleared` fire on the
event bus with the zone, device, session, mode, and (on finish) the reason,
runtime, estimation metadata, cycles, and moisture before/after.

## Diagnostics and troubleshooting

- Download diagnostics from the Moisture Loop entry: they include the
  safety-store status, run integrity results, per-zone state and session
  anchors, the resource-blocker set, and the last 50 transitions.
- The `status` sensor's attributes show the live freshness deadline,
  moisture classification, and any resource blockers.
- Check the **Repairs** dashboard for missing entities, unproven-OFF
  panics, and safety-history loss.
- Watering that "refuses to start" is almost always a guard doing its job:
  stale sensor data, an unproven-OFF actuator, an exhausted daily budget,
  or the minimum session interval.

## Privacy / local operation

Moisture Loop is entirely local. It has **no cloud account, no telemetry,
no API keys, and no outbound network access**, and it does not depend on
the Recorder for any safety decision.

## Known limitations (v0.1)

- One sensor and one actuator per zone; no weather/ET input; no flow
  meters; no shared pump modelling beyond the global one-zone-at-a-time
  rule. See the specification's non-goals for the full list.
- On Home Assistant 2025.9.x, deleting a zone from the UI takes effect at
  the next reload of the entry; reload the Moisture Loop entry (or restart)
  after deleting a zone.
