"""Moisture Loop enabled switch (SPECIFICATION.md §28.3)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MoistureLoopZoneEntity
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
            [ZoneEnabledSwitch(controller, subentry_id)],
            config_subentry_id=subentry_id,
        )


class ZoneEnabledSwitch(MoistureLoopZoneEntity, SwitchEntity):
    """Runtime enable/disable; Disable terminates an active session (I20)."""

    def __init__(self, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(controller, subentry_id, "enabled")

    @property
    def is_on(self) -> bool:
        return self._controller.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._controller.async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._controller.async_set_enabled(False)
