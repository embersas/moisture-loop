"""Constants for SoilSync.

Pure module: must not import homeassistant (SPECIFICATION.md §37) and holds
only Home Assistant-independent vocabulary. Configuration bounds implement
SPECIFICATION.md §9 exactly.
"""

from __future__ import annotations

DOMAIN = "soilsync"

# --- Runtime store (SPECIFICATION.md §23.2) -------------------------------
# The payload schema is authoritative. SafetyStore uses a schema-1 Store
# reader only while performing the one verified schema-1 -> schema-2
# transaction; every newly written payload and normal Store instance is 2.
STORE_SCHEMA_VERSION = 2
LEGACY_STORE_SCHEMA_VERSION = 1

# --- Zone configuration keys (SPECIFICATION.md §9) -------------------------
CONF_NAME = "name"
CONF_MOISTURE_SENSOR = "moisture_sensor"
CONF_ACTUATOR = "actuator"
CONF_START_THRESHOLD = "start_threshold"
CONF_TARGET_THRESHOLD = "target_threshold"
CONF_PULSE_DURATION = "pulse_duration"
CONF_SOAK_DURATION = "soak_duration"
CONF_MAX_CYCLES = "max_cycles"
CONF_MAX_SESSION_RUNTIME = "max_session_runtime"
CONF_MAX_DAILY_RUNTIME = "max_daily_runtime"
CONF_MIN_SESSION_INTERVAL = "min_session_interval"
CONF_SENSOR_MAX_AGE = "sensor_max_age"
CONF_ACTUATOR_CONFIRM_TIMEOUT = "actuator_confirm_timeout"
CONF_MANUAL_MAX_DURATION = "manual_max_duration"

# --- Config-entry identity keys (SPECIFICATION.md §23.1) -------------------
CONF_RUNTIME_STORE_GENERATION_ID = "runtime_store_generation_id"
CONF_RUNTIME_STORE_INITIALIZED = "runtime_store_initialized"

# --- Defaults (SPECIFICATION.md §9; durations in integer seconds) ----------
DEFAULT_START_THRESHOLD = 30.0
DEFAULT_TARGET_THRESHOLD = 40.0
DEFAULT_PULSE_DURATION_S = 5 * 60
DEFAULT_SOAK_DURATION_S = 20 * 60
DEFAULT_MAX_CYCLES = 4
DEFAULT_MAX_SESSION_RUNTIME_S = 30 * 60
DEFAULT_MAX_DAILY_RUNTIME_S = 60 * 60
DEFAULT_MIN_SESSION_INTERVAL_S = 6 * 60 * 60
DEFAULT_SENSOR_MAX_AGE_S = 2 * 60 * 60
DEFAULT_ACTUATOR_CONFIRM_TIMEOUT_S = 30
DEFAULT_MANUAL_MAX_DURATION_S = 30 * 60

# --- Bounds (SPECIFICATION.md §9; inclusive ranges) ------------------------
NAME_MIN_LENGTH = 1
NAME_MAX_LENGTH = 64
START_THRESHOLD_MIN = 1.0
START_THRESHOLD_MAX = 99.0
TARGET_THRESHOLD_MIN = 2.0
TARGET_THRESHOLD_MAX = 100.0
PULSE_DURATION_MIN_S = 30
PULSE_DURATION_MAX_S = 30 * 60
SOAK_DURATION_MIN_S = 60
SOAK_DURATION_MAX_S = 4 * 60 * 60
MAX_CYCLES_MIN = 1
MAX_CYCLES_MAX = 20
# max_session_runtime: pulse duration .. 4 h (lower bound is dynamic)
MAX_SESSION_RUNTIME_MAX_S = 4 * 60 * 60
# max_daily_runtime: pulse duration .. 12 h (lower bound is dynamic)
MAX_DAILY_RUNTIME_MAX_S = 12 * 60 * 60
MIN_SESSION_INTERVAL_MIN_S = 15 * 60
MIN_SESSION_INTERVAL_MAX_S = 7 * 24 * 60 * 60
SENSOR_MAX_AGE_MIN_S = 5 * 60
SENSOR_MAX_AGE_MAX_S = 24 * 60 * 60
ACTUATOR_CONFIRM_TIMEOUT_MIN_S = 5
ACTUATOR_CONFIRM_TIMEOUT_MAX_S = 5 * 60
MANUAL_MAX_DURATION_MIN_S = 60
MANUAL_MAX_DURATION_MAX_S = 2 * 60 * 60

# Accepted moisture value range (SPECIFICATION.md §10.1; 0 and 100 valid).
MOISTURE_MIN = 0.0
MOISTURE_MAX = 100.0

# Actuator entity domains accepted by §9/§11.
ACTUATOR_DOMAIN_SWITCH = "switch"
ACTUATOR_DOMAIN_VALVE = "valve"
SENSOR_DOMAIN = "sensor"

# OFF retry policy (SPECIFICATION.md §11.3: up to three total attempts).
OFF_TOTAL_ATTEMPTS = 3

# --- Guard identifiers (SPECIFICATION.md §14 guard legend) ------------------
GUARD_ENABLED = "G-EN"
GUARD_FRESH = "G-FRESH"
GUARD_START = "G-START"
GUARD_POST = "G-POST"
GUARD_ACTUATOR = "G-ACT"
GUARD_SLOT = "G-SLOT"
GUARD_CYCLES = "G-CYC"
GUARD_SESSION_FIT = "G-SESS"
GUARD_DAILY_FIT = "G-DAY"
GUARD_INTERVAL = "G-INT"
GUARD_MANUAL_SENSOR = "G-MANUAL-SENSOR"
GUARD_MANUAL_SAFE = "G-MANUAL-SAFE"
GUARD_OFF = "G-OFF"
