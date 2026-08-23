"""HA1 release-source API contract check (SPECIFICATION.md §5.1, §39.2 HA1).

Runs inside a CI environment whose homeassistant package is pinned to an exact
release (see requirements_test_ha*.txt). Because pip installs the sdist built
from the exact release tag, verifying the installed package verifies the
release source. Each check below covers one normative API the specification
depends on. Any failure exits nonzero and must block release.

Usage: python scripts/check_ha_contract.py --expect 2025.9.0
"""

from __future__ import annotations

import argparse
import inspect
import sys

FAILURES: list[str] = []


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"PASS {name}")
    except Exception as exc:
        FAILURES.append(f"{name}: {exc!r}")
        print(f"FAIL {name}: {exc!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect", required=True, help="exact expected HA version")
    args = parser.parse_args()

    import homeassistant.const as ha_const

    check(
        "exact pinned HA version",
        lambda: _assert(
            ha_const.__version__ == args.expect,
            f"installed {ha_const.__version__}, expected {args.expect}",
        ),
    )

    def subentry_helper() -> None:
        from homeassistant.config_entries import ConfigSubentryFlow

        sig = inspect.signature(ConfigSubentryFlow.async_update_and_abort)
        expected = {"self", "entry", "subentry", "unique_id", "title", "data", "data_updates"}
        _assert(set(sig.parameters) == expected, f"signature is {sig}")

    check(
        "ConfigSubentryFlow.async_update_and_abort(entry, subentry, ...)",
        subentry_helper,
    )

    def subentry_model() -> None:
        from homeassistant.config_entries import (  # noqa: F401
            ConfigEntries,
            ConfigEntry,
            ConfigSubentry,
        )

        # runtime_data is a typed instance attribute declared on the class.
        annotations = getattr(ConfigEntry, "__annotations__", {})
        _assert(
            "runtime_data" in annotations
            or hasattr(ConfigEntry, "runtime_data")
            or "runtime_data" in getattr(ConfigEntry, "__slots__", ()),
            "ConfigEntry.runtime_data missing",
        )
        for name in ("add_update_listener", "async_on_unload"):
            _assert(hasattr(ConfigEntry, name), f"ConfigEntry.{name} missing")
        _assert(
            "subentries" in annotations
            or hasattr(ConfigEntry, "subentries")
            or "subentries" in getattr(ConfigEntry, "__slots__", ()),
            "public ConfigEntry.subentries missing",
        )
        reload_sig = inspect.signature(ConfigEntries.async_reload)
        _assert("entry_id" in reload_sig.parameters, f"async_reload signature is {reload_sig}")

    check(
        "ConfigEntry listener/unload/subentries and supported ConfigEntries.async_reload",
        subentry_model,
    )

    def native_subentry_removal_ordering() -> None:
        from homeassistant.config_entries import ConfigEntries

        remove_source = inspect.getsource(ConfigEntries.async_remove_subentry)
        pop = remove_source.index("subentries.pop(subentry_id)")
        update = remove_source.index("self._async_update_entry(entry, subentries=subentries)")
        device_cleanup = remove_source.index("dev_reg.async_clear_config_subentry")
        entity_cleanup = remove_source.index("ent_reg.async_clear_config_subentry")
        _assert(
            pop < update < device_cleanup < entity_cleanup,
            "subentry mutation/update/registry-cleanup ordering changed",
        )

        update_source = inspect.getsource(ConfigEntries._async_update_entry)
        _assert(
            update_source.index('_setter(entry, "subentries"')
            < update_source.index("self._async_save_and_notify(entry)"),
            "public subentry mapping is not changed before notification",
        )
        notify_source = inspect.getsource(ConfigEntries._async_save_and_notify)
        _assert(
            "self.hass.async_create_task(" in notify_source
            and "listener(self.hass, entry)" in notify_source,
            "update listeners are no longer scheduled as unawaited tasks",
        )

    check(
        "native subentry removal mutates mapping then schedules unawaited listeners",
        native_subentry_removal_ordering,
    )

    def event_helpers() -> None:
        from homeassistant.helpers.event import (  # noqa: F401
            async_track_entity_registry_updated_event,
            async_track_state_change_event,
            async_track_state_report_event,
        )

    check("state change/report and entity-registry event helpers", event_helpers)

    def state_last_reported() -> None:
        from homeassistant.core import State

        _assert(
            "last_reported" in getattr(State, "__slots__", ()) or hasattr(State, "last_reported"),
            "State.last_reported missing",
        )

    check("State.last_reported", state_last_reported)

    def store_atomic() -> None:
        from homeassistant.helpers.storage import Store

        sig = inspect.signature(Store.__init__)
        _assert("atomic_writes" in sig.parameters, f"signature is {sig}")

    check("Store(..., atomic_writes=True)", store_atomic)

    def device_selector_filter() -> None:
        from homeassistant.helpers.selector import (
            DeviceSelector,
            DeviceSelectorConfig,
        )

        cfg = DeviceSelectorConfig(filter={"integration": "moisture_loop"}, multiple=False)
        DeviceSelector(cfg)

    check("nested DeviceSelectorConfig.filter", device_selector_filter)

    def issue_severity() -> None:
        from homeassistant.helpers.issue_registry import IssueSeverity

        for name in ("WARNING", "ERROR", "CRITICAL"):
            _assert(hasattr(IssueSeverity, name), f"IssueSeverity.{name} missing")

    check("IssueSeverity WARNING/ERROR/CRITICAL", issue_severity)

    def valve_features() -> None:
        from homeassistant.components.valve import ValveEntityFeature

        for name in ("OPEN", "CLOSE"):
            _assert(hasattr(ValveEntityFeature, name), f"ValveEntityFeature.{name} missing")

    check("ValveEntityFeature OPEN/CLOSE", valve_features)

    def stop_event() -> None:
        _assert(
            isinstance(ha_const.EVENT_HOMEASSISTANT_STOP, str), "EVENT_HOMEASSISTANT_STOP missing"
        )

    check("EVENT_HOMEASSISTANT_STOP", stop_event)

    def service_validation_error() -> None:
        from homeassistant.exceptions import ServiceValidationError  # noqa: F401

    check("ServiceValidationError", service_validation_error)

    if FAILURES:
        print(f"\n{len(FAILURES)} contract check(s) FAILED")
        return 1
    print("\nAll HA API contract checks passed")
    return 0


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    sys.exit(main())
