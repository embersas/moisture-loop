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
from dataclasses import dataclass, replace
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
    """Normalized immutable values copied from one public ConfigSubentry.

    ``config``/``sensor_identity``/``actuator_identity`` keep the *configured*
    subentry references together with the durable Registry UUID each one
    resolves to, so ``config_fingerprint`` never moves for a textual rename
    (§6, §9, §12.2, §23.2 item 1).  ``current_*_entity_id`` is the entity ID
    that same durable identity is addressable at right now; it follows a
    verified same-UUID rename (§25.1.1) and is what listeners, adapters,
    service calls and ``last_known_entity_id`` metadata must use.
    """

    subentry_id: str
    config: ZoneConfig
    sensor_identity: AppliedEntityIdentity
    actuator_identity: AppliedEntityIdentity
    config_fingerprint: str
    current_sensor_entity_id: str | None = None
    current_actuator_entity_id: str | None = None
    identity_conflict_detail: str | None = None

    @property
    def current_sensor(self) -> str:
        """Entity ID the configured moisture sensor is addressable at now."""
        return self.current_sensor_entity_id or self.sensor_identity.last_known_entity_id

    @property
    def current_actuator(self) -> str:
        """Entity ID the durable configured actuator is addressable at now."""
        return self.current_actuator_entity_id or self.actuator_identity.last_known_entity_id

    @property
    def renamed(self) -> bool:
        """Whether current addressing differs from the configured reference."""
        return (
            self.current_sensor != self.sensor_identity.last_known_entity_id
            or self.current_actuator != self.actuator_identity.last_known_entity_id
        )

    def current_config(self) -> ZoneConfig:
        """Configuration bound to the current addressable entity IDs."""
        if not self.renamed:
            return self.config
        return replace(
            self.config,
            moisture_sensor=self.current_sensor,
            actuator=self.current_actuator,
        )

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


@dataclass(frozen=True, slots=True)
class FinalOnAuthorizationToken:
    """Single-use Stage-4 authorization bound to one command attempt.

    The controller consumes this token immediately.  It is retained only so
    the same exact configuration authority can be checked again when the
    asynchronous Home Assistant service call returns or raises; it is never
    authorization for a later pulse.
    """

    subentry_id: str
    safety_record_id: str
    zone_history_id: str
    session_id: str
    command_attempt_id: str
    applied_generation: int
    zone_config_fingerprint: str
    entry_snapshot_fingerprint: str


@dataclass(frozen=True, slots=True)
class FinalOnAuthorizationResult:
    """Mechanically testable result of the authoritative Stage-4 gate."""

    token: FinalOnAuthorizationToken | None
    failed_predicates: tuple[str, ...] = ()
    configuration_authority_valid: bool = False
    requires_quiescing: bool = False

    @property
    def authorized(self) -> bool:
        """Whether every final-ON predicate passed."""
        return self.token is not None and not self.failed_predicates


def normalized_zone_fingerprint(
    subentry_id: str,
    config: ZoneConfig,
    sensor_identity: AppliedEntityIdentity,
    actuator_identity: AppliedEntityIdentity,
    ha_timezone: str,
) -> str:
    """Hash immutable normalized zone values, including Registry identities.

    The hashed entity IDs are the *configured* subentry references.  Durable
    Entity Registry identity is the equivalence key (§6, §23.2 item 1), so a
    verified same-UUID rename leaves this fingerprint byte-identical while a
    genuine reconfiguration to a different actuator still changes it.
    """
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
ReloadEntry = Callable[[], Awaitable[bool]]
TaskCreator = Callable[[Awaitable[None], str], asyncio.Task[object]]


def stable_batch_requires_reload(
    platform_snapshot: ImmutableEntrySnapshot | None,
    target_snapshot: ImmutableEntrySnapshot,
) -> bool:
    """Return whether platform/entity reconstruction is required.

    The platform snapshot is the configuration represented by the currently
    loaded entity platforms. A pure deletion needs no reload because Core
    removes its subentry-attributed registry objects itself. Any addition or
    material fingerprint change needs one reload because the current platform
    setup binds entity objects to the controller instances present at setup.
    """
    if platform_snapshot is None:
        return False
    platform = platform_snapshot.by_subentry_id()
    target = target_snapshot.by_subentry_id()
    for subentry_id, zone in target.items():
        previous = platform.get(subentry_id)
        if previous is None or previous.config_fingerprint != zone.config_fingerprint:
            return True
    return False


class ConfigurationReconciliationCoordinator:
    """One serialized, coalesced, latest-snapshot-wins entry owner."""

    def __init__(
        self,
        slots: SlotManager,
        snapshot_builder: SnapshotBuilder,
        snapshot_applier: SnapshotApplier,
        reload_entry: ReloadEntry | None = None,
        task_creator: TaskCreator | None = None,
    ) -> None:
        self._slots = slots
        self._snapshot_builder = snapshot_builder
        self._snapshot_applier = snapshot_applier
        self._reload_entry = reload_entry
        self._task_creator = task_creator
        self._ready = asyncio.Event()
        self._worker: asyncio.Task[object] | None = None
        self._reload_handle: asyncio.Handle | None = None
        self._reload_task: asyncio.Task[object] | None = None
        self._platform_snapshot: ImmutableEntrySnapshot | None = None
        self._reload_failed_fingerprint: str | None = None
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
        self.reload_pending = False
        self.reload_generation: int | None = None
        self.reload_snapshot_fingerprint: str | None = None
        self.reload_count = 0

    @property
    def stopping(self) -> bool:
        """Whether unload/reload/shutdown has revoked publication authority."""
        return self._stopping or not self._publication_allowed

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

            reload_required = stable_batch_requires_reload(self._platform_snapshot, target)
            prior_reload_failure = (
                self._reload_failed_fingerprint == target.entry_snapshot_fingerprint
            )
            if prior_reload_failure:
                # One deterministic failure remains fail closed; equivalent
                # notifications cannot create an unbounded retry loop.
                reload_required = False

            # No suspension is permitted between the final current-token
            # check, applied publication, and SlotManager admission decision.
            self.applied_generation = target_generation
            self.applied_snapshot = target
            self.dirty = False
            self.reconciling = False
            self.failed = False
            self.last_error = None
            if self._platform_snapshot is None:
                # Initial setup forwards platforms only after this publication.
                self._platform_snapshot = target
            if prior_reload_failure:
                self._fail(ReconciliationError("configuration reload previously failed"))
            elif reload_required and self._reload_entry is not None:
                self._queue_reload(target)
            else:
                self._cancel_pending_reload()
                self._slots.set_reconciliation_state_now(
                    dirty=False,
                    reconciling=False,
                    failed=False,
                )
            return

    def _queue_reload(self, target: ImmutableEntrySnapshot) -> None:
        """Queue one latest-generation reload after durable reconciliation."""
        self.reload_pending = True
        self.reload_generation = target.observed_generation
        self.reload_snapshot_fingerprint = target.entry_snapshot_fingerprint
        self._slots.set_reconciliation_state_now(
            dirty=True,
            reconciling=False,
            failed=False,
        )
        if self._reload_handle is None and self._reload_task is None:
            self._reload_handle = asyncio.get_running_loop().call_soon(
                self._begin_reload_if_current
            )

    def _begin_reload_if_current(self) -> None:
        """Start the supported reload only for the latest stable publication."""
        self._reload_handle = None
        generation = self.reload_generation
        fingerprint = self.reload_snapshot_fingerprint
        current = self.applied_snapshot
        if (
            not self.reload_pending
            or self._reload_entry is None
            or self.stopping
            or self.dirty
            or self.reconciling
            or self.failed
            or generation is None
            or fingerprint is None
            or self.observed_generation != generation
            or self.applied_generation != generation
            or current is None
            or current.entry_snapshot_fingerprint != fingerprint
        ):
            return
        coroutine = self._async_apply_reload(generation, fingerprint)
        if self._task_creator is None:
            self._reload_task = asyncio.create_task(
                coroutine,
                name="moisture_loop configuration reload",
            )
        else:
            self._reload_task = self._task_creator(
                coroutine,
                "moisture_loop configuration reload",
            )

    async def _async_apply_reload(self, generation: int, fingerprint: str) -> None:
        """Await the public reload API and retain fail-closed state on error."""
        try:
            if (
                self.stopping
                or not self.reload_pending
                or self.reload_generation != generation
                or self.reload_snapshot_fingerprint != fingerprint
                or self.observed_generation != generation
                or self.applied_generation != generation
            ):
                return
            assert self._reload_entry is not None
            reloaded = await self._reload_entry()
            if not reloaded:
                raise ReconciliationError("supported config-entry reload returned false")
        except asyncio.CancelledError:
            if not self.stopping:
                self._reload_failed_fingerprint = fingerprint
                self.reload_pending = False
                self._fail(ReconciliationError("configuration reload was cancelled"))
            raise
        except Exception as err:
            if not self.stopping and self.reload_snapshot_fingerprint == fingerprint:
                self._reload_failed_fingerprint = fingerprint
                self.reload_pending = False
                self._fail(err)
        else:
            self.reload_count += 1
            self.reload_pending = False
            self.reload_generation = None
            self.reload_snapshot_fingerprint = None
            self._platform_snapshot = self.applied_snapshot
            if not self.stopping:
                self._slots.set_reconciliation_state_now(
                    dirty=False,
                    reconciling=False,
                    failed=False,
                )
        finally:
            if self._reload_task is asyncio.current_task():
                self._reload_task = None

    def _cancel_pending_reload(self) -> None:
        """Cancel a not-yet-started obsolete reload decision."""
        handle = self._reload_handle
        if handle is not None:
            handle.cancel()
            self._reload_handle = None
        if self._reload_task is None:
            self.reload_pending = False
            self.reload_generation = None
            self.reload_snapshot_fingerprint = None

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

    def close_publication_now(self) -> None:
        """Synchronously forbid publication and close configuration admission.

        The Stage-1 full-process shutdown owner (§24.1) must close
        reconciliation publication/admission before its own first suspension
        point, so a stale worker completion can never reopen admission or
        publish a newer watering-capable generation while active flow is
        being signalled. This contains no suspension point; joining the
        worker is :meth:`async_join_workers`.
        """
        self._publication_allowed = False
        self._stopping = True
        self.dirty = True
        self._slots.set_reconciliation_state_now(dirty=True, reconciling=False)
        self._ready.set()
        self._cancel_pending_reload()

    async def async_join_workers(self) -> None:
        """Join or take over any in-flight reconciliation/reload work."""
        reload_task = self._reload_task
        current = asyncio.current_task()
        if reload_task is not None and not reload_task.done() and reload_task is not current:
            reload_task.cancel()
        worker = self._worker
        if worker is not None and not worker.done() and worker is not current:
            await asyncio.shield(worker)

    async def async_stop(self) -> None:
        """Transfer ownership to reload/unload/shutdown and forbid publication."""
        self.close_publication_now()
        await self.async_join_workers()
