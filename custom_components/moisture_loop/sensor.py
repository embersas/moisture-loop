"""Moisture Loop sensors (SPECIFICATION.md §28.1)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import ClassVar

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
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
                ZoneRuntimeTodaySensor(controller, subentry_id),
                ZoneLastSessionSensor(controller, subentry_id),
                ZoneNextEligibleSensor(controller, subentry_id),
            ],
            config_subentry_id=subentry_id,
        )


class ZoneStatusSensor(MoistureLoopZoneEntity, SensorEntity):
    """Controller state with full diagnostic attributes (§28.1)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = [state.value for state in ControllerState]

    def __init__(self, runtime: EntryRuntime, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(controller, subentry_id, "status")
        self._runtime = runtime

    @property
    def native_value(self) -> str:
        return self._controller.state.value

    @property
    def extra_state_attributes(self) -> dict:
        controller = self._controller
        session = controller.session
        observation = controller.observation
        return {
            "mode": session.mode.value if session else None,
            "cycle": session.cycle if session else None,
            "session_runtime_s": session.session_runtime_s if session else None,
            "runtime_estimated": session.runtime_estimated if session else None,
            "runtime_estimation_reason": (
                session.runtime_estimation_reason.value if session else None
            ),
            "sensor_fresh_until_utc": (
                session.sensor_fresh_until_utc.isoformat()
                if session and session.sensor_fresh_until_utc
                else None
            ),
            "active_fault": (controller.active_fault.value if controller.active_fault else None),
            "retained_sensor_fault": (
                session.retained_sensor_fault.value
                if session and session.retained_sensor_fault
                else None
            ),
            "secondary_fault": (
                controller.secondary_fault.value if controller.secondary_fault else None
            ),
            "moisture": observation.value,
            "moisture_classification": observation.classification.value,
            "moisture_reported_at_utc": (
                observation.reported_at_utc.isoformat() if observation.reported_at_utc else None
            ),
            "external_actuator_on": controller.external_on,
            "waiting_for_slot": (
                self._runtime.slots.owner != controller.zone_id
                and controller.zone_id in self._runtime.slots.snapshot().queue
            ),
            "water_resource_blockers": [
                {"zone_id": zone_id, "reason": reason.value}
                for zone_id, reason in self._runtime.slots.snapshot().blockers
            ],
        }


class ZoneRuntimeTodaySensor(MoistureLoopZoneEntity, SensorEntity):
    """Conservative current local-day runtime (§28.1)."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "s"

    def __init__(self, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(controller, subentry_id, "watering_runtime_today")

    @property
    def native_value(self) -> float:
        return round(self._controller.daily.runtime_s, 1)


class ZoneLastSessionSensor(MoistureLoopZoneEntity, SensorEntity):
    """Last session end with summary attributes (§28.1)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(controller, subentry_id, "last_session")

    @property
    def native_value(self) -> datetime | None:
        summary = self._controller.last_summary
        return summary.ended_at_utc if summary else None

    @property
    def extra_state_attributes(self) -> dict:
        summary = self._controller.last_summary
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
    """Derived minimum-interval timestamp when meaningful (§28.1)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(controller, subentry_id, "next_eligible")

    @property
    def native_value(self) -> datetime | None:
        last_end = self._controller.last_session_end
        if last_end is None:
            return None
        return last_end + timedelta(seconds=self._controller.config.min_session_interval_s)
