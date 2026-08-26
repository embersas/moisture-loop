"""Schema-2 MoistureLoop sensors (§28.1)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import ClassVar

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MoistureLoopZoneEntity
from .models import ControllerState
from .runtime import EntryRuntime
from .zone_controller import ZoneController


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime: EntryRuntime = entry.runtime_data
    for subentry_id, controller in runtime.controllers.items():
        async_add_entities(
            [
                ZoneStatusSensor(runtime, controller, subentry_id),
                ZoneRuntimeTodaySensor(runtime, controller, subentry_id),
                ZoneLastSessionSensor(runtime, controller, subentry_id),
                ZoneNextEligibleSensor(runtime, controller, subentry_id),
            ],
            config_subentry_id=subentry_id,
        )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _short(value: str | None) -> str | None:
    return value[:12] if value else None


class ZoneStatusSensor(MoistureLoopZoneEntity, SensorEntity):
    """Five-state logical-zone view plus exact actuator safety context."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = [state.value for state in ControllerState]

    def __init__(self, runtime: EntryRuntime, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(runtime, controller, subentry_id, "status")

    @property
    def native_value(self) -> str:
        authority = self._runtime.canonical_zone_authority(self._controller)
        return (
            authority[1].zone_runtime.state.value
            if authority is not None
            else self._controller.state.value
        )

    @property
    def extra_state_attributes(self) -> dict:
        controller = self._controller
        authority = self._runtime.canonical_zone_authority(controller)
        record, history = authority if authority is not None else (None, None)
        zone_runtime = history.zone_runtime if history is not None else None
        session = controller.session
        observation = controller.observation
        slots = self._runtime.slots.snapshot()
        actuator_fault = record.actuator_fault if record is not None else None
        zone_fault = zone_runtime.zone_fault if zone_runtime is not None else None
        active_fault = actuator_fault or zone_fault
        secondary_fault = (
            zone_fault
            if actuator_fault is not None
            else (zone_runtime.secondary_fault if zone_runtime is not None else None)
        )
        return {
            "controller_state": self.native_value,
            "mode": session.mode.value if session else None,
            "lifecycle": record.runtime_lifecycle.value if record else None,
            "safety_record_id": record.safety_record_id if record else None,
            "safety_lineage_id": record.safety_lineage_id if record else None,
            "zone_history_id": history.zone_history_id if history else None,
            "actuator_identity_status": (
                record.actuator_identity.identity_status.value if record else None
            ),
            "actuator_registry_id_short": (
                _short(record.actuator_identity.registry_entry_id) if record else None
            ),
            "cycle": session.cycle if session else None,
            "session_runtime_s": session.session_runtime_s if session else None,
            "runtime_estimated": session.runtime_estimated if session else None,
            "runtime_estimation_reason": (
                session.runtime_estimation_reason.value if session else None
            ),
            "sensor_fresh_until_utc": (_iso(session.sensor_fresh_until_utc) if session else None),
            "active_fault": active_fault.value if active_fault else None,
            "retained_sensor_fault": (
                session.retained_sensor_fault.value
                if session and session.retained_sensor_fault
                else None
            ),
            "secondary_fault": secondary_fault.value if secondary_fault else None,
            "identity_incident": (
                record.identity_incident.kind.value if record and record.identity_incident else None
            ),
            "moisture": observation.value,
            "moisture_classification": observation.classification.value,
            "moisture_reported_at_utc": _iso(observation.reported_at_utc),
            "external_actuator_on": controller.external_on,
            "waiting_for_slot": (
                slots.owner != controller.zone_id and controller.zone_id in slots.queue
            ),
            "water_resource_blockers": [
                {"safety_record_id": record_id, "reason": reason.value}
                for record_id, reason in slots.blockers
            ],
            "record_blockers": (
                [reason.value for reason in record.blocker_reasons] if record else []
            ),
            "possible_flow_owner": (
                record.possible_flow_owner.value if record and record.possible_flow_owner else None
            ),
            "open_accounting": bool(
                zone_runtime is not None
                and zone_runtime.session is not None
                and record is not None
                and record.possible_flow_owner is not None
            ),
            "reconciliation": {
                "observed_generation": self._runtime.coordinator.observed_generation,
                "applied_generation": self._runtime.coordinator.applied_generation,
                "dirty": self._runtime.coordinator.dirty,
                "reconciling": self._runtime.coordinator.reconciling,
                "failed": self._runtime.coordinator.failed,
                "reload_pending": self._runtime.coordinator.reload_pending,
                "last_error": self._runtime.coordinator.last_error,
                "admission_open": slots.admission_open,
            },
            "applied_generation": (
                record.applied_config.applied_generation
                if record and record.applied_config
                else None
            ),
            "config_fingerprint_short": (
                _short(record.applied_config.config_fingerprint)
                if record and record.applied_config
                else None
            ),
        }


class ZoneRuntimeTodaySensor(MoistureLoopZoneEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "s"

    def __init__(self, runtime: EntryRuntime, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(runtime, controller, subentry_id, "watering_runtime_today")

    @property
    def native_value(self) -> float:
        authority = self._runtime.canonical_zone_authority(self._controller)
        daily = authority[1].daily if authority is not None else None
        return round(daily.runtime_s if daily else 0.0, 1)


class ZoneLastSessionSensor(MoistureLoopZoneEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, runtime: EntryRuntime, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(runtime, controller, subentry_id, "last_session")

    def _summary(self):
        authority = self._runtime.canonical_zone_authority(self._controller)
        return authority[1].zone_runtime.last_session_summary if authority else None

    @property
    def native_value(self) -> datetime | None:
        summary = self._summary()
        return summary.ended_at_utc if summary else None

    @property
    def extra_state_attributes(self) -> dict:
        summary = self._summary()
        if summary is None:
            return {}
        return {
            "reason": summary.reason.value,
            "mode": summary.mode.value,
            "runtime_s": summary.runtime_s,
            "runtime_estimated": summary.runtime_estimated,
            "runtime_estimation_reason": summary.runtime_estimation_reason.value,
            "cycles": summary.cycles,
            "moisture_before": summary.moisture_before,
            "moisture_after": summary.moisture_after,
            "requested_duration_s": summary.requested_duration_s,
            "effective_duration_s": summary.effective_duration_s,
            "clamp_reasons": [reason.value for reason in summary.clamp_reasons],
        }


class ZoneNextEligibleSensor(MoistureLoopZoneEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, runtime: EntryRuntime, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(runtime, controller, subentry_id, "next_eligible")

    @property
    def native_value(self) -> datetime | None:
        authority = self._runtime.canonical_zone_authority(self._controller)
        last_end = authority[1].last_session_end_utc if authority else None
        if last_end is None:
            return None
        return last_end + timedelta(seconds=self._controller.config.min_session_interval_s)
