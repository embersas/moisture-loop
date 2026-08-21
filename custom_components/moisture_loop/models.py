"""Pure domain models for Moisture Loop.

Home Assistant-independent vocabulary and data structures implementing
SPECIFICATION.md §§6, 9, 12, 18.2, 19, 20, 23.2 and 26. This module must not
import homeassistant and performs no I/O (§37). All datetimes are
timezone-aware UTC; all durations are seconds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from enum import StrEnum
from typing import Union

from .const import (
    ACTUATOR_CONFIRM_TIMEOUT_MAX_S,
    ACTUATOR_CONFIRM_TIMEOUT_MIN_S,
    ACTUATOR_DOMAIN_SWITCH,
    ACTUATOR_DOMAIN_VALVE,
    MANUAL_MAX_DURATION_MAX_S,
    MANUAL_MAX_DURATION_MIN_S,
    MAX_CYCLES_MAX,
    MAX_CYCLES_MIN,
    MAX_DAILY_RUNTIME_MAX_S,
    MAX_SESSION_RUNTIME_MAX_S,
    MIN_SESSION_INTERVAL_MAX_S,
    MIN_SESSION_INTERVAL_MIN_S,
    MOISTURE_MAX,
    MOISTURE_MIN,
    NAME_MAX_LENGTH,
    NAME_MIN_LENGTH,
    PULSE_DURATION_MAX_S,
    PULSE_DURATION_MIN_S,
    SENSOR_DOMAIN,
    SENSOR_MAX_AGE_MAX_S,
    SENSOR_MAX_AGE_MIN_S,
    SOAK_DURATION_MAX_S,
    SOAK_DURATION_MIN_S,
    START_THRESHOLD_MAX,
    START_THRESHOLD_MIN,
    TARGET_THRESHOLD_MAX,
    TARGET_THRESHOLD_MIN,
)

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ControllerState(StrEnum):
    """Five-state controller model (SPECIFICATION.md §12.1)."""

    DISABLED = "disabled"
    IDLE = "idle"
    WATERING = "watering"
    SOAKING = "soaking"
    FAULT = "fault"


class SessionMode(StrEnum):
    """Session mode (§12.1); manual is not a sixth state."""

    AUTO = "auto"
    MANUAL = "manual"


class MoistureClassification(StrEnum):
    """Moisture observation classification (§10.2)."""

    VALID = "valid"
    STALE = "stale"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"


class FaultCode(StrEnum):
    """Latched fault codes with the §26.1 property matrix."""

    SENSOR_UNAVAILABLE = "sensor_unavailable"
    SENSOR_STALE = "sensor_stale"
    SENSOR_INVALID = "sensor_invalid"
    ACTUATOR_UNAVAILABLE = "actuator_unavailable"
    ACTUATOR_ON_TIMEOUT = "actuator_on_timeout"
    ACTUATOR_OFF_TIMEOUT = "actuator_off_timeout"
    CONFIGURATION_INVALID = "configuration_invalid"
    RESTORED_FROM_UNSAFE_STATE = "restored_from_unsafe_state"

    @property
    def blocks_automatic(self) -> bool:
        """Every latched fault blocks automatic watering (§26.1)."""
        return True

    @property
    def is_sensor_only(self) -> bool:
        """Sensor-only faults permit bounded manual watering (§20.2)."""
        return self in (
            FaultCode.SENSOR_UNAVAILABLE,
            FaultCode.SENSOR_STALE,
            FaultCode.SENSOR_INVALID,
        )

    @property
    def allows_manual(self) -> bool:
        return self.is_sensor_only

    @property
    def auto_clears(self) -> bool:
        """Faults that clear automatically when their condition resolves."""
        return self in (
            FaultCode.SENSOR_UNAVAILABLE,
            FaultCode.SENSOR_STALE,
            FaultCode.SENSOR_INVALID,
            FaultCode.ACTUATOR_UNAVAILABLE,
            FaultCode.ACTUATOR_ON_TIMEOUT,
        )

    @property
    def requires_user_ack(self) -> bool:
        """Faults cleared only by user acknowledgement (after OFF proof)."""
        return self in (
            FaultCode.ACTUATOR_OFF_TIMEOUT,
            FaultCode.RESTORED_FROM_UNSAFE_STATE,
        )

    @property
    def requires_reconfigure(self) -> bool:
        """CONFIGURATION_INVALID clears only via successful reconfiguration."""
        return self is FaultCode.CONFIGURATION_INVALID


class ReasonClass(StrEnum):
    """Completion reason classes (§26.2)."""

    SUCCESS = "success"
    CONSTRAINED = "constrained"
    CANCELLATION = "cancellation"
    RECOVERY = "recovery"
    FAULT = "fault"


class CompletionReason(StrEnum):
    """Exactly one per session (§26.2)."""

    TARGET_REACHED = "target_reached"
    MANUAL_COMPLETE = "manual_complete"
    MAX_CYCLES = "max_cycles"
    MAX_SESSION_RUNTIME = "max_session_runtime"
    DAILY_RUNTIME_LIMIT = "daily_runtime_limit"
    USER_STOP = "user_stop"
    ZONE_DISABLED = "zone_disabled"
    EXTERNAL_ACTUATOR_STATE_CHANGE = "external_actuator_state_change"
    CONFIG_RELOAD = "config_reload"
    CONFIG_CHANGED = "config_changed"
    HOME_ASSISTANT_SHUTDOWN = "home_assistant_shutdown"
    RESTART_RECOVERY = "restart_recovery"
    SENSOR_FAULT = "sensor_fault"
    ACTUATOR_FAULT = "actuator_fault"

    @property
    def reason_class(self) -> ReasonClass:
        return _REASON_CLASSES[self]


_REASON_CLASSES: dict[CompletionReason, ReasonClass] = {
    CompletionReason.TARGET_REACHED: ReasonClass.SUCCESS,
    CompletionReason.MANUAL_COMPLETE: ReasonClass.SUCCESS,
    CompletionReason.MAX_CYCLES: ReasonClass.CONSTRAINED,
    CompletionReason.MAX_SESSION_RUNTIME: ReasonClass.CONSTRAINED,
    CompletionReason.DAILY_RUNTIME_LIMIT: ReasonClass.CONSTRAINED,
    CompletionReason.USER_STOP: ReasonClass.CANCELLATION,
    CompletionReason.ZONE_DISABLED: ReasonClass.CANCELLATION,
    CompletionReason.EXTERNAL_ACTUATOR_STATE_CHANGE: ReasonClass.CANCELLATION,
    CompletionReason.CONFIG_RELOAD: ReasonClass.CANCELLATION,
    CompletionReason.CONFIG_CHANGED: ReasonClass.CANCELLATION,
    CompletionReason.HOME_ASSISTANT_SHUTDOWN: ReasonClass.CANCELLATION,
    CompletionReason.RESTART_RECOVERY: ReasonClass.RECOVERY,
    CompletionReason.SENSOR_FAULT: ReasonClass.FAULT,
    CompletionReason.ACTUATOR_FAULT: ReasonClass.FAULT,
}


class RuntimeEstimationReason(StrEnum):
    """Session runtime estimation metadata (§19.2)."""

    NONE = "none"
    RESTART_FOUND_ON = "restart_found_on"
    RESTART_FOUND_OFF_UNKNOWN_STOP = "restart_found_off_unknown_stop"
    OFF_UNCONFIRMED = "off_unconfirmed"


class BlockerReason(StrEnum):
    """Water-resource blocker reasons, keyed as (zone_id, reason) (§6, §21)."""

    EXTERNAL_FLOW = "external_flow"
    INTEGRATION_OFF_UNCONFIRMED = "integration_off_unconfirmed"
    ACTUATOR_NOT_PROVEN_OFF = "actuator_not_proven_off"


class ManualClampReason(StrEnum):
    """Caps that reduced a manual duration request (§20.1)."""

    MANUAL_MAX_DURATION = "manual_max_duration"
    MAX_SESSION_RUNTIME = "max_session_runtime"
    REMAINING_DAILY_BUDGET = "remaining_daily_budget"


class ActuatorFinding(StrEnum):
    """Startup actuator classification for persisted WATERING (§25.2)."""

    ON = "on"
    OFF = "off"
    UNPROVEN = "unproven"


class TimerKind(StrEnum):
    """Absolute-deadline timers a decision may request (§18)."""

    PULSE_END = "pulse_end"
    MANUAL_END = "manual_end"
    SOAK_END = "soak_end"
    GRACE = "grace"
    ON_CONFIRM_TIMEOUT = "on_confirm_timeout"


# ---------------------------------------------------------------------------
# Observations, tokens, configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MoistureObservation:
    """Normalized sensor input (§6). Produced by the HA adapter only."""

    value: float | None
    classification: MoistureClassification
    reported_at_utc: datetime | None
    age_s: float | None

    def validate(self) -> None:
        """Raise ValueError if the observation is structurally inconsistent."""
        cls = self.classification
        if cls in (MoistureClassification.VALID, MoistureClassification.STALE):
            if self.value is None or not math.isfinite(self.value):
                raise ValueError(f"{cls.value} observation requires a finite value")
            if not (MOISTURE_MIN <= self.value <= MOISTURE_MAX):
                raise ValueError(f"{cls.value} observation value out of [0, 100]")
            if self.reported_at_utc is None:
                raise ValueError(f"{cls.value} observation requires reported_at_utc")
            _require_utc(self.reported_at_utc, "reported_at_utc")
            if self.age_s is None or self.age_s < 0:
                raise ValueError(f"{cls.value} observation requires non-negative age_s")
        elif cls is MoistureClassification.UNAVAILABLE:
            if self.value is not None:
                raise ValueError("unavailable observation must not carry a value")
        # INVALID may carry the offending raw value (or None) and any timestamp.
        if self.reported_at_utc is not None:
            _require_utc(self.reported_at_utc, "reported_at_utc")

    def fresh_until(self, sensor_max_age_s: float) -> datetime | None:
        """Freshness deadline derived from the report time (§6, §18.2)."""
        if self.reported_at_utc is None:
            return None
        return self.reported_at_utc + timedelta(seconds=sensor_max_age_s)

    def is_fresh(self, now_utc: datetime, sensor_max_age_s: float) -> bool:
        """Fresh means reported_at_utc >= now - max_age; equality is fresh (§6)."""
        if self.reported_at_utc is None:
            return False
        return self.reported_at_utc >= now_utc - timedelta(seconds=sensor_max_age_s)


@dataclass(frozen=True, slots=True)
class WatchdogToken:
    """AUTO freshness generation/deadline token (§18.5).

    A queued callback whose token no longer matches the armed token must
    no-op; matching is exact on both fields.
    """

    generation: int
    deadline_utc: datetime

    def __post_init__(self) -> None:
        _require_utc(self.deadline_utc, "deadline_utc")


@dataclass(frozen=True, slots=True)
class ZoneConfig:
    """Per-zone configuration (§9). Durations are integer seconds."""

    name: str
    moisture_sensor: str
    actuator: str
    start_threshold: float
    target_threshold: float
    pulse_duration_s: int
    soak_duration_s: int
    max_cycles: int
    max_session_runtime_s: int
    max_daily_runtime_s: int
    min_session_interval_s: int
    sensor_max_age_s: int
    actuator_confirm_timeout_s: int
    manual_max_duration_s: int

    def validation_errors(self) -> list[str]:
        """Return every §9 bound violation (HA-independent checks only).

        Entity existence, valve features, duplicate-actuator and unique-name
        checks require Home Assistant and belong to the config flow.
        """
        errors: list[str] = []
        if not (NAME_MIN_LENGTH <= len(self.name) <= NAME_MAX_LENGTH):
            errors.append("name must be 1-64 characters")
        if _entity_domain(self.moisture_sensor) != SENSOR_DOMAIN:
            errors.append("moisture_sensor must be a sensor entity ID")
        if _entity_domain(self.actuator) not in (ACTUATOR_DOMAIN_SWITCH, ACTUATOR_DOMAIN_VALVE):
            errors.append("actuator must be a switch or valve entity ID")
        if not (START_THRESHOLD_MIN <= self.start_threshold <= START_THRESHOLD_MAX):
            errors.append("start_threshold must be within 1-99")
        if not (TARGET_THRESHOLD_MIN <= self.target_threshold <= TARGET_THRESHOLD_MAX):
            errors.append("target_threshold must be within 2-100")
        if not self.start_threshold < self.target_threshold:
            errors.append("start_threshold must be strictly less than target_threshold")
        if not (PULSE_DURATION_MIN_S <= self.pulse_duration_s <= PULSE_DURATION_MAX_S):
            errors.append("pulse_duration must be within 30 s-30 min")
        if not (SOAK_DURATION_MIN_S <= self.soak_duration_s <= SOAK_DURATION_MAX_S):
            errors.append("soak_duration must be within 1 min-4 h")
        if not (MAX_CYCLES_MIN <= self.max_cycles <= MAX_CYCLES_MAX):
            errors.append("max_cycles must be within 1-20")
        if not (self.pulse_duration_s <= self.max_session_runtime_s <= MAX_SESSION_RUNTIME_MAX_S):
            errors.append("max_session_runtime must be within pulse duration-4 h")
        if not (self.pulse_duration_s <= self.max_daily_runtime_s <= MAX_DAILY_RUNTIME_MAX_S):
            errors.append("max_daily_runtime must be within pulse duration-12 h")
        if not (
            MIN_SESSION_INTERVAL_MIN_S <= self.min_session_interval_s <= MIN_SESSION_INTERVAL_MAX_S
        ):
            errors.append("min_session_interval must be within 15 min-7 d")
        if not (SENSOR_MAX_AGE_MIN_S <= self.sensor_max_age_s <= SENSOR_MAX_AGE_MAX_S):
            errors.append("sensor_max_age must be within 5 min-24 h")
        if not (
            ACTUATOR_CONFIRM_TIMEOUT_MIN_S
            <= self.actuator_confirm_timeout_s
            <= ACTUATOR_CONFIRM_TIMEOUT_MAX_S
        ):
            errors.append("actuator_confirm_timeout must be within 5 s-5 min")
        if not (
            MANUAL_MAX_DURATION_MIN_S <= self.manual_max_duration_s <= MANUAL_MAX_DURATION_MAX_S
        ):
            errors.append("manual_max_duration must be within 1 min-2 h")
        return errors

    def validate(self) -> None:
        """Raise ValueError listing every violated §9 bound."""
        errors = self.validation_errors()
        if errors:
            raise ValueError("; ".join(errors))


def _entity_domain(entity_id: str) -> str:
    domain, sep, obj = entity_id.partition(".")
    if not sep or not domain or not obj:
        return ""
    return domain


# ---------------------------------------------------------------------------
# Session structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SessionContext:
    """Active-session context (§12.2). Immutable; use evolve() for updates."""

    session_id: str
    owner_run_id: str
    config_fingerprint: str
    mode: SessionMode
    started_at_utc: datetime
    cycle: int = 0
    session_runtime_s: float = 0.0
    runtime_estimated: bool = False
    runtime_estimation_reason: RuntimeEstimationReason = RuntimeEstimationReason.NONE
    pulse_intent_at_utc: datetime | None = None
    pulse_commanded_at_utc: datetime | None = None
    pulse_confirmed_at_utc: datetime | None = None
    pulse_ends_at_utc: datetime | None = None
    sensor_fresh_until_utc: datetime | None = None
    sensor_freshness_watchdog_generation: int = 0
    off_confirmed_at_utc: datetime | None = None
    soak_ends_at_utc: datetime | None = None
    recheck_not_before_utc: datetime | None = None
    recheck_grace_deadline_at_utc: datetime | None = None
    manual_requested_duration_s: float | None = None
    manual_effective_duration_s: float | None = None
    manual_clamp_reasons: tuple[ManualClampReason, ...] = ()
    moisture_at_start: float | None = None
    last_recheck_value: float | None = None
    retained_sensor_fault: FaultCode | None = None
    pending_termination_reason: CompletionReason | None = None

    def __post_init__(self) -> None:
        _require_utc(self.started_at_utc, "started_at_utc")
        if self.retained_sensor_fault is not None and not self.retained_sensor_fault.is_sensor_only:
            raise ValueError("retained_sensor_fault must be a sensor-only fault")

    def evolve(self, **changes: object) -> SessionContext:
        """Return a copy with the given fields replaced."""
        return replace(self, **changes)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class SessionSummary:
    """Persisted last-session summary (§23.2)."""

    mode: SessionMode
    reason: CompletionReason
    runtime_s: float
    runtime_estimated: bool
    runtime_estimation_reason: RuntimeEstimationReason
    requested_duration_s: float | None
    effective_duration_s: float | None
    clamp_reasons: tuple[ManualClampReason, ...]
    cycles: int
    moisture_before: float | None
    moisture_after: float | None
    started_at_utc: datetime
    ended_at_utc: datetime


@dataclass(frozen=True, slots=True)
class DailyRuntime:
    """Current HA-local-day conservative runtime counter (§19.3, §23.2)."""

    date_local: date
    runtime_s: float

    def __post_init__(self) -> None:
        if self.runtime_s < 0:
            raise ValueError("runtime_s must be non-negative")


@dataclass(frozen=True, slots=True)
class GuardResult:
    """Outcome of an evaluation's guard checks (§14 legend, §16)."""

    passed: bool
    failed_guards: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.passed and self.failed_guards:
            raise ValueError("a passing guard result cannot list failed guards")
        if not self.passed and not self.failed_guards:
            raise ValueError("a failing guard result must name the failed guards")


# ---------------------------------------------------------------------------
# Normalized runtime facts (assembled by the controller, consumed purely)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ActuatorAssessment:
    """Conservative actuator view (§11.1): proven_off only on terminal proof."""

    available: bool
    proven_off: bool
    observed_on: bool

    def __post_init__(self) -> None:
        if self.proven_off and self.observed_on:
            raise ValueError("an actuator cannot be both proven OFF and observed ON")


@dataclass(frozen=True, slots=True)
class ResourceAssessment:
    """Global water-resource view supplied by SlotManager (§21)."""

    slot_granted: bool
    blockers_empty: bool


# ---------------------------------------------------------------------------
# Controller events (normalized inputs to the pure state machine)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AutoEvaluate:
    """Normal guarded AUTO evaluation trigger (§16)."""


@dataclass(frozen=True, slots=True)
class ManualStartRequested:
    requested_duration_s: float


@dataclass(frozen=True, slots=True)
class StopRequested:
    pass


@dataclass(frozen=True, slots=True)
class DisableRequested:
    pass


@dataclass(frozen=True, slots=True)
class EnableRequested:
    pass


@dataclass(frozen=True, slots=True)
class ClearFaultRequested:
    pass


@dataclass(frozen=True, slots=True)
class PulseDeadlineReached:
    pass


@dataclass(frozen=True, slots=True)
class ManualDeadlineReached:
    pass


@dataclass(frozen=True, slots=True)
class SoakDeadlineReached:
    pass


@dataclass(frozen=True, slots=True)
class GraceDeadlineReached:
    pass


@dataclass(frozen=True, slots=True)
class WatchdogFired:
    """AUTO freshness watchdog callback carrying its arm token (§18.5)."""

    token: WatchdogToken


@dataclass(frozen=True, slots=True)
class MoistureReport:
    """A normalized changed or unchanged moisture observation (§5.2, §10.3)."""

    observation: MoistureObservation


@dataclass(frozen=True, slots=True)
class OnConfirmed:
    at_utc: datetime


@dataclass(frozen=True, slots=True)
class OnConfirmTimeout:
    pass


@dataclass(frozen=True, slots=True)
class OffConfirmed:
    at_utc: datetime


@dataclass(frozen=True, slots=True)
class OffNotConfirmed:
    """OFF unproven after all retries (§11.3 step 6)."""


@dataclass(frozen=True, slots=True)
class ActuatorBecameUnavailable:
    pass


@dataclass(frozen=True, slots=True)
class ExternalActuatorOn:
    """Configured actuator observed ON without an integration command (§11.4)."""


@dataclass(frozen=True, slots=True)
class ExternalActuatorOff:
    """Terminal OFF proof observed (external stop or delayed OFF evidence)."""

    at_utc: datetime


@dataclass(frozen=True, slots=True)
class HomeAssistantShutdown:
    pass


@dataclass(frozen=True, slots=True)
class ConfigEntryReload:
    """Generic entry unload/reload preparation (§24.2)."""


@dataclass(frozen=True, slots=True)
class ConfigChangedPrepare:
    """Subentry reconfiguration/deletion preparation (§24.3)."""


@dataclass(frozen=True, slots=True)
class ConfigurationInvalid:
    """Configured entity removed or setup configuration invalid (T5/T53)."""

    at_setup: bool = False


@dataclass(frozen=True, slots=True)
class StoreIntegrityLost:
    """Initialized Store missing/corrupt/future/mismatched (§23.5, T52)."""


@dataclass(frozen=True, slots=True)
class StartupPersistedWatering:
    """Startup reconciliation of a persisted WATERING session (§25.2)."""

    finding: ActuatorFinding


@dataclass(frozen=True, slots=True)
class StartupPersistedSoaking:
    """Startup evaluation of a persisted SOAKING session (§25.3).

    The lifecycle layer performs every §25.3 trust check and passes only the
    verdict; on trust, current_run_id is the new owner for the §23.3 rebase.
    unsafe_fault carries the applicable actuator/integrity fault when the
    untrusted termination is unsafe (T51 "IDLE or FAULT if unsafe").
    """

    trusted: bool
    current_run_id: str | None = None
    unsafe_fault: FaultCode | None = None


@dataclass(frozen=True, slots=True)
class SlotGranted:
    """A queued slot grant was offered; every guard re-runs (§14 note, §16)."""


ControllerEvent = Union[  # noqa: UP007 - explicit union kept for readability
    AutoEvaluate,
    ManualStartRequested,
    StopRequested,
    DisableRequested,
    EnableRequested,
    ClearFaultRequested,
    PulseDeadlineReached,
    ManualDeadlineReached,
    SoakDeadlineReached,
    GraceDeadlineReached,
    WatchdogFired,
    MoistureReport,
    OnConfirmed,
    OnConfirmTimeout,
    OffConfirmed,
    OffNotConfirmed,
    ActuatorBecameUnavailable,
    ExternalActuatorOn,
    ExternalActuatorOff,
    HomeAssistantShutdown,
    ConfigEntryReload,
    ConfigChangedPrepare,
    ConfigurationInvalid,
    StoreIntegrityLost,
    StartupPersistedWatering,
    StartupPersistedSoaking,
    SlotGranted,
]


# ---------------------------------------------------------------------------
# Requested side effects (executed by the controller, never by the core)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PersistState:
    """Persist current safety state; tag names the §23.4 anchor."""

    tag: str


@dataclass(frozen=True, slots=True)
class TurnOn:
    """Issue the domain-appropriate ON action (§11.2)."""


@dataclass(frozen=True, slots=True)
class ExecuteOff:
    """Enter/join the one idempotent OFF operation (§11.3)."""

    defensive: bool = False


@dataclass(frozen=True, slots=True)
class ArmTimer:
    kind: TimerKind
    at_utc: datetime


@dataclass(frozen=True, slots=True)
class ArmWatchdog:
    """Arm/replace the AUTO freshness watchdog with this token (§18.5)."""

    token: WatchdogToken


@dataclass(frozen=True, slots=True)
class RequestSlot:
    pass


@dataclass(frozen=True, slots=True)
class ReleaseSlot:
    pass


@dataclass(frozen=True, slots=True)
class RequeueSlotTail:
    """Release and requeue at the tail after SOAKING (§21)."""


@dataclass(frozen=True, slots=True)
class AddBlocker:
    reason: BlockerReason


@dataclass(frozen=True, slots=True)
class RemoveBlocker:
    reason: BlockerReason


@dataclass(frozen=True, slots=True)
class SetExternalOn:
    """Record external-actuator-ON bookkeeping (§11.4, T54/T55)."""

    value: bool


@dataclass(frozen=True, slots=True)
class EmitSessionStarted:
    pass


@dataclass(frozen=True, slots=True)
class EmitSessionFinished:
    pass


@dataclass(frozen=True, slots=True)
class EmitFaultSet:
    fault: FaultCode
    replaces: FaultCode | None = None


@dataclass(frozen=True, slots=True)
class EmitFaultCleared:
    fault: FaultCode


@dataclass(frozen=True, slots=True)
class ScheduleEvaluation:
    """Request a normal guarded AUTO evaluation soon (T47)."""


Action = Union[  # noqa: UP007 - explicit union kept for readability
    PersistState,
    TurnOn,
    ExecuteOff,
    ArmTimer,
    ArmWatchdog,
    RequestSlot,
    ReleaseSlot,
    RequeueSlotTail,
    AddBlocker,
    RemoveBlocker,
    SetExternalOn,
    EmitSessionStarted,
    EmitSessionFinished,
    EmitFaultSet,
    EmitFaultCleared,
    ScheduleEvaluation,
]


@dataclass(frozen=True, slots=True)
class SessionIdentity:
    """Externally supplied identity for a session the decision may create.

    The pure core is deterministic and cannot generate UUIDs or fingerprints;
    the controller supplies them (§37). Consumed only by session-creating
    rows (T1, T3, T40).
    """

    session_id: str
    owner_run_id: str
    config_fingerprint: str


# ---------------------------------------------------------------------------
# Transition input and result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TransitionInput:
    """Complete normalized input for one pure decision (§37).

    Assembled by the controller under the zone lock. Same input plus
    persisted state must always produce the same Decision.
    """

    now_utc: datetime
    config: ZoneConfig
    state: ControllerState
    enabled: bool
    session: SessionContext | None
    active_fault: FaultCode | None
    secondary_fault: FaultCode | None
    observation: MoistureObservation
    daily_runtime_s: float
    last_session_end_utc: datetime | None
    actuator: ActuatorAssessment
    resource: ResourceAssessment
    armed_watchdog: WatchdogToken | None
    event: ControllerEvent
    # True while this zone's actuator is externally ON/occupying the water
    # resource (§11.4 bookkeeping; guards T58/T59).
    external_on: bool = False
    # Identity for a session this decision may create (T1/T3/T40).
    new_session_identity: SessionIdentity | None = None

    def __post_init__(self) -> None:
        _require_utc(self.now_utc, "now_utc")
        if self.last_session_end_utc is not None:
            _require_utc(self.last_session_end_utc, "last_session_end_utc")
        if self.daily_runtime_s < 0:
            raise ValueError("daily_runtime_s must be non-negative")


@dataclass(frozen=True, slots=True)
class Decision:
    """Pure transition result: requested effects, never performed ones.

    transition_id carries the §14 row ("T1".."T59") when the decision is a
    formal state transition; commit-phase, bookkeeping, and no-op decisions
    carry None (§14 note after T59).
    """

    transition_id: str | None
    new_state: ControllerState | None
    actions: tuple[Action, ...] = ()
    reason: CompletionReason | None = None
    fault: FaultCode | None = None
    secondary_fault: FaultCode | None = None
    clear_fault: bool = False
    session: SessionContext | None = None
    clear_session: bool = False
    # Closed-session snapshot accompanying clear_session, so the controller
    # can build the §23.2 last-session summary without recomputing closure.
    final_session: SessionContext | None = None
    guard_result: GuardResult | None = None
    no_op: bool = False

    def __post_init__(self) -> None:
        if self.no_op and (self.new_state is not None or self.actions):
            raise ValueError("a no-op decision cannot change state or request actions")
        if self.session is not None and self.clear_session:
            raise ValueError("cannot both set and clear the session")
        if self.final_session is not None and not self.clear_session:
            raise ValueError("final_session accompanies clear_session only")


def _require_utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be in UTC")


# ---------------------------------------------------------------------------
# Runtime Store schema 1 (§23.2): pure data structures and strict
# serialization. Storage I/O lives in storage.py; the shapes live here so
# round-trip behaviour is provable without Home Assistant.
# ---------------------------------------------------------------------------


class StoreDataError(ValueError):
    """Base error for runtime-Store payload problems."""


class MalformedStoreData(StoreDataError):
    """Payload does not match schema 1; follows the §23.5 integrity policy."""


class FutureStoreVersion(StoreDataError):
    """Payload declares a future schema; never downgraded/defaulted (§23.5)."""


@dataclass(frozen=True, slots=True)
class RunIds:
    """Run-ID protocol state (§23.3)."""

    active_run_id: str | None
    last_clean_shutdown_run_id: str | None

    @property
    def previous_run_was_clean(self) -> bool:
        """Clean only when both are non-null and equal (§23.3)."""
        return (
            self.active_run_id is not None and self.active_run_id == self.last_clean_shutdown_run_id
        )


@dataclass(frozen=True, slots=True)
class ZoneRecord:
    """Per-zone persisted safety state (§23.2)."""

    state: ControllerState
    enabled: bool
    active_fault: FaultCode | None = None
    secondary_fault: FaultCode | None = None
    last_session_end_utc: datetime | None = None
    last_auto_session_start_utc: datetime | None = None
    daily: DailyRuntime | None = None
    last_session_summary: SessionSummary | None = None
    session: SessionContext | None = None

    def evolve(self, **changes: object) -> ZoneRecord:
        return replace(self, **changes)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class StoreData:
    """Complete runtime Store snapshot (§23.2 schema version 1)."""

    generation_id: str
    store_revision: int
    run: RunIds
    zones: dict[str, ZoneRecord]
    version: int = 1

    def evolve(self, **changes: object) -> StoreData:
        return replace(self, **changes)  # type: ignore[arg-type]


def _dt_to_iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _iso_to_dt(value: object, name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise MalformedStoreData(f"{name} must be an ISO string or null")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as err:
        raise MalformedStoreData(f"{name} is not a valid ISO datetime") from err
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise MalformedStoreData(f"{name} must be timezone-aware UTC")
    return parsed


def _enum_or_none(enum_cls: type, value: object, name: str):
    if value is None:
        return None
    try:
        return enum_cls(value)
    except (ValueError, TypeError) as err:
        raise MalformedStoreData(f"{name} has unknown value {value!r}") from err


def _require(mapping: object, key: str, context: str) -> object:
    if not isinstance(mapping, dict):
        raise MalformedStoreData(f"{context} must be an object")
    if key not in mapping:
        raise MalformedStoreData(f"{context} is missing {key!r}")
    return mapping[key]


def session_to_dict(session: SessionContext) -> dict:
    """Serialize the §23.2 persisted session fields.

    Live-only fields (sensor_fresh_until_utc, watchdog generation,
    last_recheck_value, pending_termination_reason) are deliberately not
    persisted: WATERING never resumes and blockers are rebuilt (§23.2).
    """
    return {
        "session_id": session.session_id,
        "owner_run_id": session.owner_run_id,
        "config_fingerprint": session.config_fingerprint,
        "mode": session.mode.value,
        "started_at_utc": _dt_to_iso(session.started_at_utc),
        "cycle": session.cycle,
        "session_runtime_s": session.session_runtime_s,
        "runtime_estimated": session.runtime_estimated,
        "runtime_estimation_reason": session.runtime_estimation_reason.value,
        "pulse_intent_at_utc": _dt_to_iso(session.pulse_intent_at_utc),
        "pulse_commanded_at_utc": _dt_to_iso(session.pulse_commanded_at_utc),
        "pulse_confirmed_at_utc": _dt_to_iso(session.pulse_confirmed_at_utc),
        "pulse_ends_at_utc": _dt_to_iso(session.pulse_ends_at_utc),
        "off_confirmed_at_utc": _dt_to_iso(session.off_confirmed_at_utc),
        "soak_ends_at_utc": _dt_to_iso(session.soak_ends_at_utc),
        "recheck_not_before_utc": _dt_to_iso(session.recheck_not_before_utc),
        "recheck_grace_deadline_at_utc": _dt_to_iso(session.recheck_grace_deadline_at_utc),
        "manual_requested_duration_s": session.manual_requested_duration_s,
        "manual_effective_duration_s": session.manual_effective_duration_s,
        "manual_clamp_reasons": [r.value for r in session.manual_clamp_reasons],
        "retained_sensor_fault": (
            session.retained_sensor_fault.value if session.retained_sensor_fault else None
        ),
        "moisture_at_start": session.moisture_at_start,
    }


def session_from_dict(data: object) -> SessionContext:
    started = _iso_to_dt(_require(data, "started_at_utc", "session"), "started_at_utc")
    if started is None:
        raise MalformedStoreData("session.started_at_utc must not be null")
    assert isinstance(data, dict)
    clamp_raw = _require(data, "manual_clamp_reasons", "session")
    if not isinstance(clamp_raw, list):
        raise MalformedStoreData("session.manual_clamp_reasons must be a list")
    try:
        return SessionContext(
            session_id=str(_require(data, "session_id", "session")),
            owner_run_id=str(_require(data, "owner_run_id", "session")),
            config_fingerprint=str(_require(data, "config_fingerprint", "session")),
            mode=SessionMode(_require(data, "mode", "session")),
            started_at_utc=started,
            cycle=int(_require(data, "cycle", "session")),
            session_runtime_s=float(_require(data, "session_runtime_s", "session")),
            runtime_estimated=bool(_require(data, "runtime_estimated", "session")),
            runtime_estimation_reason=RuntimeEstimationReason(
                _require(data, "runtime_estimation_reason", "session")
            ),
            pulse_intent_at_utc=_iso_to_dt(data.get("pulse_intent_at_utc"), "pulse_intent_at_utc"),
            pulse_commanded_at_utc=_iso_to_dt(
                data.get("pulse_commanded_at_utc"), "pulse_commanded_at_utc"
            ),
            pulse_confirmed_at_utc=_iso_to_dt(
                data.get("pulse_confirmed_at_utc"), "pulse_confirmed_at_utc"
            ),
            pulse_ends_at_utc=_iso_to_dt(data.get("pulse_ends_at_utc"), "pulse_ends_at_utc"),
            off_confirmed_at_utc=_iso_to_dt(
                data.get("off_confirmed_at_utc"), "off_confirmed_at_utc"
            ),
            soak_ends_at_utc=_iso_to_dt(data.get("soak_ends_at_utc"), "soak_ends_at_utc"),
            recheck_not_before_utc=_iso_to_dt(
                data.get("recheck_not_before_utc"), "recheck_not_before_utc"
            ),
            recheck_grace_deadline_at_utc=_iso_to_dt(
                data.get("recheck_grace_deadline_at_utc"), "recheck_grace_deadline_at_utc"
            ),
            manual_requested_duration_s=_float_or_none(data.get("manual_requested_duration_s")),
            manual_effective_duration_s=_float_or_none(data.get("manual_effective_duration_s")),
            manual_clamp_reasons=tuple(ManualClampReason(r) for r in clamp_raw),
            retained_sensor_fault=_enum_or_none(
                FaultCode, data.get("retained_sensor_fault"), "retained_sensor_fault"
            ),
            moisture_at_start=_float_or_none(data.get("moisture_at_start")),
        )
    except (TypeError, ValueError) as err:
        if isinstance(err, StoreDataError):
            raise
        raise MalformedStoreData(f"session payload invalid: {err}") from err


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MalformedStoreData(f"expected number, got {value!r}")
    return float(value)


def summary_to_dict(summary: SessionSummary) -> dict:
    return {
        "mode": summary.mode.value,
        "reason": summary.reason.value,
        "runtime_s": summary.runtime_s,
        "runtime_estimated": summary.runtime_estimated,
        "runtime_estimation_reason": summary.runtime_estimation_reason.value,
        "requested_duration_s": summary.requested_duration_s,
        "effective_duration_s": summary.effective_duration_s,
        "clamp_reasons": [r.value for r in summary.clamp_reasons],
        "cycles": summary.cycles,
        "moisture_before": summary.moisture_before,
        "moisture_after": summary.moisture_after,
        "started_at_utc": _dt_to_iso(summary.started_at_utc),
        "ended_at_utc": _dt_to_iso(summary.ended_at_utc),
    }


def summary_from_dict(data: object) -> SessionSummary:
    started = _iso_to_dt(_require(data, "started_at_utc", "summary"), "started_at_utc")
    ended = _iso_to_dt(_require(data, "ended_at_utc", "summary"), "ended_at_utc")
    if started is None or ended is None:
        raise MalformedStoreData("summary timestamps must not be null")
    assert isinstance(data, dict)
    clamp_raw = _require(data, "clamp_reasons", "summary")
    if not isinstance(clamp_raw, list):
        raise MalformedStoreData("summary.clamp_reasons must be a list")
    try:
        return SessionSummary(
            mode=SessionMode(_require(data, "mode", "summary")),
            reason=CompletionReason(_require(data, "reason", "summary")),
            runtime_s=float(_require(data, "runtime_s", "summary")),
            runtime_estimated=bool(_require(data, "runtime_estimated", "summary")),
            runtime_estimation_reason=RuntimeEstimationReason(
                _require(data, "runtime_estimation_reason", "summary")
            ),
            requested_duration_s=_float_or_none(data.get("requested_duration_s")),
            effective_duration_s=_float_or_none(data.get("effective_duration_s")),
            clamp_reasons=tuple(ManualClampReason(r) for r in clamp_raw),
            cycles=int(_require(data, "cycles", "summary")),
            moisture_before=_float_or_none(data.get("moisture_before")),
            moisture_after=_float_or_none(data.get("moisture_after")),
            started_at_utc=started,
            ended_at_utc=ended,
        )
    except (TypeError, ValueError) as err:
        if isinstance(err, StoreDataError):
            raise
        raise MalformedStoreData(f"summary payload invalid: {err}") from err


def zone_record_to_dict(record: ZoneRecord) -> dict:
    return {
        "state": record.state.value,
        "enabled": record.enabled,
        "active_fault": record.active_fault.value if record.active_fault else None,
        "secondary_fault": record.secondary_fault.value if record.secondary_fault else None,
        "last_session_end_utc": _dt_to_iso(record.last_session_end_utc),
        "last_auto_session_start_utc": _dt_to_iso(record.last_auto_session_start_utc),
        "daily": (
            {"date_local": record.daily.date_local.isoformat(), "runtime_s": record.daily.runtime_s}
            if record.daily
            else None
        ),
        "last_session_summary": (
            summary_to_dict(record.last_session_summary) if record.last_session_summary else None
        ),
        "session": session_to_dict(record.session) if record.session else None,
    }


def zone_record_from_dict(data: object) -> ZoneRecord:
    state_raw = _require(data, "state", "zone")
    assert isinstance(data, dict)
    try:
        state = ControllerState(state_raw)
    except ValueError as err:
        raise MalformedStoreData(f"zone.state has unknown value {state_raw!r}") from err
    enabled = _require(data, "enabled", "zone")
    if not isinstance(enabled, bool):
        raise MalformedStoreData("zone.enabled must be a boolean")
    daily_raw = data.get("daily")
    daily = None
    if daily_raw is not None:
        date_raw = _require(daily_raw, "date_local", "zone.daily")
        runtime_raw = _require(daily_raw, "runtime_s", "zone.daily")
        try:
            daily = DailyRuntime(
                date_local=date.fromisoformat(str(date_raw)),
                runtime_s=float(runtime_raw),  # type: ignore[arg-type]
            )
        except (TypeError, ValueError) as err:
            raise MalformedStoreData(f"zone.daily invalid: {err}") from err
    summary_raw = data.get("last_session_summary")
    session_raw = data.get("session")
    return ZoneRecord(
        state=state,
        enabled=enabled,
        active_fault=_enum_or_none(FaultCode, data.get("active_fault"), "zone.active_fault"),
        secondary_fault=_enum_or_none(
            FaultCode, data.get("secondary_fault"), "zone.secondary_fault"
        ),
        last_session_end_utc=_iso_to_dt(
            data.get("last_session_end_utc"), "zone.last_session_end_utc"
        ),
        last_auto_session_start_utc=_iso_to_dt(
            data.get("last_auto_session_start_utc"), "zone.last_auto_session_start_utc"
        ),
        daily=daily,
        last_session_summary=(summary_from_dict(summary_raw) if summary_raw is not None else None),
        session=session_from_dict(session_raw) if session_raw is not None else None,
    )


def store_data_to_dict(data: StoreData) -> dict:
    return {
        "version": data.version,
        "generation_id": data.generation_id,
        "store_revision": data.store_revision,
        "run": {
            "active_run_id": data.run.active_run_id,
            "last_clean_shutdown_run_id": data.run.last_clean_shutdown_run_id,
        },
        "zones": {zone_id: zone_record_to_dict(record) for zone_id, record in data.zones.items()},
    }


def store_data_from_dict(raw: object) -> StoreData:
    """Strictly parse a schema-1 payload (§23.2, §23.5).

    Raises FutureStoreVersion for a newer schema (never downgraded or
    defaulted) and MalformedStoreData for any structural violation.
    """
    version_raw = _require(raw, "version", "store")
    if not isinstance(version_raw, int) or isinstance(version_raw, bool):
        raise MalformedStoreData("store.version must be an integer")
    if version_raw > 1:
        raise FutureStoreVersion(f"store schema {version_raw} is newer than 1")
    if version_raw < 1:
        raise MalformedStoreData(f"store schema {version_raw} is invalid")
    assert isinstance(raw, dict)
    generation = _require(raw, "generation_id", "store")
    if not isinstance(generation, str) or not generation:
        raise MalformedStoreData("store.generation_id must be a non-empty string")
    revision = _require(raw, "store_revision", "store")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise MalformedStoreData("store.store_revision must be a positive integer")
    run_raw = _require(raw, "run", "store")
    active = _require(run_raw, "active_run_id", "store.run")
    last_clean = _require(run_raw, "last_clean_shutdown_run_id", "store.run")
    for name, value in (("active_run_id", active), ("last_clean_shutdown_run_id", last_clean)):
        if value is not None and not isinstance(value, str):
            raise MalformedStoreData(f"store.run.{name} must be a string or null")
    zones_raw = _require(raw, "zones", "store")
    if not isinstance(zones_raw, dict):
        raise MalformedStoreData("store.zones must be an object")
    zones = {str(zone_id): zone_record_from_dict(record) for zone_id, record in zones_raw.items()}
    return StoreData(
        version=version_raw,
        generation_id=generation,
        store_revision=revision,
        run=RunIds(active_run_id=active, last_clean_shutdown_run_id=last_clean),
        zones=zones,
    )


# ---------------------------------------------------------------------------
# Conservative runtime accounting across HA-local calendar days (§19.3)
# ---------------------------------------------------------------------------


def split_interval_by_local_days(
    start_utc: datetime, end_utc: datetime, tz: tzinfo
) -> list[tuple[date, float]]:
    """Split [start, end] at HA-local calendar-day boundaries (§19.3).

    Boundaries are real local midnights converted to UTC — never fixed
    24-hour additions, because DST days may be 23 or 25 hours. Returns one
    (local_date, seconds) segment per overlapped local day, in order. A
    zero-length interval yields one zero-second segment for its local date.
    """
    _require_utc(start_utc, "start_utc")
    _require_utc(end_utc, "end_utc")
    if end_utc < start_utc:
        raise ValueError("end_utc must not precede start_utc")
    segments: list[tuple[date, float]] = []
    cursor = start_utc
    while cursor < end_utc:
        local = cursor.astimezone(tz)
        next_midnight_local = datetime.combine(local.date() + timedelta(days=1), time(0), tzinfo=tz)
        boundary = next_midnight_local.astimezone(UTC)
        if boundary <= cursor:
            # Pathological zone data; never loop — charge the remainder here.
            boundary = end_utc
        segment_end = min(boundary, end_utc)
        segments.append((local.date(), (segment_end - cursor).total_seconds()))
        cursor = segment_end
    if not segments:
        segments.append((start_utc.astimezone(tz).date(), 0.0))
    return segments


def current_day_charge(
    start_utc: datetime, end_utc: datetime, tz: tzinfo, current_local_date: date
) -> float:
    """Seconds of [start, end] overlapping the given HA-local date (§19.3)."""
    return sum(
        seconds
        for day, seconds in split_interval_by_local_days(start_utc, end_utc, tz)
        if day == current_local_date
    )


def config_fingerprint(config: ZoneConfig, ha_timezone: str) -> str:
    """Stable config fingerprint (§23.2).

    SHA-256 digest of versioned canonical JSON containing the configured
    sensor/actuator IDs, every §9 zone setting, and the HA timezone. Keys
    are sorted and durations use integer seconds. Deterministic equality,
    not secrecy; a changed fingerprint makes persisted SOAKING ineligible
    for continuation.
    """
    import hashlib
    import json

    payload = {
        "fingerprint_version": 1,
        "name": config.name,
        "moisture_sensor": config.moisture_sensor,
        "actuator": config.actuator,
        "start_threshold": config.start_threshold,
        "target_threshold": config.target_threshold,
        "pulse_duration_s": int(config.pulse_duration_s),
        "soak_duration_s": int(config.soak_duration_s),
        "max_cycles": config.max_cycles,
        "max_session_runtime_s": int(config.max_session_runtime_s),
        "max_daily_runtime_s": int(config.max_daily_runtime_s),
        "min_session_interval_s": int(config.min_session_interval_s),
        "sensor_max_age_s": int(config.sensor_max_age_s),
        "actuator_confirm_timeout_s": int(config.actuator_confirm_timeout_s),
        "manual_max_duration_s": int(config.manual_max_duration_s),
        "ha_timezone": ha_timezone,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
