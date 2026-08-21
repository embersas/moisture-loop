"""Runtime safety Store for Moisture Loop (SPECIFICATION.md §23).

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
from collections.abc import Callable
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORE_SCHEMA_VERSION
from .models import (
    ControllerState,
    DailyRuntime,
    FaultCode,
    FutureStoreVersion,
    RunIds,
    StoreData,
    StoreDataError,
    ZoneRecord,
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
        self, runtime_store_initialized: bool
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
                raw = await self._store.async_load()
            except Exception:
                return SetupClassification.INTEGRITY_LOSS, None
            if raw is None:
                if runtime_store_initialized:
                    return SetupClassification.INTEGRITY_LOSS, None
                return SetupClassification.FIRST_INSTALL, None
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

        Creates schema-1 initial safe state (matching generation, no
        sessions, zero current-day runtime, null run IDs, revision 1), saves
        atomically, and read-back verifies. The caller sets the config-entry
        ``runtime_store_initialized=true`` only after this returns (step 5).
        """
        async with self._lock:
            data = StoreData(
                generation_id=self._generation_id,
                store_revision=1,
                run=RunIds(active_run_id=None, last_clean_shutdown_run_id=None),
                zones={},
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
            zones = {
                zone_id: ZoneRecord(
                    state=ControllerState.FAULT,
                    enabled=True,
                    active_fault=FaultCode.RESTORED_FROM_UNSAFE_STATE,
                    daily=DailyRuntime(date_local=detection_date_local, runtime_s=float(max_daily)),
                )
                for zone_id, max_daily in zone_budgets.items()
            }
            data = StoreData(
                generation_id=self._generation_id,
                store_revision=1,
                run=RunIds(active_run_id=None, last_clean_shutdown_run_id=None),
                zones=zones,
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

    # -- zone safety writes ---------------------------------------------------

    async def async_update_zone(
        self, zone_id: str, mutator: Callable[[ZoneRecord | None], ZoneRecord]
    ) -> StoreData:
        """Apply one zone mutation as a verified safety write.

        The mutator receives the current record (or None) and returns the
        replacement. The complete merged snapshot is written with the next
        revision under the entry-wide lock, so concurrent zone writes
        serialize without lost updates (PI20).
        """
        async with self._lock:
            zones = dict(self.data.zones)
            zones[zone_id] = mutator(zones.get(zone_id))
            new_data = self.data.evolve(store_revision=self.data.store_revision + 1, zones=zones)
            await self._save_and_verify_locked(new_data)
            return new_data

    async def async_rebase_soaking_owner(self, zone_id: str, new_run_id: str) -> StoreData:
        """§23.3/§25.3: adopt a trusted SOAKING session for the current run.

        Changes only ``session.owner_run_id``; every other session field is
        preserved bit-for-bit. Atomically persisted and read-back verified
        before any controller activation may proceed.
        """
        async with self._lock:
            record = self.data.zones.get(zone_id)
            if record is None or record.session is None:
                raise StoreNotLoadedError(f"zone {zone_id} has no persisted session")
            rebased = record.evolve(session=record.session.evolve(owner_run_id=new_run_id))
            zones = dict(self.data.zones)
            zones[zone_id] = rebased
            new_data = self.data.evolve(store_revision=self.data.store_revision + 1, zones=zones)
            await self._save_and_verify_locked(new_data)
            return new_data

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
        # The strict parser only accepts schema 1, so schema equality is
        # already guaranteed here; compare generation, revision, payload.
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
