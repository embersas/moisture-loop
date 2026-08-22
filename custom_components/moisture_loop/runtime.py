"""Moisture Loop — closed-loop soil-moisture irrigation for Home Assistant.

Slice 8: entry/process lifecycle orchestration (SPECIFICATION.md §§24-25).
Startup completes Store identity handling, verified new-run persistence,
configuration validation, passive actuator reconciliation with keyed
blockers, persisted-WATERING recovery (never resumed), trusted-SOAKING
adoption, and only then enables SlotManager grants. Actions/entities are
registered in later slices (§38).
"""

from __future__ import annotations

import logging
import uuid

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ACTUATOR,
    CONF_ACTUATOR_CONFIRM_TIMEOUT,
    CONF_MANUAL_MAX_DURATION,
    CONF_MAX_CYCLES,
    CONF_MAX_DAILY_RUNTIME,
    CONF_MAX_SESSION_RUNTIME,
    CONF_MIN_SESSION_INTERVAL,
    CONF_MOISTURE_SENSOR,
    CONF_NAME,
    CONF_PULSE_DURATION,
    CONF_RUNTIME_STORE_GENERATION_ID,
    CONF_RUNTIME_STORE_INITIALIZED,
    CONF_SENSOR_MAX_AGE,
    CONF_SOAK_DURATION,
    CONF_START_THRESHOLD,
    CONF_TARGET_THRESHOLD,
    DOMAIN,
)
from .models import (
    ActuatorFinding,
    BlockerReason,
    ConfigChangedPrepare,
    ConfigEntryReload,
    ControllerState,
    GraceDeadlineReached,
    HomeAssistantShutdown,
    RunIds,
    SessionContext,
    SessionMode,
    StartupPersistedSoaking,
    StartupPersistedWatering,
    ZoneConfig,
    ZoneRecord,
    config_fingerprint,
)
from .slot_manager import SlotManager
from .storage import SafetyStore, SetupClassification, StoreWriteVerificationError
from .zone_controller import ActuatorAdapter, ZoneController

_LOGGER = logging.getLogger(__name__)

# Bounded fallback for cooperative OFF at shutdown; tuning is §46 item 4.
SHUTDOWN_OFF_BUDGET_S = 8.0


def zone_config_from_subentry(data: dict) -> ZoneConfig:
    """Build the pure ZoneConfig from config-subentry data (§9 keys)."""
    return ZoneConfig(
        name=data[CONF_NAME],
        moisture_sensor=data[CONF_MOISTURE_SENSOR],
        actuator=data[CONF_ACTUATOR],
        start_threshold=float(data[CONF_START_THRESHOLD]),
        target_threshold=float(data[CONF_TARGET_THRESHOLD]),
        pulse_duration_s=int(data[CONF_PULSE_DURATION]),
        soak_duration_s=int(data[CONF_SOAK_DURATION]),
        max_cycles=int(data[CONF_MAX_CYCLES]),
        max_session_runtime_s=int(data[CONF_MAX_SESSION_RUNTIME]),
        max_daily_runtime_s=int(data[CONF_MAX_DAILY_RUNTIME]),
        min_session_interval_s=int(data[CONF_MIN_SESSION_INTERVAL]),
        sensor_max_age_s=int(data[CONF_SENSOR_MAX_AGE]),
        actuator_confirm_timeout_s=int(data[CONF_ACTUATOR_CONFIRM_TIMEOUT]),
        manual_max_duration_s=int(data[CONF_MANUAL_MAX_DURATION]),
    )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Integration-level setup: register actions once (§5.3, I25)."""
    from .services import async_register_services

    async_register_services(hass)
    return True


PLATFORMS = ["binary_sensor", "button", "sensor", "switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the single Moisture Loop controller entry."""
    runtime = EntryRuntime(hass, entry)
    await runtime.async_initialize()
    entry.runtime_data = runtime
    runtime.install_stop_listener()
    # Platforms forward only after §25.1 reconciliation completed above.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the entry (§24.2); never marks the process run clean."""
    runtime: EntryRuntime = entry.runtime_data
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await runtime.async_unload()
    return unloaded


class EntryRuntime:
    """Entry-scoped runtime: Store identity, run IDs, reconciliation (§37).

    No watering-capable activation (SlotManager grants) occurs before every
    §25.1 prerequisite completes; every safety write is verified.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        generation = entry.data[CONF_RUNTIME_STORE_GENERATION_ID]
        self.store = SafetyStore(hass, entry.entry_id, generation)
        self.slots = SlotManager(self._persist_slot_blocker)
        self.controllers: dict[str, ZoneController] = {}
        self.run_id = str(uuid.uuid4())
        self.previous_run: RunIds | None = None
        self.setup_classification: SetupClassification | None = None
        self.soaking_adoptions: dict[str, bool] = {}
        self.process_stopping = False
        self.shutdown_off_budget_s = SHUTDOWN_OFF_BUDGET_S
        self._passive_unsubs: list[CALLBACK_TYPE] = []
        self._activity_unsubs: list[CALLBACK_TYPE] = []
        self._stop_unsub: CALLBACK_TYPE | None = None
        self._local_tz = dt_util.get_default_time_zone()

    # ------------------------------------------------------------------
    # Startup (§25.1 order)
    # ------------------------------------------------------------------

    async def async_initialize(self) -> None:
        """Steps 1-8 of §25.1. Raises ConfigEntryNotReady on failed writes."""
        entry = self.entry
        initialized = bool(entry.data.get(CONF_RUNTIME_STORE_INITIALIZED, False))

        # Steps 1-2: identity and the §23.5 matrix.
        classification, _data = await self.store.async_classify_setup(initialized)
        self.setup_classification = classification
        if classification is SetupClassification.FIRST_INSTALL:
            try:
                await self.store.async_first_initialize()
            except StoreWriteVerificationError as err:
                # PI7: flag stays false; no listeners, no grants, no ON.
                raise ConfigEntryNotReady(f"initial safety store write failed: {err}") from err
            self._mark_initialized()
        elif classification is SetupClassification.INTERRUPTED_INITIALIZATION:
            # PI2/PI6: the safe Store exists; complete the flag update only.
            self._mark_initialized()
        elif classification is SetupClassification.INTEGRITY_LOSS:
            await self._reconstruct_after_integrity_loss()

        # Step 3: run protocol (§23.3).
        try:
            self.previous_run = await self.store.async_begin_new_run(self.run_id)
        except StoreWriteVerificationError as err:
            # PI19: this process must never become watering-capable.
            await self._defensive_reconciliation()
            raise ConfigEntryNotReady(f"run-id persistence failed: {err}") from err

        # Step 4: configuration validation.
        zone_configs = self._parse_zone_configs()

        # Step 5: passive actuator listeners BEFORE the snapshot (ER12),
        # then classify every configured actuator.
        self._install_passive_listeners(zone_configs)
        assessments = {
            zone_id: ActuatorAdapter(self.hass, cfg.actuator).current()
            for zone_id, cfg in zone_configs.items()
        }

        # Step 6: populate blockers and reconcile persisted state.
        for safety_record in self.store.data.safety_records.values():
            for reason in safety_record.blocker_reasons:
                await self.slots.async_add_blocker(safety_record.safety_record_id, reason)
        for zone_id, cfg in zone_configs.items():
            assessment = assessments[zone_id]
            record = self.store.data.zones.get(zone_id)
            safety_record_id = self._safety_record_id_for_zone(zone_id)
            watering_recovery = (
                record is not None
                and record.state is ControllerState.WATERING
                and record.session is not None
            )
            if not assessment.proven_off and not assessment.observed_on and not watering_recovery:
                # Unknown/unavailable/transitional at startup is never
                # proven OFF (§25.4); the keyed blocker holds until proof.
                await self.slots.async_add_blocker(
                    safety_record_id, BlockerReason.ACTUATOR_NOT_PROVEN_OFF
                )
            controller = self._create_controller(zone_id, cfg)
            await self._reconcile_zone(controller, record, assessment)
            if assessment.observed_on and not watering_recovery:
                # External flow across restart is respected, never
                # counter-commanded, but occupies the resource (§25.4):
                # T54/T55 bookkeeping adds the keyed blocker and the
                # external-ON flag so later proven OFF releases it (T58/T59).
                from .models import ExternalActuatorOn

                await controller.async_dispatch(ExternalActuatorOn())

        # Step 7: re-read every actuator after reconciliation.
        for zone_id, cfg in zone_configs.items():
            final = ActuatorAdapter(self.hass, cfg.actuator).current()
            safety_record_id = self._safety_record_id_for_zone(zone_id)
            if final.proven_off:
                # Terminal OFF proof releases this zone's startup keys
                # (exact-key; other zones/reasons are untouched, §21).
                await self.slots.async_remove_blocker(
                    safety_record_id, BlockerReason.ACTUATOR_NOT_PROVEN_OFF
                )
                await self.slots.async_remove_blocker(safety_record_id, BlockerReason.EXTERNAL_FLOW)

        # Step 8: activation. The controllers' own listeners replace the
        # passive ones (attach happened above, so there is no observation
        # gap); only now may grants be offered.
        self._remove_passive_listeners()
        self._install_periodic_triggers()
        await self.slots.async_enable_grants()

    async def _persist_slot_blocker(
        self,
        safety_record_id: str,
        reason: BlockerReason,
        active: bool,
    ) -> None:
        """Persist a live blocker when its canonical Stage-2 record exists.

        Empty-schema first-install callers still lack records until Stage 3;
        their live fallback key remains fail-closed but is deliberately not
        invented as schema-2 authority.
        """
        if not self.store.loaded or safety_record_id not in self.store.data.safety_records:
            return
        await self.store.async_set_record_blocker(safety_record_id, reason, active=active)

    def _mark_initialized(self) -> None:
        """§23.5 step 5: flag update only after verified Store state."""
        self.hass.config_entries.async_update_entry(
            self.entry,
            data={**self.entry.data, CONF_RUNTIME_STORE_INITIALIZED: True},
        )

    async def _reconstruct_after_integrity_loss(self) -> None:
        """§23.5 integrity-loss rows: reconstruct, exhaust today, Repair."""
        zone_configs = self._parse_zone_configs()
        detection_date = dt_util.utcnow().astimezone(self._local_tz).date()
        budgets = {zone_id: cfg.max_daily_runtime_s for zone_id, cfg in zone_configs.items()}
        try:
            await self.store.async_reconstruct_after_integrity_loss(budgets, detection_date)
        except StoreWriteVerificationError as err:
            raise ConfigEntryNotReady(f"integrity reconstruction write failed: {err}") from err
        from . import repairs

        repairs.async_create_integrity_issue(self.hass, self.entry.entry_id)
        _LOGGER.error(
            "Runtime safety store integrity lost (%s); watering blocked until "
            "acknowledgement and actuators are reconciled",
            self.entry.entry_id,
        )

    async def _defensive_reconciliation(self) -> None:
        """§24.4: minimal defensive OFF for persisted hazardous state."""
        if not self.store.loaded:
            return
        for zone_id, record in self.store.data.zones.items():
            if record.state is not ControllerState.WATERING:
                continue
            cfg = self._parse_zone_configs().get(zone_id)
            if cfg is None:
                continue
            adapter = ActuatorAdapter(self.hass, cfg.actuator)
            if not adapter.current().proven_off:
                try:
                    from homeassistant.core import Context

                    await adapter.async_turn_off(Context())
                except Exception as err:
                    _LOGGER.error("Defensive OFF for %s failed: %s", zone_id, err)

    def _parse_zone_configs(self) -> dict[str, ZoneConfig]:
        configs: dict[str, ZoneConfig] = {}
        for subentry_id, subentry in self.entry.subentries.items():
            if subentry.subentry_type != "zone":
                continue
            configs[subentry_id] = zone_config_from_subentry(dict(subentry.data))
        return configs

    def _create_controller(self, zone_id: str, cfg: ZoneConfig) -> ZoneController:
        controller = ZoneController(
            self.hass,
            zone_id,
            cfg,
            self.store,
            self.slots,
            run_id=self.run_id,
            local_tz=self._local_tz,
            emit=self._make_emitter(zone_id),
            safety_record_id=self._safety_record_id_for_zone(zone_id),
        )
        self.controllers[zone_id] = controller
        return controller

    def _safety_record_id_for_zone(self, zone_id: str) -> str:
        """Resolve exact blocker ownership for a current spec.3 caller.

        Stage 3 replaces the final fallback by materializing a canonical
        record before controller construction. Existing migrated records are
        already resolved by current subentry first, then unique legacy zone
        metadata; ambiguity fails closed instead of choosing a hazard owner.
        """
        if not self.store.loaded:
            return zone_id
        active = [
            record.safety_record_id
            for record in self.store.data.safety_records.values()
            if record.active_subentry_id == zone_id
        ]
        if len(active) == 1:
            return active[0]
        if len(active) > 1:
            raise ConfigEntryNotReady(f"multiple safety records own current subentry {zone_id}")
        legacy = [
            record.safety_record_id
            for record in self.store.data.safety_records.values()
            if record.zone_id == zone_id
        ]
        if len(legacy) == 1:
            return legacy[0]
        if len(legacy) > 1:
            raise ConfigEntryNotReady(f"ambiguous safety-record ownership for zone {zone_id}")
        return zone_id

    def _make_emitter(self, zone_id: str):
        def emit(kind: str, payload: dict) -> None:
            # Common identity fields (§32): subentry ID, zone name, device.
            controller = self.controllers.get(zone_id)
            enriched = dict(payload)
            enriched["zone_id"] = zone_id
            if controller is not None:
                enriched.setdefault("zone_name", controller.config_name)
                if "mode" not in enriched and controller.session is not None:
                    enriched["mode"] = controller.session.mode.value
            enriched["device_id"] = self._device_id(zone_id)
            self.hass.bus.async_fire(f"{DOMAIN}_{kind}", enriched)
            self._update_repairs(kind, zone_id, enriched)

        return emit

    def _device_id(self, zone_id: str) -> str | None:
        from homeassistant.helpers import device_registry as dr

        device = dr.async_get(self.hass).async_get_device({(DOMAIN, zone_id)})
        return device.id if device else None

    def _update_repairs(self, kind: str, zone_id: str, payload: dict) -> None:
        """§34 Repairs follow fault transitions."""
        from . import repairs
        from .models import FaultCode

        controller = self.controllers.get(zone_id)
        zone_name = controller.config_name if controller else zone_id
        if kind == "fault_set":
            fault = payload.get("fault")
            if fault == FaultCode.ACTUATOR_OFF_TIMEOUT.value:
                repairs.async_create_off_unconfirmed_issue(self.hass, zone_id, zone_name)
            elif fault == FaultCode.CONFIGURATION_INVALID.value and controller is not None:
                sensor = controller.config.moisture_sensor
                actuator = controller.config.actuator
                if self.hass.states.get(sensor) is None:
                    repairs.async_create_entity_missing_issue(
                        self.hass, zone_id, zone_name, sensor, actuator=False
                    )
                if self.hass.states.get(actuator) is None:
                    repairs.async_create_entity_missing_issue(
                        self.hass, zone_id, zone_name, actuator, actuator=True
                    )
            elif fault == FaultCode.RESTORED_FROM_UNSAFE_STATE.value:
                repairs.async_create_integrity_issue(self.hass, self.entry.entry_id)
        elif kind == "fault_cleared":
            fault = payload.get("fault")
            if fault == FaultCode.ACTUATOR_OFF_TIMEOUT.value:
                repairs.async_delete_off_unconfirmed_issue(self.hass, zone_id)
            elif fault == FaultCode.CONFIGURATION_INVALID.value:
                repairs.async_delete_entity_missing_issues(self.hass, zone_id)
            elif fault == FaultCode.RESTORED_FROM_UNSAFE_STATE.value and not any(
                c.active_fault is FaultCode.RESTORED_FROM_UNSAFE_STATE
                for c in self.controllers.values()
            ):
                repairs.async_delete_integrity_issue(self.hass, self.entry.entry_id)

    async def _reconcile_zone(
        self,
        controller: ZoneController,
        record: ZoneRecord | None,
        assessment,
    ) -> None:
        """Persisted WATERING/SOAKING/resting reconciliation (§25.2-§25.4)."""
        if record is None:
            controller.async_attach(None)
            return
        record = self._maybe_clear_configuration_fault(controller, record)
        if record.state is ControllerState.WATERING and record.session is not None:
            controller.async_attach(record)
            if assessment.observed_on:
                finding = ActuatorFinding.ON
            elif assessment.proven_off:
                finding = ActuatorFinding.OFF
            else:
                finding = ActuatorFinding.UNPROVEN
            await controller.async_dispatch(StartupPersistedWatering(finding))
            return
        if record.state is ControllerState.SOAKING and record.session is not None:
            await self._reconcile_soaking(controller, record, assessment)
            return
        controller.async_attach(record)

    async def _reconcile_soaking(
        self, controller: ZoneController, record: ZoneRecord, assessment
    ) -> None:
        """§25.3 trust checks, then atomic owner rebase before activation."""
        session = record.session
        assert session is not None
        previous = self.previous_run
        assert previous is not None
        trusted = (
            previous.previous_run_was_clean
            and session.owner_run_id == previous.active_run_id
            and self._session_structure_valid(session)
            and session.config_fingerprint
            == config_fingerprint(controller._config, str(self._local_tz))
            and assessment.available
            and assessment.proven_off
        )
        if trusted:
            try:
                # §23.3: persist and read-back verify the rebase before any
                # controller activation.
                await self.store.async_rebase_soaking_owner(controller.zone_id, self.run_id)
            except StoreWriteVerificationError as err:
                # LC9: watering-capable setup is prohibited; fail safe.
                raise ConfigEntryNotReady(f"soaking owner rebase failed: {err}") from err
            controller.async_attach(record)
            await controller.async_dispatch(
                StartupPersistedSoaking(trusted=True, current_run_id=self.run_id)
            )
            self.soaking_adoptions[controller.zone_id] = True
            session_now = controller.session
            now = dt_util.utcnow()
            if (
                session_now is not None
                and session_now.soak_ends_at_utc is not None
                and session_now.recheck_grace_deadline_at_utc is not None
                and session_now.soak_ends_at_utc <= now
                and session_now.recheck_grace_deadline_at_utc <= now
            ):
                # §25.3: both deadlines passed offline; check the current
                # observation once, then fault SENSOR_STALE if none qualify.
                controller._observation = controller._adapter.scan_current()
                await controller.async_dispatch(GraceDeadlineReached())
            return
        controller.async_attach(record)
        await controller.async_dispatch(StartupPersistedSoaking(trusted=False))
        self.soaking_adoptions[controller.zone_id] = False

    def _maybe_clear_configuration_fault(
        self, controller: ZoneController, record: ZoneRecord
    ) -> ZoneRecord:
        """§26.1: CONFIGURATION_INVALID clears via successful reconfigure.

        After a reload, if the persisted fault was CONFIGURATION_INVALID and
        both configured entities now exist, the reconfiguration resolved it:
        clear the fault and its Repairs.
        """
        from .models import ControllerState as CS
        from .models import FaultCode

        if record.active_fault is not FaultCode.CONFIGURATION_INVALID:
            return record
        config = controller.config
        if (
            self.hass.states.get(config.moisture_sensor) is None
            or self.hass.states.get(config.actuator) is None
        ):
            return record
        from . import repairs

        repairs.async_delete_entity_missing_issues(self.hass, controller.zone_id)
        _LOGGER.info(
            "Zone %s: configuration fault cleared after reconfiguration",
            controller.zone_id,
        )
        return record.evolve(state=CS.IDLE, active_fault=None)

    @staticmethod
    def _session_structure_valid(session: SessionContext) -> bool:
        if session.mode is not SessionMode.AUTO:
            return False
        soak = session.soak_ends_at_utc
        recheck = session.recheck_not_before_utc
        grace = session.recheck_grace_deadline_at_utc
        if soak is None or recheck is None or grace is None:
            return False
        if not (recheck == soak <= grace):
            return False
        off = session.off_confirmed_at_utc
        return off is not None and off <= soak

    # ------------------------------------------------------------------
    # Passive startup actuator observation (§25.1 step 5, ER12)
    # ------------------------------------------------------------------

    def _install_passive_listeners(self, zone_configs: dict[str, ZoneConfig]) -> None:
        for zone_id, cfg in zone_configs.items():
            adapter = ActuatorAdapter(self.hass, cfg.actuator)
            safety_record_id = self._safety_record_id_for_zone(zone_id)

            @callback
            def _passive(
                event: Event,
                safety_record_id: str = safety_record_id,
                adapter=adapter,
            ) -> None:
                assessment = adapter.assess(event.data["new_state"])
                if assessment.observed_on:
                    self.hass.async_create_task(
                        self.slots.async_add_blocker(safety_record_id, BlockerReason.EXTERNAL_FLOW)
                    )
                elif not assessment.proven_off:
                    self.hass.async_create_task(
                        self.slots.async_add_blocker(
                            safety_record_id,
                            BlockerReason.ACTUATOR_NOT_PROVEN_OFF,
                        )
                    )

            self._passive_unsubs.append(
                async_track_state_change_event(self.hass, [cfg.actuator], _passive)
            )

    def _remove_passive_listeners(self) -> None:
        for unsub in self._passive_unsubs:
            unsub()
        self._passive_unsubs = []

    def _install_periodic_triggers(self) -> None:
        """§16 triggers 4-5: the 15-minute fallback scan and HA-local
        midnight rollover evaluation."""
        from datetime import timedelta

        from homeassistant.helpers.event import (
            async_track_time_change,
            async_track_time_interval,
        )

        @callback
        def _scan(_now) -> None:
            for controller in self.controllers.values():
                self.hass.async_create_task(controller.async_fallback_scan())

        @callback
        def _midnight(_now) -> None:
            for controller in self.controllers.values():
                self.hass.async_create_task(controller.async_evaluate())

        self._activity_unsubs.append(
            async_track_time_interval(self.hass, _scan, timedelta(minutes=15))
        )
        self._activity_unsubs.append(
            async_track_time_change(self.hass, _midnight, hour=0, minute=0, second=0)
        )

    # ------------------------------------------------------------------
    # Full graceful process shutdown (§24.1)
    # ------------------------------------------------------------------

    def install_stop_listener(self) -> None:
        """Install the once-only EVENT_HOMEASSISTANT_STOP handler."""
        self._stop_unsub = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.async_handle_ha_stop
        )

    async def async_handle_ha_stop(self, _event: Event) -> None:
        """Once-only EVENT_HOMEASSISTANT_STOP handler (§24.1)."""
        if self.process_stopping:
            return
        self.process_stopping = True
        await self.slots.async_disable_grants()
        for controller in self.controllers.values():
            if controller.state is ControllerState.WATERING:
                await controller.async_dispatch(HomeAssistantShutdown())
                await self._await_off_within_budget(controller)
            elif controller.state is ControllerState.SOAKING:
                # T37: persist the active soak unchanged; no new water.
                await controller.async_dispatch(HomeAssistantShutdown())
            else:
                await self.store.async_update_zone(
                    controller.zone_id,
                    lambda _old, c=controller: c.build_record(),
                )
        # Only after every zone's safety handling is honestly persisted.
        # A failed clean marking is safe: the next run reads unequal IDs
        # and treats this run as unclean.
        try:
            await self.store.async_mark_clean_shutdown()
        except StoreWriteVerificationError as err:
            _LOGGER.error("Clean-shutdown marking failed: %s", err)

    async def _await_off_within_budget(self, controller: ZoneController) -> None:
        """Await cooperative OFF within the shutdown budget, then fall back.

        The budget is real wall-clock (the HA stop window is real; its
        tuning is §46 item 4). The bounded fallback cancels the session task
        and makes one best-effort call into the same OFF path (§24.1).
        """
        import asyncio

        # Give the session-owner task a few loop passes to enter the OFF
        # operation after the cooperative signal.
        for _ in range(10):
            await asyncio.sleep(0)
            if controller._off_operation is not None:
                break
        operation = controller._off_operation
        if operation is not None and not operation.done() and self.shutdown_off_budget_s > 0:
            await asyncio.wait({operation}, timeout=self.shutdown_off_budget_s)
        if operation is not None and operation.done():
            return
        if controller.session is None or controller.state is not ControllerState.WATERING:
            return
        # Bounded fallback: forced cancellation plus best-effort OFF.
        task = controller._session_task
        if task is not None and not task.done():
            task.cancel()
        from homeassistant.core import Context

        try:
            await controller._actuator.async_turn_off(Context())
        except Exception as err:
            _LOGGER.error("Zone %s: best-effort shutdown OFF failed: %s", controller.zone_id, err)

    # ------------------------------------------------------------------
    # Generic entry unload/reload (§24.2)
    # ------------------------------------------------------------------

    async def async_unload(self) -> None:
        if self._stop_unsub is not None:
            self._stop_unsub()
            self._stop_unsub = None
        await self.slots.async_disable_grants()
        if not self.process_stopping:
            # Terminate WATERING and SOAKING as CONFIG_RELOAD; never mark
            # the process run clean and never change run IDs (§24.2).
            for controller in self.controllers.values():
                was_watering = controller.state is ControllerState.WATERING
                if was_watering or controller.state is ControllerState.SOAKING:
                    await controller.async_dispatch(ConfigEntryReload())
                if was_watering:
                    # Await cooperative OFF before teardown (§24.2), with
                    # the same bounded fallback as shutdown.
                    await self._await_off_within_budget(controller)
        for controller in self.controllers.values():
            await controller.async_detach()
        self._remove_passive_listeners()
        for unsub in self._activity_unsubs:
            unsub()
        self._activity_unsubs = []
        self.controllers = {}

    # ------------------------------------------------------------------
    # Subentry reconfiguration/deletion preparation (§24.3)
    # ------------------------------------------------------------------

    async def async_prepare_reconfigure(self, zone_id: str) -> None:
        """Cooperatively terminate the zone's session as CONFIG_CHANGED.

        The config flow then calls the 2025.9.0 subentry update-and-reload
        helper exactly once (Slice 9); no update listener exists.
        """
        controller = self.controllers.get(zone_id)
        if controller is None:
            return
        await self.slots.async_cancel_request(zone_id)
        if controller.state in (ControllerState.WATERING, ControllerState.SOAKING):
            was_watering = controller.state is ControllerState.WATERING
            await controller.async_dispatch(ConfigChangedPrepare())
            if was_watering:
                await self._await_off_within_budget(controller)

    async def async_prepare_delete(self, zone_id: str) -> None:
        """Deletion preparation: same safety path (§24.3).

        Removal never clears an unproven-OFF water-resource blocker (§21).
        """
        await self.async_prepare_reconfigure(zone_id)
