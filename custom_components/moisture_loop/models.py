"""Pure domain models for Moisture Loop.

Home Assistant-independent vocabulary and data structures implementing
SPECIFICATION.md §§6, 9, 12, 18.2, 19, 20, 23.2 and 26. This module must not
import homeassistant and performs no I/O (§37). All datetimes are
timezone-aware UTC; all durations are seconds.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from enum import StrEnum
from typing import Union

from .const import (
    ACTUATOR_CONFIRM_TIMEOUT_MAX_S,
    ACTUATOR_CONFIRM_TIMEOUT_MIN_S,
    ACTUATOR_DOMAIN_SWITCH,
    ACTUATOR_DOMAIN_VALVE,
    DOMAIN,
    LEGACY_STORE_SCHEMA_VERSION,
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
    STORE_SCHEMA_VERSION,
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
    """Approved water-resource blocker reasons (§6, §21)."""

    EXTERNAL_FLOW = "external_flow"
    INTEGRATION_OFF_UNCONFIRMED = "integration_off_unconfirmed"
    ACTUATOR_NOT_PROVEN_OFF = "actuator_not_proven_off"


class RuntimeLifecycle(StrEnum):
    """Safety-object lifecycle, orthogonal to ControllerState (§12.4)."""

    ACTIVE = "active"
    DELETE_PENDING = "delete_pending"
    RETIRED = "retired"


class IdentityStatus(StrEnum):
    """Durable actuator identity resolution status (§23.2)."""

    REGISTRY_CONFIRMED = "registry_confirmed"
    REGISTRY_UNAVAILABLE = "registry_unavailable"
    MISSING = "missing"
    CONFLICT = "conflict"


class PossibleFlowOwner(StrEnum):
    """Known ownership of possible actuator flow (§23.2)."""

    INTEGRATION = "integration"
    EXTERNAL = "external"


class IdentityIncidentKind(StrEnum):
    """Persisted identity incidents requiring later reconciliation/Repair."""

    MIGRATION_UNRESOLVED = "migration_unresolved"
    IDENTITY_MISSING = "identity_missing"
    IDENTITY_CONFLICT = "identity_conflict"


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
# Historical runtime Store schema 1 (§23.2.1). ZoneRecord remains only as a
# temporary compatibility projection for untouched spec.3 runtime callers;
# it is not the canonical schema-2 persistence model.
# ---------------------------------------------------------------------------


class StoreDataError(ValueError):
    """Base error for runtime-Store payload problems."""


class MalformedStoreData(StoreDataError):
    """Payload does not match its declared schema (§23.5)."""


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
    """Historical schema-1 record / temporary runtime projection only."""

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
class Schema1StoreData:
    """Strictly parsed historical schema-1 Store snapshot (§23.2.1)."""

    generation_id: str
    store_revision: int
    run: RunIds
    zones: dict[str, ZoneRecord]
    version: int = LEGACY_STORE_SCHEMA_VERSION

    def evolve(self, **changes: object) -> Schema1StoreData:
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


def _require_exact_keys(mapping: object, expected: set[str], context: str) -> dict:
    if not isinstance(mapping, dict):
        raise MalformedStoreData(f"{context} must be an object")
    keys = set(mapping)
    if keys != expected:
        missing = sorted(expected - keys)
        extra = sorted(str(key) for key in keys - expected)
        raise MalformedStoreData(f"{context} keys invalid; missing={missing}, extra={extra}")
    return mapping


def _strict_string(value: object, name: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value:
        raise MalformedStoreData(f"{name} must be a non-empty string")
    return value


def _strict_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise MalformedStoreData(f"{name} must be a boolean")
    return value


def _strict_int(value: object, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise MalformedStoreData(f"{name} must be an integer >= {minimum}")
    return value


def _strict_float(value: object, name: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MalformedStoreData(f"{name} must be a finite number >= {minimum}")
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise MalformedStoreData(f"{name} must be a finite number >= {minimum}")
    return result


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
    data = _require_exact_keys(
        data,
        {
            "session_id",
            "owner_run_id",
            "config_fingerprint",
            "mode",
            "started_at_utc",
            "cycle",
            "session_runtime_s",
            "runtime_estimated",
            "runtime_estimation_reason",
            "pulse_intent_at_utc",
            "pulse_commanded_at_utc",
            "pulse_confirmed_at_utc",
            "pulse_ends_at_utc",
            "off_confirmed_at_utc",
            "soak_ends_at_utc",
            "recheck_not_before_utc",
            "recheck_grace_deadline_at_utc",
            "manual_requested_duration_s",
            "manual_effective_duration_s",
            "manual_clamp_reasons",
            "retained_sensor_fault",
            "moisture_at_start",
        },
        "session",
    )
    started = _iso_to_dt(_require(data, "started_at_utc", "session"), "started_at_utc")
    if started is None:
        raise MalformedStoreData("session.started_at_utc must not be null")
    assert isinstance(data, dict)
    clamp_raw = _require(data, "manual_clamp_reasons", "session")
    if not isinstance(clamp_raw, list):
        raise MalformedStoreData("session.manual_clamp_reasons must be a list")
    try:
        return SessionContext(
            session_id=_strict_string(_require(data, "session_id", "session"), "session_id"),
            owner_run_id=_strict_string(_require(data, "owner_run_id", "session"), "owner_run_id"),
            config_fingerprint=_strict_string(
                _require(data, "config_fingerprint", "session"), "config_fingerprint"
            ),
            mode=SessionMode(_require(data, "mode", "session")),
            started_at_utc=started,
            cycle=_strict_int(_require(data, "cycle", "session"), "session.cycle"),
            session_runtime_s=_strict_float(
                _require(data, "session_runtime_s", "session"), "session.session_runtime_s"
            ),
            runtime_estimated=_strict_bool(
                _require(data, "runtime_estimated", "session"), "session.runtime_estimated"
            ),
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
    result = float(value)
    if not math.isfinite(result):
        raise MalformedStoreData(f"expected finite number, got {value!r}")
    return result


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
    data = _require_exact_keys(
        data,
        {
            "mode",
            "reason",
            "runtime_s",
            "runtime_estimated",
            "runtime_estimation_reason",
            "requested_duration_s",
            "effective_duration_s",
            "clamp_reasons",
            "cycles",
            "moisture_before",
            "moisture_after",
            "started_at_utc",
            "ended_at_utc",
        },
        "summary",
    )
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
            runtime_s=_strict_float(_require(data, "runtime_s", "summary"), "summary.runtime_s"),
            runtime_estimated=_strict_bool(
                _require(data, "runtime_estimated", "summary"), "summary.runtime_estimated"
            ),
            runtime_estimation_reason=RuntimeEstimationReason(
                _require(data, "runtime_estimation_reason", "summary")
            ),
            requested_duration_s=_float_or_none(data.get("requested_duration_s")),
            effective_duration_s=_float_or_none(data.get("effective_duration_s")),
            clamp_reasons=tuple(ManualClampReason(r) for r in clamp_raw),
            cycles=_strict_int(_require(data, "cycles", "summary"), "summary.cycles"),
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
    data = _require_exact_keys(
        data,
        {
            "state",
            "enabled",
            "active_fault",
            "secondary_fault",
            "last_session_end_utc",
            "last_auto_session_start_utc",
            "daily",
            "last_session_summary",
            "session",
        },
        "zone",
    )
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
            daily_raw = _require_exact_keys(daily_raw, {"date_local", "runtime_s"}, "zone.daily")
            if not isinstance(date_raw, str):
                raise ValueError("date_local must be a string")
            daily = DailyRuntime(
                date_local=date.fromisoformat(date_raw),
                runtime_s=_strict_float(runtime_raw, "zone.daily.runtime_s"),
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


def schema1_store_data_to_dict(data: Schema1StoreData) -> dict:
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


def schema1_store_data_from_dict(raw: object) -> Schema1StoreData:
    """Strictly parse a schema-1 payload (§23.2, §23.5).

    Raises FutureStoreVersion for a newer schema (never downgraded or
    defaulted) and MalformedStoreData for any structural violation.
    """
    raw = _require_exact_keys(
        raw, {"version", "generation_id", "store_revision", "run", "zones"}, "store"
    )
    version_raw = _require(raw, "version", "store")
    if not isinstance(version_raw, int) or isinstance(version_raw, bool):
        raise MalformedStoreData("store.version must be an integer")
    if version_raw > LEGACY_STORE_SCHEMA_VERSION:
        raise FutureStoreVersion(
            f"store schema {version_raw} is newer than {LEGACY_STORE_SCHEMA_VERSION}"
        )
    if version_raw < LEGACY_STORE_SCHEMA_VERSION:
        raise MalformedStoreData(f"store schema {version_raw} is invalid")
    assert isinstance(raw, dict)
    generation = _require(raw, "generation_id", "store")
    if not isinstance(generation, str) or not generation:
        raise MalformedStoreData("store.generation_id must be a non-empty string")
    revision = _require(raw, "store_revision", "store")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise MalformedStoreData("store.store_revision must be a positive integer")
    run_raw = _require_exact_keys(
        _require(raw, "run", "store"),
        {"active_run_id", "last_clean_shutdown_run_id"},
        "store.run",
    )
    active = _require(run_raw, "active_run_id", "store.run")
    last_clean = _require(run_raw, "last_clean_shutdown_run_id", "store.run")
    for name, value in (("active_run_id", active), ("last_clean_shutdown_run_id", last_clean)):
        if value is not None and (not isinstance(value, str) or not value):
            raise MalformedStoreData(f"store.run.{name} must be a non-empty string or null")
    zones_raw = _require(raw, "zones", "store")
    if not isinstance(zones_raw, dict):
        raise MalformedStoreData("store.zones must be an object")
    zones: dict[str, ZoneRecord] = {}
    for zone_id, record in zones_raw.items():
        if not isinstance(zone_id, str) or not zone_id:
            raise MalformedStoreData("store.zones keys must be non-empty strings")
        zones[zone_id] = zone_record_from_dict(record)
    return Schema1StoreData(
        version=version_raw,
        generation_id=generation,
        store_revision=revision,
        run=RunIds(active_run_id=active, last_clean_shutdown_run_id=last_clean),
        zones=zones,
    )


# ---------------------------------------------------------------------------
# Canonical runtime Store schema 2 (§23.2)
# ---------------------------------------------------------------------------


_ACTUATOR_FAULTS = frozenset(
    {
        FaultCode.ACTUATOR_UNAVAILABLE,
        FaultCode.ACTUATOR_ON_TIMEOUT,
        FaultCode.ACTUATOR_OFF_TIMEOUT,
        FaultCode.RESTORED_FROM_UNSAFE_STATE,
    }
)
_ZONE_FAULTS = frozenset(
    {
        FaultCode.SENSOR_UNAVAILABLE,
        FaultCode.SENSOR_STALE,
        FaultCode.SENSOR_INVALID,
        FaultCode.CONFIGURATION_INVALID,
    }
)


@dataclass(frozen=True, slots=True)
class SensorIdentity:
    """Current logical-zone sensor identity; never actuator authority."""

    registry_entry_id: str | None
    last_known_entity_id: str | None

    def __post_init__(self) -> None:
        if self.registry_entry_id == "" or self.last_known_entity_id == "":
            raise ValueError("sensor identity values must be non-empty or null")
        if (
            self.last_known_entity_id is not None
            and _entity_domain(self.last_known_entity_id) != SENSOR_DOMAIN
        ):
            raise ValueError("sensor last_known_entity_id must use the sensor domain")


@dataclass(frozen=True, slots=True)
class AppliedEntityIdentity:
    """Immutable normalized identity captured in an applied shadow."""

    registry_entry_id: str | None
    last_known_entity_id: str
    domain: str

    def __post_init__(self) -> None:
        if (
            not self.last_known_entity_id
            or _entity_domain(self.last_known_entity_id) != self.domain
        ):
            raise ValueError("applied entity identity/domain mismatch")
        if self.registry_entry_id == "":
            raise ValueError("registry_entry_id must be non-empty or null")


@dataclass(frozen=True, slots=True)
class ActuatorIdentity:
    """Durable actuator safety identity and retained OFF metadata (§23.2)."""

    registry_entry_id: str | None
    last_known_entity_id: str | None
    domain: str | None
    identity_status: IdentityStatus
    off_service: str | None
    confirm_timeout_s: int | None

    def __post_init__(self) -> None:
        if self.registry_entry_id == "" or self.last_known_entity_id == "":
            raise ValueError("actuator identity strings must be non-empty or null")
        if self.domain not in (None, ACTUATOR_DOMAIN_SWITCH, ACTUATOR_DOMAIN_VALVE):
            raise ValueError("actuator identity domain must be switch, valve, or null")
        if self.last_known_entity_id is not None and (
            self.domain is None or _entity_domain(self.last_known_entity_id) != self.domain
        ):
            raise ValueError("actuator entity ID/domain mismatch")
        expected_service = {
            ACTUATOR_DOMAIN_SWITCH: "switch.turn_off",
            ACTUATOR_DOMAIN_VALVE: "valve.close_valve",
        }.get(self.domain)
        if self.off_service != expected_service:
            raise ValueError("actuator OFF service/domain mismatch")
        if self.confirm_timeout_s is not None and (
            isinstance(self.confirm_timeout_s, bool) or self.confirm_timeout_s <= 0
        ):
            raise ValueError("confirm_timeout_s must be positive or null")
        unresolved = self.identity_status in (IdentityStatus.MISSING, IdentityStatus.CONFLICT)
        if not unresolved and (
            self.last_known_entity_id is None
            or self.domain is None
            or self.confirm_timeout_s is None
        ):
            raise ValueError("resolved actuator identity requires entity/domain/timeout metadata")
        if (
            self.identity_status is IdentityStatus.REGISTRY_CONFIRMED
            and self.registry_entry_id is None
        ):
            raise ValueError("registry_confirmed identity requires registry_entry_id")
        if (
            self.identity_status is IdentityStatus.REGISTRY_UNAVAILABLE
            and self.registry_entry_id is not None
        ):
            raise ValueError("registry_unavailable identity cannot carry registry_entry_id")


@dataclass(frozen=True, slots=True)
class NormalizedZoneSettings:
    """Serialization-friendly immutable §9 settings in an applied shadow."""

    name: str
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

    @classmethod
    def from_config(cls, config: ZoneConfig) -> NormalizedZoneSettings:
        config.validate()
        return cls(
            name=config.name,
            start_threshold=config.start_threshold,
            target_threshold=config.target_threshold,
            pulse_duration_s=config.pulse_duration_s,
            soak_duration_s=config.soak_duration_s,
            max_cycles=config.max_cycles,
            max_session_runtime_s=config.max_session_runtime_s,
            max_daily_runtime_s=config.max_daily_runtime_s,
            min_session_interval_s=config.min_session_interval_s,
            sensor_max_age_s=config.sensor_max_age_s,
            actuator_confirm_timeout_s=config.actuator_confirm_timeout_s,
            manual_max_duration_s=config.manual_max_duration_s,
        )

    def validate(self, sensor_entity_id: str, actuator_entity_id: str) -> None:
        ZoneConfig(
            name=self.name,
            moisture_sensor=sensor_entity_id,
            actuator=actuator_entity_id,
            start_threshold=self.start_threshold,
            target_threshold=self.target_threshold,
            pulse_duration_s=self.pulse_duration_s,
            soak_duration_s=self.soak_duration_s,
            max_cycles=self.max_cycles,
            max_session_runtime_s=self.max_session_runtime_s,
            max_daily_runtime_s=self.max_daily_runtime_s,
            min_session_interval_s=self.min_session_interval_s,
            sensor_max_age_s=self.sensor_max_age_s,
            actuator_confirm_timeout_s=self.actuator_confirm_timeout_s,
            manual_max_duration_s=self.manual_max_duration_s,
        ).validate()


@dataclass(frozen=True, slots=True)
class AppliedConfigurationShadow:
    """Immutable normalized copy of the configuration actually applied."""

    subentry_id: str
    config_fingerprint: str
    entry_snapshot_fingerprint: str
    applied_generation: int
    normalized_settings: NormalizedZoneSettings
    sensor_identity: AppliedEntityIdentity
    actuator_identity: AppliedEntityIdentity

    def __post_init__(self) -> None:
        if (
            not self.subentry_id
            or not self.config_fingerprint
            or not self.entry_snapshot_fingerprint
        ):
            raise ValueError("applied shadow identifiers/fingerprints must be non-empty")
        if isinstance(self.applied_generation, bool) or self.applied_generation < 0:
            raise ValueError("applied_generation must be a non-negative integer")
        if self.sensor_identity.domain != SENSOR_DOMAIN:
            raise ValueError("applied sensor identity must use sensor domain")
        if self.actuator_identity.domain not in (ACTUATOR_DOMAIN_SWITCH, ACTUATOR_DOMAIN_VALVE):
            raise ValueError("applied actuator identity must use switch or valve domain")
        self.normalized_settings.validate(
            self.sensor_identity.last_known_entity_id,
            self.actuator_identity.last_known_entity_id,
        )


@dataclass(frozen=True, slots=True)
class IdentityIncident:
    """Durable identity evidence for later exact-record reconciliation."""

    kind: IdentityIncidentKind
    detail: str

    def __post_init__(self) -> None:
        if not self.detail:
            raise ValueError("identity incident detail must be non-empty")


@dataclass(frozen=True, slots=True)
class PersistedSession:
    """Schema-2 session under zone_runtime with exact safety-record owner."""

    owner_safety_record_id: str
    context: SessionContext

    def __post_init__(self) -> None:
        if not self.owner_safety_record_id:
            raise ValueError("owner_safety_record_id must be non-empty")


@dataclass(frozen=True, slots=True)
class AccountingContribution:
    """Stable zone-history accounting contribution identity (§19.5)."""

    accounting_contribution_id: str
    source_safety_record_id: str
    start_utc: datetime | None
    end_utc: datetime | None
    runtime_s: float
    runtime_estimated: bool
    local_date: date | None = None

    def __post_init__(self) -> None:
        if not self.accounting_contribution_id or not self.source_safety_record_id:
            raise ValueError("contribution IDs must be non-empty")
        if not math.isfinite(self.runtime_s) or self.runtime_s < 0:
            raise ValueError("contribution runtime_s must be finite and non-negative")
        if (self.start_utc is None) != (self.end_utc is None):
            raise ValueError("contribution interval anchors must both be known or both null")
        if self.start_utc is not None and self.end_utc is not None:
            _require_utc(self.start_utc, "contribution.start_utc")
            _require_utc(self.end_utc, "contribution.end_utc")
            if self.end_utc < self.start_utc:
                raise ValueError("contribution end precedes start")


@dataclass(frozen=True, slots=True)
class ZoneDailyRuntime:
    """Current-day budget plus contribution/audit provenance (§19.3-§19.5)."""

    date_local: date
    runtime_s: float
    conservative_unattributed_runtime_s: float = 0.0
    contributions: tuple[AccountingContribution, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("runtime_s", self.runtime_s),
            ("conservative_unattributed_runtime_s", self.conservative_unattributed_runtime_s),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.conservative_unattributed_runtime_s > self.runtime_s:
            raise ValueError("unattributed runtime cannot exceed total runtime")
        deduplicated = deduplicate_accounting_contributions(self.contributions)
        if len(deduplicated) != len(self.contributions):
            raise ValueError("persisted daily contributions must have unique IDs")
        if sum(contribution.runtime_s for contribution in self.contributions) > self.runtime_s:
            raise ValueError("daily runtime cannot be less than its known contributions")
        if any(
            contribution.local_date not in (None, self.date_local)
            for contribution in self.contributions
        ):
            raise ValueError("contribution local_date disagrees with daily date")


@dataclass(frozen=True, slots=True)
class ZoneRuntime:
    """Sole logical-zone operational persistence authority (§23.2)."""

    enabled: bool
    state: ControllerState
    zone_fault: FaultCode | None
    secondary_fault: FaultCode | None
    sensor_identity: SensorIdentity
    last_session_summary: SessionSummary | None
    session: PersistedSession | None

    def __post_init__(self) -> None:
        if self.zone_fault is not None and self.zone_fault not in _ZONE_FAULTS:
            raise ValueError("zone_fault must be sensor/configuration scoped")
        if self.secondary_fault is not None and self.secondary_fault not in _ZONE_FAULTS:
            raise ValueError("zone secondary_fault must be sensor/configuration scoped")
        if self.zone_fault is not None and self.zone_fault == self.secondary_fault:
            raise ValueError("zone primary and secondary fault must not duplicate")

    def to_legacy_record(
        self,
        *,
        actuator_fault: FaultCode | None,
        last_session_end_utc: datetime | None,
        last_auto_session_start_utc: datetime | None,
        daily: ZoneDailyRuntime | None,
    ) -> ZoneRecord:
        """Temporary spec.3 runtime projection; never serialized as authority."""
        active = actuator_fault or self.zone_fault
        secondary = self.zone_fault if actuator_fault is not None else self.secondary_fault
        if actuator_fault is not None and self.secondary_fault is not None:
            secondary = self.secondary_fault
        return ZoneRecord(
            state=self.state,
            enabled=self.enabled,
            active_fault=active,
            secondary_fault=secondary,
            last_session_end_utc=last_session_end_utc,
            last_auto_session_start_utc=last_auto_session_start_utc,
            daily=(DailyRuntime(daily.date_local, daily.runtime_s) if daily else None),
            last_session_summary=self.last_session_summary,
            session=self.session.context if self.session else None,
        )


@dataclass(frozen=True, slots=True)
class ZoneHistory:
    """Independent logical-zone history and operational authority (§23.2)."""

    zone_history_id: str
    active_subentry_id: str | None
    previous_subentry_ids: tuple[str, ...]
    last_session_end_utc: datetime | None
    last_auto_session_start_utc: datetime | None
    zone_runtime: ZoneRuntime
    daily: ZoneDailyRuntime | None

    def __post_init__(self) -> None:
        _validate_id_history(
            self.zone_history_id,
            self.active_subentry_id,
            self.previous_subentry_ids,
            "zone_history",
        )
        for name, value in (
            ("last_session_end_utc", self.last_session_end_utc),
            ("last_auto_session_start_utc", self.last_auto_session_start_utc),
        ):
            if value is not None:
                _require_utc(value, name)

    def evolve(self, **changes: object) -> ZoneHistory:
        return replace(self, **changes)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class SafetyRecord:
    """One canonical mutable actuator-safety record per durable lineage."""

    safety_record_id: str
    zone_id: str
    active_subentry_id: str | None
    previous_subentry_ids: tuple[str, ...]
    safety_lineage_id: str
    zone_history_id: str
    historical_zone_history_ids: tuple[str, ...]
    runtime_lifecycle: RuntimeLifecycle
    applied_config: AppliedConfigurationShadow | None
    actuator_identity: ActuatorIdentity
    blocker_reasons: tuple[BlockerReason, ...]
    possible_flow_owner: PossibleFlowOwner | None
    identity_incident: IdentityIncident | None
    actuator_fault: FaultCode | None
    acknowledgement_required: bool

    def __post_init__(self) -> None:
        _validate_id_history(
            self.safety_record_id,
            self.active_subentry_id,
            self.previous_subentry_ids,
            "safety_record",
        )
        if not self.zone_id or not self.safety_lineage_id or not self.zone_history_id:
            raise ValueError("safety record identities must be non-empty")
        if len(set(self.historical_zone_history_ids)) != len(self.historical_zone_history_ids):
            raise ValueError("historical_zone_history_ids must be unique")
        if self.zone_history_id in self.historical_zone_history_ids:
            raise ValueError("current zone_history_id cannot also be historical")
        if len(set(self.blocker_reasons)) != len(self.blocker_reasons):
            raise ValueError("blocker reasons must be unique")
        if self.actuator_fault is not None and self.actuator_fault not in _ACTUATOR_FAULTS:
            raise ValueError("actuator_fault must be actuator/integrity scoped")
        if self.acknowledgement_required and (
            self.actuator_fault is None or not self.actuator_fault.requires_user_ack
        ):
            raise ValueError("acknowledgement requires an acknowledgement-capable actuator fault")
        if self.runtime_lifecycle is RuntimeLifecycle.ACTIVE:
            if self.active_subentry_id is None or self.applied_config is None:
                raise ValueError("ACTIVE record requires current subentry and applied shadow")
            if self.applied_config.subentry_id != self.active_subentry_id:
                raise ValueError("applied shadow/current subentry mismatch")
            if self.actuator_identity.identity_status not in (
                IdentityStatus.REGISTRY_CONFIRMED,
                IdentityStatus.REGISTRY_UNAVAILABLE,
            ):
                raise ValueError("ACTIVE record requires a resolved actuator identity")
        elif self.active_subentry_id is not None:
            raise ValueError("non-ACTIVE record cannot own a current subentry")

    def evolve(self, **changes: object) -> SafetyRecord:
        return replace(self, **changes)  # type: ignore[arg-type]


def _validate_id_history(
    stable_id: str,
    active_subentry_id: str | None,
    previous_subentry_ids: tuple[str, ...],
    context: str,
) -> None:
    if not stable_id:
        raise ValueError(f"{context} stable ID must be non-empty")
    if active_subentry_id == "" or any(not value for value in previous_subentry_ids):
        raise ValueError(f"{context} subentry IDs must be non-empty or null")
    if len(set(previous_subentry_ids)) != len(previous_subentry_ids):
        raise ValueError(f"{context} previous_subentry_ids must be unique")
    if active_subentry_id in previous_subentry_ids:
        raise ValueError(f"{context} active subentry cannot also be previous")


@dataclass(frozen=True, slots=True)
class StoreData:
    """Canonical complete schema-2 runtime safety snapshot."""

    generation_id: str
    store_revision: int
    run: RunIds
    zone_histories: dict[str, ZoneHistory]
    safety_records: dict[str, SafetyRecord]
    version: int = STORE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        validate_store_data(self)

    def evolve(self, **changes: object) -> StoreData:
        return replace(self, **changes)  # type: ignore[arg-type]

    @property
    def zones(self) -> dict[str, ZoneRecord]:
        """Temporary read-only spec.3 projection for later remediation stages."""
        projected: dict[str, ZoneRecord] = {}
        for record_id in sorted(self.safety_records):
            record = self.safety_records[record_id]
            history = self.zone_histories[record.zone_history_id]
            projected[record.zone_id] = history.zone_runtime.to_legacy_record(
                actuator_fault=record.actuator_fault,
                last_session_end_utc=history.last_session_end_utc,
                last_auto_session_start_utc=history.last_auto_session_start_utc,
                daily=history.daily,
            )
        return projected


@dataclass(frozen=True, slots=True)
class MigrationRecordContext:
    """Caller-supplied normalized current-config facts for schema-1 migration."""

    active_subentry_id: str
    applied_config: AppliedConfigurationShadow
    actuator_identity: ActuatorIdentity
    sensor_identity: SensorIdentity

    def __post_init__(self) -> None:
        if (
            not self.active_subentry_id
            or self.applied_config.subentry_id != self.active_subentry_id
        ):
            raise ValueError("migration context subentry/shadow mismatch")
        if self.sensor_identity.last_known_entity_id != (
            self.applied_config.sensor_identity.last_known_entity_id
        ):
            raise ValueError("migration context sensor identity/shadow mismatch")
        if self.actuator_identity.last_known_entity_id != (
            self.applied_config.actuator_identity.last_known_entity_id
        ):
            raise ValueError("migration context actuator identity/shadow mismatch")


def validate_store_data(data: StoreData) -> None:
    """Reject all schema-2 structural/cross-reference contradictions."""
    if data.version != STORE_SCHEMA_VERSION:
        raise ValueError(f"StoreData version must be {STORE_SCHEMA_VERSION}")
    if not data.generation_id:
        raise ValueError("generation_id must be non-empty")
    if isinstance(data.store_revision, bool) or data.store_revision < 1:
        raise ValueError("store_revision must be a positive integer")
    if set(data.zone_histories) != {
        history.zone_history_id for history in data.zone_histories.values()
    }:
        raise ValueError("zone-history map keys must equal stable IDs")
    if set(data.safety_records) != {
        record.safety_record_id for record in data.safety_records.values()
    }:
        raise ValueError("safety-record map keys must equal stable IDs")
    lineages = [record.safety_lineage_id for record in data.safety_records.values()]
    if len(lineages) != len(set(lineages)):
        raise ValueError("safety_lineage_id must be globally unique")
    active_record_subentries = [
        record.active_subentry_id
        for record in data.safety_records.values()
        if record.active_subentry_id is not None
    ]
    if len(active_record_subentries) != len(set(active_record_subentries)):
        raise ValueError("current subentry cannot own multiple safety records")
    active_history_subentries = [
        history.active_subentry_id
        for history in data.zone_histories.values()
        if history.active_subentry_id is not None
    ]
    if len(active_history_subentries) != len(set(active_history_subentries)):
        raise ValueError("current subentry cannot own multiple zone histories")
    for record in data.safety_records.values():
        history = data.zone_histories.get(record.zone_history_id)
        if history is None:
            raise ValueError("safety record references missing zone_history_id")
        if record.runtime_lifecycle is RuntimeLifecycle.ACTIVE and (
            history.active_subentry_id != record.active_subentry_id
        ):
            raise ValueError("ACTIVE safety/history current ownership mismatch")
    for history in data.zone_histories.values():
        persisted = history.zone_runtime.session
        if persisted is None:
            continue
        owner = data.safety_records.get(persisted.owner_safety_record_id)
        if owner is None:
            raise ValueError("persisted session owner_safety_record_id does not exist")
        if owner.zone_history_id != history.zone_history_id:
            raise ValueError("persisted session owner references a different zone history")
    contribution_ids: dict[str, AccountingContribution] = {}
    for history in data.zone_histories.values():
        if history.daily is None:
            continue
        for contribution in history.daily.contributions:
            if contribution.source_safety_record_id not in data.safety_records:
                raise ValueError("accounting contribution source safety record does not exist")
            prior = contribution_ids.get(contribution.accounting_contribution_id)
            if prior is not None:
                if prior != contribution:
                    raise ValueError("conflicting duplicate accounting contribution ID")
                raise ValueError("duplicate accounting contribution ID in Store")
            contribution_ids[contribution.accounting_contribution_id] = contribution


def deduplicate_accounting_contributions(
    contributions: tuple[AccountingContribution, ...] | list[AccountingContribution],
) -> tuple[AccountingContribution, ...]:
    """Deduplicate byte-identical IDs; reject contradictory reuse (§19.5.1)."""
    by_id: dict[str, AccountingContribution] = {}
    for contribution in contributions:
        existing = by_id.get(contribution.accounting_contribution_id)
        if existing is not None and existing != contribution:
            raise ValueError("accounting contribution ID reused with different payload")
        by_id[contribution.accounting_contribution_id] = contribution
    return tuple(by_id[key] for key in sorted(by_id))


def conservative_merge_daily_runtime(
    left: ZoneDailyRuntime, right: ZoneDailyRuntime
) -> ZoneDailyRuntime:
    """Pure Stage-1 conservative aggregate primitive for later A -> B use.

    Identical contribution IDs count once. Every distinct known contribution
    remains. Aggregate runtime not proven to be represented by stable IDs is
    added from both sides and explicitly retained as unattributed evidence.
    Interval-overlap orchestration remains Stage 2/3 work.
    """
    if left.date_local != right.date_local:
        raise ValueError("daily runtime dates must match")
    contributions = deduplicate_accounting_contributions(
        (*left.contributions, *right.contributions)
    )
    left_known = sum(contribution.runtime_s for contribution in left.contributions)
    right_known = sum(contribution.runtime_s for contribution in right.contributions)
    left_unresolved = max(left.conservative_unattributed_runtime_s, left.runtime_s - left_known)
    right_unresolved = max(right.conservative_unattributed_runtime_s, right.runtime_s - right_known)
    unresolved = left_unresolved + right_unresolved
    return ZoneDailyRuntime(
        date_local=left.date_local,
        runtime_s=sum(contribution.runtime_s for contribution in contributions) + unresolved,
        conservative_unattributed_runtime_s=unresolved,
        contributions=contributions,
    )


def _stable_migration_id(generation_id: str, record_id: str, kind: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{DOMAIN}:{generation_id}:{record_id}:{kind}"))


def migrate_schema1_to_schema2(
    legacy: Schema1StoreData,
    current_records: Mapping[str, MigrationRecordContext] | None = None,
) -> StoreData:
    """Strict pure §23.2.1 migration with deterministic identity creation."""
    contexts = dict(current_records or {})
    unknown = set(contexts) - set(legacy.zones)
    if unknown:
        raise MalformedStoreData(
            f"migration context has unknown schema-1 records: {sorted(unknown)}"
        )
    safety_records: dict[str, SafetyRecord] = {}
    zone_histories: dict[str, ZoneHistory] = {}
    for safety_record_id in sorted(legacy.zones):
        old = legacy.zones[safety_record_id]
        context = contexts.get(safety_record_id)
        lineage_id = _stable_migration_id(legacy.generation_id, safety_record_id, "safety-lineage")
        history_id = _stable_migration_id(legacy.generation_id, safety_record_id, "zone-history")
        actuator_fault, zone_fault, secondary_zone_fault = _split_schema1_faults(
            old.active_fault, old.secondary_fault
        )
        persisted_session = (
            PersistedSession(safety_record_id, old.session) if old.session is not None else None
        )
        contributions: tuple[AccountingContribution, ...] = ()
        daily: ZoneDailyRuntime | None = None
        if old.daily is not None:
            contribution = AccountingContribution(
                accounting_contribution_id=_stable_migration_id(
                    legacy.generation_id,
                    safety_record_id,
                    f"schema1-daily:{old.daily.date_local.isoformat()}",
                ),
                source_safety_record_id=safety_record_id,
                start_utc=None,
                end_utc=None,
                runtime_s=old.daily.runtime_s,
                runtime_estimated=True,
                local_date=old.daily.date_local,
            )
            contributions = (contribution,)
            daily = ZoneDailyRuntime(
                date_local=old.daily.date_local,
                runtime_s=old.daily.runtime_s,
                conservative_unattributed_runtime_s=0.0,
                contributions=contributions,
            )
        if context is None:
            active_subentry_id = None
            previous_subentry_ids = (safety_record_id,)
            lifecycle = RuntimeLifecycle.DELETE_PENDING
            applied_config = None
            actuator_identity = ActuatorIdentity(
                registry_entry_id=None,
                last_known_entity_id=None,
                domain=None,
                identity_status=IdentityStatus.MISSING,
                off_service=None,
                confirm_timeout_s=None,
            )
            sensor_identity = SensorIdentity(None, None)
            blockers = {BlockerReason.ACTUATOR_NOT_PROVEN_OFF}
            if _legacy_has_possible_integration_flow(old):
                blockers.add(BlockerReason.INTEGRATION_OFF_UNCONFIRMED)
            possible_flow_owner = (
                PossibleFlowOwner.INTEGRATION
                if _legacy_has_possible_integration_flow(old)
                else None
            )
            incident = IdentityIncident(
                IdentityIncidentKind.MIGRATION_UNRESOLVED,
                "schema-1 record absent from supplied current configuration; "
                "durable actuator identity unavailable",
            )
        else:
            active_subentry_id = context.active_subentry_id
            previous_subentry_ids = (
                (safety_record_id,) if context.active_subentry_id != safety_record_id else ()
            )
            lifecycle = RuntimeLifecycle.ACTIVE
            applied_config = context.applied_config
            actuator_identity = context.actuator_identity
            sensor_identity = context.sensor_identity
            blockers = set()
            if _legacy_has_possible_integration_flow(old):
                blockers.add(BlockerReason.INTEGRATION_OFF_UNCONFIRMED)
            possible_flow_owner = (
                PossibleFlowOwner.INTEGRATION
                if _legacy_has_possible_integration_flow(old)
                else None
            )
            incident = None
        zone_runtime = ZoneRuntime(
            enabled=old.enabled,
            state=old.state,
            zone_fault=zone_fault,
            secondary_fault=secondary_zone_fault,
            sensor_identity=sensor_identity,
            last_session_summary=old.last_session_summary,
            session=persisted_session,
        )
        zone_histories[history_id] = ZoneHistory(
            zone_history_id=history_id,
            active_subentry_id=active_subentry_id,
            previous_subentry_ids=previous_subentry_ids,
            last_session_end_utc=old.last_session_end_utc,
            last_auto_session_start_utc=old.last_auto_session_start_utc,
            zone_runtime=zone_runtime,
            daily=daily,
        )
        safety_records[safety_record_id] = SafetyRecord(
            safety_record_id=safety_record_id,
            zone_id=safety_record_id,
            active_subentry_id=active_subentry_id,
            previous_subentry_ids=previous_subentry_ids,
            safety_lineage_id=lineage_id,
            zone_history_id=history_id,
            historical_zone_history_ids=(),
            runtime_lifecycle=lifecycle,
            applied_config=applied_config,
            actuator_identity=actuator_identity,
            blocker_reasons=tuple(sorted(blockers, key=str)),
            possible_flow_owner=possible_flow_owner,
            identity_incident=incident,
            actuator_fault=actuator_fault,
            acknowledgement_required=(
                actuator_fault.requires_user_ack if actuator_fault is not None else False
            ),
        )
    try:
        return StoreData(
            generation_id=legacy.generation_id,
            store_revision=legacy.store_revision + 1,
            run=legacy.run,
            zone_histories=zone_histories,
            safety_records=safety_records,
        )
    except ValueError as err:
        raise MalformedStoreData(f"migrated schema-2 payload invalid: {err}") from err


def _legacy_has_possible_integration_flow(record: ZoneRecord) -> bool:
    session = record.session
    return session is not None and (
        session.pulse_intent_at_utc is not None and session.off_confirmed_at_utc is None
    )


def _split_schema1_faults(
    primary: FaultCode | None, secondary: FaultCode | None
) -> tuple[FaultCode | None, FaultCode | None, FaultCode | None]:
    actuator_faults = [fault for fault in (primary, secondary) if fault in _ACTUATOR_FAULTS]
    if len(actuator_faults) > 1:
        raise MalformedStoreData(
            "schema-1 primary/secondary actuator faults cannot be represented unambiguously"
        )
    zone_primary = primary if primary in _ZONE_FAULTS else None
    zone_secondary = secondary if secondary in _ZONE_FAULTS else None
    return (actuator_faults[0] if actuator_faults else None, zone_primary, zone_secondary)


# -- Schema-2 deterministic serialization ---------------------------------


def _identity_to_dict(identity: SensorIdentity | AppliedEntityIdentity | ActuatorIdentity) -> dict:
    if isinstance(identity, ActuatorIdentity):
        return {
            "registry_entry_id": identity.registry_entry_id,
            "last_known_entity_id": identity.last_known_entity_id,
            "domain": identity.domain,
            "identity_status": identity.identity_status.value,
            "off_service": identity.off_service,
            "confirm_timeout_s": identity.confirm_timeout_s,
        }
    result = {
        "registry_entry_id": identity.registry_entry_id,
        "last_known_entity_id": identity.last_known_entity_id,
    }
    if isinstance(identity, AppliedEntityIdentity):
        result["domain"] = identity.domain
    return result


def _settings_to_dict(settings: NormalizedZoneSettings) -> dict:
    return {field: getattr(settings, field) for field in settings.__dataclass_fields__}


def _shadow_to_dict(shadow: AppliedConfigurationShadow) -> dict:
    return {
        "subentry_id": shadow.subentry_id,
        "config_fingerprint": shadow.config_fingerprint,
        "entry_snapshot_fingerprint": shadow.entry_snapshot_fingerprint,
        "applied_generation": shadow.applied_generation,
        "normalized_settings": _settings_to_dict(shadow.normalized_settings),
        "sensor_identity": _identity_to_dict(shadow.sensor_identity),
        "actuator_identity": _identity_to_dict(shadow.actuator_identity),
    }


def persisted_session_to_dict(session: PersistedSession) -> dict:
    payload = session_to_dict(session.context)
    payload["owner_safety_record_id"] = session.owner_safety_record_id
    return payload


def _contribution_to_dict(contribution: AccountingContribution) -> dict:
    return {
        "accounting_contribution_id": contribution.accounting_contribution_id,
        "source_safety_record_id": contribution.source_safety_record_id,
        "start_utc": _dt_to_iso(contribution.start_utc),
        "end_utc": _dt_to_iso(contribution.end_utc),
        "runtime_s": contribution.runtime_s,
        "runtime_estimated": contribution.runtime_estimated,
        "local_date": contribution.local_date.isoformat() if contribution.local_date else None,
    }


def store_data_to_dict(data: StoreData) -> dict:
    """Deterministically serialize the canonical schema-2 Store."""
    validate_store_data(data)
    return {
        "version": STORE_SCHEMA_VERSION,
        "generation_id": data.generation_id,
        "store_revision": data.store_revision,
        "run": {
            "active_run_id": data.run.active_run_id,
            "last_clean_shutdown_run_id": data.run.last_clean_shutdown_run_id,
        },
        "zone_histories": {
            history_id: {
                "active_subentry_id": history.active_subentry_id,
                "previous_subentry_ids": list(history.previous_subentry_ids),
                "last_session_end_utc": _dt_to_iso(history.last_session_end_utc),
                "last_auto_session_start_utc": _dt_to_iso(history.last_auto_session_start_utc),
                "zone_runtime": {
                    "enabled": history.zone_runtime.enabled,
                    "state": history.zone_runtime.state.value,
                    "zone_fault": (
                        history.zone_runtime.zone_fault.value
                        if history.zone_runtime.zone_fault
                        else None
                    ),
                    "secondary_fault": (
                        history.zone_runtime.secondary_fault.value
                        if history.zone_runtime.secondary_fault
                        else None
                    ),
                    "sensor_identity": _identity_to_dict(history.zone_runtime.sensor_identity),
                    "last_session_summary": (
                        summary_to_dict(history.zone_runtime.last_session_summary)
                        if history.zone_runtime.last_session_summary
                        else None
                    ),
                    "session": (
                        persisted_session_to_dict(history.zone_runtime.session)
                        if history.zone_runtime.session
                        else None
                    ),
                },
                "daily": (
                    {
                        "date_local": history.daily.date_local.isoformat(),
                        "runtime_s": history.daily.runtime_s,
                        "conservative_unattributed_runtime_s": (
                            history.daily.conservative_unattributed_runtime_s
                        ),
                        "contributions": [
                            _contribution_to_dict(contribution)
                            for contribution in history.daily.contributions
                        ],
                    }
                    if history.daily
                    else None
                ),
            }
            for history_id, history in sorted(data.zone_histories.items())
        },
        "safety_records": {
            record_id: {
                "zone_id": record.zone_id,
                "active_subentry_id": record.active_subentry_id,
                "previous_subentry_ids": list(record.previous_subentry_ids),
                "safety_lineage_id": record.safety_lineage_id,
                "zone_history_id": record.zone_history_id,
                "historical_zone_history_ids": list(record.historical_zone_history_ids),
                "runtime_lifecycle": record.runtime_lifecycle.value,
                "applied_config": (
                    _shadow_to_dict(record.applied_config) if record.applied_config else None
                ),
                "actuator_identity": _identity_to_dict(record.actuator_identity),
                "blocker_reasons": [reason.value for reason in record.blocker_reasons],
                "possible_flow_owner": (
                    record.possible_flow_owner.value if record.possible_flow_owner else None
                ),
                "identity_incident": (
                    {
                        "kind": record.identity_incident.kind.value,
                        "detail": record.identity_incident.detail,
                    }
                    if record.identity_incident
                    else None
                ),
                "actuator_fault": record.actuator_fault.value if record.actuator_fault else None,
                "acknowledgement_required": record.acknowledgement_required,
            }
            for record_id, record in sorted(data.safety_records.items())
        },
    }


def store_data_from_dict(raw: object) -> StoreData:
    """Strictly parse schema 2; schema 1 requires the migration parser."""
    if not isinstance(raw, dict):
        raise MalformedStoreData("store must be an object")
    version = raw.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise MalformedStoreData("store.version must be an integer")
    if version > STORE_SCHEMA_VERSION:
        raise FutureStoreVersion(f"store schema {version} is newer than {STORE_SCHEMA_VERSION}")
    if version != STORE_SCHEMA_VERSION:
        raise MalformedStoreData(f"store schema {version} is not schema {STORE_SCHEMA_VERSION}")
    raw = _require_exact_keys(
        raw,
        {"version", "generation_id", "store_revision", "run", "zone_histories", "safety_records"},
        "store",
    )
    generation = _strict_string(raw["generation_id"], "store.generation_id")
    revision = _strict_int(raw["store_revision"], "store.store_revision", minimum=1)
    run_raw = _require_exact_keys(
        raw["run"], {"active_run_id", "last_clean_shutdown_run_id"}, "store.run"
    )
    active = _strict_string(run_raw["active_run_id"], "store.run.active_run_id", nullable=True)
    clean = _strict_string(
        run_raw["last_clean_shutdown_run_id"],
        "store.run.last_clean_shutdown_run_id",
        nullable=True,
    )
    histories_raw = raw["zone_histories"]
    records_raw = raw["safety_records"]
    if not isinstance(histories_raw, dict) or not isinstance(records_raw, dict):
        raise MalformedStoreData("store zone_histories/safety_records must be objects")
    try:
        histories = {
            _map_id(key, "zone_history"): _zone_history_from_dict(key, value)
            for key, value in histories_raw.items()
        }
        records = {
            _map_id(key, "safety_record"): _safety_record_from_dict(key, value)
            for key, value in records_raw.items()
        }
        return StoreData(
            generation_id=generation,  # type: ignore[arg-type]
            store_revision=revision,
            run=RunIds(active, clean),
            zone_histories=histories,
            safety_records=records,
        )
    except StoreDataError:
        raise
    except (TypeError, ValueError) as err:
        raise MalformedStoreData(f"schema-2 payload invalid: {err}") from err


def _map_id(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise MalformedStoreData(f"{context} map key must be a non-empty string")
    return value


def _string_tuple(value: object, name: str, enum_cls: type[StrEnum] | None = None) -> tuple:
    if not isinstance(value, list):
        raise MalformedStoreData(f"{name} must be a list")
    try:
        result = tuple(enum_cls(item) if enum_cls else _strict_string(item, name) for item in value)
    except ValueError as err:
        raise MalformedStoreData(f"{name} contains an unknown value") from err
    if len(set(result)) != len(result):
        raise MalformedStoreData(f"{name} must not contain duplicates")
    return result


def _sensor_identity_from_dict(raw: object) -> SensorIdentity:
    raw = _require_exact_keys(raw, {"registry_entry_id", "last_known_entity_id"}, "sensor_identity")
    return SensorIdentity(
        _strict_string(raw["registry_entry_id"], "registry_entry_id", nullable=True),
        _strict_string(raw["last_known_entity_id"], "last_known_entity_id", nullable=True),
    )


def _applied_identity_from_dict(raw: object, context: str) -> AppliedEntityIdentity:
    raw = _require_exact_keys(raw, {"registry_entry_id", "last_known_entity_id", "domain"}, context)
    return AppliedEntityIdentity(
        _strict_string(raw["registry_entry_id"], f"{context}.registry_entry_id", nullable=True),
        _strict_string(raw["last_known_entity_id"], f"{context}.last_known_entity_id"),  # type: ignore[arg-type]
        _strict_string(raw["domain"], f"{context}.domain"),  # type: ignore[arg-type]
    )


def _actuator_identity_from_dict(raw: object) -> ActuatorIdentity:
    raw = _require_exact_keys(
        raw,
        {
            "registry_entry_id",
            "last_known_entity_id",
            "domain",
            "identity_status",
            "off_service",
            "confirm_timeout_s",
        },
        "actuator_identity",
    )
    timeout = raw["confirm_timeout_s"]
    return ActuatorIdentity(
        _strict_string(raw["registry_entry_id"], "registry_entry_id", nullable=True),
        _strict_string(raw["last_known_entity_id"], "last_known_entity_id", nullable=True),
        _strict_string(raw["domain"], "domain", nullable=True),
        IdentityStatus(raw["identity_status"]),
        _strict_string(raw["off_service"], "off_service", nullable=True),
        None if timeout is None else _strict_int(timeout, "confirm_timeout_s", minimum=1),
    )


_SETTING_FIELDS = tuple(NormalizedZoneSettings.__dataclass_fields__)


def _settings_from_dict(raw: object) -> NormalizedZoneSettings:
    raw = _require_exact_keys(raw, set(_SETTING_FIELDS), "normalized_settings")
    return NormalizedZoneSettings(
        name=_strict_string(raw["name"], "settings.name"),  # type: ignore[arg-type]
        start_threshold=_strict_float(raw["start_threshold"], "settings.start_threshold"),
        target_threshold=_strict_float(raw["target_threshold"], "settings.target_threshold"),
        pulse_duration_s=_strict_int(raw["pulse_duration_s"], "settings.pulse_duration_s"),
        soak_duration_s=_strict_int(raw["soak_duration_s"], "settings.soak_duration_s"),
        max_cycles=_strict_int(raw["max_cycles"], "settings.max_cycles"),
        max_session_runtime_s=_strict_int(
            raw["max_session_runtime_s"], "settings.max_session_runtime_s"
        ),
        max_daily_runtime_s=_strict_int(raw["max_daily_runtime_s"], "settings.max_daily_runtime_s"),
        min_session_interval_s=_strict_int(
            raw["min_session_interval_s"], "settings.min_session_interval_s"
        ),
        sensor_max_age_s=_strict_int(raw["sensor_max_age_s"], "settings.sensor_max_age_s"),
        actuator_confirm_timeout_s=_strict_int(
            raw["actuator_confirm_timeout_s"], "settings.actuator_confirm_timeout_s"
        ),
        manual_max_duration_s=_strict_int(
            raw["manual_max_duration_s"], "settings.manual_max_duration_s"
        ),
    )


def _shadow_from_dict(raw: object) -> AppliedConfigurationShadow:
    raw = _require_exact_keys(
        raw,
        {
            "subentry_id",
            "config_fingerprint",
            "entry_snapshot_fingerprint",
            "applied_generation",
            "normalized_settings",
            "sensor_identity",
            "actuator_identity",
        },
        "applied_config",
    )
    return AppliedConfigurationShadow(
        subentry_id=_strict_string(raw["subentry_id"], "applied_config.subentry_id"),  # type: ignore[arg-type]
        config_fingerprint=_strict_string(
            raw["config_fingerprint"], "applied_config.config_fingerprint"
        ),  # type: ignore[arg-type]
        entry_snapshot_fingerprint=_strict_string(
            raw["entry_snapshot_fingerprint"], "applied_config.entry_snapshot_fingerprint"
        ),  # type: ignore[arg-type]
        applied_generation=_strict_int(
            raw["applied_generation"], "applied_config.applied_generation"
        ),
        normalized_settings=_settings_from_dict(raw["normalized_settings"]),
        sensor_identity=_applied_identity_from_dict(raw["sensor_identity"], "applied sensor"),
        actuator_identity=_applied_identity_from_dict(raw["actuator_identity"], "applied actuator"),
    )


def persisted_session_from_dict(raw: object) -> PersistedSession:
    if not isinstance(raw, dict):
        raise MalformedStoreData("persisted session must be an object")
    owner = _strict_string(raw.get("owner_safety_record_id"), "owner_safety_record_id")
    context_raw = dict(raw)
    context_raw.pop("owner_safety_record_id", None)
    return PersistedSession(owner, session_from_dict(context_raw))  # type: ignore[arg-type]


def _contribution_from_dict(raw: object) -> AccountingContribution:
    raw = _require_exact_keys(
        raw,
        {
            "accounting_contribution_id",
            "source_safety_record_id",
            "start_utc",
            "end_utc",
            "runtime_s",
            "runtime_estimated",
            "local_date",
        },
        "accounting contribution",
    )
    local_date_raw = raw["local_date"]
    if local_date_raw is not None and not isinstance(local_date_raw, str):
        raise MalformedStoreData("contribution.local_date must be an ISO date or null")
    return AccountingContribution(
        accounting_contribution_id=_strict_string(
            raw["accounting_contribution_id"], "accounting_contribution_id"
        ),  # type: ignore[arg-type]
        source_safety_record_id=_strict_string(
            raw["source_safety_record_id"], "source_safety_record_id"
        ),  # type: ignore[arg-type]
        start_utc=_iso_to_dt(raw["start_utc"], "contribution.start_utc"),
        end_utc=_iso_to_dt(raw["end_utc"], "contribution.end_utc"),
        runtime_s=_strict_float(raw["runtime_s"], "contribution.runtime_s"),
        runtime_estimated=_strict_bool(raw["runtime_estimated"], "contribution.runtime_estimated"),
        local_date=(date.fromisoformat(local_date_raw) if local_date_raw is not None else None),
    )


def _zone_history_from_dict(history_id: object, raw: object) -> ZoneHistory:
    history_id = _map_id(history_id, "zone_history")
    raw = _require_exact_keys(
        raw,
        {
            "active_subentry_id",
            "previous_subentry_ids",
            "last_session_end_utc",
            "last_auto_session_start_utc",
            "zone_runtime",
            "daily",
        },
        "zone_history",
    )
    runtime_raw = _require_exact_keys(
        raw["zone_runtime"],
        {
            "enabled",
            "state",
            "zone_fault",
            "secondary_fault",
            "sensor_identity",
            "last_session_summary",
            "session",
        },
        "zone_runtime",
    )
    daily_raw = raw["daily"]
    daily = None
    if daily_raw is not None:
        daily_raw = _require_exact_keys(
            daily_raw,
            {"date_local", "runtime_s", "conservative_unattributed_runtime_s", "contributions"},
            "zone_history.daily",
        )
        if not isinstance(daily_raw["date_local"], str):
            raise MalformedStoreData("daily.date_local must be an ISO date string")
        contributions_raw = daily_raw["contributions"]
        if not isinstance(contributions_raw, list):
            raise MalformedStoreData("daily.contributions must be a list")
        daily = ZoneDailyRuntime(
            date_local=date.fromisoformat(daily_raw["date_local"]),
            runtime_s=_strict_float(daily_raw["runtime_s"], "daily.runtime_s"),
            conservative_unattributed_runtime_s=_strict_float(
                daily_raw["conservative_unattributed_runtime_s"],
                "daily.conservative_unattributed_runtime_s",
            ),
            contributions=tuple(_contribution_from_dict(item) for item in contributions_raw),
        )
    summary_raw = runtime_raw["last_session_summary"]
    session_raw = runtime_raw["session"]
    return ZoneHistory(
        zone_history_id=history_id,
        active_subentry_id=_strict_string(
            raw["active_subentry_id"], "zone_history.active_subentry_id", nullable=True
        ),
        previous_subentry_ids=_string_tuple(
            raw["previous_subentry_ids"], "zone_history.previous_subentry_ids"
        ),
        last_session_end_utc=_iso_to_dt(
            raw["last_session_end_utc"], "zone_history.last_session_end_utc"
        ),
        last_auto_session_start_utc=_iso_to_dt(
            raw["last_auto_session_start_utc"], "zone_history.last_auto_session_start_utc"
        ),
        zone_runtime=ZoneRuntime(
            enabled=_strict_bool(runtime_raw["enabled"], "zone_runtime.enabled"),
            state=ControllerState(runtime_raw["state"]),
            zone_fault=_enum_or_none(FaultCode, runtime_raw["zone_fault"], "zone_fault"),
            secondary_fault=_enum_or_none(
                FaultCode, runtime_raw["secondary_fault"], "secondary_fault"
            ),
            sensor_identity=_sensor_identity_from_dict(runtime_raw["sensor_identity"]),
            last_session_summary=(
                summary_from_dict(summary_raw) if summary_raw is not None else None
            ),
            session=(persisted_session_from_dict(session_raw) if session_raw is not None else None),
        ),
        daily=daily,
    )


def _safety_record_from_dict(record_id: object, raw: object) -> SafetyRecord:
    record_id = _map_id(record_id, "safety_record")
    raw = _require_exact_keys(
        raw,
        {
            "zone_id",
            "active_subentry_id",
            "previous_subentry_ids",
            "safety_lineage_id",
            "zone_history_id",
            "historical_zone_history_ids",
            "runtime_lifecycle",
            "applied_config",
            "actuator_identity",
            "blocker_reasons",
            "possible_flow_owner",
            "identity_incident",
            "actuator_fault",
            "acknowledgement_required",
        },
        "safety_record",
    )
    incident_raw = raw["identity_incident"]
    incident = None
    if incident_raw is not None:
        incident_raw = _require_exact_keys(incident_raw, {"kind", "detail"}, "identity_incident")
        incident = IdentityIncident(
            IdentityIncidentKind(incident_raw["kind"]),
            _strict_string(incident_raw["detail"], "identity_incident.detail"),  # type: ignore[arg-type]
        )
    shadow_raw = raw["applied_config"]
    return SafetyRecord(
        safety_record_id=record_id,
        zone_id=_strict_string(raw["zone_id"], "safety_record.zone_id"),  # type: ignore[arg-type]
        active_subentry_id=_strict_string(
            raw["active_subentry_id"], "safety_record.active_subentry_id", nullable=True
        ),
        previous_subentry_ids=_string_tuple(
            raw["previous_subentry_ids"], "safety_record.previous_subentry_ids"
        ),
        safety_lineage_id=_strict_string(
            raw["safety_lineage_id"], "safety_record.safety_lineage_id"
        ),  # type: ignore[arg-type]
        zone_history_id=_strict_string(raw["zone_history_id"], "safety_record.zone_history_id"),  # type: ignore[arg-type]
        historical_zone_history_ids=_string_tuple(
            raw["historical_zone_history_ids"], "safety_record.historical_zone_history_ids"
        ),
        runtime_lifecycle=RuntimeLifecycle(raw["runtime_lifecycle"]),
        applied_config=_shadow_from_dict(shadow_raw) if shadow_raw is not None else None,
        actuator_identity=_actuator_identity_from_dict(raw["actuator_identity"]),
        blocker_reasons=_string_tuple(
            raw["blocker_reasons"], "safety_record.blocker_reasons", BlockerReason
        ),
        possible_flow_owner=_enum_or_none(
            PossibleFlowOwner, raw["possible_flow_owner"], "possible_flow_owner"
        ),
        identity_incident=incident,
        actuator_fault=_enum_or_none(FaultCode, raw["actuator_fault"], "actuator_fault"),
        acknowledgement_required=_strict_bool(
            raw["acknowledgement_required"], "acknowledgement_required"
        ),
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
