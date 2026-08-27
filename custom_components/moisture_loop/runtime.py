"""Entry runtime, startup union, and configuration reconciliation ownership."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from dataclasses import dataclass, replace

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

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
    DOMAIN,
)
from .models import (
    ActuatorBecameUnavailable,
    ActuatorFinding,
    ActuatorIdentity,
    AppliedConfigurationShadow,
    AppliedEntityIdentity,
    BlockerReason,
    CompletionReason,
    ConfigChangedPrepare,
    ConfigEntryReload,
    ControllerState,
    ExternalActuatorOn,
    FaultCode,
    GraceDeadlineReached,
    HomeAssistantShutdown,
    IdentityIncident,
    IdentityIncidentKind,
    IdentityStatus,
    MigrationRecordContext,
    MoistureClassification,
    PersistedSession,
    PossibleFlowOwner,
    RunIds,
    RuntimeLifecycle,
    SafetyRecord,
    SensorIdentity,
    SessionContext,
    SessionMode,
    StartupPersistedSoaking,
    StartupPersistedWatering,
    ZoneConfig,
    ZoneDailyRuntime,
    ZoneHistory,
    config_fingerprint,
    merge_zone_history_continuity,
)
from .reconciliation import (
    ConfigurationReconciliationCoordinator,
    FinalOnAuthorizationResult,
    FinalOnAuthorizationToken,
    ImmutableEntrySnapshot,
    ImmutableZoneSnapshot,
    ReconciliationError,
    RuntimeControllerBinding,
    immutable_entry_snapshot,
    normalized_zone_fingerprint,
)
from .slot_manager import SlotManager
from .storage import SafetyStore, SetupClassification, StoreWriteVerificationError
from .zone_controller import ActuatorAdapter, ZoneController, classify_moisture

_LOGGER = logging.getLogger(__name__)

# §24.1/§46 item 4: the one overall Stage-1 active-flow closure deadline. It
# bounds the total time the authoritative shutdown owner waits for cooperative
# closure, including convergence of an already in-flight ON and the shared OFF
# operation. It is not a delay before OFF, not a per-controller allowance, and
# not a process-manager setting. Tuning is §46 item 4.
SHUTDOWN_OFF_BUDGET_S = 8.0


@dataclass(frozen=True, slots=True)
class Stage1ShutdownReport:
    """Immutable record of one §24.1 Stage-1 full-process shutdown.

    Diagnostics-grade evidence only: the authority for the next run remains
    the persisted run IDs (§23.3). ``clean`` is true only when every required
    Stage-1 outcome succeeded and the verified clean marker was written.
    """

    core_state_at_entry: str
    watering_records: tuple[str, ...]
    preserved_soaking_records: tuple[str, ...]
    failures: tuple[str, ...]
    clean: bool


class SafetyRecordAcknowledgementError(RuntimeError):
    """Translated fail-closed reason from an exact-record Repair operation."""

    def __init__(self, translation_key: str) -> None:
        super().__init__(translation_key)
        self.translation_key = translation_key


def zone_config_from_subentry(data: dict) -> ZoneConfig:
    """Build the pure ZoneConfig from config-subentry data (§9 keys)."""
    return ZoneConfig(
        name=data[CONF_NAME],
        moisture_sensor=data[CONF_MOISTURE_SENSOR],
        actuator=data[CONF_ACTUATOR],
        start_threshold=float(data[CONF_START_THRESHOLD]),
        target_threshold=float(data[CONF_TARGET_THRESHOLD]),
        pulse_duration_s=int(data[CONF_PULSE_DURATION]),
        soak_duration_s=int(data[CONF_SOAK_DURATION]),
        max_cycles=int(data[CONF_MAX_CYCLES]),
        max_session_runtime_s=int(data[CONF_MAX_SESSION_RUNTIME]),
        max_daily_runtime_s=int(data[CONF_MAX_DAILY_RUNTIME]),
        min_session_interval_s=int(data[CONF_MIN_SESSION_INTERVAL]),
        sensor_max_age_s=int(data[CONF_SENSOR_MAX_AGE]),
        actuator_confirm_timeout_s=int(data[CONF_ACTUATOR_CONFIRM_TIMEOUT]),
        manual_max_duration_s=int(data[CONF_MANUAL_MAX_DURATION]),
    )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Integration-level setup: register actions once (§5.3, I25)."""
    from .services import async_register_services

    async_register_services(hass)
    return True


PLATFORMS = ["binary_sensor", "button", "sensor", "switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the single MoistureLoop controller entry."""
    runtime = EntryRuntime(hass, entry)
    # §24.1: async_initialize registers the one Stage-1 shutdown owner before
    # any watering-capable runtime is armed.
    await runtime.async_initialize()
    entry.runtime_data = runtime
    # Platforms forward only after §25.1 reconciliation completed above.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the entry (§24.2); never marks the process run clean."""
    runtime: EntryRuntime = entry.runtime_data
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await runtime.async_unload()
    return unloaded


class EntryRuntime:
    """Entry-scoped runtime: Store identity, run IDs, reconciliation (§37).

    No watering-capable activation (SlotManager grants) occurs before every
    §25.1 prerequisite completes; every safety write is verified.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        generation = entry.data[CONF_RUNTIME_STORE_GENERATION_ID]
        self.store = SafetyStore(hass, entry.entry_id, generation)
        self.slots = SlotManager(self._persist_slot_blocker)
        self.controllers: dict[str, ZoneController] = {}
        self.bindings: dict[str, RuntimeControllerBinding] = {}
        self.retained_controllers: dict[str, ZoneController] = {}
        self.run_id = str(uuid.uuid4())
        self.previous_run: RunIds | None = None
        self.setup_classification: SetupClassification | None = None
        self.soaking_adoptions: dict[str, bool] = {}
        self.process_stopping = False
        self.shutdown_off_budget_s = SHUTDOWN_OFF_BUDGET_S
        self.shutdown_report: Stage1ShutdownReport | None = None
        self._activity_unsubs: list[CALLBACK_TYPE] = []
        self._shutdown_job_remove: CALLBACK_TYPE | None = None
        self._shutdown_operation: asyncio.Future[None] | None = None
        self._shutdown_deadline: float | None = None
        self._local_tz = dt_util.get_default_time_zone()
        self._listener_registered = False
        self._on_authorizations: dict[str, FinalOnAuthorizationToken] = {}
        self._reconciliation_issue_active = False
        self._known_identity_incidents: set[str] = set()
        self.coordinator = ConfigurationReconciliationCoordinator(
            self.slots,
            self._build_immutable_snapshot,
            self._apply_configuration_snapshot,
            self._async_reload_after_reconciliation,
            self.hass.async_create_task,
        )

    # ------------------------------------------------------------------
    # Stage-6 presentation/action authority (§§28, 31, 33)
    # ------------------------------------------------------------------

    def canonical_zone_authority(
        self, controller: ZoneController
    ) -> tuple[SafetyRecord, ZoneHistory] | None:
        """Return the exact schema-2 authorities for one current controller."""
        if not self.store.loaded:
            return None
        record = self.store.data.safety_records.get(controller.safety_record_id)
        history = self.store.data.zone_histories.get(controller.zone_history_id)
        if record is None or history is None or record.zone_history_id != history.zone_history_id:
            return None
        return record, history

    def action_refusal_key(self, controller: ZoneController) -> str | None:
        """Return the translated reason normal zone control is unavailable."""
        authority = self.canonical_zone_authority(controller)
        binding = self.bindings.get(controller.zone_id)
        if authority is None or binding is None or binding.controller is not controller:
            return "zone_not_ready"
        record, history = authority
        if (
            controller.zone_id not in self.entry.subentries
            or record.runtime_lifecycle is not RuntimeLifecycle.ACTIVE
            or record.active_subentry_id != controller.zone_id
            or history.active_subentry_id != controller.zone_id
            or binding.lifecycle is not RuntimeLifecycle.ACTIVE
            or binding.quiescing
            or controller.runtime_lifecycle is not RuntimeLifecycle.ACTIVE
            or not controller.runtime_eligible
        ):
            return "zone_not_active"
        if self.coordinator.failed or self.slots.snapshot().reconciliation_failed:
            return "reconciliation_failed"
        slots = self.slots.snapshot()
        if (
            self.process_stopping
            or self.coordinator.stopping
            or self.coordinator.dirty
            or self.coordinator.reconciling
            or self.coordinator.reload_pending
            or self.coordinator.observed_generation != self.coordinator.applied_generation
            or not slots.admission_open
        ):
            return "reconciliation_busy"
        return None

    def entity_runtime_active(self, controller: ZoneController) -> bool:
        """Whether an entity still represents a current ACTIVE configured zone."""
        authority = self.canonical_zone_authority(controller)
        if authority is None:
            return False
        record, history = authority
        return (
            record.runtime_lifecycle is RuntimeLifecycle.ACTIVE
            and record.active_subentry_id == controller.zone_id
            and history.active_subentry_id == controller.zone_id
            and self.controllers.get(controller.zone_id) is controller
            and controller.zone_id in self.entry.subentries
        )

    def control_entity_available(self, controller: ZoneController) -> bool:
        """Availability for controls/needs-water; direct calls still validate."""
        return self.action_refusal_key(controller) is None

    def controller_for_safety_record(self, safety_record_id: str) -> ZoneController | None:
        """Resolve a live ACTIVE or retained controller by exact record identity."""
        for controller in self._all_controllers():
            if controller.safety_record_id == safety_record_id:
                return controller
        return None

    # ------------------------------------------------------------------
    # Stage-4 final actuator-ON authorization (§11.2, I32, I36)
    # ------------------------------------------------------------------

    def authorize_on(
        self,
        controller: ZoneController,
        session_id: str,
        command_attempt_id: str,
    ) -> FinalOnAuthorizationResult:
        """Run the complete authoritative final gate from fresh live state.

        This method is synchronous by design.  The caller invokes it only
        after verified hazardous-intent persistence while owning its command
        transition domain, then records possible-flow ownership and starts
        the service coroutine without yielding.
        """
        result = self._evaluate_on_authority(
            controller,
            session_id,
            command_attempt_id,
            token=None,
            pre_dispatch=True,
        )
        if not result.authorized:
            return result
        token = result.token
        assert token is not None
        if command_attempt_id in self._on_authorizations:
            return FinalOnAuthorizationResult(
                token=None,
                failed_predicates=("authorization_token_single_use",),
                configuration_authority_valid=result.configuration_authority_valid,
            )
        self._on_authorizations[command_attempt_id] = token
        return result

    def recheck_on_authorization(
        self,
        controller: ZoneController,
        token: FinalOnAuthorizationToken,
    ) -> FinalOnAuthorizationResult:
        """Immediately re-read authority after an ON call returns/raises."""
        return self._evaluate_on_authority(
            controller,
            token.session_id,
            token.command_attempt_id,
            token=token,
            pre_dispatch=False,
        )

    def finish_on_authorization(self, token: FinalOnAuthorizationToken) -> None:
        """Retire a consumed token after its exact command is reconciled."""
        if self._on_authorizations.get(token.command_attempt_id) == token:
            self._on_authorizations.pop(token.command_attempt_id, None)

    def _evaluate_on_authority(
        self,
        controller: ZoneController,
        session_id: str,
        command_attempt_id: str,
        *,
        token: FinalOnAuthorizationToken | None,
        pre_dispatch: bool,
    ) -> FinalOnAuthorizationResult:
        failures: list[str] = []
        authority_failures: set[str] = set()
        quiescing_failures: set[str] = set()

        def fail(
            predicate: str,
            *,
            authority: bool = False,
            requires_quiescing: bool = False,
        ) -> None:
            if predicate not in failures:
                failures.append(predicate)
            if authority:
                authority_failures.add(predicate)
            if requires_quiescing:
                quiescing_failures.add(predicate)

        try:
            fresh_snapshot = self._build_immutable_snapshot(self.coordinator.observed_generation)
        except Exception:
            fresh_snapshot = None
            fail("current_entry_snapshot_matches", authority=True)

        fresh_zone = None
        if fresh_snapshot is not None:
            fresh_zone = fresh_snapshot.by_subentry_id().get(controller.zone_id)
        if fresh_zone is None:
            fail(
                "current_subentry_exists",
                authority=True,
                requires_quiescing=True,
            )

        binding = self.bindings.get(controller.zone_id)
        applied = controller.applied_config
        if (
            fresh_zone is None
            or applied is None
            or fresh_zone.config_fingerprint != applied.config_fingerprint
        ):
            fail(
                "current_zone_fingerprint_matches",
                authority=True,
                requires_quiescing=True,
            )

        applied_snapshot = self.coordinator.applied_snapshot
        observed_snapshot = self.coordinator.observed_snapshot
        if (
            fresh_snapshot is None
            or applied_snapshot is None
            or observed_snapshot is None
            or fresh_snapshot.entry_snapshot_fingerprint
            != applied_snapshot.entry_snapshot_fingerprint
            or fresh_snapshot.entry_snapshot_fingerprint
            != observed_snapshot.entry_snapshot_fingerprint
            or applied is None
            or fresh_snapshot.entry_snapshot_fingerprint != applied.entry_snapshot_fingerprint
        ):
            fail("current_entry_snapshot_matches", authority=True)

        if (
            applied is None
            or self.coordinator.observed_generation != self.coordinator.applied_generation
            or applied.applied_generation != self.coordinator.applied_generation
            or (
                fresh_snapshot is not None
                and fresh_snapshot.observed_generation != self.coordinator.applied_generation
            )
        ):
            fail("applied_generation_current", authority=True)

        slot_snapshot = self.slots.snapshot()
        if (
            self.process_stopping
            or self.coordinator.stopping
            or self.coordinator.dirty
            or self.coordinator.reconciling
            or self.coordinator.failed
            or self.coordinator.reload_pending
            or not slot_snapshot.admission_open
        ):
            fail("reconciliation_admission_clear", authority=True)

        if (
            binding is None
            or binding.controller is not controller
            or binding.lifecycle is not RuntimeLifecycle.ACTIVE
            or binding.quiescing
            or controller.runtime_lifecycle is not RuntimeLifecycle.ACTIVE
        ):
            fail(
                "runtime_lifecycle_active",
                authority=True,
                requires_quiescing=True,
            )

        if not controller.command_authorization_open:
            fail(
                "controller_commandable",
                authority=True,
                requires_quiescing=True,
            )

        record = self.store.data.safety_records.get(controller.safety_record_id)
        history = self.store.data.zone_histories.get(controller.zone_history_id)
        canonical_ok = (
            binding is not None
            and record is not None
            and history is not None
            and binding.safety_record_id == controller.safety_record_id
            and binding.zone_history_id == controller.zone_history_id
            and record.safety_record_id == controller.safety_record_id
            and record.zone_history_id == controller.zone_history_id
            and record.active_subentry_id == controller.zone_id
            and record.runtime_lifecycle is RuntimeLifecycle.ACTIVE
            and history.zone_history_id == controller.zone_history_id
            and history.active_subentry_id == controller.zone_id
            and record.applied_config is not None
            and record.applied_config == applied
            and binding.applied_shadow == applied
            and record.actuator_identity.last_known_entity_id == controller.config.actuator
        )
        if not canonical_ok:
            fail(
                "canonical_ownership_matches",
                authority=True,
                requires_quiescing=True,
            )

        persisted = history.zone_runtime.session if history is not None else None
        if (
            persisted is None
            or persisted.owner_safety_record_id != controller.safety_record_id
            or persisted.context.session_id != session_id
            or persisted.context.pulse_intent_at_utc is None
        ):
            fail("verified_hazard_intent_matches", authority=True)

        if slot_snapshot.owner != controller.zone_id:
            fail("slot_owned_by_session")
        if slot_snapshot.blockers:
            fail("keyed_blockers_clear")

        daily_runtime_s = 0.0
        if history is not None and history.daily is not None:
            today = dt_util.utcnow().astimezone(self._local_tz).date()
            if history.daily.date_local == today:
                daily_runtime_s = history.daily.runtime_s
        guard_failures = controller.final_on_guard_failures(
            session_id,
            authoritative_daily_runtime_s=daily_runtime_s,
            pre_dispatch=pre_dispatch,
        )
        if guard_failures:
            fail("ordinary_runtime_guards")

        if pre_dispatch:
            live_actuator = controller.refresh_actuator_for_final_gate()
            if not (
                live_actuator.available
                and live_actuator.proven_off
                and not live_actuator.observed_on
            ):
                fail("actuator_available_and_proven_off")

        if token is not None:
            expected = self._on_authorizations.get(token.command_attempt_id)
            if (
                expected != token
                or token.subentry_id != controller.zone_id
                or token.safety_record_id != controller.safety_record_id
                or token.zone_history_id != controller.zone_history_id
                or token.session_id != session_id
                or token.command_attempt_id != command_attempt_id
                or applied is None
                or token.applied_generation != applied.applied_generation
                or token.zone_config_fingerprint != applied.config_fingerprint
                or token.entry_snapshot_fingerprint != applied.entry_snapshot_fingerprint
            ):
                fail("authorization_token_matches", authority=True)

        authority_valid = not authority_failures
        if failures:
            return FinalOnAuthorizationResult(
                token=None,
                failed_predicates=tuple(failures),
                configuration_authority_valid=authority_valid,
                requires_quiescing=bool(quiescing_failures),
            )
        assert applied is not None
        authorized_token = token or FinalOnAuthorizationToken(
            subentry_id=controller.zone_id,
            safety_record_id=controller.safety_record_id,
            zone_history_id=controller.zone_history_id,
            session_id=session_id,
            command_attempt_id=command_attempt_id,
            applied_generation=applied.applied_generation,
            zone_config_fingerprint=applied.config_fingerprint,
            entry_snapshot_fingerprint=applied.entry_snapshot_fingerprint,
        )
        return FinalOnAuthorizationResult(
            token=authorized_token,
            configuration_authority_valid=True,
        )

    # ------------------------------------------------------------------
    # Startup (§25.1 order)
    # ------------------------------------------------------------------

    async def async_initialize(self) -> None:
        """Reconcile current config + Store union before enabling grants."""
        entry = self.entry
        # §24.1/§37: registration MUST complete before any watering-capable
        # runtime is armed, so no process can reach a commandable ON without
        # an installed authoritative Stage-1 shutdown owner.
        self.register_shutdown_job()
        self._register_update_listener()
        self.coordinator.observe_current()
        initial_snapshot = self.coordinator.observed_snapshot
        if initial_snapshot is None:
            raise ConfigEntryNotReady("initial configuration snapshot could not be normalized")
        initialized = bool(entry.data.get(CONF_RUNTIME_STORE_INITIALIZED, False))

        # Identity/schema migration precedes controller materialization.  A
        # matching schema-1 record receives the same immutable current facts;
        # current-only zones are materialized by the union transaction below.
        classification, _data = await self.store.async_classify_setup(
            initialized,
            self._migration_contexts(initial_snapshot),
        )
        self.setup_classification = classification
        if classification is SetupClassification.FIRST_INSTALL:
            try:
                await self.store.async_first_initialize()
            except StoreWriteVerificationError as err:
                # PI7: flag stays false; no listeners, no grants, no ON.
                raise ConfigEntryNotReady(f"initial safety store write failed: {err}") from err
            self._mark_initialized()
        elif classification is SetupClassification.INTERRUPTED_INITIALIZATION:
            # PI2/PI6: the safe Store exists; complete the flag update only.
            self._mark_initialized()
        elif classification is SetupClassification.INTEGRITY_LOSS:
            await self._reconstruct_after_integrity_loss()

        # Step 3: run protocol (§23.3).
        try:
            self.previous_run = await self.store.async_begin_new_run(self.run_id)
        except StoreWriteVerificationError as err:
            # PI19: this process must never become watering-capable.
            await self._defensive_reconciliation()
            raise ConfigEntryNotReady(f"run-id persistence failed: {err}") from err

        # Durable actuator/sensor Registry identity is readable only after
        # the Store is loaded.  Re-observe the public mapping so a verified
        # same-UUID rename resolves before the first publication and cannot be
        # misclassified as a missing/conflicting identity (SPEC 25.1 steps
        # 5-6, 25.1.1).
        self.coordinator.observe_current()

        # The coordinator consumes every generation observed during the
        # awaited Store/run work.  It publishes only the latest stable union.
        try:
            await self.coordinator.async_start()
        except ReconciliationError as err:
            self._sync_repairs_from_authority()
            raise ConfigEntryNotReady(str(err)) from err

        self._sync_repairs_from_authority()

        self._install_periodic_triggers()
        await self.slots.async_enable_grants()

    def _register_update_listener(self) -> None:
        """Register exactly one supported public update listener."""
        if self._listener_registered:
            return

        def _entry_updated(_hass: HomeAssistant, _entry: ConfigEntry):
            self.coordinator.observe_current()
            return self._async_reconcile_and_sync_repairs()

        unsubscribe = self.entry.add_update_listener(_entry_updated)
        self.entry.async_on_unload(unsubscribe)
        self._listener_registered = True

    async def _async_reconcile_and_sync_repairs(self) -> None:
        """Join authoritative reconciliation and mirror incidents to Repairs."""
        was_failed = self._reconciliation_issue_active
        try:
            await self.coordinator.async_reconcile()
        finally:
            self._sync_repairs_from_authority()
        if was_failed and not self.coordinator.failed:
            _LOGGER.info(
                "Configuration reconciliation recovered for entry %s at generation %s",
                self.entry.entry_id,
                self.coordinator.applied_generation,
            )

    async def _async_reload_after_reconciliation(self) -> bool:
        """Apply platform reconstruction through HA's supported reload API."""
        try:
            return await self.hass.config_entries.async_reload(self.entry.entry_id)
        finally:
            # Reload success/failure is classified by the coordinator after
            # this callback returns. Mirror that final state next loop turn.
            asyncio.get_running_loop().call_soon(self._sync_repairs_from_authority)

    def _migration_contexts(
        self, snapshot: ImmutableEntrySnapshot
    ) -> dict[str, MigrationRecordContext]:
        contexts: dict[str, MigrationRecordContext] = {}
        for zone in snapshot.zones:
            contexts[zone.subentry_id] = MigrationRecordContext(
                active_subentry_id=zone.subentry_id,
                applied_config=zone.applied_shadow(
                    entry_snapshot_fingerprint=snapshot.entry_snapshot_fingerprint,
                    applied_generation=snapshot.observed_generation,
                ),
                actuator_identity=self._durable_actuator_identity(zone, current=False),
                sensor_identity=SensorIdentity(
                    zone.sensor_identity.registry_entry_id,
                    zone.sensor_identity.last_known_entity_id,
                ),
            )
        return contexts

    def _durable_identity_hints(self) -> dict[str, tuple[tuple[str, str | None], ...]]:
        """Persisted durable Registry UUIDs for each current subentry.

        A hint is offered only while the subentry still stores the exact
        configured reference that produced that record.  An unchanged
        reference whose durable UUID still resolves is the same entity under
        a rename (SPEC 23.2 item 1, 25.1.1); a user reconfiguration to a
        different entity changes the stored text and must therefore resolve
        independently as the 24.4 A -> B replacement it is.
        """
        hints: dict[str, tuple[tuple[str, str | None], ...]] = {}
        if not self.store.loaded:
            return hints
        for record in self.store.data.safety_records.values():
            subentry_id = record.active_subentry_id
            shadow = record.applied_config
            if subentry_id is None or shadow is None:
                continue
            history = self.store.data.zone_histories.get(record.zone_history_id)
            sensor_uuid = (
                history.zone_runtime.sensor_identity.registry_entry_id
                if history is not None
                else None
            )
            hints[subentry_id] = (
                (shadow.sensor_identity.last_known_entity_id, sensor_uuid),
                (
                    shadow.actuator_identity.last_known_entity_id,
                    record.actuator_identity.registry_entry_id,
                ),
            )
        return hints

    @staticmethod
    def _resolve_configured_entity(
        registry: er.EntityRegistry,
        configured_entity_id: str,
        hint: tuple[str, str | None] | None,
    ) -> tuple[str | None, str, bool]:
        """Return ``(registry_entry_id, current_entity_id, ambiguous)``.

        SPEC 25.1.1: a stored durable UUID still present in the Entity
        Registry *is* the entity, and a different current entity ID for that
        exact UUID is a rename.  SPEC 23.2 item 3 overrides that whenever the
        configured reference has meanwhile been taken by a *different*
        durable identity: two candidates then compete for one configured
        zone, which is ambiguity and must fail closed rather than silently
        pick either.  Textual resolution remains the fallback otherwise.
        """
        if hint is not None:
            hinted_reference, durable_uuid = hint
            if durable_uuid is not None and hinted_reference == configured_entity_id:
                renamed = registry.async_get(durable_uuid)
                if (
                    renamed is not None
                    and renamed.entity_id.split(".", 1)[0]
                    == (configured_entity_id.split(".", 1)[0])
                ):
                    # The durable identity is retained either way, so the
                    # record is never tombstoned by ambiguity and recovers as
                    # soon as the competing claim goes away.
                    competing = registry.async_get(configured_entity_id)
                    return (
                        renamed.id,
                        renamed.entity_id,
                        competing is not None and competing.id != durable_uuid,
                    )
        resolved = registry.async_get(configured_entity_id)
        if resolved is not None:
            return resolved.id, resolved.entity_id, False
        return None, configured_entity_id, False

    def _build_immutable_snapshot(self, generation: int) -> ImmutableEntrySnapshot:
        """Copy the current public subentry mapping into immutable values."""
        registry = er.async_get(self.hass)
        hints = self._durable_identity_hints()
        zones: list[ImmutableZoneSnapshot] = []
        for subentry_id, subentry in sorted(self.entry.subentries.items()):
            if subentry.subentry_type != "zone":
                continue
            config = zone_config_from_subentry(dict(subentry.data))
            zone_hints = hints.get(subentry_id)
            sensor_uuid, current_sensor, _sensor_ambiguous = self._resolve_configured_entity(
                registry,
                config.moisture_sensor,
                zone_hints[0] if zone_hints is not None else None,
            )
            actuator_uuid, current_actuator, actuator_ambiguous = self._resolve_configured_entity(
                registry,
                config.actuator,
                zone_hints[1] if zone_hints is not None else None,
            )
            conflict_detail = (
                f"configured actuator {config.actuator} for {subentry_id} now resolves to a "
                "different Entity Registry identity than the durable identity already held"
                if actuator_ambiguous
                else None
            )
            sensor_identity = AppliedEntityIdentity(
                sensor_uuid,
                config.moisture_sensor,
                config.moisture_sensor.split(".", 1)[0],
            )
            actuator_identity = AppliedEntityIdentity(
                actuator_uuid,
                config.actuator,
                config.actuator.split(".", 1)[0],
            )
            fingerprint = normalized_zone_fingerprint(
                subentry_id,
                config,
                sensor_identity,
                actuator_identity,
                str(self._local_tz),
            )
            zones.append(
                ImmutableZoneSnapshot(
                    subentry_id=subentry_id,
                    config=config,
                    sensor_identity=sensor_identity,
                    actuator_identity=actuator_identity,
                    config_fingerprint=fingerprint,
                    current_sensor_entity_id=current_sensor,
                    current_actuator_entity_id=current_actuator,
                    identity_conflict_detail=conflict_detail,
                )
            )
        return immutable_entry_snapshot(generation, zones)

    @staticmethod
    def _durable_actuator_identity(
        zone: ImmutableZoneSnapshot, *, current: bool = True
    ) -> ActuatorIdentity:
        # SPEC 23.2 item 1/PI24: last_known_entity_id is current addressing
        # metadata, updated only after verified same-UUID resolution.
        domain = zone.actuator_identity.domain
        return ActuatorIdentity(
            registry_entry_id=zone.actuator_identity.registry_entry_id,
            last_known_entity_id=(
                zone.current_actuator if current else zone.actuator_identity.last_known_entity_id
            ),
            domain=domain,
            identity_status=(
                IdentityStatus.REGISTRY_CONFIRMED
                if zone.actuator_identity.registry_entry_id is not None
                else IdentityStatus.REGISTRY_UNAVAILABLE
            ),
            off_service=("switch.turn_off" if domain == "switch" else "valve.close_valve"),
            confirm_timeout_s=zone.config.actuator_confirm_timeout_s,
        )

    @staticmethod
    def _same_actuator(record: SafetyRecord, zone: ImmutableZoneSnapshot) -> bool:
        stored = record.actuator_identity
        current_uuid = zone.actuator_identity.registry_entry_id
        if current_uuid is not None:
            return stored.registry_entry_id == current_uuid
        return (
            record.active_subentry_id == zone.subentry_id
            and stored.identity_status is IdentityStatus.REGISTRY_UNAVAILABLE
            and stored.last_known_entity_id == zone.current_actuator
        )

    async def _apply_configuration_snapshot(
        self,
        snapshot: ImmutableEntrySnapshot,
        is_current,
    ) -> None:
        """Consume one snapshot through the canonical schema-2 authorities."""
        zones = snapshot.by_subentry_id()
        prior_records = dict(self.store.data.safety_records) if self.store.loaded else {}

        # Removed and changed applied controllers quiesce before Store
        # ownership changes.  Supersession may conservatively end a session,
        # but cannot detach or publish the stale configuration.
        for subentry_id, binding in list(self.bindings.items()):
            current = zones.get(subentry_id)
            if current is not None and (
                current.config_fingerprint == binding.applied_shadow.config_fingerprint
            ):
                continue
            binding.quiescing = True
            binding.controller.begin_quiescing()
            await self.slots.async_cancel_request(subentry_id)
            controller = binding.controller
            if controller.state in (ControllerState.WATERING, ControllerState.SOAKING):
                was_watering = controller.state is ControllerState.WATERING
                await controller.async_dispatch(ConfigChangedPrepare())
                if was_watering:
                    await self._await_off_within_budget(controller)

        if not is_current():
            return

        await self._reconcile_displaced_persisted_sessions(snapshot)
        if not is_current():
            return

        conflicts: list[str] = []
        assessments = self._actuator_assessments(snapshot)

        def _mutate(data):
            return self._plan_reconciled_store(
                data,
                snapshot,
                assessments,
                conflicts,
            )

        await self.store.async_reconcile(_mutate)
        self._log_record_lifecycle_changes(prior_records)
        if not is_current():
            return

        # Restore every durable blocker before any controller/grant path.
        persisted_blockers = {
            (record.safety_record_id, reason)
            for record in self.store.data.safety_records.values()
            for reason in record.blocker_reasons
        }
        for record in self.store.data.safety_records.values():
            for reason in record.blocker_reasons:
                await self.slots.async_add_blocker(record.safety_record_id, reason)
        for safety_record_id, reason in self.slots.blockers() - persisted_blockers:
            await self.slots.async_remove_blocker(safety_record_id, reason)
        if not is_current():
            return
        if conflicts:
            raise ReconciliationError("; ".join(sorted(set(conflicts))))

        await self._synchronize_live_controllers(snapshot, is_current)
        if not is_current():
            return
        await self._synchronize_retained_controllers(snapshot, is_current)
        if not is_current():
            return

        # Final actuator re-read closes startup observation windows.  Exact
        # proven OFF removes only that record's startup/external keys.
        for subentry_id, binding in self.bindings.items():
            zone = zones[subentry_id]
            record = self.store.data.safety_records.get(binding.safety_record_id)
            history = (
                self.store.data.zone_histories.get(record.zone_history_id)
                if record is not None
                else None
            )
            # SPEC 11.4/21: external_flow describes a genuinely non-session
            # IDLE/DISABLED zone.  An actuator observed ON while this record
            # owns a session is integration-owned possible flow, whose key is
            # integration_off_unconfirmed and whose release belongs to the
            # session's own OFF path.  Labelling it external here would leave
            # a key that no OFF evidence for this record can clear.
            session_owned = history is not None and history.zone_runtime.session is not None
            final = ActuatorAdapter(self.hass, zone.current_actuator).current()
            if final.proven_off:
                await self.slots.async_remove_blocker(
                    binding.safety_record_id,
                    BlockerReason.ACTUATOR_NOT_PROVEN_OFF,
                )
                await self.slots.async_remove_blocker(
                    binding.safety_record_id,
                    BlockerReason.EXTERNAL_FLOW,
                )
            elif final.observed_on:
                if not session_owned:
                    await self.slots.async_add_blocker(
                        binding.safety_record_id,
                        BlockerReason.EXTERNAL_FLOW,
                    )
            else:
                await self.slots.async_add_blocker(
                    binding.safety_record_id,
                    BlockerReason.ACTUATOR_NOT_PROVEN_OFF,
                )

    def _log_record_lifecycle_changes(self, prior_records: dict[str, SafetyRecord]) -> None:
        """Log canonical tombstone/reactivation transitions at useful levels."""
        for record_id, current in self.store.data.safety_records.items():
            prior = prior_records.get(record_id)
            if prior is None or prior.runtime_lifecycle is current.runtime_lifecycle:
                continue
            if current.runtime_lifecycle is RuntimeLifecycle.ACTIVE:
                _LOGGER.info(
                    "Safety record %s reactivated for subentry %s",
                    record_id,
                    current.active_subentry_id,
                )
            elif prior.runtime_lifecycle is RuntimeLifecycle.ACTIVE:
                _LOGGER.warning(
                    "Safety record %s retained as %s after configuration removal/change",
                    record_id,
                    current.runtime_lifecycle.value,
                )
            elif current.runtime_lifecycle is RuntimeLifecycle.RETIRED:
                _LOGGER.info(
                    "Safety record %s retired after exact OFF/accounting closure",
                    record_id,
                )

    def _actuator_assessments(self, snapshot: ImmutableEntrySnapshot) -> dict[str, object]:
        """Resolve current and retained actuators by Registry UUID first."""
        registry = er.async_get(self.hass)
        assessments: dict[str, object] = {}
        for zone in snapshot.zones:
            assessments[f"zone:{zone.subentry_id}"] = ActuatorAdapter(
                self.hass, zone.current_actuator
            ).current()
        if not self.store.loaded:
            return assessments
        for record in self.store.data.safety_records.values():
            identity = record.actuator_identity
            entity_id: str | None = None
            if identity.registry_entry_id is not None:
                registry_entry = registry.async_get(identity.registry_entry_id)
                if registry_entry is not None:
                    entity_id = registry_entry.entity_id
            elif (
                identity.identity_status is IdentityStatus.REGISTRY_UNAVAILABLE
                and record.runtime_lifecycle is RuntimeLifecycle.ACTIVE
            ):
                entity_id = identity.last_known_entity_id
            if entity_id is not None:
                assessments[f"record:{record.safety_record_id}"] = ActuatorAdapter(
                    self.hass, entity_id
                ).current()
        return assessments

    async def _reconcile_displaced_persisted_sessions(
        self, snapshot: ImmutableEntrySnapshot
    ) -> None:
        """Close startup sessions whose actuator is no longer current.

        An interrupted offline A -> B change can leave A's session in the
        continuing zone history before any live binding exists.  Reconcile
        that session against A's exact retained actuator before B is allowed
        to adopt the history.  The controller remains retained when OFF or
        accounting evidence is still open.
        """
        zones = snapshot.by_subentry_id()
        for history in list(self.store.data.zone_histories.values()):
            persisted = history.zone_runtime.session
            if persisted is None:
                continue
            record = self.store.data.safety_records.get(persisted.owner_safety_record_id)
            if record is None or record.applied_config is None:
                continue
            if (
                persisted.context.pending_termination_reason is None
                and history.zone_runtime.state is ControllerState.FAULT
                and record.actuator_fault is FaultCode.ACTUATOR_OFF_TIMEOUT
            ):
                # ``pending_termination_reason`` is deliberately live-only in
                # schema 2. T15 makes ACTUATOR_FAULT authoritative whenever
                # OFF exhaustion supersedes the original request, so restore
                # that deterministic reason before a post-restart OFF can
                # close the retained accounting record.
                restored = PersistedSession(
                    persisted.owner_safety_record_id,
                    persisted.context.evolve(
                        pending_termination_reason=CompletionReason.ACTUATOR_FAULT
                    ),
                )

                def _restore_terminal_reason(
                    data,
                    history_id=history.zone_history_id,
                    restored_session=restored,
                ):
                    histories = dict(data.zone_histories)
                    current = histories[history_id]
                    histories[history_id] = current.evolve(
                        zone_runtime=replace(current.zone_runtime, session=restored_session)
                    )
                    return dict(data.safety_records), histories

                await self.store.async_reconcile(_restore_terminal_reason)
                history = self.store.data.zone_histories[history.zone_history_id]
                persisted = history.zone_runtime.session
                assert persisted is not None
            current = (
                zones.get(record.active_subentry_id)
                if record.active_subentry_id is not None
                else None
            )
            if current is not None and self._same_actuator(record, current):
                continue
            # A live binding already owns this exact session and its event
            # subscriptions. The normal synchronization path below transfers
            # that controller to retained ownership. Materializing a second
            # observer here would duplicate delayed OFF/fault/finish events.
            if any(
                binding.safety_record_id == record.safety_record_id
                for binding in self.bindings.values()
            ):
                continue
            if record.safety_record_id in self.retained_controllers:
                continue
            identity = record.actuator_identity
            if identity.identity_status not in (
                IdentityStatus.REGISTRY_CONFIRMED,
                IdentityStatus.REGISTRY_UNAVAILABLE,
            ):
                continue
            config = self._config_from_record(record)
            controller = ZoneController(
                self.hass,
                record.zone_id,
                config,
                self.store,
                self.slots,
                run_id=self.run_id,
                local_tz=self._local_tz,
                emit=self._make_emitter(record.zone_id, record.safety_record_id),
                safety_record_id=record.safety_record_id,
                authorization=self,
                on_entity_renamed=self._make_rename_handler(record.zone_id),
            )
            history = self.store.data.zone_histories[record.zone_history_id]
            assessment = ActuatorAdapter(self.hass, config.actuator).current()
            if history.zone_runtime.state is ControllerState.SOAKING:
                controller.async_attach()
                await controller.async_dispatch(StartupPersistedSoaking(trusted=False))
            else:
                await self._reconcile_zone(controller, record, assessment)
            self.retained_controllers[record.safety_record_id] = controller

    def _plan_reconciled_store(
        self,
        data,
        snapshot: ImmutableEntrySnapshot,
        assessments: dict[str, object],
        conflicts: list[str],
    ) -> tuple[dict[str, SafetyRecord], dict[str, ZoneHistory]]:
        """Build the complete canonical config+Store union transaction."""
        records = dict(data.safety_records)
        histories = dict(data.zone_histories)
        zones = snapshot.by_subentry_id()
        original_active = {
            record.active_subentry_id: record
            for record in data.safety_records.values()
            if record.active_subentry_id is not None
        }

        # Duplicate current durable identities are configuration conflicts.
        seen_current: dict[tuple[str, str], str] = {}
        for zone in snapshot.zones:
            identity_key = (
                (
                    "uuid",
                    zone.actuator_identity.registry_entry_id,
                )
                if zone.actuator_identity.registry_entry_id
                else (
                    "text",
                    zone.current_actuator,
                )
            )
            other = seen_current.get(identity_key)
            if other is not None:
                conflicts.append(
                    f"actuator identity is selected by both {other} and {zone.subentry_id}"
                )
            seen_current[identity_key] = zone.subentry_id

        # First materialize every config-absent or A -> B old owner as a
        # durable tombstone.  The old applied shadow remains closure authority.
        for record_id, old_record in list(records.items()):
            subentry_id = old_record.active_subentry_id
            if subentry_id is None:
                record = old_record
            else:
                zone = zones.get(subentry_id)
                if zone is not None and self._same_actuator(old_record, zone):
                    continue
                previous = old_record.previous_subentry_ids
                if subentry_id not in previous:
                    previous = (*previous, subentry_id)
                record = old_record.evolve(
                    active_subentry_id=None,
                    previous_subentry_ids=previous,
                    runtime_lifecycle=RuntimeLifecycle.DELETE_PENDING,
                )
                if zone is None:
                    history = histories[record.zone_history_id]
                    prior_history = history.previous_subentry_ids
                    if subentry_id not in prior_history:
                        prior_history = (*prior_history, subentry_id)
                    histories[history.zone_history_id] = history.evolve(
                        active_subentry_id=None,
                        previous_subentry_ids=prior_history,
                    )
            records[record_id] = self._reconcile_retained_record(
                record,
                histories[record.zone_history_id],
                assessments.get(f"record:{record_id}"),
            )

        for zone in snapshot.zones:
            prior = original_active.get(zone.subentry_id)
            created_new = False
            current_uuid = zone.actuator_identity.registry_entry_id
            current_entity = zone.current_actuator

            if zone.identity_conflict_detail is not None:
                # SPEC 23.2 item 3/25.5 item 8: competing durable identities
                # for one configured reference are ambiguous.  Keep every
                # record and its evidence, close admission, and Repair.
                conflicts.append(zone.identity_conflict_detail)
                for candidate in [
                    record
                    for record in records.values()
                    if record.actuator_identity.registry_entry_id == current_uuid
                    or record.active_subentry_id == zone.subentry_id
                    or record.zone_id == zone.subentry_id
                ]:
                    records[candidate.safety_record_id] = candidate.evolve(
                        identity_incident=IdentityIncident(
                            IdentityIncidentKind.IDENTITY_CONFLICT,
                            zone.identity_conflict_detail,
                        ),
                        blocker_reasons=self._with_blocker(
                            candidate.blocker_reasons,
                            BlockerReason.ACTUATOR_NOT_PROVEN_OFF,
                        ),
                    )
                continue

            exact = [
                record
                for record in records.values()
                if current_uuid is not None
                and record.actuator_identity.registry_entry_id == current_uuid
            ]
            textual_conflicts = [
                record
                for record in records.values()
                if record.actuator_identity.last_known_entity_id == current_entity
                and record.actuator_identity.registry_entry_id not in (None, current_uuid)
            ]
            mapped_candidates = [
                record
                for record in records.values()
                if record.zone_id == zone.subentry_id
                and record.active_subentry_id is None
                and record.actuator_identity.identity_status is IdentityStatus.MISSING
            ]
            if len(exact) > 1 or textual_conflicts:
                candidates = [record.safety_record_id for record in (*exact, *textual_conflicts)]
                detail = f"identity conflict for {zone.subentry_id}: records {sorted(candidates)}"
                conflicts.append(detail)
                for candidate in (*exact, *textual_conflicts):
                    records[candidate.safety_record_id] = candidate.evolve(
                        identity_incident=IdentityIncident(
                            IdentityIncidentKind.IDENTITY_CONFLICT,
                            detail,
                        ),
                        blocker_reasons=self._with_blocker(
                            candidate.blocker_reasons,
                            BlockerReason.ACTUATOR_NOT_PROVEN_OFF,
                        ),
                    )
                continue

            if prior is not None and self._same_actuator(prior, zone):
                selected = records[prior.safety_record_id]
            elif len(exact) == 1:
                selected = exact[0]
            elif (
                len(mapped_candidates) == 1
                and not textual_conflicts
                and (current_uuid is not None or self.hass.states.get(current_entity) is not None)
            ):
                # Integrity reconstruction/schema migration retained this
                # exact current subentry's canonical record but could not
                # invent identity.  Current public ownership plus a unique,
                # conflict-free configured actuator materializes that same
                # record and preserves its exhausted budget/fault evidence.
                selected = mapped_candidates[0]
            elif current_uuid is None and prior is not None and self._same_actuator(prior, zone):
                selected = records[prior.safety_record_id]
            else:
                unregistered_conflicts = [
                    record
                    for record in records.values()
                    if current_uuid is None
                    and record.active_subentry_id != zone.subentry_id
                    and record.actuator_identity.last_known_entity_id == current_entity
                ]
                if unregistered_conflicts or self.hass.states.get(current_entity) is None:
                    detail = f"durable actuator identity missing/ambiguous for {zone.subentry_id}"
                    conflicts.append(detail)
                    for candidate in unregistered_conflicts:
                        records[candidate.safety_record_id] = candidate.evolve(
                            identity_incident=IdentityIncident(
                                IdentityIncidentKind.IDENTITY_MISSING,
                                detail,
                            ),
                            blocker_reasons=self._with_blocker(
                                candidate.blocker_reasons,
                                BlockerReason.ACTUATOR_NOT_PROVEN_OFF,
                            ),
                        )
                    continue
                selected = self._new_safety_record(zone, snapshot)
                created_new = True
                records[selected.safety_record_id] = selected
                histories[selected.zone_history_id] = self._new_zone_history(
                    selected,
                    zone,
                )

            continuing_history_id = (
                prior.zone_history_id if prior is not None else selected.zone_history_id
            )
            if selected.zone_history_id != continuing_history_id:
                retained_history_id = selected.zone_history_id
                continuing = histories[continuing_history_id]
                retained = histories[retained_history_id]
                if retained.zone_runtime.session is not None:
                    conflicts.append(
                        f"retained record {selected.safety_record_id} has unresolved session"
                    )
                    continue
                histories[continuing_history_id] = merge_zone_history_continuity(
                    continuing,
                    retained,
                )
                if not any(
                    record.safety_record_id != selected.safety_record_id
                    and record.zone_history_id == retained_history_id
                    for record in records.values()
                ):
                    del histories[retained_history_id]
                historical_ids = selected.historical_zone_history_ids
                if retained_history_id not in historical_ids:
                    historical_ids = (*historical_ids, retained_history_id)
                selected = selected.evolve(
                    zone_history_id=continuing_history_id,
                    historical_zone_history_ids=historical_ids,
                )

            history = histories[continuing_history_id]
            continuing_same_actuator = (
                prior is not None
                and selected.safety_record_id == prior.safety_record_id
                and self._same_actuator(prior, zone)
            ) or (
                # A delete/re-add has no current subentry-owned ``prior``.
                # Exact Registry UUID reactivation still owns the same open
                # actuator accounting.  Do not extend this to A -> retained B:
                # that path has a different current ``prior`` and must close
                # B's historical operational session before handoff.
                prior is None
                and len(exact) == 1
                and selected.safety_record_id == exact[0].safety_record_id
                and self._same_actuator(selected, zone)
            )
            if history.zone_runtime.session is not None and not continuing_same_actuator:
                conflicts.append(f"zone history {continuing_history_id} has unresolved session")
                continue
            history_previous = tuple(
                item for item in history.previous_subentry_ids if item != zone.subentry_id
            )
            if (
                history.active_subentry_id not in (None, zone.subentry_id)
                and history.active_subentry_id not in history_previous
            ):
                history_previous = (*history_previous, history.active_subentry_id)
            runtime_state = history.zone_runtime.state
            persisted_session = history.zone_runtime.session
            configuration_changed = (
                selected.applied_config is None
                or selected.applied_config.config_fingerprint != zone.config_fingerprint
                or selected.active_subentry_id != zone.subentry_id
            )
            reevaluate_operational_state = (
                not continuing_same_actuator or configuration_changed
            ) and not (created_new and prior is None)
            zone_fault = history.zone_runtime.zone_fault
            secondary_zone_fault = history.zone_runtime.secondary_fault
            if reevaluate_operational_state:
                zone_fault = self._current_zone_fault(zone)
                secondary_zone_fault = None
                runtime_state = (
                    ControllerState.DISABLED
                    if not history.zone_runtime.enabled
                    else (
                        ControllerState.FAULT
                        if selected.actuator_fault is not None or zone_fault is not None
                        else ControllerState.IDLE
                    )
                )
            zone_runtime = replace(
                history.zone_runtime,
                state=runtime_state,
                sensor_identity=SensorIdentity(
                    zone.sensor_identity.registry_entry_id,
                    zone.current_sensor,
                ),
                zone_fault=zone_fault,
                secondary_fault=secondary_zone_fault,
                session=persisted_session if continuing_same_actuator else None,
            )
            histories[continuing_history_id] = history.evolve(
                active_subentry_id=zone.subentry_id,
                previous_subentry_ids=history_previous,
                zone_runtime=zone_runtime,
            )

            previous = tuple(
                item for item in selected.previous_subentry_ids if item != zone.subentry_id
            )
            if (
                selected.active_subentry_id not in (None, zone.subentry_id)
                and selected.active_subentry_id not in previous
            ):
                previous = (*previous, selected.active_subentry_id)
            selected = selected.evolve(
                zone_id=zone.subentry_id,
                active_subentry_id=zone.subentry_id,
                previous_subentry_ids=previous,
                zone_history_id=continuing_history_id,
                runtime_lifecycle=RuntimeLifecycle.ACTIVE,
                applied_config=zone.applied_shadow(
                    entry_snapshot_fingerprint=snapshot.entry_snapshot_fingerprint,
                    applied_generation=snapshot.observed_generation,
                ),
                actuator_identity=self._durable_actuator_identity(zone),
                identity_incident=None,
            )
            selected = self._reconcile_active_record(
                selected,
                histories[continuing_history_id],
                assessments.get(f"zone:{zone.subentry_id}"),
            )
            records[selected.safety_record_id] = selected

        return records, histories

    def _current_zone_fault(self, zone: ImmutableZoneSnapshot):
        state = self.hass.states.get(zone.current_sensor)
        observation = classify_moisture(
            state,
            state.last_reported if state is not None else None,
            dt_util.utcnow(),
            zone.config.sensor_max_age_s,
        )
        return {
            MoistureClassification.UNAVAILABLE: FaultCode.SENSOR_UNAVAILABLE,
            MoistureClassification.INVALID: FaultCode.SENSOR_INVALID,
            MoistureClassification.STALE: FaultCode.SENSOR_STALE,
        }.get(observation.classification)

    @staticmethod
    def _with_blocker(
        blockers: tuple[BlockerReason, ...], reason: BlockerReason
    ) -> tuple[BlockerReason, ...]:
        return tuple(sorted({*blockers, reason}, key=lambda item: item.value))

    @staticmethod
    def _without_blockers(
        blockers: tuple[BlockerReason, ...], *reasons: BlockerReason
    ) -> tuple[BlockerReason, ...]:
        return tuple(item for item in blockers if item not in reasons)

    def _reconcile_active_record(
        self, record: SafetyRecord, history: ZoneHistory, assessment
    ) -> SafetyRecord:
        blockers = record.blocker_reasons
        owner = record.possible_flow_owner
        session = history.zone_runtime.session
        if assessment is None:
            blockers = self._with_blocker(blockers, BlockerReason.ACTUATOR_NOT_PROVEN_OFF)
        elif assessment.proven_off:
            blockers = self._without_blockers(
                blockers,
                BlockerReason.ACTUATOR_NOT_PROVEN_OFF,
                BlockerReason.EXTERNAL_FLOW,
            )
            if session is None and BlockerReason.INTEGRATION_OFF_UNCONFIRMED not in blockers:
                owner = None
        elif assessment.observed_on and session is None:
            blockers = self._with_blocker(blockers, BlockerReason.EXTERNAL_FLOW)
            owner = PossibleFlowOwner.EXTERNAL
        else:
            blockers = self._with_blocker(blockers, BlockerReason.ACTUATOR_NOT_PROVEN_OFF)
        return record.evolve(blocker_reasons=blockers, possible_flow_owner=owner)

    def _reconcile_retained_record(
        self, record: SafetyRecord, history: ZoneHistory, assessment
    ) -> SafetyRecord:
        record = self._retained_identity_after_rename(record)
        record = self._reconcile_active_record(record, history, assessment)
        resolved = assessment is not None
        identity = record.actuator_identity
        if not resolved:
            detail = f"retained actuator identity unresolved for {record.safety_record_id}"
            identity = replace(identity, identity_status=IdentityStatus.MISSING)
            record = record.evolve(
                actuator_identity=identity,
                identity_incident=IdentityIncident(
                    IdentityIncidentKind.IDENTITY_MISSING,
                    detail,
                ),
            )
        session = history.zone_runtime.session
        safe_to_retire = (
            assessment is not None
            and assessment.proven_off
            and not record.blocker_reasons
            and record.possible_flow_owner is None
            and session is None
        )
        return record.evolve(
            runtime_lifecycle=(
                RuntimeLifecycle.RETIRED if safe_to_retire else RuntimeLifecycle.DELETE_PENDING
            )
        )

    def _retained_identity_after_rename(self, record: SafetyRecord) -> SafetyRecord:
        """Update a tombstone's last-known entity ID after a verified rename.

        SPEC 25.1.1: a stored ``registry_entry_id`` that still resolves *is*
        that actuator, and a different current entity ID for the exact same
        UUID is a rename.  Only addressing metadata changes; the lineage,
        blockers, accounting and faults stay on the same record (PI24, TB8).
        """
        identity = record.actuator_identity
        if identity.registry_entry_id is None or identity.domain is None:
            return record
        registry_entry = er.async_get(self.hass).async_get(identity.registry_entry_id)
        if (
            registry_entry is None
            or registry_entry.entity_id == identity.last_known_entity_id
            or registry_entry.entity_id.split(".", 1)[0] != identity.domain
        ):
            return record
        _LOGGER.info(
            "Retained safety record %s follows actuator rename %s -> %s (same Registry identity)",
            record.safety_record_id,
            identity.last_known_entity_id,
            registry_entry.entity_id,
        )
        return record.evolve(
            actuator_identity=replace(identity, last_known_entity_id=registry_entry.entity_id)
        )

    def _new_safety_record(
        self,
        zone: ImmutableZoneSnapshot,
        snapshot: ImmutableEntrySnapshot,
    ) -> SafetyRecord:
        record_id = str(uuid.uuid4())
        return SafetyRecord(
            safety_record_id=record_id,
            zone_id=zone.subentry_id,
            active_subentry_id=zone.subentry_id,
            previous_subentry_ids=(),
            safety_lineage_id=str(uuid.uuid4()),
            zone_history_id=str(uuid.uuid4()),
            historical_zone_history_ids=(),
            runtime_lifecycle=RuntimeLifecycle.ACTIVE,
            applied_config=zone.applied_shadow(
                entry_snapshot_fingerprint=snapshot.entry_snapshot_fingerprint,
                applied_generation=snapshot.observed_generation,
            ),
            actuator_identity=self._durable_actuator_identity(zone),
            blocker_reasons=(),
            possible_flow_owner=None,
            identity_incident=None,
            actuator_fault=None,
            acknowledgement_required=False,
        )

    def _new_zone_history(self, record: SafetyRecord, zone: ImmutableZoneSnapshot) -> ZoneHistory:
        """Mint the first ``zone_runtime`` for a genuinely new logical zone.

        §24.4/LC14: a newly configured zone begins ``enabled=false`` in state
        DISABLED.  This is the single authoritative fresh-zone default and it
        is persisted and read-back verified before any controller for the zone
        is constructed, published, or admitted, so no creation-time interval
        exists in which the zone is watering-eligible.  Only an explicit user
        enable through the supported control path may lift it.  Existing zones
        never reach this method: every adoption path (same-subentry continuity,
        exact durable-identity re-add, schema migration, A -> B replacement)
        preserves its persisted ``zone_runtime.enabled`` (§25.5, I20).
        """
        from .models import ZoneRuntime

        return ZoneHistory(
            zone_history_id=record.zone_history_id,
            active_subentry_id=zone.subentry_id,
            previous_subentry_ids=(),
            last_session_end_utc=None,
            last_auto_session_start_utc=None,
            zone_runtime=ZoneRuntime(
                enabled=False,
                state=ControllerState.DISABLED,
                zone_fault=None,
                secondary_fault=None,
                sensor_identity=SensorIdentity(
                    zone.sensor_identity.registry_entry_id,
                    zone.current_sensor,
                ),
                last_session_summary=None,
                session=None,
            ),
            daily=ZoneDailyRuntime(
                date_local=dt_util.utcnow().astimezone(self._local_tz).date(),
                runtime_s=0.0,
            ),
        )

    async def _synchronize_live_controllers(
        self,
        snapshot: ImmutableEntrySnapshot,
        is_current,
    ) -> None:
        zones = snapshot.by_subentry_id()

        for subentry_id, binding in list(self.bindings.items()):
            desired = zones.get(subentry_id)
            record = self.store.data.safety_records.get(binding.safety_record_id)
            keep = (
                desired is not None
                and record is not None
                and record.runtime_lifecycle is RuntimeLifecycle.ACTIVE
                and record.active_subentry_id == subentry_id
                and record.applied_config is not None
                and record.applied_config.config_fingerprint == desired.config_fingerprint
            )
            if keep:
                binding.lifecycle = RuntimeLifecycle.ACTIVE
                binding.applied_shadow = record.applied_config
                binding.zone_history_id = record.zone_history_id
                binding.quiescing = False
                binding.controller.update_runtime_ownership(
                    zone_history_id=record.zone_history_id,
                    lifecycle=record.runtime_lifecycle,
                    applied_config=record.applied_config,
                )
                continue
            if not is_current():
                return
            self.controllers.pop(subentry_id, None)
            self.bindings.pop(subentry_id, None)
            if record is not None and record.runtime_lifecycle is RuntimeLifecycle.DELETE_PENDING:
                binding.controller.update_runtime_ownership(
                    zone_history_id=record.zone_history_id,
                    lifecycle=record.runtime_lifecycle,
                    applied_config=record.applied_config,
                )
                self.retained_controllers[record.safety_record_id] = binding.controller
            else:
                await binding.controller.async_detach()

        for zone in snapshot.zones:
            matches = [
                record
                for record in self.store.data.safety_records.values()
                if record.active_subentry_id == zone.subentry_id
                and record.runtime_lifecycle is RuntimeLifecycle.ACTIVE
            ]
            if len(matches) != 1:
                raise ReconciliationError(
                    f"configured zone {zone.subentry_id} has {len(matches)} canonical records"
                )
            record = matches[0]
            existing = self.bindings.get(zone.subentry_id)
            if existing is not None:
                continue
            retained = self.retained_controllers.pop(record.safety_record_id, None)
            if retained is not None:
                await retained.async_detach()
            if not is_current():
                return
            controller = self._create_controller(zone, record)
            history = self.store.data.zone_histories[record.zone_history_id]
            assessment = ActuatorAdapter(self.hass, zone.current_actuator).current()
            watering_recovery = (
                history.zone_runtime.state is ControllerState.WATERING
                and history.zone_runtime.session is not None
            )
            await self._reconcile_zone(controller, record, assessment)
            if assessment.observed_on and not watering_recovery:
                await controller.async_dispatch(ExternalActuatorOn())
            binding = RuntimeControllerBinding(
                subentry_id=zone.subentry_id,
                safety_record_id=record.safety_record_id,
                zone_history_id=record.zone_history_id,
                lifecycle=record.runtime_lifecycle,
                applied_shadow=record.applied_config,
                controller=controller,
            )
            self.bindings[zone.subentry_id] = binding
            self.controllers[zone.subentry_id] = controller

    async def _synchronize_retained_controllers(
        self,
        snapshot: ImmutableEntrySnapshot,
        is_current,
    ) -> None:
        current_record_ids = {binding.safety_record_id for binding in self.bindings.values()}
        for record_id, controller in list(self.retained_controllers.items()):
            record = self.store.data.safety_records.get(record_id)
            if record is None or record_id in current_record_ids:
                await controller.async_detach()
                self.retained_controllers.pop(record_id, None)
                continue
            controller.update_runtime_ownership(
                zone_history_id=record.zone_history_id,
                lifecycle=record.runtime_lifecycle,
                applied_config=record.applied_config,
            )

        for record in self.store.data.safety_records.values():
            if record.safety_record_id in current_record_ids:
                continue
            history = self.store.data.zone_histories[record.zone_history_id]
            needs_observation = (
                record.runtime_lifecycle is RuntimeLifecycle.DELETE_PENDING
                or bool(record.blocker_reasons)
                or record.possible_flow_owner is not None
                or history.zone_runtime.session is not None
            )
            if not needs_observation or record.applied_config is None:
                continue
            if record.safety_record_id in self.retained_controllers:
                continue
            identity = record.actuator_identity
            if identity.identity_status not in (
                IdentityStatus.REGISTRY_CONFIRMED,
                IdentityStatus.REGISTRY_UNAVAILABLE,
            ):
                continue
            if not is_current():
                return
            config = self._config_from_record(record)
            controller = ZoneController(
                self.hass,
                record.zone_id,
                config,
                self.store,
                self.slots,
                run_id=self.run_id,
                local_tz=self._local_tz,
                emit=self._make_emitter(record.zone_id, record.safety_record_id),
                safety_record_id=record.safety_record_id,
                authorization=self,
                on_entity_renamed=self._make_rename_handler(record.zone_id),
            )
            history = self.store.data.zone_histories[record.zone_history_id]
            assessment = ActuatorAdapter(self.hass, config.actuator).current()
            if (
                history.zone_runtime.state is ControllerState.SOAKING
                and history.zone_runtime.session is not None
            ):
                controller.async_attach()
                await controller.async_dispatch(StartupPersistedSoaking(trusted=False))
            else:
                await self._reconcile_zone(controller, record, assessment)
            self.retained_controllers[record.safety_record_id] = controller

        await self._refresh_tombstone_lifecycles()

    async def _refresh_tombstone_lifecycles(self) -> None:
        registry = er.async_get(self.hass)
        assessment_by_record: dict[str, object] = {}
        for record in self.store.data.safety_records.values():
            if record.runtime_lifecycle is RuntimeLifecycle.ACTIVE:
                continue
            identity = record.actuator_identity
            registry_entry = (
                registry.async_get(identity.registry_entry_id)
                if identity.registry_entry_id is not None
                else None
            )
            entity_id = registry_entry.entity_id if registry_entry is not None else None
            if entity_id is not None:
                assessment_by_record[record.safety_record_id] = ActuatorAdapter(
                    self.hass, entity_id
                ).current()

        def _mutate(data):
            records = dict(data.safety_records)
            histories = dict(data.zone_histories)
            for record_id, record in records.items():
                if record.runtime_lifecycle is RuntimeLifecycle.ACTIVE:
                    continue
                records[record_id] = self._reconcile_retained_record(
                    record,
                    histories[record.zone_history_id],
                    assessment_by_record.get(record_id),
                )
            return records, histories

        await self.store.async_reconcile(_mutate)
        for record_id, controller in list(self.retained_controllers.items()):
            record = self.store.data.safety_records[record_id]
            controller.update_runtime_ownership(
                zone_history_id=record.zone_history_id,
                lifecycle=record.runtime_lifecycle,
                applied_config=record.applied_config,
            )
            if (
                record.runtime_lifecycle is RuntimeLifecycle.RETIRED
                and not record.blocker_reasons
                and record.possible_flow_owner is None
            ):
                await controller.async_detach()
                self.retained_controllers.pop(record_id, None)

    def _config_from_record(self, record: SafetyRecord) -> ZoneConfig:
        """Retained-record configuration bound to current addressing.

        The applied shadow keeps the configured subentry reference, while
        ``actuator_identity``/``sensor_identity`` hold the entity IDs the same
        durable Registry identities are addressable at now (SPEC 23.2 item 1).
        A retained tombstone must command and observe the current entity.
        """
        assert record.applied_config is not None
        history = self.store.data.zone_histories.get(record.zone_history_id)
        sensor_entity_id = (
            history.zone_runtime.sensor_identity.last_known_entity_id
            if history is not None and history.zone_runtime.sensor_identity.last_known_entity_id
            else record.applied_config.sensor_identity.last_known_entity_id
        )
        return replace(
            self._config_from_shadow(record.applied_config),
            moisture_sensor=sensor_entity_id,
            actuator=(
                record.actuator_identity.last_known_entity_id
                or record.applied_config.actuator_identity.last_known_entity_id
            ),
        )

    @staticmethod
    def _config_from_shadow(shadow: AppliedConfigurationShadow) -> ZoneConfig:
        settings = shadow.normalized_settings
        return ZoneConfig(
            name=settings.name,
            moisture_sensor=shadow.sensor_identity.last_known_entity_id,
            actuator=shadow.actuator_identity.last_known_entity_id,
            start_threshold=settings.start_threshold,
            target_threshold=settings.target_threshold,
            pulse_duration_s=settings.pulse_duration_s,
            soak_duration_s=settings.soak_duration_s,
            max_cycles=settings.max_cycles,
            max_session_runtime_s=settings.max_session_runtime_s,
            max_daily_runtime_s=settings.max_daily_runtime_s,
            min_session_interval_s=settings.min_session_interval_s,
            sensor_max_age_s=settings.sensor_max_age_s,
            actuator_confirm_timeout_s=settings.actuator_confirm_timeout_s,
            manual_max_duration_s=settings.manual_max_duration_s,
        )

    async def _persist_slot_blocker(
        self,
        safety_record_id: str,
        reason: BlockerReason,
        active: bool,
    ) -> None:
        """Persist one exact canonical blocker; missing ownership is fatal."""
        if not self.store.loaded or safety_record_id not in self.store.data.safety_records:
            raise StoreWriteVerificationError(
                f"blocker has no canonical safety record: {safety_record_id}"
            )
        await self.store.async_set_record_blocker(safety_record_id, reason, active=active)

    def _mark_initialized(self) -> None:
        """§23.5 step 5: flag update only after verified Store state."""
        self.hass.config_entries.async_update_entry(
            self.entry,
            data={**self.entry.data, CONF_RUNTIME_STORE_INITIALIZED: True},
        )

    async def _reconstruct_after_integrity_loss(self) -> None:
        """§23.5 integrity-loss rows: reconstruct, exhaust today, Repair."""
        zone_configs = self._parse_zone_configs()
        detection_date = dt_util.utcnow().astimezone(self._local_tz).date()
        budgets = {zone_id: cfg.max_daily_runtime_s for zone_id, cfg in zone_configs.items()}
        try:
            await self.store.async_reconstruct_after_integrity_loss(budgets, detection_date)
        except StoreWriteVerificationError as err:
            raise ConfigEntryNotReady(f"integrity reconstruction write failed: {err}") from err
        from . import repairs

        repairs.async_create_integrity_issue(self.hass, self.entry.entry_id)
        _LOGGER.error(
            "Runtime safety store integrity lost (%s); watering blocked until "
            "acknowledgement and actuators are reconciled",
            self.entry.entry_id,
        )

    async def _defensive_reconciliation(self) -> None:
        """§24.4: minimal defensive OFF for persisted hazardous state."""
        if not self.store.loaded:
            return
        registry = er.async_get(self.hass)
        for record in self.store.data.safety_records.values():
            history = self.store.data.zone_histories[record.zone_history_id]
            if history.zone_runtime.state is not ControllerState.WATERING:
                continue
            identity = record.actuator_identity
            entity_id = None
            if identity.registry_entry_id is not None:
                registry_entry = registry.async_get(identity.registry_entry_id)
                if registry_entry is not None:
                    entity_id = registry_entry.entity_id
            elif (
                identity.identity_status is IdentityStatus.REGISTRY_UNAVAILABLE
                and record.runtime_lifecycle is RuntimeLifecycle.ACTIVE
            ):
                entity_id = identity.last_known_entity_id
            if entity_id is None:
                continue
            adapter = ActuatorAdapter(self.hass, entity_id)
            if not adapter.current().proven_off:
                try:
                    from homeassistant.core import Context

                    await adapter.async_turn_off(Context())
                except Exception as err:
                    _LOGGER.error("Defensive OFF for %s failed: %s", record.safety_record_id, err)

    def _parse_zone_configs(self) -> dict[str, ZoneConfig]:
        configs: dict[str, ZoneConfig] = {}
        for subentry_id, subentry in self.entry.subentries.items():
            if subentry.subentry_type != "zone":
                continue
            configs[subentry_id] = zone_config_from_subentry(dict(subentry.data))
        return configs

    def _create_controller(
        self,
        zone: ImmutableZoneSnapshot,
        record: SafetyRecord,
    ) -> ZoneController:
        """Construct only after canonical record/history verification."""
        if (
            record.runtime_lifecycle is not RuntimeLifecycle.ACTIVE
            or record.active_subentry_id != zone.subentry_id
            or record.applied_config is None
            or record.zone_history_id not in self.store.data.zone_histories
        ):
            raise ReconciliationError(
                f"zone {zone.subentry_id} lacks verified ACTIVE canonical ownership"
            )
        return ZoneController(
            self.hass,
            zone.subentry_id,
            zone.current_config(),
            self.store,
            self.slots,
            run_id=self.run_id,
            local_tz=self._local_tz,
            emit=self._make_emitter(zone.subentry_id, record.safety_record_id),
            safety_record_id=record.safety_record_id,
            authorization=self,
            on_entity_renamed=self._make_rename_handler(zone.subentry_id),
        )

    def _make_rename_handler(self, zone_id: str):
        """Reconcile durable metadata after a controller followed a rename.

        The controller has already re-pointed its adapters/listeners under the
        verified same-UUID rule without an observation gap.  Admission closes
        synchronously here, then one ordinary reconciliation pass republishes
        the applied shadow and current ``last_known_entity_id`` metadata.  The
        zone fingerprint is unchanged, so this is never a T21/T39 change.
        """

        @callback
        def _renamed(kind: str, old_entity_id: str, new_entity_id: str) -> None:
            _LOGGER.info(
                "Zone %s: configured %s renamed %s -> %s; same Registry identity retained",
                zone_id,
                kind,
                old_entity_id,
                new_entity_id,
            )
            self.coordinator.observe_current()
            self.hass.async_create_task(
                self._async_reconcile_and_sync_repairs(),
                f"moisture_loop rename reconciliation {zone_id}",
            )

        return _renamed

    def _make_emitter(self, zone_id: str, safety_record_id: str | None = None):
        def emit(kind: str, payload: dict) -> None:
            # Common identity fields (§32) come from the exact schema-2
            # record. A deleted device/subentry is optional presentation
            # metadata and is never required to emit delayed safety evidence.
            controller = self.controllers.get(zone_id)
            if safety_record_id is None and controller is not None:
                record_id = controller.safety_record_id
            else:
                record_id = safety_record_id
            record = (
                self.store.data.safety_records.get(record_id)
                if self.store.loaded and record_id is not None
                else None
            )
            history = (
                self.store.data.zone_histories.get(record.zone_history_id)
                if record is not None
                else None
            )
            enriched = dict(payload)
            enriched.setdefault("zone_id", zone_id)
            if controller is not None:
                enriched.setdefault("zone_name", controller.config_name)
                if "mode" not in enriched and controller.session is not None:
                    enriched["mode"] = controller.session.mode.value
            elif record is not None and record.applied_config is not None:
                enriched.setdefault("zone_name", record.applied_config.normalized_settings.name)
            if record is not None:
                enriched["safety_record_id"] = record.safety_record_id
                enriched["safety_lineage_id"] = record.safety_lineage_id
                enriched["zone_history_id"] = record.zone_history_id
                enriched["runtime_lifecycle"] = record.runtime_lifecycle.value
                enriched["subentry_id"] = record.active_subentry_id
                enriched["previous_subentry_ids"] = list(record.previous_subentry_ids)
            elif history is not None:
                enriched["zone_history_id"] = history.zone_history_id
            device_id = self._device_id(zone_id)
            if device_id is not None:
                enriched["device_id"] = device_id
            self.hass.bus.async_fire(f"{DOMAIN}_{kind}", enriched)
            self._update_repairs(kind, zone_id, record_id, enriched)

        return emit

    def _device_id(self, zone_id: str) -> str | None:
        from homeassistant.helpers import device_registry as dr

        device = dr.async_get(self.hass).async_get_device({(DOMAIN, zone_id)})
        return device.id if device else None

    def _update_repairs(
        self,
        kind: str,
        zone_id: str,
        safety_record_id: str | None,
        payload: dict,
    ) -> None:
        """§34 Repairs follow fault transitions."""
        from . import repairs
        from .models import FaultCode

        controller = self.controllers.get(zone_id)
        zone_name = controller.config_name if controller else zone_id
        if kind == "fault_set":
            fault = payload.get("fault")
            if fault == FaultCode.ACTUATOR_OFF_TIMEOUT.value and safety_record_id is not None:
                record = self.store.data.safety_records.get(safety_record_id)
                if record is not None:
                    repairs.async_create_off_unconfirmed_issue(
                        self.hass,
                        self.entry.entry_id,
                        record,
                        zone_name,
                    )
            elif fault == FaultCode.CONFIGURATION_INVALID.value and controller is not None:
                sensor = controller.config.moisture_sensor
                actuator = controller.config.actuator
                if self.hass.states.get(sensor) is None:
                    repairs.async_create_entity_missing_issue(
                        self.hass, zone_id, zone_name, sensor, actuator=False
                    )
                if self.hass.states.get(actuator) is None:
                    repairs.async_create_entity_missing_issue(
                        self.hass, zone_id, zone_name, actuator, actuator=True
                    )
            elif fault == FaultCode.RESTORED_FROM_UNSAFE_STATE.value:
                repairs.async_create_integrity_issue(self.hass, self.entry.entry_id)
        elif kind == "fault_cleared":
            fault = payload.get("fault")
            if fault == FaultCode.ACTUATOR_OFF_TIMEOUT.value and safety_record_id is not None:
                repairs.async_delete_record_issue(
                    self.hass,
                    self.entry.entry_id,
                    safety_record_id,
                    repairs.ISSUE_OFF_UNCONFIRMED,
                )
            elif fault == FaultCode.CONFIGURATION_INVALID.value:
                repairs.async_delete_entity_missing_issues(self.hass, zone_id)
            elif fault == FaultCode.RESTORED_FROM_UNSAFE_STATE.value and not any(
                c.active_fault is FaultCode.RESTORED_FROM_UNSAFE_STATE
                for c in self.controllers.values()
            ):
                repairs.async_delete_integrity_issue(self.hass, self.entry.entry_id)

    def _sync_repairs_from_authority(self) -> None:
        """Project canonical Store/reconciliation incidents into HA Repairs."""
        from . import repairs

        if not self.store.loaded:
            return
        current_identity_incidents: set[str] = set()
        for record in self.store.data.safety_records.values():
            name = (
                record.applied_config.normalized_settings.name
                if record.applied_config is not None
                else record.zone_id
            )
            if (
                record.actuator_fault is FaultCode.ACTUATOR_OFF_TIMEOUT
                and record.acknowledgement_required
            ):
                repairs.async_create_off_unconfirmed_issue(
                    self.hass,
                    self.entry.entry_id,
                    record,
                    name,
                )
            else:
                repairs.async_delete_record_issue(
                    self.hass,
                    self.entry.entry_id,
                    record.safety_record_id,
                    repairs.ISSUE_OFF_UNCONFIRMED,
                )

            if record.identity_incident is not None:
                issue_type = (
                    repairs.ISSUE_TOMBSTONE_ACTUATOR_MISSING
                    if record.identity_incident.kind
                    in (
                        IdentityIncidentKind.IDENTITY_MISSING,
                        IdentityIncidentKind.MIGRATION_UNRESOLVED,
                    )
                    else repairs.ISSUE_IDENTITY_CONFLICT
                )
                repairs.async_create_identity_issue(
                    self.hass,
                    self.entry.entry_id,
                    record,
                    issue_type,
                    name,
                )
                identity_issue_id = repairs.record_issue_id(
                    self.entry.entry_id,
                    record.safety_record_id,
                    issue_type,
                )
                current_identity_incidents.add(identity_issue_id)
                if identity_issue_id not in self._known_identity_incidents:
                    _LOGGER.error(
                        "Actuator identity incident for safety record %s: %s",
                        record.safety_record_id,
                        record.identity_incident.detail,
                    )
            else:
                # A resolved incident must clear its exact-record Repair even
                # when this runtime never raised it, because a reload or
                # restart starts with an empty in-memory incident set and a
                # stale identity Repair would otherwise outlive its cause.
                for issue_type in (
                    repairs.ISSUE_IDENTITY_CONFLICT,
                    repairs.ISSUE_TOMBSTONE_ACTUATOR_MISSING,
                ):
                    repairs.async_delete_record_issue(
                        self.hass,
                        self.entry.entry_id,
                        record.safety_record_id,
                        issue_type,
                    )

        for issue_id in self._known_identity_incidents - current_identity_incidents:
            repairs.async_delete_issue_id(self.hass, issue_id)
        self._known_identity_incidents = current_identity_incidents

        if self.coordinator.failed:
            repairs.async_create_reconciliation_issue(
                self.hass,
                self.entry.entry_id,
                self.coordinator.last_error or "configuration reconciliation failed",
                self.coordinator.observed_generation,
                self.coordinator.applied_generation,
            )
            if not self._reconciliation_issue_active:
                _LOGGER.error(
                    "Configuration reconciliation failed for entry %s: %s",
                    self.entry.entry_id,
                    self.coordinator.last_error,
                )
            self._reconciliation_issue_active = True
        else:
            repairs.async_delete_reconciliation_issue(self.hass, self.entry.entry_id)
            self._reconciliation_issue_active = False

    async def async_acknowledge_safety_record(
        self,
        safety_record_id: str,
        safety_lineage_id: str,
        issue_type: str,
    ) -> None:
        """Acknowledge exactly one retained record for a Repair fix flow."""
        from . import repairs

        if issue_type != repairs.ISSUE_OFF_UNCONFIRMED:
            raise SafetyRecordAcknowledgementError("record_fault_not_acknowledgeable")
        if not self.store.loaded:
            raise SafetyRecordAcknowledgementError("record_not_found")
        record = self.store.data.safety_records.get(safety_record_id)
        if record is None or record.safety_lineage_id != safety_lineage_id:
            raise SafetyRecordAcknowledgementError("record_not_found")
        if record.actuator_fault is not FaultCode.ACTUATOR_OFF_TIMEOUT:
            raise SafetyRecordAcknowledgementError("record_fault_changed")
        if not record.acknowledgement_required:
            raise SafetyRecordAcknowledgementError("record_fault_not_acknowledgeable")
        if record.identity_incident is not None or record.actuator_identity.identity_status in (
            IdentityStatus.MISSING,
            IdentityStatus.CONFLICT,
        ):
            raise SafetyRecordAcknowledgementError("record_identity_unresolved")
        history = self.store.data.zone_histories[record.zone_history_id]
        if (
            record.blocker_reasons
            or record.possible_flow_owner is not None
            or history.zone_runtime.session is not None
        ):
            raise SafetyRecordAcknowledgementError("record_off_not_proven")

        controller = self.controller_for_safety_record(safety_record_id)
        if controller is not None:
            if not controller.refresh_actuator_for_final_gate().proven_off:
                raise SafetyRecordAcknowledgementError("record_off_not_proven")
            decision = await controller.async_clear_fault()
            refreshed = self.store.data.safety_records.get(safety_record_id)
            if (
                decision.transition_id == "T44"
                or refreshed is None
                or refreshed.actuator_fault is not None
                or refreshed.acknowledgement_required
            ):
                raise SafetyRecordAcknowledgementError("record_fault_changed")
        else:
            if record.runtime_lifecycle is not RuntimeLifecycle.RETIRED:
                raise SafetyRecordAcknowledgementError("record_off_not_proven")
            try:
                await self.store.async_acknowledge_actuator_fault(
                    safety_record_id,
                    safety_lineage_id,
                    FaultCode.ACTUATOR_OFF_TIMEOUT,
                )
            except StoreWriteVerificationError as err:
                _LOGGER.error(
                    "Exact-record acknowledgement failed for %s: %s",
                    safety_record_id,
                    err,
                )
                raise SafetyRecordAcknowledgementError("record_acknowledgement_failed") from err
            self._make_emitter(record.zone_id, safety_record_id)(
                "fault_cleared",
                {"fault": FaultCode.ACTUATOR_OFF_TIMEOUT.value},
            )
        self._sync_repairs_from_authority()

    async def _reconcile_zone(
        self,
        controller: ZoneController,
        record: SafetyRecord,
        assessment,
    ) -> None:
        """Persisted WATERING/SOAKING/resting reconciliation (§25.2-§25.4)."""
        await self._maybe_clear_configuration_fault(controller, record)
        record = self.store.data.safety_records[record.safety_record_id]
        history = self.store.data.zone_histories[record.zone_history_id]
        persisted_session = history.zone_runtime.session
        if history.zone_runtime.state is ControllerState.WATERING and persisted_session is not None:
            controller.async_attach()
            if assessment.observed_on:
                finding = ActuatorFinding.ON
            elif assessment.proven_off:
                finding = ActuatorFinding.OFF
            else:
                finding = ActuatorFinding.UNPROVEN
            await controller.async_dispatch(StartupPersistedWatering(finding))
            return
        if history.zone_runtime.state is ControllerState.SOAKING and persisted_session is not None:
            await self._reconcile_soaking(controller, persisted_session.context, assessment)
            return
        controller.async_attach()

    async def _reconcile_soaking(
        self, controller: ZoneController, session: SessionContext, assessment
    ) -> None:
        """§25.3 trust checks, then atomic owner rebase before activation."""
        previous = self.previous_run
        assert previous is not None
        trusted = (
            previous.previous_run_was_clean
            and session.owner_run_id == previous.active_run_id
            and self._session_structure_valid(session)
            and session.config_fingerprint
            == config_fingerprint(controller._config, str(self._local_tz))
            and assessment.available
            and assessment.proven_off
        )
        if trusted:
            try:
                # §23.3: persist and read-back verify the rebase before any
                # controller activation.
                await self.store.async_rebase_soaking_owner_for_record(
                    controller.safety_record_id,
                    self.run_id,
                )
            except StoreWriteVerificationError as err:
                # LC9: watering-capable setup is prohibited; fail safe.
                raise ConfigEntryNotReady(f"soaking owner rebase failed: {err}") from err
            controller.async_attach()
            await controller.async_dispatch(
                StartupPersistedSoaking(trusted=True, current_run_id=self.run_id)
            )
            self.soaking_adoptions[controller.zone_id] = True
            session_now = controller.session
            now = dt_util.utcnow()
            if (
                session_now is not None
                and session_now.soak_ends_at_utc is not None
                and session_now.recheck_grace_deadline_at_utc is not None
                and session_now.soak_ends_at_utc <= now
                and session_now.recheck_grace_deadline_at_utc <= now
            ):
                # §25.3: both deadlines passed offline; check the current
                # observation once, then fault SENSOR_STALE if none qualify.
                controller._observation = controller._adapter.scan_current()
                await controller.async_dispatch(GraceDeadlineReached())
            return
        controller.async_attach()
        await controller.async_dispatch(StartupPersistedSoaking(trusted=False))
        self.soaking_adoptions[controller.zone_id] = False

    async def _maybe_clear_configuration_fault(
        self, controller: ZoneController, record: SafetyRecord
    ) -> None:
        """§26.1: CONFIGURATION_INVALID clears via successful reconfigure.

        After a reload, if the persisted fault was CONFIGURATION_INVALID and
        both configured entities now exist, the reconfiguration resolved it:
        clear the fault and its Repairs.
        """
        history = self.store.data.zone_histories[record.zone_history_id]
        runtime = history.zone_runtime
        if runtime.zone_fault is not FaultCode.CONFIGURATION_INVALID:
            return
        config = controller.config
        if (
            self.hass.states.get(config.moisture_sensor) is None
            or self.hass.states.get(config.actuator) is None
        ):
            return

        def _clear(data):
            current_record = data.safety_records[record.safety_record_id]
            current_history = data.zone_histories[current_record.zone_history_id]
            current_runtime = current_history.zone_runtime
            if current_runtime.zone_fault is not FaultCode.CONFIGURATION_INVALID:
                return dict(data.safety_records), dict(data.zone_histories)
            histories = dict(data.zone_histories)
            histories[current_history.zone_history_id] = current_history.evolve(
                zone_runtime=replace(
                    current_runtime,
                    # §24.4 derivation order: a disabled zone stays DISABLED
                    # when its configuration fault clears; only an enabled
                    # zone returns to IDLE.
                    state=(
                        ControllerState.IDLE
                        if current_runtime.enabled
                        else ControllerState.DISABLED
                    ),
                    zone_fault=None,
                )
            )
            return dict(data.safety_records), histories

        await self.store.async_reconcile(_clear)
        from . import repairs

        repairs.async_delete_entity_missing_issues(self.hass, controller.zone_id)
        _LOGGER.info(
            "Zone %s: configuration fault cleared after reconfiguration",
            controller.zone_id,
        )

    @staticmethod
    def _session_structure_valid(session: SessionContext) -> bool:
        if session.mode is not SessionMode.AUTO:
            return False
        soak = session.soak_ends_at_utc
        recheck = session.recheck_not_before_utc
        grace = session.recheck_grace_deadline_at_utc
        if soak is None or recheck is None or grace is None:
            return False
        if not (recheck == soak <= grace):
            return False
        off = session.off_confirmed_at_utc
        return off is not None and off <= soak

    def _install_periodic_triggers(self) -> None:
        """§16 triggers 4-5: the 15-minute fallback scan and HA-local
        midnight rollover evaluation."""
        from datetime import timedelta

        from homeassistant.helpers.event import (
            async_track_time_change,
            async_track_time_interval,
        )

        @callback
        def _scan(_now) -> None:
            for controller in self.controllers.values():
                self.hass.async_create_task(controller.async_fallback_scan())

        @callback
        def _midnight(_now) -> None:
            for controller in self.controllers.values():
                self.hass.async_create_task(controller.async_evaluate())

        self._activity_unsubs.append(
            async_track_time_interval(self.hass, _scan, timedelta(minutes=15))
        )
        self._activity_unsubs.append(
            async_track_time_change(self.hass, _midnight, hour=0, minute=0, second=0)
        )

    # ------------------------------------------------------------------
    # Full graceful process shutdown: the one Stage-1 owner (§24.1, §22.1)
    # ------------------------------------------------------------------

    def register_shutdown_job(self) -> None:
        """Register this runtime's one removable Stage-1 shutdown job.

        §24.1: exactly one active ``EntryRuntime`` registers exactly one
        removable ``HomeAssistant.async_add_shutdown_job()`` HassJob, and that
        job is the sole authoritative full-process shutdown owner. Core runs
        and awaits every registered shutdown job in Stage 1 of
        ``HomeAssistant.async_stop()``, strictly before it cancels background
        tasks, before it sets ``CoreState.stopping``, and before it fires
        ``EVENT_HOMEASSISTANT_STOP`` -- which is precisely why this hook, and
        only this hook, can complete the mandatory §23.4 immediate fresh-Store
        verification. The returned removal callback is owned by entry unload
        (§24.2), including the setup-failure path, so neither a reload nor an
        aborted setup can accumulate or strand a shutdown owner.
        """
        if self._shutdown_job_remove is not None:
            return
        self._shutdown_job_remove = self.hass.async_add_shutdown_job(
            HassJob(
                self.async_stage1_shutdown,
                f"moisture_loop stage-1 shutdown {self.entry.entry_id}",
            )
        )
        self.entry.async_on_unload(self.remove_shutdown_job)

    @callback
    def remove_shutdown_job(self) -> None:
        """Idempotently remove this runtime's Stage-1 shutdown job (§24.2)."""
        remove = self._shutdown_job_remove
        self._shutdown_job_remove = None
        if remove is not None:
            remove()

    @property
    def shutdown_job_registered(self) -> bool:
        """Whether this runtime currently owns a registered Stage-1 job."""
        return self._shutdown_job_remove is not None

    async def async_stage1_shutdown(self) -> None:
        """Authoritative full-process shutdown owner (§24.1).

        Home Assistant creates this job eagerly inside Stage 1, so everything
        before the first ``await`` below runs synchronously while Core is
        still iterating its shutdown jobs: admission is therefore closed
        before any other lifecycle work can observe a commandable runtime.
        Repeated initiation joins the same operation, so no second OFF and no
        second clean revision can be produced (§22.3).
        """
        operation = self._shutdown_operation
        if operation is not None:
            await asyncio.shield(operation)
            return

        # --- synchronous, before this coroutine's first suspension point ---
        self.process_stopping = True
        self.coordinator.close_publication_now()
        self.slots.close_admission_now()
        snapshot = self._all_controllers()
        for controller in snapshot:
            # Revokes manual/evaluation admission, queued command intent, and
            # every armed timer for this runtime safety object.
            controller.begin_quiescing()
        # One overall absolute active-flow deadline. Nested joins reuse this
        # exact instant, so no operation receives an independent full budget.
        self._shutdown_deadline = self.hass.loop.time() + max(0.0, self.shutdown_off_budget_s)
        core_state = getattr(self.hass.state, "name", str(self.hass.state))
        operation = self.hass.loop.create_future()
        self._shutdown_operation = operation
        # --- end of the synchronous admission-closure region ---

        failures: list[str] = []
        watering: list[str] = []
        preserved: list[str] = []
        try:
            await self._run_stage1_shutdown(snapshot, failures, watering, preserved)
        except asyncio.CancelledError:
            # Core's Stage-1 timeout or a forced teardown: never clean.
            failures.append("stage1_cancelled")
            raise
        except Exception as err:  # Core must still finish stopping
            failures.append(f"stage1_failed:{type(err).__name__}")
            _LOGGER.error("MoistureLoop Stage-1 shutdown handling failed: %s", err)
        finally:
            report = Stage1ShutdownReport(
                core_state_at_entry=core_state,
                watering_records=tuple(watering),
                preserved_soaking_records=tuple(preserved),
                failures=tuple(dict.fromkeys(failures)),
                clean=not failures,
            )
            self.shutdown_report = report
            if not operation.done():
                operation.set_result(None)
            if report.clean:
                _LOGGER.info(
                    "MoistureLoop Stage-1 shutdown completed cleanly for entry %s",
                    self.entry.entry_id,
                )
            else:
                _LOGGER.warning(
                    "MoistureLoop Stage-1 shutdown is unclean for entry %s: %s",
                    self.entry.entry_id,
                    ", ".join(report.failures),
                )

    async def _run_stage1_shutdown(
        self,
        snapshot: list[ZoneController],
        failures: list[str],
        watering: list[str],
        preserved: list[str],
    ) -> None:
        """Execute the normative §24.1 Stage-1 algorithm after admission closed."""
        fresh_zones = self._fresh_zone_snapshots(failures)

        # 1. Immediate active-flow signalling. No reconciliation worker,
        #    reload, platform unload, or diagnostic cleanup may be awaited
        #    before this (finding B2-1: physical OFF timing is the boundary).
        for controller in snapshot:
            if controller.state in (ControllerState.WATERING, ControllerState.SOAKING):
                continue
            # No live session decision is pending for these records, so the
            # one idempotent OFF may begin/join synchronously.
            self._begin_shutdown_off(controller)
        for controller in snapshot:
            state = controller.state
            if state is ControllerState.WATERING:
                watering.append(controller.safety_record_id)
                # Signal first: OffConfirmed before a committed terminal
                # reason would be an ordinary T6 pulse end, not a shutdown.
                await controller.async_dispatch(HomeAssistantShutdown())
                if controller.inflight_on is None:
                    # An integration-owned WATERING exit always begins or
                    # joins the one idempotent OFF (§11.3); an ON still in
                    # flight converges first (§22.3).
                    controller.begin_off_operation()
            elif state is ControllerState.SOAKING:
                event, eligible, needs_off = self._soaking_shutdown_outcome(controller, fresh_zones)
                await controller.async_dispatch(event)
                if eligible:
                    preserved.append(controller.safety_record_id)
                elif needs_off:
                    self._begin_shutdown_off(controller)

        # 2. Bounded convergence: any in-flight ON is driven into the same one
        #    OFF path, and every started/joined OFF operation is directly
        #    awaited, all inside the one Stage-1 active-flow deadline.
        for controller in snapshot:
            operation = controller.off_operation
            if (
                controller.safety_record_id in watering
                or controller.inflight_on is not None
                or (operation is not None and not operation.done())
            ):
                await self._await_off_within_budget(controller)

        # 3. Join or take over the unawaited reconciliation/lifecycle handoff.
        try:
            await self.coordinator.async_join_workers()
        except Exception as err:  # recorded, never swallowed
            failures.append(f"reconciliation_handoff:{type(err).__name__}")
            _LOGGER.error("Stage-1 reconciliation handoff failed: %s", err)

        # 4. Per-object outcome: persist honest current state through the one
        #    §23.4 verified-write contract. There is no shutdown exception.
        for controller in snapshot:
            record_id = controller.safety_record_id
            if controller.persist_failed:
                failures.append(f"safety_write_failed:{record_id}")
                continue
            if not self._owns_zone_runtime(controller):
                # A retained record that no longer owns its logical zone's
                # operational authority (§23.2) must not overwrite it.
                continue
            try:
                await controller.async_persist_current_state("stage1_shutdown")
            except StoreWriteVerificationError as err:
                failures.append(f"safety_write_failed:{record_id}")
                _LOGGER.error("Stage-1 safety write failed for %s: %s", record_id, err)

        # 5. Clean-run aggregation (§23.3, I14). Honest evidence is not
        #    success: integration-owned possible flow that was not proven OFF
        #    keeps the run unclean, while a correctly persisted external_flow
        #    owner is successful MoistureLoop handling.
        if not self.store.loaded:
            failures.append("safety_store_not_loaded")
            return
        for record in self.store.data.safety_records.values():
            if (
                record.possible_flow_owner is PossibleFlowOwner.INTEGRATION
                or BlockerReason.INTEGRATION_OFF_UNCONFIRMED in record.blocker_reasons
            ):
                failures.append(f"integration_off_unconfirmed:{record.safety_record_id}")
        for controller in snapshot:
            record_id = controller.safety_record_id
            if record_id not in watering and record_id not in preserved:
                continue
            if not controller.refresh_actuator_for_final_gate().proven_off:
                failures.append(f"terminal_off_not_proven:{record_id}")
        if failures:
            return

        # 6. The clean marker is the final verified safety transaction and is
        #    reachable only after total success (§23.3 items 1-5).
        try:
            await self.store.async_mark_clean_shutdown()
        except StoreWriteVerificationError as err:
            # The previous marker is deliberately left unchanged; the next run
            # reads unequal IDs and treats this run as unclean.
            failures.append(f"clean_marker_write_failed:{type(err).__name__}")
            _LOGGER.error("Clean-shutdown marking failed: %s", err)

    def _fresh_zone_snapshots(self, failures: list[str]) -> dict[str, ImmutableZoneSnapshot]:
        """Read current public configuration once for Stage-1 eligibility."""
        try:
            snapshot = self._build_immutable_snapshot(self.coordinator.observed_generation)
        except Exception as err:  # fail closed, never guess
            failures.append(f"configuration_snapshot:{type(err).__name__}")
            return {}
        return snapshot.by_subentry_id()

    def _integration_owned_possible_flow(self, controller: ZoneController) -> bool:
        """Whether this record is integration-owned physically possible flow."""
        if controller.inflight_on is not None:
            return True
        if not self.store.loaded:
            return False
        record = self.store.data.safety_records.get(controller.safety_record_id)
        if record is None:
            return False
        return (
            record.possible_flow_owner is PossibleFlowOwner.INTEGRATION
            or BlockerReason.INTEGRATION_OFF_UNCONFIRMED in record.blocker_reasons
        )

    def _begin_shutdown_off(self, controller: ZoneController) -> None:
        """Begin or join this record's one idempotent OFF operation (§11.3)."""
        if controller.inflight_on is not None:
            # §22.3: an already dispatched ON must converge first. Issuing OFF
            # while that call is still outstanding could let the ON reach
            # hardware afterwards; the convergence phase joins the same one
            # compensating OFF operation once the call returns or is cancelled.
            return
        if not self._integration_owned_possible_flow(controller):
            return
        if controller.off_operation is None and self.store.loaded:
            record = self.store.data.safety_records.get(controller.safety_record_id)
            if record is not None and record.actuator_identity.identity_status in (
                IdentityStatus.MISSING,
                IdentityStatus.CONFLICT,
            ):
                # §25.1.1: an unresolved identity is never commanded as this
                # record's actuator. Its evidence is retained instead.
                return
        controller.begin_off_operation()

    def _soaking_shutdown_outcome(
        self,
        controller: ZoneController,
        fresh_zones: dict[str, ImmutableZoneSnapshot],
    ) -> tuple[object, bool, bool]:
        """Decide T37 preservation versus already-arbitrated termination.

        §24.1 preserves an active soak only while its lifecycle is ACTIVE,
        the current configuration still matches the applied shadow, and the
        actuator remains proven OFF. Every other case terminates through an
        existing transition; no new controller state or transition exists.
        """
        live = controller.refresh_actuator_for_final_gate()
        if live.observed_on or not live.proven_off:
            if not live.available:
                # T32: unavailable is not OFF, and no new command is possible.
                return ActuatorBecameUnavailable(), False, False
            # T33/T34: interference during an integration-owned soak.
            return ExternalActuatorOn(), False, True
        record = (
            self.store.data.safety_records.get(controller.safety_record_id)
            if self.store.loaded
            else None
        )
        binding = self.bindings.get(controller.zone_id)
        applied = controller.applied_config
        fresh_zone = fresh_zones.get(controller.zone_id)
        eligible = (
            record is not None
            and record.runtime_lifecycle is RuntimeLifecycle.ACTIVE
            and record.active_subentry_id == controller.zone_id
            and binding is not None
            and binding.controller is controller
            and applied is not None
            and fresh_zone is not None
            and fresh_zone.config_fingerprint == applied.config_fingerprint
        )
        if eligible:
            # T37: persist the active soak unchanged; no new water.
            return HomeAssistantShutdown(), True, False
        # T39: the configuration change/deletion already arbitrated this.
        return ConfigChangedPrepare(), False, False

    def _owns_zone_runtime(self, controller: ZoneController) -> bool:
        """Whether this controller is the logical zone's operational authority.

        §23.2 gives each ``zone_history`` exactly one operational owner. A
        retained A record sharing the continuing history after an A -> B
        replacement keeps its own actuator safety authority but must never
        write B's ``zone_runtime``.
        """
        if not self.store.loaded:
            return False
        record = self.store.data.safety_records.get(controller.safety_record_id)
        if record is None or record.zone_history_id != controller.zone_history_id:
            return False
        if controller.zone_history_id not in self.store.data.zone_histories:
            return False
        return not any(
            other.safety_record_id != controller.safety_record_id
            and other.zone_history_id == controller.zone_history_id
            and other.runtime_lifecycle is RuntimeLifecycle.ACTIVE
            for other in self.store.data.safety_records.values()
        )

    async def _await_off_within_budget(
        self, controller: ZoneController, deadline: float | None = None
    ) -> None:
        """Join the controller's one OFF operation within the lifecycle budget.

        An ON service already in flight must finish or be cancelled before
        OFF is allowed to land; otherwise that ON could reach hardware after
        OFF.  Cancellation is handled by ``_perform_on`` as uncertain flow
        and converges on this same operation.  There is no lifecycle-specific
        direct actuator call.

        ``deadline`` is an absolute monotonic instant. During Stage-1 process
        shutdown every caller shares the one overall active-flow deadline
        (§24.1), so nested joins cannot receive independent full budgets.
        """
        loop = asyncio.get_running_loop()
        if deadline is None:
            deadline = self._shutdown_deadline
        if deadline is None:
            deadline = loop.time() + max(0.0, self.shutdown_off_budget_s)
        absolute_deadline = deadline

        def remaining() -> float:
            return max(0.0, absolute_deadline - loop.time())

        task = controller.session_owner_task
        if controller.inflight_on is not None and remaining() > 0:
            await controller.async_wait_on_dispatch_completed(remaining())

        # Give the cooperative session owner a bounded set of deterministic
        # event-loop turns to publish the shared operation.
        for _ in range(10):
            if controller.off_operation is not None:
                break
            await asyncio.sleep(0)
        operation = controller.off_operation
        if operation is not None and not operation.done() and remaining() > 0:
            await asyncio.wait({operation}, timeout=remaining())
        if operation is not None and operation.done():
            return

        # Bounded fallback: force the session owner through cancellation
        # compensation.  If an OFF is already running, end that exact
        # operation as unconfirmed (which persists the exact blocker) instead
        # of issuing a second actuator command sequence.
        task = controller.session_owner_task
        if task is not None and not task.done():
            task.cancel()
        for _ in range(10):
            operation = controller.off_operation
            if operation is not None:
                break
            await asyncio.sleep(0)
        if operation is not None and not operation.done():
            await controller.async_abort_off_as_unconfirmed()
        if task is not None and not task.done():
            for _ in range(10):
                if task.done():
                    break
                await asyncio.sleep(0)
            if task.done():
                with contextlib.suppress(asyncio.CancelledError):
                    task.result()

        # A faulted OFF result deliberately leaves the session/accounting
        # open.  Once that exact future has durably resolved unconfirmed, the
        # reconciler may publish a retained DELETE_PENDING controller; it must
        # not fail merely because the session owner remains alive to consume a
        # later exact OFF observation.
        operation = controller.off_operation
        if operation is not None and operation.done():
            with contextlib.suppress(asyncio.CancelledError):
                operation.result()
            return

        # Cancellation of an in-flight ON begins compensation synchronously;
        # allow it to publish the shared future before considering a direct
        # entry into that same controller operation.
        if controller.session is None and controller.inflight_on is None:
            return
        operation = controller.off_operation or controller.begin_off_operation()
        if operation.done():
            return
        if remaining() > 0:
            await asyncio.wait({operation}, timeout=remaining())
        if not operation.done():
            await controller.async_abort_off_as_unconfirmed()

    # ------------------------------------------------------------------
    # Generic entry unload/reload (§24.2)
    # ------------------------------------------------------------------

    async def async_unload(self) -> None:
        # §24.2: an unloaded entry holds no process-shutdown responsibility.
        self.remove_shutdown_job()
        operation = self._shutdown_operation
        if operation is not None and not operation.done():
            # Stage-1 process shutdown already won: this unload is
            # cleanup/join only. It creates no competing terminal reason, no
            # second OFF, and never writes or owns the clean marker.
            await asyncio.shield(operation)
        await self.coordinator.async_stop()
        await self.slots.async_disable_grants()
        if not self.process_stopping:
            # Terminate WATERING and SOAKING as CONFIG_RELOAD; never mark
            # the process run clean and never change run IDs (§24.2).
            for controller in self._all_controllers():
                was_watering = controller.state is ControllerState.WATERING
                if was_watering or controller.state is ControllerState.SOAKING:
                    await controller.async_dispatch(ConfigEntryReload())
                if was_watering:
                    # Await cooperative OFF before teardown (§24.2), with
                    # the same bounded fallback as shutdown.
                    await self._await_off_within_budget(controller)
        for controller in self._all_controllers():
            await controller.async_detach()
        for unsub in self._activity_unsubs:
            unsub()
        self._activity_unsubs = []
        self.controllers = {}
        self.bindings = {}
        self.retained_controllers = {}

    def _all_controllers(self) -> list[ZoneController]:
        """Return each current/retained controller exactly once."""
        by_identity = {
            id(controller): controller
            for controller in (
                *self.controllers.values(),
                *self.retained_controllers.values(),
            )
        }
        return list(by_identity.values())

    # ------------------------------------------------------------------
    # Subentry reconfiguration/deletion preparation (§24.3)
    # ------------------------------------------------------------------

    async def async_prepare_reconfigure(self, zone_id: str) -> None:
        """Cooperatively terminate the zone's session as CONFIG_CHANGED.

        This is preparation only: the flow subsequently asks Core to mutate
        the ConfigSubentry, and the registered update listener/reconciler owns
        the new canonical/applied state and any required platform reload.
        """
        controller = self.controllers.get(zone_id)
        if controller is None:
            return
        await self.slots.async_cancel_request(zone_id)
        if controller.state in (ControllerState.WATERING, ControllerState.SOAKING):
            was_watering = controller.state is ControllerState.WATERING
            await controller.async_dispatch(ConfigChangedPrepare())
            if was_watering:
                await self._await_off_within_budget(controller)
