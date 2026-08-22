"""Entry-wide immutable configuration reconciliation ownership (spec.4 §22.4).

The coordinator is deliberately separate from Home Assistant's
``DataUpdateCoordinator``: configuration changes are pushed by the public
config-entry update-listener and are serialized into one latest-snapshot-wins
mutation stream.  The listener-facing ``observe_current`` method performs no
await and closes SlotManager admission before Core can continue its unawaited
notification path.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .models import (
    AppliedConfigurationShadow,
    AppliedEntityIdentity,
    NormalizedZoneSettings,
    RuntimeLifecycle,
    ZoneConfig,
)

if TYPE_CHECKING:
    from .slot_manager import SlotManager
    from .zone_controller import ZoneController


class ReconciliationError(RuntimeError):
    """The current observed configuration could not be safely reconciled."""


@dataclass(frozen=True, slots=True)
class ImmutableZoneSnapshot:
    """Normalized immutable values copied from one public ConfigSubentry."""

    subentry_id: str
    config: ZoneConfig
    sensor_identity: AppliedEntityIdentity
    actuator_identity: AppliedEntityIdentity
    config_fingerprint: str

    def applied_shadow(
        self, *, entry_snapshot_fingerprint: str, applied_generation: int
    ) -> AppliedConfigurationShadow:
        """Build the approved persisted applied-configuration shadow."""
        return AppliedConfigurationShadow(
            subentry_id=self.subentry_id,
            config_fingerprint=self.config_fingerprint,
            entry_snapshot_fingerprint=entry_snapshot_fingerprint,
            applied_generation=applied_generation,
            normalized_settings=NormalizedZoneSettings.from_config(self.config),
            sensor_identity=self.sensor_identity,
            actuator_identity=self.actuator_identity,
        )


@dataclass(frozen=True, slots=True)
class ImmutableEntrySnapshot:
    """One deterministic immutable snapshot of ``entry.subentries``."""

    observed_generation: int
    entry_snapshot_fingerprint: str
    zones: tuple[ImmutableZoneSnapshot, ...]

    def by_subentry_id(self) -> dict[str, ImmutableZoneSnapshot]:
        """Return a fresh mapping; the snapshot itself retains no mutable map."""
        return {zone.subentry_id: zone for zone in self.zones}


@dataclass(slots=True)
class RuntimeControllerBinding:
    """Canonical live relationship among config, safety, history and controller."""

    subentry_id: str
    safety_record_id: str
    zone_history_id: str
    lifecycle: RuntimeLifecycle
    applied_shadow: AppliedConfigurationShadow
    controller: ZoneController
    quiescing: bool = False


def normalized_zone_fingerprint(
    subentry_id: str,
    config: ZoneConfig,
    sensor_identity: AppliedEntityIdentity,
    actuator_identity: AppliedEntityIdentity,
    ha_timezone: str,
) -> str:
    """Hash immutable normalized zone values, including Registry identities."""
    settings = NormalizedZoneSettings.from_config(config)
    payload = {
        "version": 2,
        "subentry_id": subentry_id,
        "ha_timezone": ha_timezone,
        "sensor": {
            "registry_entry_id": sensor_identity.registry_entry_id,
            "entity_id": sensor_identity.last_known_entity_id,
            "domain": sensor_identity.domain,
        },
        "actuator": {
            "registry_entry_id": actuator_identity.registry_entry_id,
            "entity_id": actuator_identity.last_known_entity_id,
            "domain": actuator_identity.domain,
        },
        "settings": {field: getattr(settings, field) for field in settings.__dataclass_fields__},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def immutable_entry_snapshot(
    observed_generation: int,
    zones: list[ImmutableZoneSnapshot] | tuple[ImmutableZoneSnapshot, ...],
) -> ImmutableEntrySnapshot:
    """Create a sorted snapshot and its complete-entry fingerprint."""
    ordered = tuple(sorted(zones, key=lambda zone: zone.subentry_id))
    canonical = json.dumps(
        [(zone.subentry_id, zone.config_fingerprint) for zone in ordered],
        separators=(",", ":"),
    )
    return ImmutableEntrySnapshot(
        observed_generation=observed_generation,
        entry_snapshot_fingerprint=hashlib.sha256(canonical.encode()).hexdigest(),
        zones=ordered,
    )


SnapshotBuilder = Callable[[int], ImmutableEntrySnapshot]
SnapshotApplier = Callable[[ImmutableEntrySnapshot, Callable[[], bool]], Awaitable[None]]


class ConfigurationReconciliationCoordinator:
    """One serialized, coalesced, latest-snapshot-wins entry owner."""

    def __init__(
        self,
        slots: SlotManager,
        snapshot_builder: SnapshotBuilder,
        snapshot_applier: SnapshotApplier,
    ) -> None:
        self._slots = slots
        self._snapshot_builder = snapshot_builder
        self._snapshot_applier = snapshot_applier
        self._ready = asyncio.Event()
        self._worker: asyncio.Task[object] | None = None
        self._publication_allowed = True
        self._stopping = False
        self._observation_error: Exception | None = None

        self.observed_generation = 0
        self.applied_generation = 0
        self.observed_snapshot: ImmutableEntrySnapshot | None = None
        self.applied_snapshot: ImmutableEntrySnapshot | None = None
        self.dirty = False
        self.reconciling = False
        self.failed = False
        self.superseded_count = 0
        self.last_error: str | None = None

    def observe_current(self) -> int:
        """Synchronously record one public mapping notification.

        This is the only work invoked directly by the config-entry listener:
        generation/snapshot capture, dirty state, and immediate closure of the
        existing SlotManager reconciliation barrier.  It never awaits and it
        never retains a mutable ConfigSubentry object.
        """
        self.observed_generation += 1
        generation = self.observed_generation
        try:
            self.observed_snapshot = self._snapshot_builder(generation)
            self._observation_error = None
        except Exception as err:  # the worker converts this to fail-closed state
            self.observed_snapshot = None
            self._observation_error = err
        self.dirty = True
        self.failed = self._observation_error is not None
        self._slots.set_reconciliation_state_now(
            dirty=True,
            failed=self.failed,
        )
        return generation

    async def async_start(self) -> None:
        """Permit the captured setup generations to reconcile and join them."""
        self._ready.set()
        await self.async_reconcile()
        if self.failed:
            raise ReconciliationError(self.last_error or "configuration reconciliation failed")

    async def async_reconcile(self) -> None:
        """Run or join the single mutation worker used by all notifications."""
        await self._ready.wait()
        if self._stopping:
            return
        if not self.dirty and self.applied_generation == self.observed_generation:
            return
        current = asyncio.current_task()
        assert current is not None
        worker = self._worker
        if worker is not None and not worker.done() and worker is not current:
            await asyncio.shield(worker)
            return
        if worker is current:
            return
        self._worker = current
        try:
            await self._run_latest_loop()
        finally:
            if self._worker is current:
                self._worker = None

    async def _run_latest_loop(self) -> None:
        while self._publication_allowed and not self._stopping:
            target_generation = self.observed_generation
            target = self.observed_snapshot
            observation_error = self._observation_error
            if target is None or observation_error is not None:
                self._fail(observation_error or ReconciliationError("missing snapshot"))
                return

            self.reconciling = True
            self.failed = False
            self._slots.set_reconciliation_state_now(
                dirty=True,
                reconciling=True,
                failed=False,
            )

            def is_current(
                generation: int = target_generation,
                snapshot: ImmutableEntrySnapshot = target,
            ) -> bool:
                return (
                    self._publication_allowed
                    and not self._stopping
                    and self.observed_generation == generation
                    and self.observed_snapshot is snapshot
                )

            try:
                await self._snapshot_applier(target, is_current)
            except Exception as err:
                self._fail(err)
                return

            if not self._publication_allowed or self._stopping:
                return

            # Re-read the public mapping after the awaited application.  This
            # catches a mapping mutation even if a notification task has not
            # yet begun executing.
            if self.observed_generation == target_generation:
                try:
                    fresh = self._snapshot_builder(target_generation)
                except Exception as err:
                    self._fail(err)
                    return
                if fresh.entry_snapshot_fingerprint != target.entry_snapshot_fingerprint:
                    self.observe_current()

            if not is_current():
                self.superseded_count += 1
                continue

            # No suspension is permitted between the final current-token
            # check, applied publication, and SlotManager barrier opening.
            self.applied_generation = target_generation
            self.applied_snapshot = target
            self.dirty = False
            self.reconciling = False
            self.failed = False
            self.last_error = None
            self._slots.set_reconciliation_state_now(
                dirty=False,
                reconciling=False,
                failed=False,
            )
            return

    def _fail(self, err: Exception) -> None:
        self.dirty = True
        self.reconciling = False
        self.failed = True
        self.last_error = f"{type(err).__name__}: {err}"
        self._slots.set_reconciliation_state_now(
            dirty=True,
            reconciling=False,
            failed=True,
        )

    async def async_stop(self) -> None:
        """Transfer ownership to reload/unload/shutdown and forbid publication."""
        self._publication_allowed = False
        self._stopping = True
        self.dirty = True
        self._slots.set_reconciliation_state_now(dirty=True, reconciling=False)
        self._ready.set()
        worker = self._worker
        current = asyncio.current_task()
        if worker is not None and not worker.done() and worker is not current:
            await asyncio.shield(worker)
