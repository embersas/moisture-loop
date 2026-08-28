"""Schema-2 exact-record Repairs for MoistureLoop (§§26.3, 34)."""

from __future__ import annotations

from typing import Any, cast

import voluptuous as vol
from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import CONF_ACTUATOR_REMOVED_OFF, DOMAIN
from .models import SafetyRecord

ISSUE_SENSOR_MISSING = "zone_sensor_missing"
ISSUE_ACTUATOR_MISSING = "zone_actuator_missing"
ISSUE_TOMBSTONE_ACTUATOR_MISSING = "tombstone_actuator_missing"
ISSUE_TOMBSTONE_ACTUATOR_REMOVED = "tombstone_actuator_removed"
ISSUE_IDENTITY_CONFLICT = "actuator_identity_conflict"
ISSUE_RECONCILIATION_FAILED = "configuration_reconciliation_failed"
ISSUE_OFF_UNCONFIRMED = "actuator_off_unconfirmed"
ISSUE_INTEGRITY_LOST = "runtime_store_integrity_lost"


def _short(value: str | None) -> str:
    return value[:8] if value else "unavailable"


def record_issue_id(entry_id: str, safety_record_id: str, issue_type: str) -> str:
    """Encode the normative (entry, stable record, issue type) key."""
    return f"{issue_type}_{entry_id}_{safety_record_id}"


def _zone_issue_id(kind: str, zone_id: str) -> str:
    return f"{kind}_{zone_id}"


def _record_placeholders(record: SafetyRecord, zone_name: str) -> dict[str, str]:
    identity = record.actuator_identity
    return {
        "zone_name": zone_name,
        "safety_record_id": _short(record.safety_record_id),
        "safety_lineage_id": _short(record.safety_lineage_id),
        "registry_entry_id": _short(identity.registry_entry_id),
        "entity_id": identity.last_known_entity_id or "unavailable",
        "lifecycle": record.runtime_lifecycle.value,
        "fault": record.actuator_fault.value if record.actuator_fault else "none",
        "blockers": ", ".join(reason.value for reason in record.blocker_reasons) or "none",
        "accounting": ("open" if record.possible_flow_owner is not None else "closed or not owned"),
    }


def async_create_off_unconfirmed_issue(
    hass: HomeAssistant,
    entry_id: str,
    record: SafetyRecord,
    zone_name: str,
) -> None:
    """CRITICAL exact-record issue; deletion/re-add never re-keys it."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        record_issue_id(entry_id, record.safety_record_id, ISSUE_OFF_UNCONFIRMED),
        is_fixable=True,
        severity=ir.IssueSeverity.CRITICAL,
        translation_key=ISSUE_OFF_UNCONFIRMED,
        translation_placeholders=_record_placeholders(record, zone_name),
        data={
            "entry_id": entry_id,
            "safety_record_id": record.safety_record_id,
            "safety_lineage_id": record.safety_lineage_id,
            "issue_type": ISSUE_OFF_UNCONFIRMED,
        },
    )


def async_create_identity_issue(
    hass: HomeAssistant,
    entry_id: str,
    record: SafetyRecord,
    issue_type: str,
    zone_name: str,
    *,
    removal_recoverable: bool = False,
) -> None:
    """Expose an exact-record identity incident without unsafe adoption.

    ``removal_recoverable`` is set only for the exact §26.4 condition: a
    retained record whose durable actuator registry row is definitively
    ABSENT and whose every other safety precondition is already clear. Only
    that condition may offer the operator acknowledgement flow; an
    unavailable, unknown, or conflicting identity stays unfixable.
    """
    placeholders = _record_placeholders(record, zone_name)
    placeholders["detail"] = (
        record.identity_incident.detail if record.identity_incident else "identity unresolved"
    )
    translation_key = (
        ISSUE_TOMBSTONE_ACTUATOR_REMOVED
        if removal_recoverable and issue_type == ISSUE_TOMBSTONE_ACTUATOR_MISSING
        else issue_type
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        record_issue_id(entry_id, record.safety_record_id, issue_type),
        is_fixable=removal_recoverable,
        severity=ir.IssueSeverity.ERROR,
        translation_key=translation_key,
        translation_placeholders=placeholders,
        data={
            "entry_id": entry_id,
            "safety_record_id": record.safety_record_id,
            "safety_lineage_id": record.safety_lineage_id,
            "issue_type": (ISSUE_TOMBSTONE_ACTUATOR_REMOVED if removal_recoverable else issue_type),
        },
    )


def async_delete_record_issue(
    hass: HomeAssistant,
    entry_id: str,
    safety_record_id: str,
    issue_type: str,
) -> None:
    ir.async_delete_issue(
        hass,
        DOMAIN,
        record_issue_id(entry_id, safety_record_id, issue_type),
    )


def async_delete_issue_id(hass: HomeAssistant, issue_id: str) -> None:
    ir.async_delete_issue(hass, DOMAIN, issue_id)


def async_create_reconciliation_issue(
    hass: HomeAssistant,
    entry_id: str,
    error: str,
    observed_generation: int,
    applied_generation: int,
) -> None:
    """ERROR entry incident while admission is authoritatively closed."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{ISSUE_RECONCILIATION_FAILED}_{entry_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_RECONCILIATION_FAILED,
        translation_placeholders={
            "entry_id": _short(entry_id),
            "error": error,
            "observed_generation": str(observed_generation),
            "applied_generation": str(applied_generation),
        },
        data={"entry_id": entry_id, "issue_type": ISSUE_RECONCILIATION_FAILED},
    )


def async_delete_reconciliation_issue(hass: HomeAssistant, entry_id: str) -> None:
    ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_RECONCILIATION_FAILED}_{entry_id}")


def async_create_entity_missing_issue(
    hass: HomeAssistant, zone_id: str, zone_name: str, entity_id: str, actuator: bool
) -> None:
    """ERROR current logical-zone configuration issue."""
    kind = ISSUE_ACTUATOR_MISSING if actuator else ISSUE_SENSOR_MISSING
    ir.async_create_issue(
        hass,
        DOMAIN,
        _zone_issue_id(kind, zone_id),
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=kind,
        translation_placeholders={"zone_name": zone_name, "entity_id": entity_id},
    )


def async_delete_entity_missing_issues(hass: HomeAssistant, zone_id: str) -> None:
    ir.async_delete_issue(hass, DOMAIN, _zone_issue_id(ISSUE_SENSOR_MISSING, zone_id))
    ir.async_delete_issue(hass, DOMAIN, _zone_issue_id(ISSUE_ACTUATOR_MISSING, zone_id))


def async_create_integrity_issue(hass: HomeAssistant, entry_id: str) -> None:
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{ISSUE_INTEGRITY_LOST}_{entry_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_INTEGRITY_LOST,
    )


def async_delete_integrity_issue(hass: HomeAssistant, entry_id: str) -> None:
    ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_INTEGRITY_LOST}_{entry_id}")


class ExactRecordFaultFixFlow(RepairsFlow):
    """Entry-level tombstone-safe acknowledgement flow (§26.3)."""

    def __init__(self, data: dict[str, Any]) -> None:
        super().__init__()
        self._entry_id = cast(str, data["entry_id"])
        self._record_id = cast(str, data["safety_record_id"])
        self._lineage_id = cast(str, data["safety_lineage_id"])
        self._issue_type = cast(str, data["issue_type"])

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        # Home Assistant seeds the flow with data={"issue_id": ...} and passes
        # that dict here as user_input. Forwarding it would make merely OPENING
        # this Repair count as the operator's acknowledgement, so the confirm
        # step is always entered unsubmitted (matching Core's ConfirmRepairFlow).
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        from .runtime import SafetyRecordAcknowledgementError

        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        runtime = None
        record = None
        if entry is not None and entry.state is ConfigEntryState.LOADED:
            runtime = getattr(entry, "runtime_data", None)
            if runtime is not None and runtime.store.loaded:
                record = runtime.store.data.safety_records.get(self._record_id)

        if user_input is not None:
            if runtime is None:
                errors["base"] = "record_entry_not_loaded"
            elif record is None or record.safety_lineage_id != self._lineage_id:
                errors["base"] = "record_not_found"
            else:
                try:
                    await runtime.async_acknowledge_safety_record(
                        self._record_id,
                        self._lineage_id,
                        self._issue_type,
                    )
                except SafetyRecordAcknowledgementError as err:
                    errors["base"] = err.translation_key
                else:
                    return self.async_create_entry(data={})

        placeholders = {
            "zone_name": "retained zone",
            "safety_record_id": _short(self._record_id),
            "safety_lineage_id": _short(self._lineage_id),
            "registry_entry_id": "unavailable",
            "entity_id": "unavailable",
            "lifecycle": "unknown",
            "fault": "unknown",
            "blockers": "unknown",
            "accounting": "unknown",
        }
        if record is not None:
            name = (
                record.applied_config.normalized_settings.name
                if record.applied_config is not None
                else record.zone_id
            )
            placeholders = _record_placeholders(record, name)
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=placeholders,
            errors=errors,
        )


class RemovedActuatorFixFlow(RepairsFlow):
    """Operator certification that a removed actuator is OFF (§26.4).

    This is a safety assertion, not a dismissal. It is offered only for a
    retained record whose durable registry identity is definitively ABSENT,
    and every precondition is revalidated at submit time inside the Store
    transaction, so a change between rendering and confirming fails closed.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        super().__init__()
        self._entry_id = cast(str, data["entry_id"])
        self._record_id = cast(str, data["safety_record_id"])
        self._lineage_id = cast(str, data["safety_lineage_id"])

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        # See ExactRecordFaultFixFlow: the seeding dict must never be mistaken
        # for the operator's safety assertion.
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        from .runtime import SafetyRecordAcknowledgementError

        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        runtime = None
        if entry is not None and entry.state is ConfigEntryState.LOADED:
            runtime = getattr(entry, "runtime_data", None)

        context = None
        if runtime is not None:
            context = runtime.removed_actuator_recovery_context(self._record_id, self._lineage_id)

        if user_input is not None and CONF_ACTUATOR_REMOVED_OFF in user_input:
            if runtime is None:
                errors["base"] = "record_entry_not_loaded"
            elif context is None:
                errors["base"] = "record_removal_not_confirmed"
            elif not user_input[CONF_ACTUATOR_REMOVED_OFF]:
                errors["base"] = "record_confirmation_required"
            else:
                try:
                    await runtime.async_acknowledge_removed_actuator(
                        self._record_id,
                        self._lineage_id,
                    )
                except SafetyRecordAcknowledgementError as err:
                    errors["base"] = err.translation_key
                else:
                    return self.async_create_entry(data={})

        placeholders = {
            "zone_name": "retained zone",
            "safety_record_id": _short(self._record_id),
            "safety_lineage_id": _short(self._lineage_id),
            "registry_entry_id": "unavailable",
            "entity_id": "unavailable",
            "lifecycle": "unknown",
            "fault": "unknown",
            "blockers": "unknown",
            "accounting": "unknown",
        }
        if context is not None:
            record = context[0]
            name = (
                record.applied_config.normalized_settings.name
                if record.applied_config is not None
                else record.zone_id
            )
            placeholders = _record_placeholders(record, name)
        return self.async_show_form(
            step_id="confirm",
            # Deliberately unchecked: the operator must actively assert it.
            data_schema=vol.Schema({vol.Required(CONF_ACTUATOR_REMOVED_OFF, default=False): bool}),
            description_placeholders=placeholders,
            errors=errors,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create only the supported exact-record acknowledgement flow."""
    if data and all(data.get(key) for key in ("entry_id", "safety_record_id", "safety_lineage_id")):
        if data.get("issue_type") == ISSUE_OFF_UNCONFIRMED:
            return ExactRecordFaultFixFlow(data)
        if data.get("issue_type") == ISSUE_TOMBSTONE_ACTUATOR_REMOVED:
            return RemovedActuatorFixFlow(data)
    return ConfirmRepairFlow()
