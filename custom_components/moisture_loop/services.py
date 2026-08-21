"""Integration-level actions for Moisture Loop (SPECIFICATION.md §5.3, §31).

Actions are registered exactly once from integration-level ``async_setup``
(never per entry), so they remain discoverable while entries are unloaded
(I25). Every handler requires exactly one zone ``device_id`` and resolves it
in the backend: the device must carry the ``(moisture_loop, subentry_id)``
identifier, belong to the Moisture Loop entry/subentry, and have a loaded
runtime; frontend filtering is never trusted (§5.3). Failures raise
translated ``ServiceValidationError``s.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

if TYPE_CHECKING:
    from .zone_controller import ZoneController

SERVICE_START_MANUAL = "start_manual_watering"
SERVICE_STOP = "stop_watering"
SERVICE_EVALUATE = "evaluate_zone"
SERVICE_CLEAR_FAULT = "clear_fault"

_DEVICE_SCHEMA = vol.Schema({vol.Required("device_id"): cv.string})
_MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Required("duration"): vol.All(vol.Coerce(float)),
    }
)


def _error(key: str, **placeholders: str) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders or None,
    )


def _resolve_controller(hass: HomeAssistant, device_id: str) -> ZoneController:
    """Authoritative backend zone-device resolution (§5.3, LC2)."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device is None:
        raise _error("device_not_found")
    subentry_ids = [identifier[1] for identifier in device.identifiers if identifier[0] == DOMAIN]
    if len(subentry_ids) != 1:
        raise _error("not_a_zone_device")
    subentry_id = subentry_ids[0]
    entries = hass.config_entries.async_entries(DOMAIN)
    entry = next((e for e in entries if e.entry_id in device.config_entries), None)
    if entry is None:
        raise _error("not_a_zone_device")
    if subentry_id not in entry.subentries:
        raise _error("zone_deleted")
    if entry.state is not ConfigEntryState.LOADED:
        raise _error("entry_not_loaded")
    runtime = getattr(entry, "runtime_data", None)
    controller = runtime.controllers.get(subentry_id) if runtime else None
    if controller is None:
        raise _error("zone_not_ready")
    return controller


def _raise_for_refusal(decision, action: str) -> None:
    """Translate a pure guard refusal into a ServiceValidationError."""
    result = decision.guard_result
    if result is None or result.passed:
        return
    failed = set(result.failed_guards)
    if "G-EN" in failed:
        raise _error("zone_disabled")
    if any(tag.endswith("invalid_duration") for tag in failed):
        raise _error("invalid_duration")
    if any(tag.endswith("active_session") for tag in failed):
        raise _error("session_active")
    if "G-MANUAL-SENSOR" in failed:
        raise _error("fault_blocks_manual")
    if "G-ACT" in failed:
        raise _error("actuator_not_ready")
    if any(tag.endswith("daily_exhausted") for tag in failed):
        raise _error("daily_budget_exhausted")
    if any(tag.endswith("water_resource_occupied") for tag in failed):
        raise _error("water_resource_occupied")
    if "G-SLOT" in failed:
        # Queueing for the slot is a wait, not a refusal.
        return
    raise _error("request_refused")


def async_register_services(hass: HomeAssistant) -> None:
    """Register all §31 actions once from async_setup (I25)."""
    if hass.services.has_service(DOMAIN, SERVICE_START_MANUAL):
        return  # registered once; reloads never duplicate (LC1)

    async def start_manual_watering(call: ServiceCall) -> None:
        controller = _resolve_controller(hass, call.data["device_id"])
        duration = float(call.data["duration"])
        # Validity is enforced by the pure G-MANUAL-SAFE guard; the refusal
        # is translated below (finite, strictly positive).
        decision = await controller.async_manual_start(duration)
        _raise_for_refusal(decision, SERVICE_START_MANUAL)

    async def stop_watering(call: ServiceCall) -> None:
        controller = _resolve_controller(hass, call.data["device_id"])
        await controller.async_stop_watering()

    async def evaluate_zone(call: ServiceCall) -> None:
        controller = _resolve_controller(hass, call.data["device_id"])
        await controller.async_evaluate()

    async def clear_fault(call: ServiceCall) -> None:
        controller = _resolve_controller(hass, call.data["device_id"])
        decision = await controller.async_clear_fault()
        if decision.transition_id == "T44":
            raise _error("fault_not_clearable")

    hass.services.async_register(
        DOMAIN, SERVICE_START_MANUAL, start_manual_watering, _MANUAL_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_STOP, stop_watering, _DEVICE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_EVALUATE, evaluate_zone, _DEVICE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_FAULT, clear_fault, _DEVICE_SCHEMA)
