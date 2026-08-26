"""Schema-2 config-entry diagnostics (SPECIFICATION.md §33.2)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from enum import Enum
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as ha_version
from homeassistant.core import HomeAssistant

from .const import CONF_RUNTIME_STORE_GENERATION_ID
from .models import (
    AppliedConfigurationShadow,
    SafetyRecord,
    ZoneHistory,
    store_data_to_dict,
)
from .runtime import EntryRuntime
from .zone_controller import ZoneController

_REDACT_ENTRY = {CONF_RUNTIME_STORE_GENERATION_ID}
_REDACT_STORE = {"generation_id", "active_run_id", "last_clean_shutdown_run_id"}


def _short(value: str | None) -> str | None:
    return None if value is None else value[:8]


def _serializable(value: Any) -> Any:
    """Convert immutable runtime structures without mutating authority."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serializable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_serializable(item) for item in value]
    return value


def _shadow(shadow: AppliedConfigurationShadow | None) -> dict[str, Any] | None:
    if shadow is None:
        return None
    result = _serializable(asdict(shadow))
    result["config_fingerprint"] = _short(shadow.config_fingerprint)
    result["entry_snapshot_fingerprint"] = _short(shadow.entry_snapshot_fingerprint)
    return result


def _record(record: SafetyRecord) -> dict[str, Any]:
    identity = record.actuator_identity
    incident = record.identity_incident
    return {
        "safety_record_id": record.safety_record_id,
        "safety_lineage_id": record.safety_lineage_id,
        "zone_history_id": record.zone_history_id,
        "historical_zone_history_ids": list(record.historical_zone_history_ids),
        "zone_id": record.zone_id,
        "active_subentry_id": record.active_subentry_id,
        "previous_subentry_ids": list(record.previous_subentry_ids),
        "lifecycle": record.runtime_lifecycle.value,
        "applied_shadow": _shadow(record.applied_config),
        "actuator_identity": {
            "registry_entry_id_short": _short(identity.registry_entry_id),
            "last_known_entity_id": identity.last_known_entity_id,
            "domain": identity.domain,
            "identity_status": identity.identity_status.value,
            "off_service": identity.off_service,
            "confirm_timeout_s": identity.confirm_timeout_s,
        },
        "blockers": [reason.value for reason in record.blocker_reasons],
        "possible_flow_owner": (
            record.possible_flow_owner.value if record.possible_flow_owner else None
        ),
        "actuator_fault": record.actuator_fault.value if record.actuator_fault else None,
        "acknowledgement_required": record.acknowledgement_required,
        "identity_incident": (
            {"kind": incident.kind.value, "detail": incident.detail} if incident else None
        ),
    }


def _history(history: ZoneHistory) -> dict[str, Any]:
    zone_runtime = history.zone_runtime
    session = zone_runtime.session
    daily = history.daily
    return {
        "zone_history_id": history.zone_history_id,
        "active_subentry_id": history.active_subentry_id,
        "previous_subentry_ids": list(history.previous_subentry_ids),
        "last_session_end_utc": (
            history.last_session_end_utc.isoformat() if history.last_session_end_utc else None
        ),
        "last_auto_session_start_utc": (
            history.last_auto_session_start_utc.isoformat()
            if history.last_auto_session_start_utc
            else None
        ),
        "zone_runtime": {
            "enabled": zone_runtime.enabled,
            "state": zone_runtime.state.value,
            "zone_fault": (zone_runtime.zone_fault.value if zone_runtime.zone_fault else None),
            "secondary_fault": (
                zone_runtime.secondary_fault.value if zone_runtime.secondary_fault else None
            ),
            "sensor_identity": {
                "registry_entry_id_short": _short(zone_runtime.sensor_identity.registry_entry_id),
                "last_known_entity_id": (zone_runtime.sensor_identity.last_known_entity_id),
            },
            "current_session": (
                {
                    "owner_safety_record_id": session.owner_safety_record_id,
                    "context": _serializable(asdict(session.context)),
                }
                if session
                else None
            ),
            "last_session_summary": (
                _serializable(asdict(zone_runtime.last_session_summary))
                if zone_runtime.last_session_summary
                else None
            ),
        },
        "daily": (
            {
                "date_local": daily.date_local.isoformat(),
                "runtime_s": daily.runtime_s,
                "conservative_unattributed_runtime_s": (daily.conservative_unattributed_runtime_s),
                "contributions": [
                    _serializable(asdict(contribution)) for contribution in daily.contributions
                ],
            }
            if daily
            else None
        ),
    }


def _controller(controller: ZoneController | None) -> dict[str, Any] | None:
    if controller is None:
        return None
    observation = controller.observation
    operation = controller.off_operation
    return {
        "controller_state": controller.state.value,
        "enabled": controller.enabled,
        "runtime_eligible": controller.runtime_eligible,
        "controller_lifecycle": controller.runtime_lifecycle.value,
        "observation": {
            "value": observation.value,
            "classification": observation.classification.value,
            "reported_at_utc": (
                observation.reported_at_utc.isoformat() if observation.reported_at_utc else None
            ),
            "age_s": observation.age_s,
        },
        "actuator_classification": {
            "available": controller.assessment.available,
            "proven_off": controller.assessment.proven_off,
            "observed_on": controller.assessment.observed_on,
        },
        "external_actuator_on": controller.external_on,
        "may_be_flowing": controller.may_be_flowing,
        "off_operation": (
            {
                "done": operation.done(),
                "confirmed": operation.result() if operation.done() else None,
            }
            if operation
            else None
        ),
        "last_on_authorization": (
            _serializable(asdict(controller.last_on_authorization))
            if controller.last_on_authorization
            else None
        ),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return active zones and retained records from canonical schema 2."""
    runtime: EntryRuntime = entry.runtime_data
    store_data = runtime.store.data if runtime.store.loaded else None
    slots = runtime.slots.snapshot()
    coordinator = runtime.coordinator

    zones: dict[str, Any] = {}
    tombstones: dict[str, Any] = {}
    transitions: list[dict[str, Any]] = []
    controllers = {
        controller.safety_record_id: controller
        for controller in [
            *runtime.controllers.values(),
            *runtime.retained_controllers.values(),
        ]
    }
    if store_data is not None:
        for record_id, record in store_data.safety_records.items():
            history = store_data.zone_histories[record.zone_history_id]
            controller = controllers.get(record_id)
            payload = {
                **_record(record),
                "zone_history": _history(history),
                "runtime": _controller(controller),
                "open_accounting": history.zone_runtime.session is not None,
            }
            if record.active_subentry_id is not None:
                zones[record.active_subentry_id] = payload
            else:
                tombstones[record_id] = payload
            if controller is not None:
                transitions.extend(controller.transitions)

    transitions.sort(key=lambda item: item["at_utc"])
    observed = coordinator.observed_snapshot
    applied = coordinator.applied_snapshot
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
            "generation_id_short": (_short(store_data.generation_id) if store_data else None),
            "current_run_id_short": _short(runtime.run_id),
            "previous_run_was_clean": (
                runtime.previous_run.previous_run_was_clean if runtime.previous_run else None
            ),
            "soaking_adoptions": runtime.soaking_adoptions,
        },
        "reconciliation": {
            "observed_generation": coordinator.observed_generation,
            "applied_generation": coordinator.applied_generation,
            "observed_fingerprint_short": (
                _short(observed.entry_snapshot_fingerprint) if observed else None
            ),
            "applied_fingerprint_short": (
                _short(applied.entry_snapshot_fingerprint) if applied else None
            ),
            "dirty": coordinator.dirty,
            "reconciling": coordinator.reconciling,
            "failed": coordinator.failed,
            "last_error": coordinator.last_error,
            "superseded_count": coordinator.superseded_count,
            "reload_pending": coordinator.reload_pending,
            "reload_generation": coordinator.reload_generation,
            "reload_count": coordinator.reload_count,
            "admission_open": slots.admission_open,
        },
        "shutdown": {
            # §24.1: exactly one removable Stage-1 shutdown owner per loaded
            # entry runtime. EVENT_HOMEASSISTANT_STOP owns no safety work.
            "stage1_job_registered": runtime.shutdown_job_registered,
            "shutdown_off_budget_s": runtime.shutdown_off_budget_s,
            "process_stopping": runtime.process_stopping,
            "last_stage1_report": (
                _serializable(asdict(runtime.shutdown_report))
                if runtime.shutdown_report is not None
                else None
            ),
        },
        "slot_manager": {
            "owner": slots.owner,
            "queue": list(slots.queue),
            "blockers": [
                {"safety_record_id": record_id, "reason": reason.value}
                for record_id, reason in slots.blockers
            ],
            "grants_enabled": slots.grants_enabled,
            "reconciliation_dirty": slots.reconciliation_dirty,
            "reconciling": slots.reconciling,
            "reconciliation_failed": slots.reconciliation_failed,
            "admission_open": slots.admission_open,
        },
        "zones": zones,
        "retained_tombstones": tombstones,
        "recent_transitions": transitions[-50:],
        "raw_store": (
            async_redact_data(store_data_to_dict(store_data), _REDACT_STORE) if store_data else None
        ),
    }
