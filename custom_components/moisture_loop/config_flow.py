"""Config flow for MoistureLoop (SPECIFICATION.md §§7-9, 24.3, 29-30).

One top-level controller entry (single_config_entry) created with the
immutable runtime-Store generation UUID and ``runtime_store_initialized:
false`` (§23.1). Zones are config subentries with add/reconfigure flows.
There is no options flow (§30). Core subentry mutations feed the one
entry-owned update listener; reconfiguration uses
``ConfigSubentryFlow.async_update_and_abort(...)`` after optional cooperative
old-runtime preparation. Backend validation is authoritative; selector
filtering is UI convenience only (§5.3).
"""

from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from . import zone_config_from_subentry
from .const import (
    CONF_ACTUATOR,
    CONF_ACTUATOR_CONFIRM_TIMEOUT,
    CONF_MANUAL_MAX_DURATION,
    CONF_MAX_CYCLES,
    CONF_MAX_DAILY_RUNTIME,
    CONF_MAX_SESSION_RUNTIME,
    CONF_MIN_SESSION_INTERVAL,
    CONF_MOISTURE_SENSOR,
    CONF_NAME,
    CONF_PULSE_DURATION,
    CONF_RUNTIME_STORE_GENERATION_ID,
    CONF_RUNTIME_STORE_INITIALIZED,
    CONF_SENSOR_MAX_AGE,
    CONF_SOAK_DURATION,
    CONF_START_THRESHOLD,
    CONF_TARGET_THRESHOLD,
    DEFAULT_ACTUATOR_CONFIRM_TIMEOUT_S,
    DEFAULT_MANUAL_MAX_DURATION_S,
    DEFAULT_MAX_CYCLES,
    DEFAULT_MAX_DAILY_RUNTIME_S,
    DEFAULT_MAX_SESSION_RUNTIME_S,
    DEFAULT_MIN_SESSION_INTERVAL_S,
    DEFAULT_PULSE_DURATION_S,
    DEFAULT_SENSOR_MAX_AGE_S,
    DEFAULT_SOAK_DURATION_S,
    DEFAULT_START_THRESHOLD,
    DEFAULT_TARGET_THRESHOLD,
    DOMAIN,
)

# ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE without importing the
# valve component at module import time.
_VALVE_FEATURE_OPEN = 1
_VALVE_FEATURE_CLOSE = 2


class MoistureLoopConfigFlow(ConfigFlow, domain=DOMAIN):
    """Top-level controller entry flow (§29)."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Create the single controller entry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(
                title="MoistureLoop",
                data={
                    # Immutable identity; never regenerated on Store absence
                    # (§23.1, I29).
                    CONF_RUNTIME_STORE_GENERATION_ID: str(uuid.uuid4()),
                    CONF_RUNTIME_STORE_INITIALIZED: False,
                },
            )
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """One `zone` subentry flow per §5.1."""
        return {"zone": ZoneSubentryFlow}


def _identity_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): selector.TextSelector(),
            vol.Required(
                CONF_MOISTURE_SENSOR, default=defaults.get(CONF_MOISTURE_SENSOR)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Required(
                CONF_ACTUATOR, default=defaults.get(CONF_ACTUATOR)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["switch", "valve"])),
        }
    )


def _number(min_value: float, max_value: float, unit: str) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=min_value,
            max=max_value,
            unit_of_measurement=unit,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _thresholds_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_START_THRESHOLD,
                default=defaults.get(CONF_START_THRESHOLD, DEFAULT_START_THRESHOLD),
            ): _number(1, 99, "%"),
            vol.Required(
                CONF_TARGET_THRESHOLD,
                default=defaults.get(CONF_TARGET_THRESHOLD, DEFAULT_TARGET_THRESHOLD),
            ): _number(2, 100, "%"),
            vol.Required(
                CONF_PULSE_DURATION,
                default=defaults.get(CONF_PULSE_DURATION, DEFAULT_PULSE_DURATION_S),
            ): _number(30, 1800, "s"),
            vol.Required(
                CONF_SOAK_DURATION,
                default=defaults.get(CONF_SOAK_DURATION, DEFAULT_SOAK_DURATION_S),
            ): _number(60, 14400, "s"),
        }
    )


def _limits_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_MAX_CYCLES, default=defaults.get(CONF_MAX_CYCLES, DEFAULT_MAX_CYCLES)
            ): _number(1, 20, "cycles"),
            vol.Required(
                CONF_MAX_SESSION_RUNTIME,
                default=defaults.get(CONF_MAX_SESSION_RUNTIME, DEFAULT_MAX_SESSION_RUNTIME_S),
            ): _number(30, 14400, "s"),
            vol.Required(
                CONF_MAX_DAILY_RUNTIME,
                default=defaults.get(CONF_MAX_DAILY_RUNTIME, DEFAULT_MAX_DAILY_RUNTIME_S),
            ): _number(30, 43200, "s"),
            vol.Required(
                CONF_MIN_SESSION_INTERVAL,
                default=defaults.get(CONF_MIN_SESSION_INTERVAL, DEFAULT_MIN_SESSION_INTERVAL_S),
            ): _number(900, 604800, "s"),
            vol.Required(
                CONF_SENSOR_MAX_AGE,
                default=defaults.get(CONF_SENSOR_MAX_AGE, DEFAULT_SENSOR_MAX_AGE_S),
            ): _number(300, 86400, "s"),
            vol.Required(
                CONF_ACTUATOR_CONFIRM_TIMEOUT,
                default=defaults.get(
                    CONF_ACTUATOR_CONFIRM_TIMEOUT, DEFAULT_ACTUATOR_CONFIRM_TIMEOUT_S
                ),
            ): _number(5, 300, "s"),
            vol.Required(
                CONF_MANUAL_MAX_DURATION,
                default=defaults.get(CONF_MANUAL_MAX_DURATION, DEFAULT_MANUAL_MAX_DURATION_S),
            ): _number(60, 7200, "s"),
        }
    )


_IDENTITY_KEYS = (CONF_NAME, CONF_MOISTURE_SENSOR, CONF_ACTUATOR)
_THRESHOLD_KEYS = (
    CONF_START_THRESHOLD,
    CONF_TARGET_THRESHOLD,
    CONF_PULSE_DURATION,
    CONF_SOAK_DURATION,
)
_LIMIT_KEYS = (
    CONF_MAX_CYCLES,
    CONF_MAX_SESSION_RUNTIME,
    CONF_MAX_DAILY_RUNTIME,
    CONF_MIN_SESSION_INTERVAL,
    CONF_SENSOR_MAX_AGE,
    CONF_ACTUATOR_CONFIRM_TIMEOUT,
    CONF_MANUAL_MAX_DURATION,
)
_INT_KEYS = (
    CONF_PULSE_DURATION,
    CONF_SOAK_DURATION,
    CONF_MAX_CYCLES,
    CONF_MAX_SESSION_RUNTIME,
    CONF_MAX_DAILY_RUNTIME,
    CONF_MIN_SESSION_INTERVAL,
    CONF_SENSOR_MAX_AGE,
    CONF_ACTUATOR_CONFIRM_TIMEOUT,
    CONF_MANUAL_MAX_DURATION,
)


class ZoneSubentryFlow(ConfigSubentryFlow):
    """Zone add/reconfigure flow (§29): identity, thresholds, limits."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._shared_sensor_warning = False

    # -- add flow --------------------------------------------------------

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._validate_identity(user_input, reconfigure_id=None)
            if not errors:
                self._data.update(user_input)
                return await self.async_step_thresholds()
        return self.async_show_form(
            step_id="user",
            data_schema=_identity_schema(user_input or self._data),
            errors=errors,
            description_placeholders=self._placeholders(),
        )

    async def async_step_thresholds(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._validate_partial({**self._data, **user_input})
            if not errors:
                self._data.update(user_input)
                return await self.async_step_limits()
        return self.async_show_form(
            step_id="thresholds",
            data_schema=_thresholds_schema(user_input or self._data),
            errors=errors,
            description_placeholders=self._placeholders(),
        )

    async def async_step_limits(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            candidate = self._normalize({**self._data, **user_input})
            errors = self._validate_full(candidate, reconfigure_id=None)
            if not errors:
                # Core attaches the subentry and notifies the single
                # entry-owned listener. The reconciler alone applies it and
                # decides whether platform reconstruction needs one reload.
                return self.async_create_entry(title=candidate[CONF_NAME], data=candidate)
        return self.async_show_form(
            step_id="limits",
            data_schema=_limits_schema(user_input or self._data),
            errors=errors,
            description_placeholders=self._placeholders(),
        )

    # -- reconfigure flow ---------------------------------------------------

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        if not self._data:
            self._data = dict(subentry.data)
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._validate_identity(user_input, reconfigure_id=subentry.subentry_id)
            if not errors:
                self._data.update(user_input)
                return await self.async_step_reconfigure_thresholds()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_identity_schema(user_input or self._data),
            errors=errors,
            description_placeholders=self._placeholders(),
        )

    async def async_step_reconfigure_thresholds(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._validate_partial({**self._data, **user_input})
            if not errors:
                self._data.update(user_input)
                return await self.async_step_reconfigure_limits()
        return self.async_show_form(
            step_id="reconfigure_thresholds",
            data_schema=_thresholds_schema(user_input or self._data),
            errors=errors,
            description_placeholders=self._placeholders(),
        )

    async def async_step_reconfigure_limits(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            candidate = self._normalize({**self._data, **user_input})
            errors = self._validate_full(candidate, reconfigure_id=subentry.subentry_id)
            if not errors:
                entry = self._get_entry()
                current = self._normalize(dict(subentry.data))
                if candidate == current:
                    # A normalized no-op does not mutate Core, advance the
                    # observed generation, quiesce a session, or reload.
                    return self.async_abort(reason="reconfigure_successful")

                # §24.4: the flow owns only safe old-runtime preparation.
                # It never publishes the candidate runtime or performs the
                # same-record/A -> B handoff.
                runtime = getattr(entry, "runtime_data", None)
                prepare = getattr(runtime, "async_prepare_reconfigure", None)
                if prepare is not None:
                    await prepare(subentry.subentry_id)

                # Core mutation -> existing ConfigEntry update listener ->
                # Stage-3 reconciler -> optional reconciler-owned reload.
                return self.async_update_and_abort(
                    entry,
                    subentry,
                    title=candidate[CONF_NAME],
                    data=candidate,
                )
        return self.async_show_form(
            step_id="reconfigure_limits",
            data_schema=_limits_schema(user_input or self._data),
            errors=errors,
            description_placeholders=self._placeholders(),
        )

    # -- validation (backend authoritative, §5.3) ---------------------------

    def _placeholders(self) -> dict[str, str]:
        return {
            "shared_sensor_warning": (
                "Warning: this moisture sensor is already used by another "
                "zone. Both zones will water from the same reading."
                if self._shared_sensor_warning
                else ""
            )
        }

    def _other_zones(self, reconfigure_id: str | None) -> list[dict[str, Any]]:
        entry = self._get_entry()
        return [
            dict(subentry.data)
            for subentry_id, subentry in entry.subentries.items()
            if subentry.subentry_type == "zone" and subentry_id != reconfigure_id
        ]

    def _validate_identity(
        self, user_input: dict[str, Any], reconfigure_id: str | None
    ) -> dict[str, str]:
        errors: dict[str, str] = {}
        self._shared_sensor_warning = False
        name = str(user_input.get(CONF_NAME, "")).strip()
        sensor = user_input.get(CONF_MOISTURE_SENSOR)
        actuator = user_input.get(CONF_ACTUATOR)
        others = self._other_zones(reconfigure_id)
        registry = er.async_get(self.hass)

        if not 1 <= len(name) <= 64:
            errors[CONF_NAME] = "invalid_name"
        elif any(str(o[CONF_NAME]).casefold() == name.casefold() for o in others):
            errors[CONF_NAME] = "duplicate_name"

        sensor_state = self.hass.states.get(sensor) if sensor else None
        if not sensor or sensor_state is None:
            errors[CONF_MOISTURE_SENSOR] = "entity_not_found"
        elif not sensor.startswith("sensor."):
            errors[CONF_MOISTURE_SENSOR] = "wrong_domain"
        elif any(
            self._same_registry_identity(registry, o[CONF_MOISTURE_SENSOR], sensor) for o in others
        ):
            # Shared sensor is permitted with a warning (§9).
            self._shared_sensor_warning = True

        actuator_state = self.hass.states.get(actuator) if actuator else None
        if not actuator or actuator_state is None:
            errors[CONF_ACTUATOR] = "entity_not_found"
        elif not (actuator.startswith("switch.") or actuator.startswith("valve.")):
            errors[CONF_ACTUATOR] = "wrong_domain"
        elif actuator.startswith("valve."):
            features = actuator_state.attributes.get("supported_features", 0) or 0
            if not (features & _VALVE_FEATURE_OPEN and features & _VALVE_FEATURE_CLOSE):
                # A position-only valve is not accepted in v0.1 (§11.1).
                errors[CONF_ACTUATOR] = "valve_features_missing"
        if CONF_ACTUATOR not in errors:
            if any(
                self._same_registry_identity(registry, o[CONF_ACTUATOR], actuator) for o in others
            ):
                errors[CONF_ACTUATOR] = "duplicate_actuator"
            else:
                identity_error = self._retained_actuator_identity_error(
                    registry, actuator, reconfigure_id
                )
                if identity_error is not None:
                    errors[CONF_ACTUATOR] = identity_error
        return errors

    @staticmethod
    def _same_registry_identity(registry, first: str, second: str) -> bool:
        """Compare Registry UUID first, retaining text only as fallback."""
        if first == second:
            return True
        first_entry = registry.async_get(first)
        second_entry = registry.async_get(second)
        return (
            first_entry is not None
            and second_entry is not None
            and first_entry.id == second_entry.id
        )

    def _retained_actuator_identity_error(
        self, registry, actuator: str, reconfigure_id: str | None
    ) -> str | None:
        """Validate candidate identity against loaded canonical evidence.

        Exact retained UUID matches are deliberately accepted: the Stage-3
        reconciler reactivates that same canonical record. Conflicting or
        ambiguous evidence fails before Core mutation. No record is created,
        adopted, or altered here.
        """
        entry = self._get_entry()
        runtime = getattr(entry, "runtime_data", None)
        store = getattr(runtime, "store", None)
        if store is None or not getattr(store, "loaded", False):
            return None

        candidate = registry.async_get(actuator)
        candidate_uuid = candidate.id if candidate is not None else None
        records = tuple(store.data.safety_records.values())
        exact = [
            record
            for record in records
            if candidate_uuid is not None
            and record.actuator_identity.registry_entry_id == candidate_uuid
        ]
        if len(exact) > 1:
            return "actuator_identity_conflict"
        if exact:
            owner = exact[0].active_subentry_id
            if owner is not None and owner != reconfigure_id:
                return "duplicate_actuator"

        for record in records:
            identity = record.actuator_identity
            if identity.last_known_entity_id != actuator:
                continue
            if candidate_uuid is None:
                if record not in exact and record.active_subentry_id != reconfigure_id:
                    return "actuator_identity_conflict"
            elif identity.registry_entry_id not in (
                None,
                candidate_uuid,
            ) or (
                identity.registry_entry_id is None and record.active_subentry_id != reconfigure_id
            ):
                return "actuator_identity_conflict"
        return None

    @staticmethod
    def _normalize(data: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(data)
        normalized[CONF_NAME] = str(data[CONF_NAME]).strip()
        for key in _INT_KEYS:
            normalized[key] = int(data[key])
        for key in (CONF_START_THRESHOLD, CONF_TARGET_THRESHOLD):
            normalized[key] = float(data[key])
        return {key: normalized[key] for key in (*_IDENTITY_KEYS, *_THRESHOLD_KEYS, *_LIMIT_KEYS)}

    def _validate_partial(self, data: dict[str, Any]) -> dict[str, str]:
        errors: dict[str, str] = {}
        start = float(data[CONF_START_THRESHOLD])
        target = float(data[CONF_TARGET_THRESHOLD])
        if not start < target:
            # Strict threshold ordering (§9, §17).
            errors[CONF_TARGET_THRESHOLD] = "target_not_above_start"
        return errors

    def _validate_full(
        self, candidate: dict[str, Any], reconfigure_id: str | None
    ) -> dict[str, str]:
        errors = self._validate_identity(candidate, reconfigure_id)
        errors.update(self._validate_partial(candidate))
        if errors:
            return errors
        # Every §9 bound via the pure model — backend authoritative.
        config = zone_config_from_subentry(candidate)
        violations = config.validation_errors()
        if violations:
            errors["base"] = "invalid_configuration"
        return errors
