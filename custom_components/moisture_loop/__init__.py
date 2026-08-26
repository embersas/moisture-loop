"""MoistureLoop — closed-loop soil-moisture irrigation for Home Assistant.

The package init stays free of homeassistant imports so the pure domain
layer (models, state machine, slot manager) remains importable and provable
in an environment without homeassistant installed (§37). Home Assistant
resolves the integration's setup/unload entry points lazily through the
module ``__getattr__`` below; the actual lifecycle lives in ``runtime.py``.
"""

from __future__ import annotations

_LIFECYCLE_EXPORTS = {
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
    "EntryRuntime",
    "zone_config_from_subentry",
    "SHUTDOWN_OFF_BUDGET_S",
}


def __getattr__(name: str):
    if name in _LIFECYCLE_EXPORTS:
        from . import runtime

        return getattr(runtime, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
