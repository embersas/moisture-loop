# Home Assistant Subentry Deletion Investigation

## Executive verdict

Home Assistant 2025.9.0 provides no supported config-subentry pre-removal callback. Native UI deletion removes the subentry from `entry.subentries`, schedules—but does not await—generic config-entry update listeners, and then clears associated device/entity registry records. It does not reload or unload the integration and invokes no integration removal callback.

A robust supported solution nevertheless exists:

`Recommended resolution: Update-listener-driven tombstoned runtime reconciliation with authoritative pre-ON configuration gates`

This architecture:

- Retains the Home Assistant 2025.9.0 minimum.
- Accepts Core's configuration-object removal ordering.
- Keeps the runtime safety object alive independently.
- Detects removal through the public `entry.subentries` mapping.
- Blocks all new integration ON operations as soon as runtime and configuration differ.
- Cooperatively terminates active watering with `CONFIG_CHANGED`.
- Preserves unresolved blockers, accounting, actuator identity, and fault evidence in a durable tombstone.
- Recovers safely after a crash between Core deletion and listener execution.

A config-entry update listener alone is insufficient because Core does not await it. Every final ON boundary must independently revalidate the current public subentry mapping and the runtime's applied configuration generation.

The normative deletion and persistence lifecycle must change; this warrants `0.1.0-spec.4`, not a corrective clarification under spec.3.

## HA 2025.9.0 actual deletion sequence

### Source revisions inspected

- Home Assistant Core tag `2025.9.0`, commit `220c233c0b217619fd2b7f3bc3309b8fab0da9a5`.
- Frontend package pinned by that release: `20250903.2`, commit `510fc71b40d9cf2cb36e0a497879d4229e60e9d0`.
- Current stable comparison: Core `2026.8.3`, commit `759e4658f40b3ccb671d418b8a0ed95224bf4561`.
- Current frontend comparison: `20260729.7`, commit `91c28c2f587553a817a315cfbbeee072a6ed5de4`.
- Current Core `dev` was also inspected.

### Exact native deletion ordering

1. The frontend subentry row renders its Delete control unconditionally. Only reconfigure support is capability-controlled; there is no integration-supplied "deletable" or delete-handler capability.

   Source: [`ha-config-sub-entry-row.ts`, Delete menu and handler](https://github.com/home-assistant/frontend/blob/510fc71b40d9cf2cb36e0a497879d4229e60e9d0/src/panels/config/integrations/ha-config-sub-entry-row.ts#L148-L164).

2. After the generic confirmation dialog, `_handleDeleteSub` calls `deleteSubEntry(...)`.

   Source: [`ha-config-sub-entry-row.ts:244-265`](https://github.com/home-assistant/frontend/blob/510fc71b40d9cf2cb36e0a497879d4229e60e9d0/src/panels/config/integrations/ha-config-sub-entry-row.ts#L244-L265).

3. `deleteSubEntry` sends websocket command:

   ```text
   type: config_entries/subentries/delete
   entry_id: ...
   subentry_id: ...
   ```

   Source: [`src/data/config_entries.ts:58-67`](https://github.com/home-assistant/frontend/blob/510fc71b40d9cf2cb36e0a497879d4229e60e9d0/src/data/config_entries.ts#L58-L67).

4. Backend handler `config_subentry_delete` resolves the entry and directly calls:

   ```python
   hass.config_entries.async_remove_subentry(entry, subentry_id)
   ```

   It does not start a `ConfigSubentryFlow` and does not call the integration.

   Source: [`homeassistant/components/config/config_entries.py:776-803`](https://github.com/home-assistant/core/blob/2025.9.0/homeassistant/components/config/config_entries.py#L776-L803).

5. `ConfigEntries.async_remove_subentry`:

   - Copies `entry.subentries`.
   - Pops the requested ID.
   - Discards the popped `ConfigSubentry`; it is not passed to any callback.
   - Calls `_async_update_entry(entry, subentries=new_mapping)`.
   - After notification, clears device-registry associations.
   - Then clears entity-registry entries.

   Source: [`homeassistant/config_entries.py:2471-2485`](https://github.com/home-assistant/core/blob/2025.9.0/homeassistant/config_entries.py#L2471-L2485).

6. `_async_update_entry` installs the new `MappingProxyType` on `entry.subentries` before notifying anything.

   Source: [`homeassistant/config_entries.py:2434-2444`](https://github.com/home-assistant/core/blob/2025.9.0/homeassistant/config_entries.py#L2434-L2444).

7. `_async_save_and_notify` then executes this order:

   - Calls each registered update listener and creates a task for its returned coroutine.
   - Does not await those tasks.
   - Schedules config-entry storage saving.
   - Clears config-entry caches.
   - Dispatches internal `ConfigEntryChange.UPDATED`.

   Source: [`homeassistant/config_entries.py:2448-2458`](https://github.com/home-assistant/core/blob/2025.9.0/homeassistant/config_entries.py#L2448-L2458).

   In exact 2025.9.0, task creation uses eager execution, so a listener may run until its first suspension point during task creation. That is internal scheduler behaviour, not a supported safety contract. Even under eager execution, `entry.subentries` has already been changed.

8. The internal dispatcher sends the already-mutated entry to Core/frontend subscribers. It is not an integration lifecycle hook.

9. `device_registry.async_clear_config_subentry` removes the matching config-subentry association and may remove/orphan a device when that was its final association.

   Source: [`device_registry.py:1548-1584`](https://github.com/home-assistant/core/blob/2025.9.0/homeassistant/helpers/device_registry.py#L1548-L1584).

10. `entity_registry.async_clear_config_subentry` synchronously removes each matching registry entity.

    Source: [`entity_registry.py:1695-1716`](https://github.com/home-assistant/core/blob/2025.9.0/homeassistant/helpers/entity_registry.py#L1695-L1716).

11. Live entities react to the registry-removal event by scheduling `async_removed_from_registry()` and `async_remove()`. Completion can occur asynchronously.

    Source: [`entity.py:1503-1524`](https://github.com/home-assistant/core/blob/2025.9.0/homeassistant/helpers/entity.py#L1503-L1524).

12. The websocket handler sends success after `async_remove_subentry` returns. Listener safety work may still be running.

### Direct answers

| Question | HA 2025.9.0 result |
|---|---|
| Callback before subentry removal? | No supported callback. |
| Callback immediately after removal? | A generic config-entry update listener is scheduled after the mapping mutation. |
| `ConfigEntryChange.UPDATED` dispatched? | Yes. |
| Update listeners invoked? | Yes. |
| Update listeners awaited? | No. |
| Automatic config-entry reload? | No. |
| `async_unload_entry` called? | No. |
| Integration `async_remove_entry` called? | No; that callback is for whole-entry removal. |
| Registry cleanup automatic? | Yes, after listener task creation. |
| Live entity teardown necessarily complete before success? | No. |
| Can the deleted ID be detected? | Yes: runtime controller IDs minus current `entry.subentries` IDs. |
| Is the removed `ConfigSubentry` passed to the listener? | No. |
| Can the controller survive? | Yes. `entry.runtime_data`, controller tasks, actuator listeners, and the separately-owned source actuator are not removed by subentry registry cleanup. |
| Can it OFF safely afterward? | Yes, if it retained immutable actuator configuration and its lifetime is not tied to the removed SoilSync entities/device. |

Core's own deletion test confirms that the listener sees an empty subentry mapping, the entity is removed, and integration `async_remove_entry` is not called: [`tests/test_config_entries.py:602-655`](https://github.com/home-assistant/core/blob/2025.9.0/tests/test_config_entries.py#L602-L655).

Tests also confirm that add, update, and removal all notify the same update listener: [`tests/test_config_entries.py:1596-1647`](https://github.com/home-assistant/core/blob/2025.9.0/tests/test_config_entries.py#L1596-L1647).

### Add, reconfigure, and reload ordering

- `ConfigSubentryFlowManager.async_finish_flow` calls `async_add_subentry`; add notifies listeners but does not reload: [`config_entries.py:3315-3350`](https://github.com/home-assistant/core/blob/2025.9.0/homeassistant/config_entries.py#L3315-L3350).
- `async_update_subentry` mutates the existing `ConfigSubentry` object in place and then notifies. Runtime must retain an immutable normalized shadow/fingerprint rather than a reference to the Core object: [`config_entries.py:2488-2533`](https://github.com/home-assistant/core/blob/2025.9.0/homeassistant/config_entries.py#L2488-L2533).
- `ConfigSubentryFlow.async_update_and_abort` updates without reload: [`config_entries.py:3417-3443`](https://github.com/home-assistant/core/blob/2025.9.0/homeassistant/config_entries.py#L3417-L3443).
- `async_update_reload_and_abort` updates first, then raises `ValueError` if an update listener exists. It therefore cannot remain once SoilSync adds a listener: [`config_entries.py:3446-3479`](https://github.com/home-assistant/core/blob/2025.9.0/homeassistant/config_entries.py#L3446-L3479).
- `async_schedule_reload` merely creates an `async_reload` task; reload takes the entry setup lock, unloads, and sets up again. Native subentry deletion never calls it: [`config_entries.py:2238-2282`](https://github.com/home-assistant/core/blob/2025.9.0/homeassistant/config_entries.py#L2238-L2282).

## Supported lifecycle hooks available in 2025.9.0

### Supported/public integration APIs

| API | Supported use |
|---|---|
| `ConfigEntry.add_update_listener` | Detects all config-entry updates, including changed subentry sets. |
| `ConfigEntry.async_on_unload` | Correctly owns removal of the listener during unload. |
| `ConfigEntry.subentries` | Public current configuration state and the authoritative deletion predicate. |
| `ConfigEntry.runtime_data` | May retain runtime/controller objects beyond config-subentry entity cleanup. |
| `ConfigEntries.async_add_subentry` | Supported Core subentry mutation. |
| `ConfigEntries.async_update_subentry` | Supported Core subentry mutation. |
| `ConfigEntries.async_remove_subentry` | Supported removal method, but provides no pre-hook. |
| `ConfigSubentryFlow` | Supported add/reconfigure flow abstraction; not used for native deletion. |
| `async_update_and_abort` | Compatible with an update-listener-owned reconciliation architecture. |
| `async_update_reload_and_abort` | Supported only when there are no entry update listeners. |
| `async_schedule_reload` / `async_reload` | Supported reload path, but integration-owned scheduling is required. |
| Whole-entry `async_unload_entry` / `async_remove_entry` | Used for reload/full entry removal, not subentry removal. |

Official guidance now explicitly documents the listener plus `async_update_and_abort` pattern and the conflict with update-and-reload helpers: [Home Assistant developer guidance, 7 May 2026](https://developers.home-assistant.io/blog/2026/05/07/config-entry-listener-together-with-reloading-methods/).

### Private/internal or unsupported

These are not acceptable safety foundations:

- `_async_update_entry`
- `_async_save_and_notify`
- `_async_dispatch`
- `SIGNAL_CONFIG_ENTRY_CHANGED`
- `async_dispatcher_send_internal`
- Relying on eager task-start timing
- Intercepting the websocket handler
- Monkey-patching `ConfigEntries.async_remove_subentry`
- Frontend patches or custom-card replacement
- Entity/device registry events as a pre-delete hook
- Polling private config-entry internals

There is no supported integration callback between confirmation and the mapping mutation.

There is also no supported way to hide, disable, or replace the native subentry Delete control. A custom safe-delete action can improve UX but cannot close the native path.

## Current implementation/spec mismatch

Specification §24.3 requires safe preparation before deletion. Home Assistant's native path cannot invoke that preparation.

Current implementation evidence:

- `custom_components/soilsync/config_flow.py:257` manually schedules add reloads and explicitly excludes an update listener.
- `custom_components/soilsync/config_flow.py:320` pre-prepares reconfiguration, then uses `async_update_reload_and_abort`.
- `custom_components/soilsync/runtime.py:628` implements `async_prepare_reconfigure`.
- `custom_components/soilsync/runtime.py:644` implements `async_prepare_delete`, but native Home Assistant never calls it.
- `custom_components/soilsync/runtime.py:255` skips persisted hazardous zones when their current config is absent.
- `custom_components/soilsync/runtime.py:274` constructs configuration only from current subentries.
- `custom_components/soilsync/models.py:922` has no persisted actuator identity or tombstone lifecycle in `ZoneRecord`.
- `custom_components/soilsync/zone_controller.py:1166` performs freshness checks before ON, but does not revalidate current subentry membership/config generation.
- `custom_components/soilsync/services.py:64` correctly refuses user services for a deleted subentry, but automatic controller paths remain live.

Consequences under the current implementation:

- An AUTO controller can continue its session and potentially start later pulses after native deletion.
- A SOAKING controller can wake and water again.
- No automatic reload stops it.
- After restart, a Store-only hazardous record is skipped.
- Because actuator identity exists only in deleted configuration, startup may be unable to prove or attempt OFF.
- An unresolved flow hazard can be silently lost from effective runtime protection.

That contradicts the specification's safety intent even though the existing `async_prepare_delete` implementation itself is sound when explicitly invoked.

## Options investigated

### Option A

Accept immediate subentry removal and clean up during the next integration reload using `CONFIG_RELOAD`.

This is platform-supported but unsafe:

- Native deletion does not schedule a reload.
- Delay is unbounded.
- AUTO/SOAKING may continue.
- `CONFIG_RELOAD` obscures the real terminal reason.
- Current startup skips Store-only deleted zones.
- Crash before reload loses access to the actuator identity.

Recommendation: reject.

### Option B

Require/document a manual integration reload.

This adds user dependency to a fail-safe operation and still does not preserve missing actuator identity or guarantee immediate OFF.

Recommendation: reject.

### Option C

Use a config-entry update listener only for subentry deletion while keeping existing add/reconfigure reload behaviour.

Removal notification is supported, but this isolated approach is incomplete:

- Listener completion is not awaited.
- It conflicts with the current `async_update_reload_and_abort` helper.
- It leaves multiple synchronization/reload owners.
- It needs final ON gates, tombstones, Store changes, generation coalescing, failure handling, and unload coordination.

Once those requirements are added coherently, this becomes Option D.

Recommendation: do not adopt C in isolation.

### Option D

Make a config-entry update listener the sole owner of runtime synchronization for add, update, and delete, while retaining pre-update reconfigure preparation where the integration controls the flow.

Architecture:

- Add: Core adds the subentry; listener integrates it and schedules one reload if entity construction requires it.
- Reconfigure: flow safely prepares the old controller, calls `async_update_and_abort`, and the listener owns reconciliation/reload.
- Delete: Core removes the subentry; mapping mismatch immediately tombstones the retained controller and the listener performs safety closure.
- Existing flow-owned reload scheduling is removed.
- No listener is combined with `async_update_reload_and_abort`.
- One serialized, generation-coalesced worker owns reconciliation and any necessary reload.

Recommendation: preferred.

### Option E

Provide a SoilSync-specific "Delete Zone" workflow/action.

That workflow can prepare safely and then call public `async_remove_subentry`. However, the native Delete control cannot be hidden or replaced in 2025.9.0 or the current frontend. It therefore creates two paths, only one of which is pre-safe.

Recommendation: optional supplementary UX only, never the safety mechanism.

### Option F

Raise the minimum Home Assistant version.

Current Core 2026.8.3 still directly removes subentries with no pre-removal hook: [`config_entries.py:2686-2699`](https://github.com/home-assistant/core/blob/2026.8.3/homeassistant/config_entries.py#L2686-L2699). The current frontend still exposes the same unconditional native Delete action: [`ha-config-sub-entry-row.ts:273-294`](https://github.com/home-assistant/frontend/blob/20260729.7/src/panels/config/integrations/ha-config-sub-entry-row.ts#L273-L294).

The inspected current `dev` source also has no hook. Consequently, there is no "first release" to target.

Recommendation: reject; retain 2025.9.0.

### Option G

Represent every zone as a separate top-level config entry.

Full-entry deletion has unload-before-removal lifecycle support. This could provide pre-removal safety, but it requires a major redesign of:

- Single-controller UX
- Shared `SlotManager`
- Store ownership
- Cross-entry blockers
- Services and device targeting
- Atomic configuration changes
- Reload/shutdown serialization

It would still need durable deleted-zone hazard records if OFF remained unresolved.

Recommendation: technically supported but disproportionate and less maintainable for v0.1.

## Update-listener investigation

1. **Supported in HA 2025.9.0?**

   Yes. `ConfigEntry.add_update_listener` is a public API and Core tests explicitly cover subentry add/update/remove notification.

2. **Does removal generate the notification?**

   Yes. It schedules update listeners and dispatches `ConfigEntryChange.UPDATED`.

3. **Does the listener observe the change early enough?**

   It observes the changed mapping, but Core does not await safety work. Therefore the listener alone is not early enough. The public mapping mismatch must itself be an immediate no-ON condition.

4. **Duplicate reload risk?**

   Yes, unless all flow-owned reload scheduling is removed. `async_update_reload_and_abort` must be replaced with `async_update_and_abort`; add must no longer schedule its own reload.

5. **Can add/reconfigure/delete use one mechanism?**

   Yes. All three generate update-listener notification. Reconfigure may retain its supported pre-mutation preparation but reconciliation/reload ownership remains centralized.

6. **Can deleted subentries be identified reliably?**

   Yes:

   ```text
   removed_ids = runtime_snapshot_ids - entry.subentries.keys()
   ```

   Reconfiguration detection must compare immutable normalized fingerprints because Core mutates the existing `ConfigSubentry` object in place.

7. **May the listener await cooperative preparation?**

   Yes, within its task. Core and the websocket caller do not await it.

8. **What if another update occurs while preparation runs?**

   Core creates another listener task. SoilSync must use:

   - One entry-wide reconciliation lock/worker.
   - A runtime-owned monotonic generation or immutable snapshot fingerprint.
   - A dirty flag.
   - Re-read-after-every-await.
   - Coalescing to the newest configuration.
   - At most one scheduled reload per batch.

9. **What if HA reloads or shuts down concurrently?**

   Unload/shutdown must join or independently invoke the same reconciliation path. It cannot assume the listener finished. Any incomplete safety result remains in Store for startup union reconciliation.

10. **Can another ON occur after deletion but before listener completion?**

    It can unless all ON paths contain an authoritative final fence.

Required final fence, after preparatory awaits and immediately before command dispatch:

- Current zone ID still exists in `entry.subentries`.
- Current normalized config fingerprint matches the controller snapshot.
- The entry's current subentry-set fingerprint matches the applied runtime generation.
- Controller is not tombstoned, quiescing, or terminal.
- Entry-wide reconciliation barrier is clear.
- Global blocker eligibility still passes.

There must be no suspension point between that authorization decision and starting the actuator service call. If the command was already dispatched before Core deletion, it is treated as an in-flight pre-delete ON and immediately compensated through the shared OFF operation.

The global mapping comparison is essential: deletion of zone A must prevent zone B from beginning ON until A's possible-flow hazard has either been disproved or represented by a durable global blocker.

## Runtime tombstone investigation

Configuration deletion and runtime safety-object destruction must be explicitly separated.

### Logical tombstone creation

A tombstone exists immediately when:

```text
zone ID exists in the runtime/applied snapshot
AND
zone ID is absent from current entry.subentries
```

That predicate becomes true synchronously when Core replaces `entry.subentries`. It does not depend on the listener first setting a mutable flag.

Consequently, every final ON gate can reject immediately—even before the listener task runs.

### Materialized tombstone lifecycle

The listener/reconciler then:

1. Closes the entry-wide new-ON gate.
2. Finds removed and changed runtime controllers.
3. Marks them no-start/quiescing.
4. Cancels queued slot requests and timers.
5. Preserves the controller's immutable actuator configuration.
6. Persists or confirms the tombstone.
7. For WATERING, commits the appropriate terminal cause and joins one OFF operation.
8. For SOAKING, commits terminal state and prohibits another pulse.
9. Preserves blocker ownership, fault evidence, and open accounting.
10. Keeps the controller/listener alive until safe closure.
11. Detaches the live controller only after safe state has been durably recorded.

For delete-only reconciliation, no reload is required: Core already removes the UI entities/device. Avoiding reload also avoids prematurely destroying a live unresolved tombstone.

For add/reconfigure—or a mixed batch requiring entity reconstruction—the listener may schedule exactly one reload after delete/reconfigure safety handoff has been durably established. Reload/startup must reconstruct any unresolved Store-only tombstone.

### In-flight ON boundary

The current ON path releases its controller lock around the actuator service call. Deletion can race with that call.

Required ordering:

- If deletion is visible before invocation, do not call ON.
- If ON was invoked before deletion and remains in flight, regard it as integration-owned possible flow.
- Join or serialize its completion before finalizing the deletion OFF path where possible.
- Recheck membership immediately after the ON call returns.
- Never persist a continuing/resumable session when the post-call check fails.
- Execute the shared idempotent OFF operation exactly once.
- If completion is uncertain, retain conservative possible-flow evidence and the blocker.

A listener without this command-boundary change does not close the deletion race.

## Persistence/restart implications

### Required Store identity

Every configured zone's Store record must persist enough actuator identity before that zone is eligible to water:

- Subentry/zone ID.
- Last-known actuator entity ID.
- Entity-registry entry UUID where available.
- Actuator domain/type.
- Relevant confirmation timeout/configuration.
- Last normalized configuration fingerprint.
- Display identity for Repairs/diagnostics.
- Blocker/evidence ownership.
- Tombstone lifecycle: `active`, `delete_pending`, or `retired`.

The registry UUID supports rename recovery; the last entity ID remains a fallback.

### Startup set

Startup must reconcile the union of:

```text
current configured zone IDs
UNION
persisted zone safety-record IDs
```

A Store-only record is an implicit tombstone even if HA crashed after Core removed the subentry but before the listener persisted `delete_pending`.

No zone may receive a grant until configured zones and Store-only tombstones have been reconciled.

### Runtime/history handling

- Daily runtime remains attached to the tombstone.
- `last_session_end_utc`, minimum-session interval, last summary, and crash history remain.
- An open estimated-runtime interval stays open and is conservatively charged until OFF proof.
- Deletion does not acknowledge `ACTUATOR_OFF_TIMEOUT`.
- `integration_off_unconfirmed` remains keyed to the deleted zone.
- Once OFF is proven, its blocker may clear, but the fault/Repair remains until valid acknowledgement.
- `external_flow` remains until observed external OFF; deletion does not authorize counter-commanding an external actor.
- Re-adding the same actuator under another subentry must adopt its current-day runtime, interval history, blockers, and fault evidence rather than create a fresh budget.

### Physical deletion

The safest v0.1 policy is not to automatically delete retired tombstone records.

A future explicit compaction/purge may remove one only after:

- OFF is proven.
- No blocker remains.
- No open accounting exists.
- Fault acknowledgement requirements are complete.
- Runtime/minimum-interval history has expired or been transferred.
- The record is not needed to prevent delete/re-add budget reset.

### Tombstone acknowledgement

Native deletion removes the zone device, so device-targeted `clear_fault` cannot be the only acknowledgement route.

A supported entry-level Repair/fix flow or equivalent tombstone-aware action is required. It must resolve the tombstone by stored identity, prove OFF, and clear only that tombstone's fault/blocker key.

## Race and failure analysis

1. **IDLE and proven OFF**

   The mapping mismatch blocks new ON. Re-read/confirm OFF, persist `retired`, preserve history, then detach the live controller. No OFF command is required merely because the zone was deleted.

2. **WATERING(AUTO)**

   Commit `CONFIG_CHANGED` unless an earlier terminal cause already won. Cancel future pulses/requests, finish the ordered in-flight ON boundary if necessary, perform one idempotent OFF, and account runtime through confirmed or estimated OFF. Never resume.

3. **WATERING(MANUAL)**

   Same as AUTO. Deletion is terminal; manual mode provides no exemption or resurrection path.

4. **SOAKING**

   Cancel soak timer and slot request, commit `CONFIG_CHANGED`, and prohibit the next pulse. Confirm/observe OFF; use defensive OFF only when ownership/uncertainty requires it.

5. **`ACTUATOR_OFF_TIMEOUT` with `integration_off_unconfirmed`**

   Preserve actuator identity, open accounting, fault, blocker, and critical Repair. Deletion neither clears nor acknowledges them. Later OFF proof clears only the matching blocker; fault acknowledgement remains separate.

6. **External ON with `external_flow`**

   Preserve external ownership. Do not turn it OFF solely due to deletion. Keep the actuator listener and keyed global blocker until a terminal external OFF is observed.

7. **Actuator becomes unavailable**

   Unavailable is not OFF. For integration-owned watering, make the one bounded OFF attempt and retain unconfirmed-flow evidence on failure. For external ownership, retain `external_flow`. Persist identity for restart reconciliation.

8. **Watchdog, Stop, Disable, external events, reload, or shutdown race**

   - One controller serialization domain chooses the first terminal reason.
   - Deletion still installs the no-start tombstone even when another reason won.
   - Stop/Disable/watchdog/delete join the same OFF future.
   - External OFF may close accounting and satisfy OFF proof.
   - External ON during integration-owned exit becomes interference/possible-flow evidence.
   - Reload/unload joins reconciliation.
   - Shutdown persists unresolved state; startup reconstructs it.

9. **Multiple rapid deletes**

   All mapping mismatches become immediate no-start tombstones. One generation-coalesced worker processes the newest map. Blockers remain keyed per zone/reason. At most one reload is scheduled for the batch if add/reconfigure work requires it.

10. **Removal/update listener fails or raises**

    Core deletion remains committed. The listener wrapper must catch failures, leave the runtime/config mismatch barrier closed, conservatively stop active integration-owned controllers, preserve runtime objects, persist a Repair/incident where possible, and avoid destructive reload/rebuild. If Store persistence also fails, ON remains prohibited and the live controller/evidence remains in memory. Startup's Store/config union is the final recovery path.

## Decision matrix

Scores are `1–5`, higher is better. Score order is platform correctness / irrigation safety / race resistance / maintainability / UX / minimum-version impact.

| Option | HA 2025.9 supported? | Pre-delete safety? | Post-delete race | Persists hazards safely? | UX | Complexity | Scores | Recommendation |
|---|---|---|---|---|---|---|---|---|
| A: later reload | Yes | No | Severe/unbounded | No, as proposed | Poor | Low | 5/1/1/3/2/5 | Reject |
| B: manual reload | Yes | No | Severe/user-dependent | No | Very poor | Low | 5/1/1/2/1/5 | Reject |
| C: delete-only listener | Yes, but incompatible with current reload helper | No | Incomplete without gates/tombstones | Only with major extension | Good | Medium-high | 4/3/3/2/4/5 | Fold into D |
| D: listener-owned synchronization plus tombstones | Yes | No native pre-hook; equivalent immediate gate | Controlled | Yes | Good/native | High | 5/5/5/4/5/5 | Preferred |
| E: custom safe-delete action | Yes on custom path | Yes on custom path | Native unsafe path remains | Potentially | Confusing dual path | Medium | 4/2/2/3/2/5 | Supplement only |
| F: raise HA floor | No qualifying release | N/A | N/A | N/A | No benefit | N/A | 1/1/1/2/2/1 | Reject |
| G: zone as top-level entry | Yes | Via full-entry unload | Low | Yes with Store work | Fragmented | Very high | 5/5/5/2/2/5 | Reject for v0.1 |

## Recommended resolution

`Recommended resolution: Update-listener-driven tombstoned runtime reconciliation with authoritative pre-ON configuration gates`

1. **Why safer than alternatives**

   It does not depend on an unavailable pre-hook, user reload, private dispatcher, frontend replacement, or listener timing. The changed public mapping itself becomes a synchronous no-ON condition. Runtime safety state outlives configuration state.

2. **Why Home Assistant-supported**

   It uses public `ConfigEntry.add_update_listener`, `ConfigEntry.subentries`, `async_on_unload`, `ConfigSubentryFlow.async_update_and_abort`, and supported reload APIs. No internal dispatch interception is required.

3. **Minimum version**

   Retain Home Assistant 2025.9.0.

4. **Exact deletion sequence**

   ```text
   Native UI
     -> websocket delete
     -> Core removes subentry from entry.subentries
     -> runtime/config mismatch immediately closes the final ON gate
     -> Core schedules update listener
     -> Core clears SoilSync registry device/entities
     -> listener/coalesced worker identifies removed runtime ID
     -> controller becomes delete-pending tombstone
     -> queued work/timers are cancelled
     -> CONFIG_CHANGED closure and OFF assurance execute
     -> Store persists safe or unresolved tombstone
     -> controller remains live until closure
     -> controller may detach only after durable safe handoff
   ```

5. **Active WATERING**

   AUTO and MANUAL both terminate cooperatively as `CONFIG_CHANGED` unless another terminal event already committed first. Any already-started ON is serialized as an in-flight integration-owned operation. Exactly one shared OFF operation runs, accounting continues to OFF proof/estimate, and the session cannot resume.

6. **SOAKING**

   Cancel the soak timer and slot request, commit terminal `CONFIG_CHANGED`, and prevent the next pulse. The retained controller supplies OFF observation/assurance until closure.

7. **Global blockers**

   Blockers remain keyed by tombstone zone ID and reason. Deletion cannot clear another zone's blocker. `integration_off_unconfirmed` and `external_flow` remain globally effective until their own OFF conditions are satisfied.

8. **Store/tombstone**

   Actuator entity ID and registry UUID are persisted while the zone is active, before ON eligibility. Deletion produces `delete_pending`; OFF-proven/no-hazard state becomes `retired`. v0.1 retains retired records rather than auto-purging them.

9. **Restart after partial deletion**

   Startup reconciles `configured IDs ∪ Store IDs`. Any Store-only zone is an implicit tombstone. The stored actuator identity is used to resolve the actuator, restore listeners/blockers, close open accounting, attempt integration-owned OFF where required, and keep grants disabled until reconciliation is safe.

10. **Specification changes**

    Replace impossible pre-delete ordering with post-Core-removal logical tombstoning, define the final configuration-membership gate, listener-owned synchronization, persisted actuator identity, Store-only startup reconciliation, and tombstone acknowledgement/retention.

11. **Implementation changes**

    Add the listener/reconciliation coordinator, Store schema and migration, runtime tombstones, command-boundary membership/generation checks, in-flight ON/delete serialization, tombstone Repairs, and centralized reload ownership.

12. **Tests before Slice 9 completion**

    Native websocket deletion, all active-state cases, every ON boundary, blockers, unavailable/external actuators, Store crash windows, Store-only startup, rapid updates, listener failure, reload/shutdown, delete/re-add history, and exact one-OFF/no-resurrection invariants must pass.

## Minimum Home Assistant version decision

Retain:

```text
Home Assistant 2025.9.0
```

No later supported release through current stable 2026.8.3 provides the required pre-removal hook. Current frontend behaviour is also unchanged. Raising the minimum version would therefore provide no architectural safety benefit.

If Home Assistant later introduces a documented `async_prepare_remove_subentry`-style lifecycle hook that is awaited before mutation, it should be evaluated as a future simplification. No such released API currently exists.

## Required specification changes

Do not treat this as a local wording correction. Publish `0.1.0-spec.4` with a document-wide consistency update.

- **§5 Home Assistant architecture/API research**
  - Record exact 2025.9 deletion ordering.
  - Replace the "no update listener" decision.
  - Require `add_update_listener` plus `async_update_and_abort`.
  - Prohibit listener plus `async_update_reload_and_abort`.

- **§21 global resource behaviour**
  - Define tombstones as runtime-known potential resource owners.
  - Keep blockers active after config deletion.
  - Require entry-wide no-ON while configuration reconciliation is dirty.

- **§22 concurrency**
  - Define reconciliation generation, lock/coalescing, dirty barrier, first-terminal arbitration, in-flight ON/delete ordering, and reload/shutdown joining.

- **§23 persistence**
  - Add actuator entity ID, registry UUID, fingerprint, ownership evidence, and tombstone lifecycle.
  - Define `active`, `delete_pending`, and `retired`.
  - Preserve budget/history/accounting across deletion and re-add.
  - Prohibit automatic v0.1 tombstone deletion.

- **§24 lifecycle**
  - Replace the impossible "prepare before native subentry removal" rule with configuration deletion followed by immediate logical tombstoning and cooperative safety closure.
  - Retain supported pre-preparation for integration-controlled reconfigure.

- **§25 startup/reconciliation**
  - Reconcile the union of configured and persisted zone records.
  - Treat Store-only records as implicit tombstones.
  - Keep grants disabled until reconciliation finishes.

- **§26 acknowledgement**
  - Define tombstone-safe OFF-timeout acknowledgement without the deleted zone device.

- **§29 config/subentry UX**
  - Document native Delete ordering.
  - State that a custom Delete action cannot replace native Delete.
  - Explain background safe closure and persistent Repairs.

- **§30 configuration application**
  - Centralize reload ownership in the reconciler.
  - Define when add/reconfigure require one reload and why delete-only does not.

- **§33–§34 diagnostics and Repairs**
  - Expose delete-pending/retired tombstones, stored actuator identity, reconciliation failure, and unresolved hazards.

- **§37 architecture**
  - Add the reconciliation coordinator, applied configuration shadow, and runtime tombstone layer.

- **§39 tests**
  - Add native deletion, command-boundary, listener failure, crash-window, and Store-only reconciliation coverage.

- **§40 failure analysis**
  - Add deletion/listener/reload/persistence failure modes.

- **§42 Store schema/version**
  - Define migration and malformed/future-version behaviour for new tombstone fields.

- **§43 documentation**
  - Document safe native deletion behaviour and persistent post-delete Repairs.

- **§45 acceptance criteria**
  - Require native UI/backend deletion safety, no post-delete ON, durable orphan recovery, and blocker preservation.

- **§46 prototype validation**
  - Pin validation to the actual 2025.9 native websocket path and real actuator in-flight command behaviour.

## Required implementation changes

| File | Approximate nature of change | Risk |
|---|---|---|
| `custom_components/soilsync/__init__.py` | Register/unregister update listener before runtime watering is enabled; coordinate unload | Medium |
| `custom_components/soilsync/runtime.py` | Immutable configuration shadow, generation-coalesced reconciler, tombstone lifecycle, startup union, reload/shutdown joining | High |
| `custom_components/soilsync/config_flow.py` | Replace reload helper with `async_update_and_abort`; remove add-owned reload; retain pre-update reconfigure preparation | Medium-high |
| `custom_components/soilsync/models.py` | Add actuator identity, lifecycle, fingerprint, and tombstone evidence fields | High |
| `custom_components/soilsync/storage.py` | Schema migration, verified tombstone writes, Store-only lookup, history adoption | High |
| `custom_components/soilsync/zone_controller.py` | Final membership/generation gates, no-start tombstone state, in-flight ON/delete ordering, safe detach | High |
| `custom_components/soilsync/slot_manager.py` | Entry-wide configuration-dirty admission barrier and removed-zone request cancellation | Medium-high |
| `custom_components/soilsync/services.py` | Retain deleted-target refusal; route tombstone-safe acknowledgement if service-based | Medium |
| `custom_components/soilsync/repairs.py` | Persistent tombstone issue and entry-level acknowledgement/fix flow | Medium |
| `custom_components/soilsync/diagnostics.py` | Report reconciliation state and active/delete-pending/retired tombstones | Low-medium |
| `custom_components/soilsync/const.py` | Store schema/lifecycle constants | Medium |
| Entity platforms | Verify Core registry removal does not own controller lifetime | Low |
| Strings/translations | Tombstone Repair and acknowledgement UX | Low |

## Required tests

### Add

- Native `config_entries/subentries/delete` websocket-path test against HA 2025.9 semantics.
- Listener sees the post-removal mapping and receives no removed object.
- No automatic reload and no integration `async_remove_entry`.
- IDLE/OFF deletion.
- AUTO and MANUAL deletion at:
  - Before intent persistence.
  - After intent persistence.
  - Before actuator service invocation.
  - While ON is in flight.
  - After ON returns but before commanded-state persistence.
  - During ON confirmation.
- SOAKING deletion cannot issue another pulse.
- OFF-timeout tombstone retains open accounting, Repair, identity, and blocker.
- External ON deletion retains `external_flow` without counter-command.
- Unavailable actuator deletion.
- Watchdog, Stop, Disable, external OFF/ON, reload, and shutdown races.
- Multiple rapid add/update/delete events.
- Listener exception and Store write-verification failure.
- Crash after Core mapping mutation but before explicit tombstone write.
- Startup reconstruction of an implicit Store-only tombstone.
- Actuator rename resolution through registry UUID.
- Delete/re-add of the same actuator cannot reset daily or minimum-session history.
- Tombstone acknowledgement without a zone device.
- Registry cleanup cannot destroy the runtime safety object.
- No ON while runtime/config snapshots differ.
- One OFF operation and no session resurrection.
- At most one listener-owned reload per update batch.

### Change

- `tests/test_config_flow.py`: replace add/reconfigure flow-owned reload expectations.
- `tests/test_lifecycle.py`: include Store-only tombstone setup, unload, reload, and shutdown.
- `tests/test_zone_controller.py`: add final configuration fence and in-flight ON/delete cases.
- `tests/test_storage.py` and `tests/test_storage_pure.py`: schema migration, round-trip, malformed and future-version cases.
- `tests/test_slot_manager.py`: configuration-dirty global barrier and exact-key preservation.
- Service/Repair/diagnostic tests: tombstone targeting and reporting.
- Acceptance/traceability tests: replace pre-delete callback assumption with native post-mutation tombstone semantics.

### Retain unchanged and rerun

- Pure state-machine `CONFIG_CHANGED` transition semantics.
- Existing idempotent OFF tests.
- Exact-key blocker isolation.
- External ownership behaviour.
- Watchdog and sensor-report freshness.
- Runtime accounting, crash estimation, DST, and Store atomicity.
- Deleted-device service refusal.
- Existing coverage thresholds, including state-machine branch coverage.

## Slice 9 exit criteria

Slice 9 may change from:

```text
[?] Requires specification review
```

to:

```text
[x] Complete
```

only when all of the following evidence exists:

1. `0.1.0-spec.4` is approved with document-wide consistent tombstone semantics.
2. A pinned HA 2025.9 test exercises the actual native websocket removal path.
3. The update listener is registered and owned through `async_on_unload`.
4. `async_update_reload_and_abort` and add-owned reload scheduling are no longer used with the listener.
5. Every final ON path rejects absent or mismatched subentries.
6. In-flight ON/delete ordering terminates without resurrection and produces one OFF operation.
7. The Store already contains sufficient actuator identity before a zone can water.
8. Startup reconciles Store-only tombstones before enabling grants.
9. Global blockers, open accounting, fault acknowledgement, and runtime history survive deletion.
10. AUTO, MANUAL, SOAKING, external-flow, unavailable-actuator, rapid-delete, listener-failure, reload, and shutdown cases pass.
11. Native registry cleanup is proven not to destroy unresolved runtime safety state.
12. No private dispatcher, monkey patch, frontend patch, polling workaround, or manual reload dependency is used.
13. Full test, lint, and coverage gates pass.
14. Physical/prototype validation records the limits of simulated service-call ordering.

Slice 13 must not begin as part of this resolution.

## Confidence / unresolved platform questions

Confidence is high on the platform findings. Exact tagged Core, the frontend pinned to that release, Core tests, current stable, and current `dev` all agree:

- No supported subentry pre-removal callback exists.
- Native Delete cannot be hidden or replaced by the integration.
- Removal mutates first, schedules listeners without awaiting them, and does not reload.
- A retained runtime controller remains technically capable of safety closure.

No unresolved Home Assistant API question changes the recommendation.

Remaining validation questions are implementation/hardware questions:

- How each real switch/valve integration behaves when deletion races with an already-dispatched service call.
- Whether a slow or non-cancellable actuator service requires additional bounded OFF compensation.
- Final user-facing design of tombstone fault acknowledgement.

This report is research and recommendation only. It does not modify `SPECIFICATION.md`, `PROGRESS.md`, implementation code, or Slice 9 status.
