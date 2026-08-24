"""Runtime safety Store for SoilSync (SPECIFICATION.md §23).

Owns the §23.5 initialization/integrity decision matrix, atomic revisioned
persistence with fresh-Store read-back verification (§23.4), the run-ID
protocol primitives (§23.3), and integrity-loss reconstruction. Lifecycle
orchestration (config-entry flag updates, actuator reconciliation ordering)
belongs to the entry runtime (Slice 8); this module never commands water.

Every Store instance is constructed with ``atomic_writes=True``. Every
safety write increments ``store_revision``, saves, then loads through a
fresh same-key Store and compares schema, generation, revision, and payload;
a failed read-back raises and the in-memory snapshot is not adopted, so no
dependent action (in particular no ON command) can proceed from an
unverified write. All load/modify/save/verify operations serialize on one
entry-wide lock.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.helpers.storage import Store

from .const import DOMAIN, LEGACY_STORE_SCHEMA_VERSION, STORE_SCHEMA_VERSION
from .models import (
    AccountingContribution,
    ActuatorIdentity,
    BlockerReason,
    ControllerState,
    DailyRuntime,
    FaultCode,
    FutureStoreVersion,
    IdentityIncident,
    IdentityIncidentKind,
    IdentityStatus,
    MigrationRecordContext,
    PersistedSession,
    PossibleFlowOwner,
    RunIds,
    RuntimeLifecycle,
    SafetyRecord,
    SensorIdentity,
    SessionContext,
    SessionSummary,
    StoreData,
    StoreDataError,
    ZoneDailyRuntime,
    ZoneHistory,
    ZoneRuntime,
    merge_zone_history_continuity,
    migrate_schema1_to_schema2,
    schema1_store_data_from_dict,
    store_data_from_dict,
    store_data_to_dict,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class StoreWriteVerificationError(RuntimeError):
    """A safety write could not be read-back verified (§23.4).

    The write must be treated as failed: do not command ON, do not activate
    watering-capable runtime.
    """


class StoreNotLoadedError(RuntimeError):
    """The Store has no verified in-memory snapshot yet."""


class SetupClassification(StrEnum):
    """§23.5 setup decision matrix outcome."""

    FIRST_INSTALL = "first_install"
    INTERRUPTED_INITIALIZATION = "interrupted_initialization"
    INITIALIZED_OK = "initialized_ok"
    INTEGRITY_LOSS = "integrity_loss"


def _new_store(hass: HomeAssistant, key: str) -> Store:
    return Store(hass, STORE_SCHEMA_VERSION, key, atomic_writes=True)


def _new_schema1_reader(hass: HomeAssistant, key: str) -> Store:
    """Construct the historical Store wrapper only for strict migration read."""
    return Store(hass, LEGACY_STORE_SCHEMA_VERSION, key, atomic_writes=True, read_only=True)


class SafetyStore:
    """Entry-scoped runtime safety Store (§23.1-§23.5)."""

    def __init__(self, hass: HomeAssistant, entry_id: str, generation_id: str) -> None:
        self._hass = hass
        self._key = f"{DOMAIN}.{entry_id}"
        self._generation_id = generation_id
        self._store = _new_store(hass, self._key)
        self._lock = asyncio.Lock()
        self._data: StoreData | None = None

    @property
    def generation_id(self) -> str:
        return self._generation_id

    @property
    def data(self) -> StoreData:
        """The last read-back-verified snapshot."""
        if self._data is None:
            raise StoreNotLoadedError("safety store has no verified snapshot")
        return self._data

    @property
    def loaded(self) -> bool:
        return self._data is not None

    # -- §23.5 setup decision matrix ---------------------------------------

    async def async_classify_setup(
        self,
        runtime_store_initialized: bool,
        migration_records: dict[str, MigrationRecordContext] | None = None,
    ) -> tuple[SetupClassification, StoreData | None]:
        """Classify startup per the §23.5 matrix. Adopts data on success.

        Never reinterprets previously initialized state as a first install
        (I29): with ``initialized=true``, absence (including Core moving
        corrupt JSON aside) and every malformed/mismatched/future payload is
        integrity loss. With ``initialized=false``, only genuine absence is
        a first install; a valid Store with the matching generation is the
        safe interrupted-initialization row and is adopted unchanged.
        """
        async with self._lock:
            try:
                raw = await self._load_current_or_schema1_locked()
            except Exception:
                return SetupClassification.INTEGRITY_LOSS, None
            if raw is None:
                if runtime_store_initialized:
                    return SetupClassification.INTEGRITY_LOSS, None
                return SetupClassification.FIRST_INSTALL, None
            if not isinstance(raw, dict):
                return SetupClassification.INTEGRITY_LOSS, None
            version = raw.get("version")
            if version == LEGACY_STORE_SCHEMA_VERSION:
                try:
                    legacy = schema1_store_data_from_dict(raw)
                except StoreDataError:
                    return SetupClassification.INTEGRITY_LOSS, None
                if legacy.generation_id != self._generation_id:
                    return SetupClassification.INTEGRITY_LOSS, None
                try:
                    # Current configuration may contain zones added after
                    # the schema-1 snapshot.  Only same-key legacy records
                    # are migration contexts; Stage 3 materializes current-
                    # only zones in the subsequent config+Store union.
                    relevant_records = {
                        record_id: context
                        for record_id, context in (migration_records or {}).items()
                        if record_id in legacy.zones
                    }
                    migrated = migrate_schema1_to_schema2(legacy, relevant_records)
                except (StoreDataError, ValueError):
                    return SetupClassification.INTEGRITY_LOSS, None
                await self._save_and_verify_locked(migrated)
                parsed = migrated
            else:
                try:
                    parsed = store_data_from_dict(raw)
                except FutureStoreVersion:
                    return SetupClassification.INTEGRITY_LOSS, None
                except StoreDataError:
                    return SetupClassification.INTEGRITY_LOSS, None
            if parsed.generation_id != self._generation_id:
                return SetupClassification.INTEGRITY_LOSS, None
            self._data = parsed
            if runtime_store_initialized:
                return SetupClassification.INITIALIZED_OK, parsed
            return SetupClassification.INTERRUPTED_INITIALIZATION, parsed

    async def async_first_initialize(self) -> StoreData:
        """§23.5 first-install transaction steps 3-4.

        Creates schema-2 initial safe state (matching generation, no records,
        histories, sessions, or blockers; null run IDs; revision 1), saves
        atomically, and read-back verifies. The caller sets the config-entry
        ``runtime_store_initialized=true`` only after this returns (step 5).
        """
        async with self._lock:
            data = StoreData(
                generation_id=self._generation_id,
                store_revision=1,
                run=RunIds(active_run_id=None, last_clean_shutdown_run_id=None),
                zone_histories={},
                safety_records={},
            )
            await self._save_and_verify_locked(data)
            return data

    async def async_reconstruct_after_integrity_loss(
        self,
        zone_budgets: dict[str, int],
        detection_date_local: date,
    ) -> StoreData:
        """§23.5 integrity-loss reconstruction (steps 4-5).

        Every zone enters FAULT(RESTORED_FROM_UNSAFE_STATE) with the
        detection-day budget fully exhausted (``daily_runtime_s =
        max_daily_runtime``), so neither AUTO nor MANUAL can become eligible
        through a zero counter, including after same-day acknowledgement.
        Actuator reconciliation and the Repair are the lifecycle's part.
        """
        async with self._lock:
            records: dict[str, SafetyRecord] = {}
            histories: dict[str, ZoneHistory] = {}
            for zone_id, max_daily in zone_budgets.items():
                history_id = _integrity_id(self._generation_id, zone_id, "zone-history")
                contribution = AccountingContribution(
                    accounting_contribution_id=_integrity_id(
                        self._generation_id,
                        zone_id,
                        f"integrity-daily:{detection_date_local.isoformat()}",
                    ),
                    source_safety_record_id=zone_id,
                    start_utc=None,
                    end_utc=None,
                    runtime_s=float(max_daily),
                    runtime_estimated=True,
                    local_date=detection_date_local,
                )
                histories[history_id] = ZoneHistory(
                    zone_history_id=history_id,
                    active_subentry_id=None,
                    previous_subentry_ids=(zone_id,),
                    last_session_end_utc=None,
                    last_auto_session_start_utc=None,
                    zone_runtime=ZoneRuntime(
                        enabled=True,
                        state=ControllerState.FAULT,
                        zone_fault=None,
                        secondary_fault=None,
                        sensor_identity=SensorIdentity(None, None),
                        last_session_summary=None,
                        session=None,
                    ),
                    daily=ZoneDailyRuntime(
                        date_local=detection_date_local,
                        runtime_s=float(max_daily),
                        conservative_unattributed_runtime_s=0.0,
                        contributions=(contribution,),
                    ),
                )
                records[zone_id] = SafetyRecord(
                    safety_record_id=zone_id,
                    zone_id=zone_id,
                    active_subentry_id=None,
                    previous_subentry_ids=(zone_id,),
                    safety_lineage_id=_integrity_id(self._generation_id, zone_id, "safety-lineage"),
                    zone_history_id=history_id,
                    historical_zone_history_ids=(),
                    runtime_lifecycle=RuntimeLifecycle.DELETE_PENDING,
                    applied_config=None,
                    actuator_identity=ActuatorIdentity(
                        registry_entry_id=None,
                        last_known_entity_id=None,
                        domain=None,
                        identity_status=IdentityStatus.MISSING,
                        off_service=None,
                        confirm_timeout_s=None,
                    ),
                    blocker_reasons=(BlockerReason.ACTUATOR_NOT_PROVEN_OFF,),
                    possible_flow_owner=None,
                    identity_incident=IdentityIncident(
                        IdentityIncidentKind.MIGRATION_UNRESOLVED,
                        "runtime Store integrity was reconstructed without durable identity",
                    ),
                    actuator_fault=FaultCode.RESTORED_FROM_UNSAFE_STATE,
                    acknowledgement_required=True,
                )
            data = StoreData(
                generation_id=self._generation_id,
                store_revision=1,
                run=RunIds(active_run_id=None, last_clean_shutdown_run_id=None),
                zone_histories=histories,
                safety_records=records,
            )
            await self._save_and_verify_locked(data)
            return data

    # -- §23.3 run-ID protocol ----------------------------------------------

    async def async_begin_new_run(self, new_active_run_id: str) -> RunIds:
        """Steps 1-4: capture previous IDs, persist/verify the new one.

        Returns the previous RunIds for cleanliness and trust checks;
        ``last_clean_shutdown_run_id`` is left unchanged.
        """
        async with self._lock:
            previous = self.data.run
            new_data = self.data.evolve(
                store_revision=self.data.store_revision + 1,
                run=RunIds(
                    active_run_id=new_active_run_id,
                    last_clean_shutdown_run_id=previous.last_clean_shutdown_run_id,
                ),
            )
            await self._save_and_verify_locked(new_data)
            return previous

    async def async_mark_clean_shutdown(self) -> None:
        """Graceful full-shutdown marker: last_clean = active (§23.3, §24.1)."""
        async with self._lock:
            run = self.data.run
            new_data = self.data.evolve(
                store_revision=self.data.store_revision + 1,
                run=RunIds(
                    active_run_id=run.active_run_id,
                    last_clean_shutdown_run_id=run.active_run_id,
                ),
            )
            await self._save_and_verify_locked(new_data)

    async def async_update_controller_runtime(
        self,
        safety_record_id: str,
        zone_history_id: str,
        *,
        state: ControllerState,
        enabled: bool,
        active_fault: FaultCode | None,
        secondary_fault: FaultCode | None,
        last_session_end_utc: datetime | None,
        last_auto_session_start_utc: datetime | None,
        daily: DailyRuntime | None,
        last_session_summary: SessionSummary | None,
        session: SessionContext | None,
        possible_flow_owner: PossibleFlowOwner | None,
    ) -> StoreData:
        """Write controller/session/accounting state through schema-2 owners.

        This is the Stage-4 live-command persistence API.  Both stable IDs
        are explicit: logical operational state/session/accounting mutate the
        exact ``zone_history_id`` while actuator possible-flow/fault evidence
        mutates only ``safety_record_id``.  No ``ZoneRecord`` projection is
        created or consumed on this path.
        """
        async with self._lock:
            record = self.data.safety_records.get(safety_record_id)
            history = self.data.zone_histories.get(zone_history_id)
            if record is None:
                raise StoreWriteVerificationError(
                    f"unknown canonical safety_record_id {safety_record_id}"
                )
            if history is None or record.zone_history_id != zone_history_id:
                raise StoreWriteVerificationError(
                    "controller safety-record/zone-history ownership mismatch"
                )

            actuator_fault, zone_fault, secondary_zone_fault = _partition_controller_faults(
                active_fault, secondary_fault
            )
            zone_runtime = ZoneRuntime(
                enabled=enabled,
                state=state,
                zone_fault=zone_fault,
                secondary_fault=secondary_zone_fault,
                sensor_identity=history.zone_runtime.sensor_identity,
                last_session_summary=last_session_summary,
                session=(
                    PersistedSession(safety_record_id, session) if session is not None else None
                ),
            )
            histories = dict(self.data.zone_histories)
            histories[zone_history_id] = history.evolve(
                last_session_end_utc=last_session_end_utc,
                last_auto_session_start_utc=last_auto_session_start_utc,
                zone_runtime=zone_runtime,
                daily=_merge_controller_daily_runtime(history.daily, daily),
            )
            records = dict(self.data.safety_records)
            records[safety_record_id] = record.evolve(
                possible_flow_owner=possible_flow_owner,
                actuator_fault=actuator_fault,
                acknowledgement_required=(
                    actuator_fault.requires_user_ack if actuator_fault is not None else False
                ),
            )
            new_data = self.data.evolve(
                store_revision=self.data.store_revision + 1,
                zone_histories=histories,
                safety_records=records,
            )
            await self._save_and_verify_locked(new_data)
            return new_data

    async def async_acknowledge_actuator_fault(
        self,
        safety_record_id: str,
        safety_lineage_id: str,
        expected_fault: FaultCode,
    ) -> StoreData:
        """Acknowledge one exact retained actuator record, fail closed.

        This is the Store-owned half of the §26.3 entry-level Repair flow.
        It deliberately accepts stable actuator identity rather than a
        subentry/device/entity identifier and refuses any unresolved physical
        evidence.  The runtime proves live OFF state before calling this for a
        live controller; a detached record is eligible only after the
        reconciler has durably made it RETIRED.
        """
        async with self._lock:
            record = self.data.safety_records.get(safety_record_id)
            if record is None:
                raise StoreWriteVerificationError(
                    f"unknown canonical safety_record_id {safety_record_id}"
                )
            if record.safety_lineage_id != safety_lineage_id:
                raise StoreWriteVerificationError("safety-record lineage mismatch")
            if record.actuator_fault is not expected_fault:
                raise StoreWriteVerificationError("safety-record fault changed")
            if not record.acknowledgement_required or not expected_fault.requires_user_ack:
                raise StoreWriteVerificationError("fault is not user-acknowledgeable")
            if record.identity_incident is not None or record.actuator_identity.identity_status in (
                IdentityStatus.MISSING,
                IdentityStatus.CONFLICT,
            ):
                raise StoreWriteVerificationError("actuator identity is unresolved")
            if (
                record.blocker_reasons
                or record.possible_flow_owner is not None
                or self.data.zone_histories[record.zone_history_id].zone_runtime.session is not None
            ):
                raise StoreWriteVerificationError("physical OFF/accounting evidence is unresolved")
            if record.runtime_lifecycle is not RuntimeLifecycle.RETIRED:
                raise StoreWriteVerificationError(
                    "detached acknowledgement requires a safely RETIRED record"
                )

            records = dict(self.data.safety_records)
            records[safety_record_id] = record.evolve(
                actuator_fault=None,
                acknowledgement_required=False,
            )
            new_data = self.data.evolve(
                store_revision=self.data.store_revision + 1,
                safety_records=records,
            )
            await self._save_and_verify_locked(new_data)
            return new_data

    async def async_reconcile(
        self,
        mutator: Callable[[StoreData], tuple[dict[str, SafetyRecord], dict[str, ZoneHistory]]],
    ) -> StoreData:
        """Apply one complete serialized Stage-3 reconciliation transaction.

        The mutator receives the last verified immutable snapshot and returns
        the full canonical record/history maps.  SafetyStore owns the revision
        increment, schema validation, atomic save, and fresh-Store read-back.
        """
        async with self._lock:
            records, histories = mutator(self.data)
            new_data = self.data.evolve(
                store_revision=self.data.store_revision + 1,
                safety_records=records,
                zone_histories=histories,
            )
            await self._save_and_verify_locked(new_data)
            return new_data

    async def async_set_record_blocker(
        self,
        safety_record_id: str,
        reason: BlockerReason,
        *,
        active: bool,
    ) -> StoreData:
        """Persist one exact-record blocker without touching any other key."""
        async with self._lock:
            record = self.data.safety_records.get(safety_record_id)
            if record is None:
                raise StoreNotLoadedError(f"unknown safety_record_id {safety_record_id}")
            blockers = set(record.blocker_reasons)
            if active:
                blockers.add(reason)
            else:
                blockers.discard(reason)
            ordered = tuple(sorted(blockers, key=lambda item: item.value))
            if ordered == record.blocker_reasons:
                return self.data
            possible_flow_owner = record.possible_flow_owner
            if active and reason is BlockerReason.EXTERNAL_FLOW:
                possible_flow_owner = PossibleFlowOwner.EXTERNAL
            elif active and reason is BlockerReason.INTEGRATION_OFF_UNCONFIRMED:
                possible_flow_owner = PossibleFlowOwner.INTEGRATION
            elif not active:
                if BlockerReason.INTEGRATION_OFF_UNCONFIRMED in blockers:
                    possible_flow_owner = PossibleFlowOwner.INTEGRATION
                elif BlockerReason.EXTERNAL_FLOW in blockers:
                    possible_flow_owner = PossibleFlowOwner.EXTERNAL
                elif possible_flow_owner is not None:
                    possible_flow_owner = None
            records = dict(self.data.safety_records)
            records[safety_record_id] = record.evolve(
                blocker_reasons=ordered,
                possible_flow_owner=possible_flow_owner,
            )
            new_data = self.data.evolve(
                store_revision=self.data.store_revision + 1,
                safety_records=records,
            )
            await self._save_and_verify_locked(new_data)
            return new_data

    async def async_merge_zone_history_for_record(
        self,
        continuing_zone_history_id: str,
        retained_safety_record_id: str,
    ) -> StoreData:
        """Verified Stage-2 history handoff with exact A/B hazard separation.

        The retained record must already be non-ACTIVE and have no unresolved
        operational session. Stage 3 performs those lifecycle prerequisites;
        this transaction merges only budget/interval evidence, repoints that
        exact record, and leaves every actuator-owned field byte-for-byte
        unchanged.
        """
        async with self._lock:
            continuing = self.data.zone_histories.get(continuing_zone_history_id)
            retained_record = self.data.safety_records.get(retained_safety_record_id)
            if continuing is None:
                raise StoreNotLoadedError(f"unknown zone_history_id {continuing_zone_history_id}")
            if retained_record is None:
                raise StoreNotLoadedError(f"unknown safety_record_id {retained_safety_record_id}")
            retained_history_id = retained_record.zone_history_id
            if retained_history_id == continuing_zone_history_id:
                return self.data
            retained = self.data.zone_histories.get(retained_history_id)
            if retained is None:
                raise StoreNotLoadedError(f"unknown retained zone_history_id {retained_history_id}")
            if retained_record.runtime_lifecycle is RuntimeLifecycle.ACTIVE:
                raise StoreWriteVerificationError(
                    "retained record must be quiesced before history handoff"
                )
            if retained.zone_runtime.session is not None:
                raise StoreWriteVerificationError(
                    "retained operational session must be reconciled before history handoff"
                )
            referrers = {
                record.safety_record_id
                for record in self.data.safety_records.values()
                if record.zone_history_id == retained_history_id
            }
            if referrers != {retained_safety_record_id}:
                raise StoreWriteVerificationError(
                    "retained history must have exactly one owning safety record"
                )

            merged = merge_zone_history_continuity(continuing, retained)
            historical_ids = retained_record.historical_zone_history_ids
            if retained_history_id not in historical_ids:
                historical_ids = (*historical_ids, retained_history_id)
            records = dict(self.data.safety_records)
            records[retained_safety_record_id] = retained_record.evolve(
                zone_history_id=continuing_zone_history_id,
                historical_zone_history_ids=historical_ids,
            )
            histories = dict(self.data.zone_histories)
            histories[continuing_zone_history_id] = merged
            del histories[retained_history_id]
            new_data = self.data.evolve(
                store_revision=self.data.store_revision + 1,
                safety_records=records,
                zone_histories=histories,
            )
            await self._save_and_verify_locked(new_data)
            return new_data

    async def async_rebase_soaking_owner_for_record(
        self, safety_record_id: str, new_run_id: str
    ) -> StoreData:
        """Exact-record Stage-3 trusted-SOAKING owner rebase."""
        async with self._lock:
            record = self.data.safety_records.get(safety_record_id)
            if record is None:
                raise StoreNotLoadedError(f"record {safety_record_id} has no persisted session")
            return await self._rebase_soaking_owner_locked(record, new_run_id)

    async def _rebase_soaking_owner_locked(
        self, record: SafetyRecord, new_run_id: str
    ) -> StoreData:
        history = self.data.zone_histories[record.zone_history_id]
        persisted = history.zone_runtime.session
        if persisted is None:
            raise StoreNotLoadedError(f"record {record.safety_record_id} has no persisted session")
        runtime = replace(
            history.zone_runtime,
            session=PersistedSession(
                persisted.owner_safety_record_id,
                persisted.context.evolve(owner_run_id=new_run_id),
            ),
        )
        histories = dict(self.data.zone_histories)
        histories[history.zone_history_id] = history.evolve(zone_runtime=runtime)
        new_data = self.data.evolve(
            store_revision=self.data.store_revision + 1, zone_histories=histories
        )
        await self._save_and_verify_locked(new_data)
        return new_data

    async def _load_current_or_schema1_locked(self) -> object | None:
        """Load schema 2 normally, falling back to the historical Store wrapper.

        The fallback Store is read-only. It never invokes Home Assistant's
        automatic migration/save path; only SafetyStore's strict parser and
        verified complete schema-2 transaction may rewrite schema 1.
        """
        try:
            return await self._store.async_load()
        except NotImplementedError:
            legacy_reader = _new_schema1_reader(self._hass, self._key)
            return await legacy_reader.async_load()

    # -- verified write core ----------------------------------------------

    async def _save_and_verify_locked(self, data: StoreData) -> None:
        """§23.4: save atomically, then verify through a fresh same-key Store.

        Core 2025.9.0 logs and consumes serialization/write errors instead
        of propagating them from ``async_save``, so the supported-Store
        round trip is the only trustworthy success signal. On any mismatch
        the in-memory snapshot is not adopted and the write counts as
        failed.
        """
        payload = store_data_to_dict(data)
        try:
            await self._store.async_save(payload)
        except Exception as err:
            raise StoreWriteVerificationError(f"safety write failed: {err!r}") from err
        fresh = _new_store(self._hass, self._key)
        try:
            raw = await fresh.async_load()
        except Exception as err:
            raise StoreWriteVerificationError(f"read-back load failed: {err!r}") from err
        if raw is None:
            raise StoreWriteVerificationError("read-back returned no data")
        try:
            loaded = store_data_from_dict(raw)
        except StoreDataError as err:
            raise StoreWriteVerificationError(f"read-back malformed: {err}") from err
        if loaded.version != STORE_SCHEMA_VERSION:
            raise StoreWriteVerificationError("read-back schema mismatch")
        if loaded.generation_id != data.generation_id:
            raise StoreWriteVerificationError("read-back generation mismatch")
        if loaded.store_revision != data.store_revision:
            raise StoreWriteVerificationError("read-back revision mismatch")
        # Compare the persisted projection: live-only session fields are
        # deliberately not stored (§23.2), so the expected safety payload for
        # this revision is the serialized form.
        if store_data_to_dict(loaded) != payload:
            raise StoreWriteVerificationError("read-back payload mismatch")
        self._data = data


_ACTUATOR_FAULTS = {
    FaultCode.ACTUATOR_UNAVAILABLE,
    FaultCode.ACTUATOR_ON_TIMEOUT,
    FaultCode.ACTUATOR_OFF_TIMEOUT,
    FaultCode.RESTORED_FROM_UNSAFE_STATE,
}
_ZONE_FAULTS = {
    FaultCode.SENSOR_UNAVAILABLE,
    FaultCode.SENSOR_STALE,
    FaultCode.SENSOR_INVALID,
    FaultCode.CONFIGURATION_INVALID,
}


def _partition_controller_faults(
    primary: FaultCode | None, secondary: FaultCode | None
) -> tuple[FaultCode | None, FaultCode | None, FaultCode | None]:
    actuator_faults = [fault for fault in (primary, secondary) if fault in _ACTUATOR_FAULTS]
    if len(actuator_faults) > 1:
        raise StoreWriteVerificationError(
            "controller state contains two actuator faults and cannot be represented safely"
        )
    return (
        actuator_faults[0] if actuator_faults else None,
        primary if primary in _ZONE_FAULTS else None,
        secondary if secondary in _ZONE_FAULTS else None,
    )


def _merge_controller_daily_runtime(
    current: ZoneDailyRuntime | None,
    replacement: DailyRuntime | None,
) -> ZoneDailyRuntime | None:
    if replacement is None:
        return None
    if current is None or current.date_local != replacement.date_local:
        return ZoneDailyRuntime(
            replacement.date_local,
            replacement.runtime_s,
            conservative_unattributed_runtime_s=replacement.runtime_s,
        )
    known = sum(contribution.runtime_s for contribution in current.contributions)
    return ZoneDailyRuntime(
        replacement.date_local,
        replacement.runtime_s,
        conservative_unattributed_runtime_s=max(0.0, replacement.runtime_s - known),
        contributions=current.contributions,
    )


def _integrity_id(generation_id: str, zone_id: str, kind: str) -> str:
    """Stable schema-2 identity for fail-closed integrity reconstruction."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{DOMAIN}:{generation_id}:{zone_id}:{kind}"))
