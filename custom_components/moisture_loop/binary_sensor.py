"""Moisture Loop binary sensors (SPECIFICATION.md §28.2)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MoistureLoopZoneEntity
from .models import MoistureClassification
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
                ZoneWateringBinarySensor(controller, subentry_id),
                ZoneProblemBinarySensor(controller, subentry_id),
                ZoneNeedsWaterBinarySensor(controller, subentry_id),
            ],
            config_subentry_id=subentry_id,
        )


class ZoneWateringBinarySensor(MoistureLoopZoneEntity, BinarySensorEntity):
    """ON while this configured actuator may be flowing (§28.2)."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(controller, subentry_id, "watering")

    @property
    def is_on(self) -> bool:
        return self._controller.may_be_flowing


class ZoneProblemBinarySensor(MoistureLoopZoneEntity, BinarySensorEntity):
    """ON whenever active or retained fault metadata exists (§28.2)."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(controller, subentry_id, "problem")

    @property
    def is_on(self) -> bool:
        controller = self._controller
        session = controller.session
        return (
            controller.active_fault is not None
            or controller.secondary_fault is not None
            or (session is not None and session.retained_sensor_fault is not None)
        )


class ZoneNeedsWaterBinarySensor(MoistureLoopZoneEntity, BinarySensorEntity):
    """Informational dryness view; never a guard bypass (§28.2, I27).

    ON only when the latest observation is VALID+fresh and strictly below
    the start threshold; unavailable when invalid, unavailable, stale, or
    absent — never falsely OFF.
    """

    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    def __init__(self, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(controller, subentry_id, "needs_water")

    @property
    def available(self) -> bool:
        observation = self._controller.observation
        return observation.classification is MoistureClassification.VALID

    @property
    def is_on(self) -> bool:
        observation = self._controller.observation
        if observation.classification is not MoistureClassification.VALID:
            return False
        assert observation.value is not None
        return observation.value < self._controller.config.start_threshold
