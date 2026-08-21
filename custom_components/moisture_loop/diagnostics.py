"""Config-entry diagnostics for Moisture Loop (SPECIFICATION.md §33.2).

Diagnostics are presentation only, never safety authority; Recorder is not
consulted (I28). Run/generation UUIDs are hash-shortened via the standard
redaction helper where full values are unnecessary.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as ha_version
from homeassistant.core import HomeAssistant

from .const import CONF_RUNTIME_STORE_GENERATION_ID
from .models import store_data_to_dict
from .runtime import EntryRuntime

_REDACT_ENTRY = {CONF_RUNTIME_STORE_GENERATION_ID}
_REDACT_STORE = {"generation_id", "active_run_id", "last_clean_shutdown_run_id"}


def _short(value: str | None) -> str | None:
    return None if value is None else value[:8]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return the §33.2 diagnostic payload."""
    runtime: EntryRuntime = entry.runtime_data
    store_data = runtime.store.data if runtime.store.loaded else None
    slots = runtime.slots.snapshot()

    zones: dict[str, Any] = {}
    transitions: list[dict[str, Any]] = []
    for zone_id, controller in runtime.controllers.items():
        session = controller.session
        observation = controller.observation
        off_operation = controller._off_operation
        zones[zone_id] = {
            "config": {
                "name": controller.config.name,
                "moisture_sensor": controller.config.moisture_sensor,
                "actuator": controller.config.actuator,
                "start_threshold": controller.config.start_threshold,
                "target_threshold": controller.config.target_threshold,
                "pulse_duration_s": controller.config.pulse_duration_s,
                "soak_duration_s": controller.config.soak_duration_s,
                "max_cycles": controller.config.max_cycles,
                "max_session_runtime_s": controller.config.max_session_runtime_s,
                "max_daily_runtime_s": controller.config.max_daily_runtime_s,
                "min_session_interval_s": controller.config.min_session_interval_s,
                "sensor_max_age_s": controller.config.sensor_max_age_s,
                "actuator_confirm_timeout_s": controller.config.actuator_confirm_timeout_s,
                "manual_max_duration_s": controller.config.manual_max_duration_s,
            },
            "state": controller.state.value,
            "enabled": controller.enabled,
            "active_fault": (controller.active_fault.value if controller.active_fault else None),
            "secondary_fault": (
                controller.secondary_fault.value if controller.secondary_fault else None
            ),
            "observation": {
                "value": observation.value,
                "classification": observation.classification.value,
                "reported_at_utc": (
                    observation.reported_at_utc.isoformat() if observation.reported_at_utc else None
                ),
                "age_s": observation.age_s,
            },
            "sensor_fresh_until_utc": (
                session.sensor_fresh_until_utc.isoformat()
                if session and session.sensor_fresh_until_utc
                else None
            ),
            "actuator_classification": {
                "available": controller.assessment.available,
                "proven_off": controller.assessment.proven_off,
                "observed_on": controller.assessment.observed_on,
            },
            "external_actuator_on": controller.external_on,
            "session": {
                "session_id": session.session_id,
                "mode": session.mode.value,
                "cycle": session.cycle,
                "started_at_utc": session.started_at_utc.isoformat(),
                "pulse_intent_at_utc": (
                    session.pulse_intent_at_utc.isoformat() if session.pulse_intent_at_utc else None
                ),
                "pulse_commanded_at_utc": (
                    session.pulse_commanded_at_utc.isoformat()
                    if session.pulse_commanded_at_utc
                    else None
                ),
                "pulse_confirmed_at_utc": (
                    session.pulse_confirmed_at_utc.isoformat()
                    if session.pulse_confirmed_at_utc
                    else None
                ),
                "off_confirmed_at_utc": (
                    session.off_confirmed_at_utc.isoformat()
                    if session.off_confirmed_at_utc
                    else None
                ),
                "soak_ends_at_utc": (
                    session.soak_ends_at_utc.isoformat() if session.soak_ends_at_utc else None
                ),
                "recheck_grace_deadline_at_utc": (
                    session.recheck_grace_deadline_at_utc.isoformat()
                    if session.recheck_grace_deadline_at_utc
                    else None
                ),
                "pending_termination_reason": (
                    session.pending_termination_reason.value
                    if session.pending_termination_reason
                    else None
                ),
                "runtime_s": session.session_runtime_s,
                "runtime_estimated": session.runtime_estimated,
                "runtime_estimation_reason": session.runtime_estimation_reason.value,
                "retained_sensor_fault": (
                    session.retained_sensor_fault.value if session.retained_sensor_fault else None
                ),
            }
            if session
            else None,
            "off_operation": (
                None
                if off_operation is None
                else {
                    "done": off_operation.done(),
                    "confirmed": (off_operation.result() if off_operation.done() else None),
                }
            ),
            "daily": {
                "date_local": controller.daily.date_local.isoformat(),
                "runtime_s": controller.daily.runtime_s,
            },
            "last_session_end_utc": (
                controller.last_session_end.isoformat() if controller.last_session_end else None
            ),
        }
        transitions.extend(controller.transitions)

    transitions.sort(key=lambda item: item["at_utc"])
    return {
        "home_assistant_version": ha_version,
        "manifest": {
            "integration_type": "helper",
            "iot_class": "calculated",
            "single_config_entry": True,
        },
        "entry_data": async_redact_data(dict(entry.data), _REDACT_ENTRY),
        "store": {
            "loaded": runtime.store.loaded,
            "setup_classification": (
                runtime.setup_classification.value if runtime.setup_classification else None
            ),
            "schema_version": store_data.version if store_data else None,
            "store_revision": store_data.store_revision if store_data else None,
            "current_run_id_short": _short(runtime.run_id),
            "previous_run_was_clean": (
                runtime.previous_run.previous_run_was_clean if runtime.previous_run else None
            ),
            "soaking_adoptions": runtime.soaking_adoptions,
        },
        "slot_manager": {
            "owner": slots.owner,
            "queue": list(slots.queue),
            "blockers": [
                {"zone_id": zone_id, "reason": reason.value} for zone_id, reason in slots.blockers
            ],
            "grants_enabled": slots.grants_enabled,
        },
        "zones": zones,
        "recent_transitions": transitions[-50:],
        "raw_store": (
            async_redact_data(store_data_to_dict(store_data), _REDACT_STORE) if store_data else None
        ),
    }
