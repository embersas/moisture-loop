"""MoistureLoop control buttons (SPECIFICATION.md §28.3).

Manual watering is offered only as fixed-duration buttons. A button cannot
prompt for a value, so each one carries its own bounded duration as part of
its identity; the open-ended manual start stays action-only (§31).
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MoistureLoopZoneEntity
from .runtime import EntryRuntime
from .services import raise_for_manual_refusal
from .zone_controller import ZoneController

# Offered manual durations in whole minutes (§28.3). Each value is a distinct
# entity key, so this tuple is part of the stable unique-ID surface and must
# not be reordered or renumbered.
MANUAL_PULSE_MINUTES = (15, 30, 60)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime: EntryRuntime = entry.runtime_data
    for subentry_id, controller in runtime.controllers.items():
        entities: list[ButtonEntity] = [
            ZoneStopButton(runtime, controller, subentry_id),
            ZoneEvaluateButton(runtime, controller, subentry_id),
            ZoneClearFaultButton(runtime, controller, subentry_id),
        ]
        entities.extend(
            ZoneManualPulseButton(runtime, controller, subentry_id, minutes)
            for minutes in MANUAL_PULSE_MINUTES
        )
        async_add_entities(entities, config_subentry_id=subentry_id)


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


class ZoneManualPulseButton(MoistureLoopZoneEntity, ButtonEntity):
    """One fixed-duration manual watering request (§20, §28.3).

    The duration is fixed at construction, so the press supplies a bounded
    value and never an open-ended ON. Every §14 guard, the §20 clamp against
    ``manual_max_duration``/``max_session_runtime``/remaining daily budget,
    the FIFO slot, and the final live authorization fence all still apply:
    this is presentation over ``async_manual_start`` and decides nothing
    itself (I27).
    """

    def __init__(
        self,
        runtime: EntryRuntime,
        controller: ZoneController,
        subentry_id: str,
        minutes: int,
    ) -> None:
        super().__init__(runtime, controller, subentry_id, f"manual_pulse_{minutes}")
        self._duration_s = float(minutes * 60)

    @property
    def available(self) -> bool:
        return self._runtime.control_entity_available(self._controller)

    async def async_press(self) -> None:
        self._ensure_control_available()
        decision = await self._controller.async_manual_start(self._duration_s)
        # A refusal must be visible. Waiting for the slot is not a refusal,
        # so a queued request returns normally.
        raise_for_manual_refusal(decision)
