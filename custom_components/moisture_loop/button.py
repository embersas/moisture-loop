"""Moisture Loop control buttons (SPECIFICATION.md §28.3).

There is deliberately no manual-start button: a mandatory duration cannot
be safely supplied by a button press (§28.3).
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
            [
                ZoneStopButton(runtime, controller, subentry_id),
                ZoneEvaluateButton(runtime, controller, subentry_id),
                ZoneClearFaultButton(runtime, controller, subentry_id),
            ],
            config_subentry_id=subentry_id,
        )


class ZoneStopButton(MoistureLoopZoneEntity, ButtonEntity):
    """Cooperative Stop (§28.3); a no-op in inactive states."""

    def __init__(self, runtime: EntryRuntime, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(runtime, controller, subentry_id, "stop")

    @property
    def available(self) -> bool:
        return self._runtime.control_entity_available(self._controller)

    async def async_press(self) -> None:
        self._ensure_control_available()
        await self._controller.async_stop_watering()


class ZoneEvaluateButton(MoistureLoopZoneEntity, ButtonEntity):
    """Normal guarded AUTO evaluation (§28.3); bypasses nothing."""

    def __init__(self, runtime: EntryRuntime, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(runtime, controller, subentry_id, "evaluate_now")

    @property
    def available(self) -> bool:
        return self._runtime.control_entity_available(self._controller)

    async def async_press(self) -> None:
        self._ensure_control_available()
        await self._controller.async_evaluate()


class ZoneClearFaultButton(MoistureLoopZoneEntity, ButtonEntity):
    """Fault acknowledgement through the validated path (§26.1, §28.3)."""

    def __init__(self, runtime: EntryRuntime, controller: ZoneController, subentry_id: str) -> None:
        super().__init__(runtime, controller, subentry_id, "clear_fault")

    @property
    def available(self) -> bool:
        return self._runtime.control_entity_available(self._controller)

    async def async_press(self) -> None:
        self._ensure_control_available()
        await self._controller.async_clear_fault()
