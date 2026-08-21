"""Repairs issues for Moisture Loop (SPECIFICATION.md §34).

Only supported ``IssueSeverity`` constants are used (§5.5): ERROR for
broken-zone/integrity conditions and the reserved CRITICAL only for the true
panic of a valve not proven OFF. Transient sensor faults, constrained
completions, and resolved interference remain events/log/entity state.
Issues are not "fixable" flows: acknowledgement happens through the
validated ``clear_fault`` path or reconfiguration, which then clears the
issue.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

ISSUE_SENSOR_MISSING = "zone_sensor_missing"
ISSUE_ACTUATOR_MISSING = "zone_actuator_missing"
ISSUE_OFF_UNCONFIRMED = "actuator_off_unconfirmed"
ISSUE_INTEGRITY_LOST = "runtime_store_integrity_lost"


def _zone_issue_id(kind: str, zone_id: str) -> str:
    return f"{kind}_{zone_id}"


def async_create_off_unconfirmed_issue(hass: HomeAssistant, zone_id: str, zone_name: str) -> None:
    """CRITICAL: possible uncontrolled water flow (§34)."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        _zone_issue_id(ISSUE_OFF_UNCONFIRMED, zone_id),
        is_fixable=False,
        severity=ir.IssueSeverity.CRITICAL,
        translation_key=ISSUE_OFF_UNCONFIRMED,
        translation_placeholders={"zone_name": zone_name},
    )


def async_delete_off_unconfirmed_issue(hass: HomeAssistant, zone_id: str) -> None:
    ir.async_delete_issue(hass, DOMAIN, _zone_issue_id(ISSUE_OFF_UNCONFIRMED, zone_id))


def async_create_entity_missing_issue(
    hass: HomeAssistant, zone_id: str, zone_name: str, entity_id: str, actuator: bool
) -> None:
    """ERROR: configured sensor/actuator missing; zone broken (§34)."""
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
    """ERROR: initialized runtime safety state lost; operation blocked (§34)."""
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
