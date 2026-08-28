"""MoistureLoop binary sensors (SPECIFICATION.md §28.2)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MoistureLoopZoneEntity
from .models import BlockerReason, ControllerState, MoistureClassification
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
                ZoneWateringBinarySensor(runtime, controller, subentry_id),
                ZoneProblemBinarySensor(runtime, controller, subentry_id),
                ZoneNeedsWaterBinarySensor(runtime, controller, subentry_id),
            ],
            config_subentry_id=subentry_id,
        )


class ZoneWateringBinarySensor(MoistureLoopZoneEntity, BinarySensorEntity):
    """ON while this configured actuator may be flowing (§28.2)."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, runtime: EntryRuntime, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(runtime, controller, subentry_id, "watering")

    @property
    def is_on(self) -> bool:
        authority = self._runtime.canonical_zone_authority(self._controller)
        if authority is None:
            return False
        record, history = authority
        return (
            history.zone_runtime.state is ControllerState.WATERING
            or record.possible_flow_owner is not None
            or BlockerReason.EXTERNAL_FLOW in record.blocker_reasons
            or BlockerReason.INTEGRATION_OFF_UNCONFIRMED in record.blocker_reasons
        )


class ZoneProblemBinarySensor(MoistureLoopZoneEntity, BinarySensorEntity):
    """ON for this zone's fault metadata or a global water-resource block (§28.2).

    A keyed water-resource blocker anywhere in the entry withholds the single
    watering slot from every configured zone (I19, §21), so a zone can be
    perfectly healthy and still be unable to ever water. Reporting OK in that
    state hides an integration-wide safety condition, so the blocker set is
    part of Problem.

    Ordinary serialization is deliberately excluded: waiting behind another
    legitimately watering zone is normal operation, not a problem, so slot
    ownership and queue position never raise this sensor.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, runtime: EntryRuntime, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(runtime, controller, subentry_id, "problem")

    @property
    def is_on(self) -> bool:
        authority = self._runtime.canonical_zone_authority(self._controller)
        if authority is None:
            return False
        record, history = authority
        session = history.zone_runtime.session
        return (
            record.actuator_fault is not None
            or history.zone_runtime.zone_fault is not None
            or history.zone_runtime.secondary_fault is not None
            or record.identity_incident is not None
            or self._runtime.coordinator.failed
            or (session is not None and session.context.retained_sensor_fault is not None)
            or self._runtime.water_resource_blocked
        )

    @property
    def extra_state_attributes(self) -> dict:
        # Reasons only: a normal entity state never needs internal record UUIDs.
        return {
            "water_resource_blocked": self._runtime.water_resource_blocked,
            "water_resource_blocker_reasons": self._runtime.water_resource_blocker_reasons,
        }


class ZoneNeedsWaterBinarySensor(MoistureLoopZoneEntity, BinarySensorEntity):
    """Informational dryness view; never a guard bypass (§28.2, I27).

    ON only when the latest observation is VALID+fresh and strictly below
    the start threshold; unavailable when invalid, unavailable, stale, or
    absent — never falsely OFF.

    No device class: ON means "needs water" (dry), which is the opposite of
    ``BinarySensorDeviceClass.MOISTURE`` (ON = wet). State wording comes from
    the ``needs_water`` translation key instead (Yes/No).
    """

    def __init__(self, runtime: EntryRuntime, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(runtime, controller, subentry_id, "needs_water")

    @property
    def available(self) -> bool:
        observation = self._controller.observation
        return (
            self._runtime.control_entity_available(self._controller)
            and observation.classification is MoistureClassification.VALID
        )

    @property
    def is_on(self) -> bool:
        observation = self._controller.observation
        if not self.available:
            return False
        assert observation.value is not None
        return observation.value < self._controller.config.start_threshold
