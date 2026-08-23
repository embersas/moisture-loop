"""Base entity for Moisture Loop zone entities (SPECIFICATION.md §28).

All entities use stable ``{subentry_id}_{key}`` unique IDs,
``has_entity_name = True``, translation keys, and the zone device with the
subentry attribution. Entities are presentation only: they never make
safety decisions (I27) and route every control through the validated
controller paths.
"""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .runtime import EntryRuntime
from .zone_controller import ZoneController


class MoistureLoopZoneEntity(Entity):
    """Common zone-device wiring for all Moisture Loop entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        runtime: EntryRuntime,
        controller: ZoneController,
        subentry_id: str,
        key: str,
    ) -> None:
        self._runtime = runtime
        self._controller = controller
        self._key = key
        self._attr_unique_id = f"{subentry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=controller.config_name,
        )

    @property
    def available(self) -> bool:
        """Entities never present a tombstone as a configured ACTIVE zone."""
        return self._runtime.entity_runtime_active(self._controller)

    def _ensure_control_available(self) -> None:
        """Direct entity calls fail visibly instead of silently no-oping."""
        if (key := self._runtime.action_refusal_key(self._controller)) is not None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=key,
            )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._controller.async_add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
