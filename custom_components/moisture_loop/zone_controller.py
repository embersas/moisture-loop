"""Zone controller: Home Assistant adapter and session execution.

Slice 6 implements the moisture sensor adapter only: entity-filtered
listeners for both changed states and unchanged reports (§5.2), one shared
normalization path producing `MoistureObservation` (§6, §10), and
entity-registry removal/rename inputs. The asynchronous session owner,
actuator command execution, timers/watchdogs, and SlotManager integration
are Slice 7 per PROGRESS.md.

Adapter rules (§10.3, §5.2):
- The configured entity ID is passed directly to
  ``async_track_state_report_event``; a global/wildcard listener is
  forbidden.
- Report time is always ``State.last_reported`` (changed path) or the
  report event's ``last_reported`` (unchanged path). Callback time and
  fallback-scan time are never report time; a fallback scan re-reads the
  current State and cannot manufacture a new report timestamp.
- Callbacks stay lightweight: they normalize and hand the observation to
  the controller sink; they never call actuator services or authorize
  water.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import uuid
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta, tzinfo
from typing import TYPE_CHECKING

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Context, Event, HomeAssistant, State, callback
from homeassistant.helpers.event import (
    async_track_entity_registry_updated_event,
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_state_report_event,
)
from homeassistant.util import dt as dt_util

from .const import MOISTURE_MAX, MOISTURE_MIN, OFF_TOTAL_ATTEMPTS
from .models import (
    ActuatorAssessment,
    ActuatorBecameUnavailable,
    AddBlocker,
    ArmTimer,
    ArmWatchdog,
    AutoEvaluate,
    BlockerReason,
    ClearFaultRequested,
    CompletionReason,
    ConfigurationInvalid,
    ControllerState,
    DailyRuntime,
    Decision,
    DisableRequested,
    EmitFaultCleared,
    EmitFaultSet,
    EmitSessionFinished,
    EmitSessionStarted,
    EnableRequested,
    ExecuteOff,
    ExternalActuatorOff,
    ExternalActuatorOn,
    FaultCode,
    GraceDeadlineReached,
    ManualDeadlineReached,
    ManualStartRequested,
    MoistureClassification,
    MoistureObservation,
    MoistureReport,
    OffConfirmed,
    OffNotConfirmed,
    OnConfirmed,
    OnConfirmTimeout,
    PersistState,
    PulseDeadlineReached,
    ReleaseSlot,
    RemoveBlocker,
    RequestSlot,
    ResourceAssessment,
    ScheduleEvaluation,
    SessionContext,
    SessionIdentity,
    SessionMode,
    SessionSummary,
    SetExternalOn,
    SlotGranted,
    SoakDeadlineReached,
    StopRequested,
    TimerKind,
    TransitionInput,
    TurnOn,
    WatchdogFired,
    WatchdogToken,
    ZoneConfig,
    ZoneRecord,
    config_fingerprint,
    current_day_charge,
)
from .slot_manager import SlotManager
from .state_machine import decide
from .storage import SafetyStore, StoreWriteVerificationError

if TYPE_CHECKING:
    from homeassistant.core import (
        EventStateChangedData,
        EventStateReportedData,
    )
    from homeassistant.helpers.event import EventEntityRegistryUpdatedData

_LOGGER = logging.getLogger(__name__)

type ObservationSink = Callable[[MoistureObservation], None]


def classify_moisture(
    state: State | None,
    reported_at_utc: datetime | None,
    now_utc: datetime,
    sensor_max_age_s: float,
) -> MoistureObservation:
    """Normalize one HA state into the §10.2 classification table.

    ``reported_at_utc`` is the authoritative report time (``last_reported``
    from the state or the report event) — never the callback or scan time.
    Out-of-range data is rejected, never clamped (§10.2). Values 0 and 100
    are valid (§10.1).
    """
    if state is None or state.state == STATE_UNAVAILABLE:
        return MoistureObservation(
            value=None,
            classification=MoistureClassification.UNAVAILABLE,
            reported_at_utc=None,
            age_s=None,
        )
    if state.state == STATE_UNKNOWN:
        return MoistureObservation(
            value=None,
            classification=MoistureClassification.INVALID,
            reported_at_utc=reported_at_utc,
            age_s=_age_s(reported_at_utc, now_utc),
        )
    try:
        value = float(state.state)
    except (TypeError, ValueError):
        return MoistureObservation(
            value=None,
            classification=MoistureClassification.INVALID,
            reported_at_utc=reported_at_utc,
            age_s=_age_s(reported_at_utc, now_utc),
        )
    if not math.isfinite(value) or value < MOISTURE_MIN or value > MOISTURE_MAX:
        return MoistureObservation(
            value=value if math.isfinite(value) else None,
            classification=MoistureClassification.INVALID,
            reported_at_utc=reported_at_utc,
            age_s=_age_s(reported_at_utc, now_utc),
        )
    age = _age_s(reported_at_utc, now_utc)
    if reported_at_utc is None:
        # A finite in-range value without a report timestamp cannot prove
        # anything; conservatively invalid telemetry.
        return MoistureObservation(
            value=value,
            classification=MoistureClassification.INVALID,
            reported_at_utc=None,
            age_s=None,
        )
    fresh = MoistureObservation(value, MoistureClassification.VALID, reported_at_utc, age).is_fresh(
        now_utc, sensor_max_age_s
    )
    return MoistureObservation(
        value=value,
        classification=(MoistureClassification.VALID if fresh else MoistureClassification.STALE),
        reported_at_utc=reported_at_utc,
        age_s=age,
    )


def _age_s(reported_at_utc: datetime | None, now_utc: datetime) -> float | None:
    if reported_at_utc is None:
        return None
    return max(0.0, (now_utc - reported_at_utc).total_seconds())


class MoistureAdapter:
    """Entity-filtered moisture listeners feeding one normalized sink (§5.2).

    Changed states arrive via ``async_track_state_change_event`` using
    ``new_state.last_reported``; unchanged reports arrive via the
    entity-filtered ``async_track_state_report_event`` using the event's
    ``last_reported``. Both paths meet in :func:`classify_moisture`.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entity_id: str,
        sensor_max_age_s: float,
        sink: ObservationSink,
        on_removed: Callable[[], None],
        on_renamed: Callable[[str], None] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._hass = hass
        self._entity_id = entity_id
        self._sensor_max_age_s = sensor_max_age_s
        self._sink = sink
        self._on_removed = on_removed
        self._on_renamed = on_renamed
        self._clock = clock if clock is not None else dt_util.utcnow
        self._unsubscribers: list[Callable[[], None]] = []

    @property
    def entity_id(self) -> str:
        return self._entity_id

    @property
    def started(self) -> bool:
        return bool(self._unsubscribers)

    def async_start(self) -> None:
        """Install both entity-filtered listeners plus registry tracking."""
        if self._unsubscribers:
            return
        self._unsubscribers = [
            async_track_state_change_event(
                self._hass, [self._entity_id], self._handle_state_change
            ),
            async_track_state_report_event(
                self._hass, [self._entity_id], self._handle_state_report
            ),
            async_track_entity_registry_updated_event(
                self._hass, self._entity_id, self._handle_registry_update
            ),
        ]

    def async_stop(self) -> None:
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers = []

    def scan_current(self) -> MoistureObservation:
        """Fallback scan: re-evaluate the latest stored report (§10.3).

        Uses the stored State's ``last_reported`` — scan time never becomes
        report time and a scan can never manufacture a new report.
        """
        state = self._hass.states.get(self._entity_id)
        reported_at = state.last_reported if state is not None else None
        return classify_moisture(state, reported_at, self._clock(), self._sensor_max_age_s)

    @callback
    def _handle_state_change(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        reported_at = new_state.last_reported if new_state is not None else None
        observation = classify_moisture(
            new_state, reported_at, self._clock(), self._sensor_max_age_s
        )
        self._sink(observation)

    @callback
    def _handle_state_report(self, event: Event[EventStateReportedData]) -> None:
        # An identical report is a real observation: the event's
        # last_reported advances and refreshes freshness (§10.3).
        observation = classify_moisture(
            event.data["new_state"],
            event.data["last_reported"],
            self._clock(),
            self._sensor_max_age_s,
        )
        self._sink(observation)

    @callback
    def _handle_registry_update(self, event: Event[EventEntityRegistryUpdatedData]) -> None:
        action = event.data["action"]
        if action == "remove":
            # §10.4: entity registry removal -> CONFIGURATION_INVALID input.
            self._on_removed()
            return
        if action == "update" and "old_entity_id" in event.data:
            new_entity_id = event.data["entity_id"]
            # Rename auto-fixup is a §46 prototype validation; instrument
            # without inventing fallback semantics.
            _LOGGER.warning(
                "Configured moisture sensor %s was renamed to %s; "
                "rename tracking is pending prototype validation",
                self._entity_id,
                new_entity_id,
            )
            if self._on_renamed is not None:
                self._on_renamed(new_entity_id)


# ---------------------------------------------------------------------------
# Actuator adapter (§11.1): switch and valve command/observation semantics
# ---------------------------------------------------------------------------


class ActuatorAdapter:
    """Domain-appropriate ON/OFF commands and conservative state assessment.

    ``unknown``, ``unavailable``, unrecognized, and transitional states are
    never proven OFF; a known ``current_position > 0`` is potentially
    flowing; position 0 (or no position) with terminal ``closed`` is OFF
    (§11.1). Full open/close actions only; positions are never commanded.
    """

    def __init__(self, hass: HomeAssistant, entity_id: str) -> None:
        self._hass = hass
        self._entity_id = entity_id
        self._domain = entity_id.partition(".")[0]

    @property
    def entity_id(self) -> str:
        return self._entity_id

    def assess(self, state: State | None) -> ActuatorAssessment:
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return ActuatorAssessment(available=False, proven_off=False, observed_on=False)
        raw = state.state
        if self._domain == "valve":
            position = state.attributes.get("current_position")
            if raw == "open":
                return ActuatorAssessment(available=True, proven_off=False, observed_on=True)
            if raw == "closed":
                if position is None or position == 0:
                    return ActuatorAssessment(available=True, proven_off=True, observed_on=False)
                # Terminal closed but nonzero position: potentially flowing.
                return ActuatorAssessment(available=True, proven_off=False, observed_on=True)
            if raw in ("opening", "closing"):
                # Transitional: never proof of the requested terminal state.
                observed_on = bool(position) and position > 0
                return ActuatorAssessment(available=True, proven_off=False, observed_on=observed_on)
            return ActuatorAssessment(available=True, proven_off=False, observed_on=False)
        if raw == "on":
            return ActuatorAssessment(available=True, proven_off=False, observed_on=True)
        if raw == "off":
            return ActuatorAssessment(available=True, proven_off=True, observed_on=False)
        return ActuatorAssessment(available=True, proven_off=False, observed_on=False)

    def current(self) -> ActuatorAssessment:
        return self.assess(self._hass.states.get(self._entity_id))

    def is_terminal_on(self, state: State | None) -> bool:
        """True only for the terminal ON/open state (§11.2 acknowledgement).

        Transitional ``opening`` is potentially flowing (conservative
        blocking, §11.1) but never acknowledgement of the requested state.
        """
        if state is None:
            return False
        if self._domain == "valve":
            return state.state == "open"
        return state.state == "on"

    async def async_turn_on(self, context: Context) -> None:
        service = "open_valve" if self._domain == "valve" else "turn_on"
        await self._hass.services.async_call(
            self._domain,
            service,
            {"entity_id": self._entity_id},
            blocking=True,
            context=context,
        )

    async def async_turn_off(self, context: Context) -> None:
        service = "close_valve" if self._domain == "valve" else "turn_off"
        await self._hass.services.async_call(
            self._domain,
            service,
            {"entity_id": self._entity_id},
            blocking=True,
            context=context,
        )


# ---------------------------------------------------------------------------
# Zone runtime controller (Slice 7): session owner, timers, OFF operation
# ---------------------------------------------------------------------------


class ZoneController:
    """Asynchronous per-zone session execution layer (SPEC §§11, 12, 16-22, 37).

    Every normalized event is decided by the pure state machine under one
    zone transition lock; this class only executes the requested side
    effects. The session-owner task is the only normal ON caller and the
    normal OFF owner (§22.1); callbacks set the pending termination through
    ``decide()`` and wake the task. One shared idempotent OFF-operation
    future exists per active session (§11.3).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        zone_id: str,
        config: ZoneConfig,
        store: SafetyStore,
        slots: SlotManager,
        run_id: str,
        local_tz: tzinfo,
        emit: Callable[[str, dict], None] | None = None,
        clock: Callable[[], datetime] | None = None,
        safety_record_id: str | None = None,
    ) -> None:
        self._hass = hass
        self.zone_id = zone_id
        # Stage 2 separates controller/subentry identity from durable
        # actuator-safety ownership. The fallback retains historical direct
        # test callers until Stage 3 materializes every configured record.
        self.safety_record_id = safety_record_id or zone_id
        if not self.safety_record_id:
            raise ValueError("safety_record_id must be non-empty")
        self._config = config
        self._store = store
        self._slots = slots
        self._run_id = run_id
        self._tz = local_tz
        self._emit = emit if emit is not None else (lambda kind, payload: None)
        self._clock = clock if clock is not None else dt_util.utcnow

        self._lock = asyncio.Lock()
        self._state: ControllerState = ControllerState.IDLE
        self._enabled = True
        self._session: SessionContext | None = None
        self._active_fault: FaultCode | None = None
        self._secondary_fault: FaultCode | None = None
        self._last_session_end: datetime | None = None
        self._last_auto_session_start: datetime | None = None
        self._last_summary: SessionSummary | None = None
        self._daily = DailyRuntime(
            date_local=self._clock().astimezone(local_tz).date(), runtime_s=0.0
        )
        self._observation = MoistureObservation(
            None, MoistureClassification.UNAVAILABLE, None, None
        )
        self._external_on = False
        self._armed_watchdog: WatchdogToken | None = None
        self._actuator = ActuatorAdapter(hass, config.actuator)
        self._assessment = ActuatorAssessment(False, False, False)
        self._adapter = MoistureAdapter(
            hass,
            config.moisture_sensor,
            config.sensor_max_age_s,
            sink=self._on_moisture,
            on_removed=self._on_sensor_removed,
            clock=self._clock,
        )
        self._fingerprint = config_fingerprint(config, str(local_tz))

        self._timers: dict[TimerKind, Callable[[], None]] = {}
        self._watchdog_unsub: Callable[[], None] | None = None
        self._unsubscribers: list[Callable[[], None]] = []

        self._session_task: asyncio.Task | None = None
        self._wake = asyncio.Event()
        self._on_requested = False
        self._off_requested = False
        self._off_operation: asyncio.Future[bool] | None = None
        self._off_proven = asyncio.Event()
        self._off_proven_at: datetime | None = None
        self._slot_task: asyncio.Task | None = None
        self._pending_manual: float | None = None
        self._persist_failed = False
        self._listeners: list[Callable[[], None]] = []
        # Last transitions for diagnostics (§33.2); merged/capped at 50
        # across zones by diagnostics.
        self.transitions: deque[dict] = deque(maxlen=50)

    # -- lifecycle -----------------------------------------------------------

    def async_attach(self, record: ZoneRecord | None = None) -> None:
        """Adopt persisted resting state and install listeners.

        Startup reconciliation ordering (which events to dispatch for
        persisted WATERING/SOAKING) is the entry runtime's job (Slice 8);
        this only restores fields and subscribes.
        """
        if record is not None:
            self._state = record.state
            self._enabled = record.enabled
            self._active_fault = record.active_fault
            self._secondary_fault = record.secondary_fault
            self._last_session_end = record.last_session_end_utc
            self._last_auto_session_start = record.last_auto_session_start_utc
            self._last_summary = record.last_session_summary
            if record.daily is not None:
                self._daily = record.daily
            self._session = record.session
        self._assessment = self._actuator.current()
        # Seed the observation from the stored report (§10.3 fallback-scan
        # semantics: the stored last_reported, never the scan time).
        self._observation = self._adapter.scan_current()
        self._adapter.async_start()
        self._unsubscribers.append(
            async_track_state_change_event(
                self._hass, [self._config.actuator], self._on_actuator_event
            )
        )

    async def async_detach(self) -> None:
        """Tear down listeners/timers/tasks; no state decisions here."""
        self._adapter.async_stop()
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers = []
        self._cancel_all_timers()
        if self._slot_task is not None:
            self._slot_task.cancel()
            self._slot_task = None
        task = self._session_task
        if task is not None and not task.done():
            # Cooperative shutdown budgets use HA timers and belong to the
            # entry lifecycle (Slice 8); teardown falls back to cancellation
            # with a best-effort path into the same idempotent OFF (§22.1).
            self._wake.set()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._session_task = None

    # -- public inputs ---------------------------------------------------------

    async def async_dispatch(self, event: object) -> Decision:
        """Decide and apply one normalized controller event."""
        async with self._lock:
            return await self._decide_and_apply_locked(event)

    async def async_evaluate(self) -> Decision:
        return await self.async_dispatch(AutoEvaluate())

    async def async_fallback_scan(self) -> Decision:
        """§16 trigger 4: re-evaluate the latest stored report.

        The scan cannot manufacture a new report timestamp (§10.3); the
        normalized observation flows through the same decision paths, so a
        stale replay no-ops and freshness is never invented.
        """
        observation = self._adapter.scan_current()
        async with self._lock:
            self._observation = observation
            decision = await self._decide_and_apply_locked(MoistureReport(observation))
        self._notify_listeners()
        return decision

    async def async_manual_start(self, requested_duration_s: float) -> Decision:
        return await self.async_dispatch(ManualStartRequested(requested_duration_s))

    async def async_stop_watering(self) -> Decision:
        return await self.async_dispatch(StopRequested())

    async def async_set_enabled(self, enabled: bool) -> Decision:
        async with self._lock:
            self._enabled = enabled
            event = EnableRequested() if enabled else DisableRequested()
            return await self._decide_and_apply_locked(event)

    async def async_clear_fault(self) -> Decision:
        return await self.async_dispatch(ClearFaultRequested())

    # -- snapshots ----------------------------------------------------------------

    @property
    def state(self) -> ControllerState:
        return self._state

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def session(self) -> SessionContext | None:
        return self._session

    @property
    def active_fault(self) -> FaultCode | None:
        return self._active_fault

    @property
    def secondary_fault(self) -> FaultCode | None:
        return self._secondary_fault

    @property
    def observation(self) -> MoistureObservation:
        return self._observation

    @property
    def daily(self) -> DailyRuntime:
        return self._current_daily()

    @property
    def last_session_end(self) -> datetime | None:
        return self._last_session_end

    @property
    def last_summary(self) -> SessionSummary | None:
        return self._last_summary

    @property
    def external_on(self) -> bool:
        return self._external_on

    @property
    def armed_watchdog(self) -> WatchdogToken | None:
        return self._armed_watchdog

    @property
    def assessment(self) -> ActuatorAssessment:
        return self._assessment

    @property
    def config(self) -> ZoneConfig:
        return self._config

    @property
    def config_name(self) -> str:
        return self._config.name

    @property
    def may_be_flowing(self) -> bool:
        """Whether this configured actuator may be flowing (§28.2).

        Includes integration WATERING, respected external ON, observed ON,
        and OFF-unconfirmed open accounting.
        """
        if self._state is ControllerState.WATERING:
            return True
        if self._external_on or self._assessment.observed_on:
            return True
        session = self._session
        return session is not None and session.pending_termination_reason is not None

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe to state updates (entity refresh)."""
        self._listeners.append(listener)

        def _remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _remove

    def _notify_listeners(self) -> None:
        for listener in list(self._listeners):
            listener()

    # -- event sources ---------------------------------------------------------

    @callback
    def _on_moisture(self, observation: MoistureObservation) -> None:
        self._hass.async_create_task(self._async_moisture(observation))

    async def _async_moisture(self, observation: MoistureObservation) -> None:
        async with self._lock:
            self._observation = observation
            await self._decide_and_apply_locked(MoistureReport(observation))
        self._notify_listeners()

    @callback
    def _on_sensor_removed(self) -> None:
        self._hass.async_create_task(self.async_dispatch(ConfigurationInvalid(at_setup=False)))

    @callback
    def _on_actuator_event(self, event: Event) -> None:
        new_state = event.data["new_state"]
        assessment = self._actuator.assess(new_state)
        terminal_on = self._actuator.is_terminal_on(new_state)
        previous = self._assessment
        self._assessment = assessment
        now = self._clock()
        if assessment.proven_off:
            self._off_proven_at = now
            self._off_proven.set()
        else:
            self._off_proven.clear()
        self._hass.async_create_task(
            self._async_actuator_change(previous, assessment, terminal_on, now)
        )

    async def _async_actuator_change(
        self,
        previous: ActuatorAssessment,
        assessment: ActuatorAssessment,
        terminal_on: bool,
        observed_at: datetime,
    ) -> None:
        async with self._lock:
            state = self._state
            session = self._session
            if not assessment.available:
                if state in (ControllerState.WATERING, ControllerState.SOAKING):
                    await self._decide_and_apply_locked(ActuatorBecameUnavailable())
                return
            off_op_active = self._off_operation is not None and not self._off_operation.done()
            if assessment.observed_on:
                if state is ControllerState.WATERING and session is not None:
                    # Our own ON acknowledgement requires the terminal
                    # ON/open state; transitional states never confirm
                    # (§11.1, §11.2 step 5).
                    if (
                        terminal_on
                        and session.pulse_commanded_at_utc is not None
                        and session.pulse_confirmed_at_utc is None
                        and session.pending_termination_reason is None
                        and not off_op_active
                    ):
                        await self._decide_and_apply_locked(OnConfirmed(observed_at))
                    return
                # ON without an integration command: external (§11.4).
                await self._decide_and_apply_locked(ExternalActuatorOn())
                return
            if assessment.proven_off and not previous.proven_off:
                # Terminal OFF proof always releases this zone's startup
                # not-proven-off key (exact-key, idempotent; §21, §25.4).
                await self._slots.async_remove_blocker(
                    self.safety_record_id, BlockerReason.ACTUATOR_NOT_PROVEN_OFF
                )
                if off_op_active:
                    return  # the OFF operation consumes this proof
                await self._decide_and_apply_locked(ExternalActuatorOff(observed_at))

    # -- decide/apply core -------------------------------------------------------

    async def _decide_and_apply_locked(self, event: object) -> Decision:
        inp = self._build_input(event)
        decision = decide(inp)
        await self._apply_locked(decision, inp)
        return decision

    def _build_input(self, event: object) -> TransitionInput:
        return TransitionInput(
            now_utc=self._clock(),
            config=self._config,
            state=self._state,
            enabled=self._enabled,
            session=self._session,
            active_fault=self._active_fault,
            secondary_fault=self._secondary_fault,
            observation=self._observation,
            daily_runtime_s=self._current_daily().runtime_s,
            last_session_end_utc=self._last_session_end,
            actuator=self._assessment,
            resource=ResourceAssessment(
                slot_granted=self._slots.owner == self.zone_id,
                blockers_empty=self._slots.blockers_empty(),
            ),
            armed_watchdog=self._armed_watchdog,
            event=event,  # type: ignore[arg-type]
            external_on=self._external_on,
            new_session_identity=SessionIdentity(
                session_id=str(uuid.uuid4()),
                owner_run_id=self._run_id,
                config_fingerprint=self._fingerprint,
            ),
        )

    async def _apply_locked(self, decision: Decision, inp: TransitionInput) -> None:
        if decision.no_op:
            return
        previous_state = self._state
        previous_runtime = inp.session.session_runtime_s if inp.session is not None else 0.0
        if decision.session is not None:
            self._session = decision.session
            if inp.session is None and decision.session.mode is SessionMode.AUTO:
                self._last_auto_session_start = decision.session.started_at_utc
        closed: SessionContext | None = None
        if decision.clear_session:
            closed = decision.final_session
            self._session = None
        if decision.new_state is not None:
            self._state = decision.new_state
        if decision.fault is not None:
            self._active_fault = decision.fault
        if decision.clear_fault:
            self._active_fault = None
        if decision.secondary_fault is not None:
            self._secondary_fault = decision.secondary_fault

        # Accounting: charge any runtime growth to HA-local days (§19.3).
        grown = self._session if self._session is not None else closed
        if grown is not None and grown.session_runtime_s > previous_runtime:
            delta = grown.session_runtime_s - previous_runtime
            end = grown.off_confirmed_at_utc or inp.now_utc
            self._charge_runtime(delta, end)

        if closed is not None:
            self._finalize_summary(decision, closed, inp)

        # Timer housekeeping on state exits and confirmations.
        if previous_state is ControllerState.WATERING and self._state is not (
            ControllerState.WATERING
        ):
            self._cancel_timers(
                TimerKind.PULSE_END, TimerKind.MANUAL_END, TimerKind.ON_CONFIRM_TIMEOUT
            )
            self._cancel_watchdog()
        if previous_state is ControllerState.SOAKING and self._state is not (
            ControllerState.SOAKING
        ):
            self._cancel_timers(TimerKind.SOAK_END, TimerKind.GRACE)
        if self._session is not None and self._session.pulse_confirmed_at_utc is not None:
            self._cancel_timers(TimerKind.ON_CONFIRM_TIMEOUT)

        # A manual request that must wait for the slot is re-issued with its
        # duration when the grant is offered (§14 note); record it before
        # the RequestSlot action can spawn the waiting task.
        if isinstance(inp.event, ManualStartRequested) and any(
            isinstance(a, RequestSlot) for a in decision.actions
        ):
            self._pending_manual = inp.event.requested_duration_s

        for action in decision.actions:
            try:
                await self._apply_action_locked(action, decision)
            except StoreWriteVerificationError as err:
                await self._handle_persist_failure_locked(err)
                return

        self._record_and_log(decision, inp)
        if self._session is not None or self._on_requested or self._off_requested:
            self._ensure_session_task()
        self._wake.set()
        self._notify_listeners()

    async def _apply_action_locked(self, action: object, decision: Decision) -> None:
        if isinstance(action, PersistState):
            await self._persist_locked()
        elif isinstance(action, TurnOn):
            self._on_requested = True
            # A new pulse gets a fresh idempotent OFF operation (§11.3).
            self._off_operation = None
        elif isinstance(action, ExecuteOff):
            self._off_requested = True
        elif isinstance(action, ArmTimer):
            self._arm_timer(action.kind, action.at_utc)
        elif isinstance(action, ArmWatchdog):
            self._arm_watchdog(action.token)
        elif isinstance(action, RequestSlot):
            self._ensure_slot_request()
        elif isinstance(action, ReleaseSlot):
            await self._slots.async_release(self.zone_id)
            await self._slots.async_cancel_request(self.zone_id)
        elif isinstance(action, AddBlocker):
            await self._slots.async_add_blocker(self.safety_record_id, action.reason)
        elif isinstance(action, RemoveBlocker):
            await self._slots.async_remove_blocker(self.safety_record_id, action.reason)
        elif isinstance(action, SetExternalOn):
            self._external_on = action.value
        elif isinstance(action, EmitSessionStarted):
            self._emit("session_started", self._session_payload(self._session))
        elif isinstance(action, EmitSessionFinished):
            self._emit("session_finished", self._finished_payload(decision))
        elif isinstance(action, EmitFaultSet):
            self._emit(
                "fault_set",
                {
                    "zone_id": self.zone_id,
                    "fault": action.fault.value,
                    "replaces": action.replaces.value if action.replaces else None,
                },
            )
        elif isinstance(action, EmitFaultCleared):
            self._emit("fault_cleared", {"zone_id": self.zone_id, "fault": action.fault.value})
        elif isinstance(action, ScheduleEvaluation):
            self._hass.async_create_task(self.async_evaluate())

    def _record_and_log(self, decision: Decision, inp: TransitionInput) -> None:
        """§33.1 logging levels and the diagnostics transition buffer."""
        event_name = type(inp.event).__name__
        if decision.transition_id is not None:
            self.transitions.append(
                {
                    "at_utc": inp.now_utc.isoformat(),
                    "zone_id": self.zone_id,
                    "event": event_name,
                    "transition": decision.transition_id,
                    "new_state": decision.new_state.value if decision.new_state else None,
                    "reason": decision.reason.value if decision.reason else None,
                    "fault": decision.fault.value if decision.fault else None,
                }
            )
        reason = decision.reason
        fault = decision.fault
        if fault is FaultCode.ACTUATOR_OFF_TIMEOUT:
            # CRITICAL is represented as a Repair plus an ERROR log (§33.1).
            _LOGGER.error(
                "Zone %s: actuator OFF not proven after retries; possible uncontrolled water flow",
                self.zone_id,
            )
        elif fault in (
            FaultCode.ACTUATOR_UNAVAILABLE,
            FaultCode.ACTUATOR_ON_TIMEOUT,
            FaultCode.CONFIGURATION_INVALID,
            FaultCode.RESTORED_FROM_UNSAFE_STATE,
        ):
            _LOGGER.error("Zone %s: fault %s", self.zone_id, fault.value)
        elif fault is not None:
            _LOGGER.warning(
                "Zone %s: sensor fault %s terminated automatic watering",
                self.zone_id,
                fault.value,
            )
        if reason is not None:
            if reason.reason_class.value == "success":
                _LOGGER.info("Zone %s: session finished (%s)", self.zone_id, reason.value)
            elif reason.reason_class.value == "constrained":
                _LOGGER.warning(
                    "Zone %s: session completed constrained (%s)",
                    self.zone_id,
                    reason.value,
                )
            elif reason is CompletionReason.EXTERNAL_ACTUATOR_STATE_CHANGE:
                _LOGGER.warning(
                    "Zone %s: external actuator interference ended the session",
                    self.zone_id,
                )
            elif reason is CompletionReason.RESTART_RECOVERY:
                _LOGGER.warning(
                    "Zone %s: crash reconciliation finished with estimated runtime",
                    self.zone_id,
                )
            else:
                _LOGGER.info("Zone %s: session ended (%s)", self.zone_id, reason.value)
        if decision.transition_id == "T1" or decision.transition_id == "T40":
            _LOGGER.info("Zone %s: session started (%s)", self.zone_id, event_name)
        elif decision.transition_id == "T42":
            _LOGGER.info("Zone %s: fault auto-cleared", self.zone_id)
        elif decision.transition_id in ("T54", "T55"):
            _LOGGER.info("Zone %s: external flow occupies the water resource", self.zone_id)
        elif decision.transition_id in ("T58", "T59"):
            _LOGGER.info("Zone %s: external flow released", self.zone_id)
        else:
            _LOGGER.debug(
                "Zone %s: %s -> %s (state %s)",
                self.zone_id,
                event_name,
                decision.transition_id or ("no-op" if decision.no_op else "action"),
                decision.new_state.value if decision.new_state else self._state.value,
            )

    # -- persistence -------------------------------------------------------------

    def build_record(self) -> ZoneRecord:
        return ZoneRecord(
            state=self._state,
            enabled=self._enabled,
            active_fault=self._active_fault,
            secondary_fault=self._secondary_fault,
            last_session_end_utc=self._last_session_end,
            last_auto_session_start_utc=self._last_auto_session_start,
            daily=self._current_daily(),
            last_session_summary=self._last_summary,
            session=self._session,
        )

    async def _persist_locked(self) -> None:
        record = self.build_record()
        await self._store.async_update_zone(self.zone_id, lambda _old: record)

    async def _handle_persist_failure_locked(self, err: Exception) -> None:
        """§23.4: a failed safety write must never authorize watering."""
        _LOGGER.error("Zone %s: safety write failed; blocking operation: %s", self.zone_id, err)
        self._persist_failed = True
        self._on_requested = False
        self._active_fault = FaultCode.RESTORED_FROM_UNSAFE_STATE
        self._state = ControllerState.FAULT
        self._emit(
            "fault_set",
            {
                "zone_id": self.zone_id,
                "fault": FaultCode.RESTORED_FROM_UNSAFE_STATE.value,
                "replaces": None,
            },
        )
        # Reconcile OFF where needed; the idempotent operation is safe even
        # when nothing is flowing.
        if not self._assessment.proven_off:
            self._off_requested = True
            self._ensure_session_task()
            self._wake.set()

    # -- accounting -----------------------------------------------------------

    def _current_daily(self) -> DailyRuntime:
        today = self._clock().astimezone(self._tz).date()
        if self._daily.date_local != today:
            # Lazy HA-local rollover (§19.3).
            self._daily = DailyRuntime(date_local=today, runtime_s=0.0)
        return self._daily

    def _charge_runtime(self, delta_s: float, end_utc: datetime) -> None:
        start_utc = end_utc - timedelta(seconds=delta_s)
        current = self._current_daily()
        charge = current_day_charge(start_utc, end_utc, self._tz, current.date_local)
        if charge > 0:
            self._daily = DailyRuntime(
                date_local=current.date_local, runtime_s=current.runtime_s + charge
            )

    def _finalize_summary(
        self, decision: Decision, closed: SessionContext, inp: TransitionInput
    ) -> None:
        reason = decision.reason
        assert reason is not None  # every pure closure carries a reason
        ended = closed.off_confirmed_at_utc or inp.now_utc
        self._last_summary = SessionSummary(
            mode=closed.mode,
            reason=reason,
            runtime_s=closed.session_runtime_s,
            runtime_estimated=closed.runtime_estimated,
            runtime_estimation_reason=closed.runtime_estimation_reason,
            requested_duration_s=closed.manual_requested_duration_s,
            effective_duration_s=closed.manual_effective_duration_s,
            clamp_reasons=closed.manual_clamp_reasons,
            cycles=closed.cycle,
            moisture_before=closed.moisture_at_start,
            moisture_after=closed.last_recheck_value,
            started_at_utc=closed.started_at_utc,
            ended_at_utc=ended,
        )
        # §19.4: every created session resets the minimum interval when
        # conservative accounting closes.
        self._last_session_end = ended

    def _session_payload(self, session: SessionContext | None) -> dict:
        return {
            "zone_id": self.zone_id,
            "session_id": session.session_id if session else None,
            "mode": session.mode.value if session else None,
        }

    def _finished_payload(self, decision: Decision) -> dict:
        summary = self._last_summary
        payload: dict = {
            "zone_id": self.zone_id,
            "reason": decision.reason.value if decision.reason else None,
        }
        # session_finished is emitted only after closure built the summary.
        assert summary is not None
        payload.update(
            {
                "mode": summary.mode.value,
                "runtime_s": summary.runtime_s,
                "runtime_estimated": summary.runtime_estimated,
                "runtime_estimation_reason": summary.runtime_estimation_reason.value,
                "cycles": summary.cycles,
                "moisture_before": summary.moisture_before,
                "moisture_after": summary.moisture_after,
                "requested_duration_s": summary.requested_duration_s,
                "effective_duration_s": summary.effective_duration_s,
                "clamp_reasons": [r.value for r in summary.clamp_reasons],
            }
        )
        return payload

    # -- timers ---------------------------------------------------------------

    def _arm_timer(self, kind: TimerKind, at_utc: datetime) -> None:
        self._cancel_timers(kind)
        self._timers[kind] = async_track_point_in_time(
            self._hass, self._make_timer_callback(kind), at_utc
        )

    def _make_timer_callback(self, kind: TimerKind):
        @callback
        def _fired(_now: datetime) -> None:
            self._timers.pop(kind, None)
            event = _TIMER_EVENTS[kind]()
            self._hass.async_create_task(self.async_dispatch(event))

        return _fired

    def _cancel_timers(self, *kinds: TimerKind) -> None:
        for kind in kinds:
            unsub = self._timers.pop(kind, None)
            if unsub is not None:
                unsub()

    def _cancel_all_timers(self) -> None:
        self._cancel_timers(*list(self._timers))
        self._cancel_watchdog()

    def _arm_watchdog(self, token: WatchdogToken) -> None:
        # Cancelling the old handle is best-effort cleanup; correctness
        # comes from token validation in the pure core (§18.5).
        self._cancel_watchdog()
        self._armed_watchdog = token

        @callback
        def _fired(_now: datetime) -> None:
            self._watchdog_unsub = None
            self._hass.async_create_task(self.async_dispatch(WatchdogFired(token)))

        self._watchdog_unsub = async_track_point_in_time(self._hass, _fired, token.deadline_utc)

    def _cancel_watchdog(self) -> None:
        if self._watchdog_unsub is not None:
            self._watchdog_unsub()
            self._watchdog_unsub = None

    # -- slot integration -------------------------------------------------------

    def _ensure_slot_request(self) -> None:
        if self._slot_task is not None and not self._slot_task.done():
            return
        self._slot_task = self._hass.async_create_background_task(
            self._await_slot(), name=f"moisture_loop.slot.{self.zone_id}"
        )

    async def _await_slot(self) -> None:
        request = await self._slots.async_request(self.zone_id)
        try:
            await request.granted
        except asyncio.CancelledError:
            await self._slots.async_cancel_request(self.zone_id)
            raise
        pending_manual = self._pending_manual
        self._pending_manual = None
        if pending_manual is not None:
            await self.async_dispatch(ManualStartRequested(pending_manual))
        else:
            await self.async_dispatch(SlotGranted())

    # -- session-owner task (§22.1) --------------------------------------------

    def _ensure_session_task(self) -> None:
        if self._session_task is None or self._session_task.done():
            # Background task: it lives for the whole session and must not
            # block Home Assistant's tracked-task draining.
            self._session_task = self._hass.async_create_background_task(
                self._run_session(), name=f"moisture_loop.session.{self.zone_id}"
            )

    async def _run_session(self) -> None:
        """The only normal ON caller and normal OFF owner (§22.1)."""
        while True:
            self._wake.clear()
            if self._on_requested:
                self._on_requested = False
                await self._perform_on()
                continue
            if self._off_requested:
                self._off_requested = False
                await self._ensure_off_operation()
                continue
            async with self._lock:
                if self._session is None and not self._on_requested and not self._off_requested:
                    return
            await self._wake.wait()

    async def _perform_on(self) -> None:
        """§11.2 ON sequence steps 3-4 with the §18.5 pre-ON recheck."""
        async with self._lock:
            session = self._session
            if session is None or self._state is not ControllerState.WATERING:
                return
            if session.pending_termination_reason is not None:
                return
            now = self._clock()
            if (
                session.mode is SessionMode.AUTO
                and session.sensor_fresh_until_utc is not None
                and session.sensor_fresh_until_utc <= now
                and self._armed_watchdog is not None
            ):
                # Freshness expired during persistence: never issue ON;
                # terminate through the stale/OFF-assurance path (§18.1).
                await self._decide_and_apply_locked(WatchdogFired(self._armed_watchdog))
                return
            context = Context()
        try:
            await self._actuator.async_turn_on(context)
        except Exception as err:
            _LOGGER.error("Zone %s: ON command failed: %s", self.zone_id, err)
            await self.async_dispatch(OnConfirmTimeout())
            return
        async with self._lock:
            if self._session is not None:
                # §11.2 step 4: persist commanded immediately after the call.
                self._session = self._session.evolve(pulse_commanded_at_utc=self._clock())
                try:
                    await self._persist_locked()
                except StoreWriteVerificationError as err:
                    await self._handle_persist_failure_locked(err)

    async def _ensure_off_operation(self) -> bool:
        """Enter/join the one idempotent OFF operation (§11.3)."""
        operation = self._off_operation
        if operation is not None:
            if not operation.done():
                return await asyncio.shield(operation)
            if operation.result() and self._assessment.proven_off:
                return True  # already proven OFF for this exit
            # A previous operation ended unconfirmed, or it belonged to an
            # earlier exit and the actuator is flowing again (external ON
            # during SOAKING): a fresh defensive operation is required
            # (§11.3, §11.4).
        loop = asyncio.get_running_loop()
        operation = loop.create_future()
        self._off_operation = operation
        try:
            confirmed_at = await self._run_off_attempts()
        except Exception:
            operation.set_result(False)
            raise
        if confirmed_at is not None:
            operation.set_result(True)
            await self.async_dispatch(OffConfirmed(confirmed_at))
            return True
        operation.set_result(False)
        await self.async_dispatch(OffNotConfirmed())
        return False

    async def _run_off_attempts(self) -> datetime | None:
        for _attempt in range(OFF_TOTAL_ATTEMPTS):
            # The OFF action is always issued at least once, even when the
            # actuator already reads OFF: defensive assurance (§19.1).
            context = Context()
            try:
                await self._actuator.async_turn_off(context)
            except Exception as err:
                _LOGGER.warning("Zone %s: OFF command failed: %s", self.zone_id, err)
            if self._assessment.proven_off or await self._wait_off_proof():
                return self._off_proven_at or self._clock()
        return None

    async def _wait_off_proof(self) -> bool:
        """Await OFF proof within the confirm timeout using HA timers."""
        if self._off_proven.is_set() or self._assessment.proven_off:
            return True
        timeout_event = asyncio.Event()
        deadline = self._clock() + timedelta(seconds=self._config.actuator_confirm_timeout_s)

        @callback
        def _timed_out(_now: datetime) -> None:
            timeout_event.set()

        unsub = async_track_point_in_time(self._hass, _timed_out, deadline)
        proof_task = asyncio.ensure_future(self._off_proven.wait())
        timeout_task = asyncio.ensure_future(timeout_event.wait())
        try:
            await asyncio.wait((proof_task, timeout_task), return_when=asyncio.FIRST_COMPLETED)
        finally:
            unsub()
            proof_task.cancel()
            timeout_task.cancel()
        return self._off_proven.is_set() or self._assessment.proven_off


_TIMER_EVENTS: dict[TimerKind, type] = {
    TimerKind.PULSE_END: PulseDeadlineReached,
    TimerKind.MANUAL_END: ManualDeadlineReached,
    TimerKind.SOAK_END: SoakDeadlineReached,
    TimerKind.GRACE: GraceDeadlineReached,
    TimerKind.ON_CONFIRM_TIMEOUT: OnConfirmTimeout,
}
