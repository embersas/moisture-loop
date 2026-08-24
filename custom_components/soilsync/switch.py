"""SoilSync enabled switch (SPECIFICATION.md §28.3)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import SoilSyncZoneEntity
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
            [ZoneEnabledSwitch(runtime, controller, subentry_id)],
            config_subentry_id=subentry_id,
        )


class ZoneEnabledSwitch(SoilSyncZoneEntity, SwitchEntity):
    """Runtime enable/disable; Disable terminates an active session (I20)."""

    def __init__(self, runtime: EntryRuntime, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(runtime, controller, subentry_id, "enabled")

    @property
    def available(self) -> bool:
        return self._runtime.control_entity_available(self._controller)

    @property
    def is_on(self) -> bool:
        authority = self._runtime.canonical_zone_authority(self._controller)
        return bool(authority and authority[1].zone_runtime.enabled)

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._ensure_control_available()
        await self._controller.async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._ensure_control_available()
        await self._controller.async_set_enabled(False)
