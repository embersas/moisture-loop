"""Slice 8 tests: startup/reload/reconfigure/shutdown lifecycle (§§24-25).

Covers PI12-PI15 crash recovery, LC3-LC12, trusted-SOAKING adoption across
runs, the once-only stop handler, generic reload semantics, setup failure,
and the ER12 subscribe-before-snapshot interleaving. HA-harness suite.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.moisture_loop import EntryRuntime, zone_config_from_subentry
from custom_components.moisture_loop.const import (
    CONF_RUNTIME_STORE_GENERATION_ID,
    CONF_RUNTIME_STORE_INITIALIZED,
    DOMAIN,
)
from custom_components.moisture_loop.models import (
    ActuatorIdentity,
    AppliedConfigurationShadow,
    AppliedEntityIdentity,
    BlockerReason,
    CompletionReason,
    ControllerState,
    DailyRuntime,
    FaultCode,
    IdentityStatus,
    MigrationRecordContext,
    NormalizedZoneSettings,
    RunIds,
    RuntimeEstimationReason,
    Schema1StoreData,
    SensorIdentity,
    SessionContext,
    SessionMode,
    StoreData,
    ZoneRecord,
    config_fingerprint,
    migrate_schema1_to_schema2,
    store_data_to_dict,
)
from custom_components.moisture_loop.storage import (
    SafetyStore,
    SetupClassification,
    StoreWriteVerificationError,
)

GEN = "11111111-2222-3333-4444-555555555555"
ZONE = "zone-sub-1"
SENSOR = "sensor.moisture_1"
SWITCH = "switch.valve_1"
START_AT = "2026-08-21 12:00:00+00:00"
NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=UTC)

ZONE_DATA = {
    "name": "Front bed",
    "moisture_sensor": SENSOR,
    "actuator": SWITCH,
    "start_threshold": 30.0,
    "target_threshold": 40.0,
    "pulse_duration": 300,
    "soak_duration": 1200,
    "max_cycles": 4,
    "max_session_runtime": 1800,
    "max_daily_runtime": 3600,
    "min_session_interval": 900,
    "sensor_max_age": 7200,
    "actuator_confirm_timeout": 30,
    "manual_max_duration": 1800,
}


class ScriptedSwitch:
    def __init__(self, hass) -> None:
        self.hass = hass
        self.on_calls = 0
        self.off_calls = 0
        self.off_behavior = "ack"
        hass.states.async_set(SWITCH, "off")

        async def turn_on(call) -> None:
            self.on_calls += 1
            hass.states.async_set(SWITCH, "on", context=call.context)

        async def turn_off(call) -> None:
            self.off_calls += 1
            if self.off_behavior == "ack":
                hass.states.async_set(SWITCH, "off", context=call.context)

        hass.services.async_register("switch", "turn_on", turn_on)
        hass.services.async_register("switch", "turn_off", turn_off)

    def set_state(self, state: str) -> None:
        self.hass.states.async_set(SWITCH, state)


def make_entry(hass, initialized: bool = True) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Moisture Loop",
        data={
            CONF_RUNTIME_STORE_GENERATION_ID: GEN,
            CONF_RUNTIME_STORE_INITIALIZED: initialized,
        },
        subentries_data=[
            ConfigSubentryData(
                data=ZONE_DATA,
                subentry_type="zone",
                title="Front bed",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    return entry


def zone_subentry_id(entry: MockConfigEntry) -> str:
    return next(iter(entry.subentries))


def seed_store(hass_storage, entry, data: StoreData) -> None:
    key = f"{DOMAIN}.{entry.entry_id}"
    hass_storage[key] = {
        "version": 1,
        "minor_version": 1,
        "key": key,
        "data": store_data_to_dict(data),
    }


def store_snapshot(
    zones: dict[str, ZoneRecord],
    active: str | None = "run-a",
    clean: str | None = "run-a",
    revision: int = 5,
) -> StoreData:
    config = zone_config_from_subentry(ZONE_DATA)
    contexts: dict[str, MigrationRecordContext] = {}
    for zone_id in zones:
        shadow = AppliedConfigurationShadow(
            subentry_id=zone_id,
            config_fingerprint="test-migration-shadow",
            entry_snapshot_fingerprint="test-migration-entry",
            applied_generation=1,
            normalized_settings=NormalizedZoneSettings.from_config(config),
            sensor_identity=AppliedEntityIdentity(None, SENSOR, "sensor"),
            actuator_identity=AppliedEntityIdentity(None, SWITCH, "switch"),
        )
        contexts[zone_id] = MigrationRecordContext(
            active_subentry_id=zone_id,
            applied_config=shadow,
            actuator_identity=ActuatorIdentity(
                registry_entry_id=None,
                last_known_entity_id=SWITCH,
                domain="switch",
                identity_status=IdentityStatus.REGISTRY_UNAVAILABLE,
                off_service="switch.turn_off",
                confirm_timeout_s=config.actuator_confirm_timeout_s,
            ),
            sensor_identity=SensorIdentity(None, SENSOR),
        )
    migrated = migrate_schema1_to_schema2(
        Schema1StoreData(
            generation_id=GEN,
            store_revision=max(1, revision - 1),
            run=RunIds(active_run_id=active, last_clean_shutdown_run_id=clean),
            zones=zones,
        ),
        contexts,
    )
    return migrated.evolve(
        generation_id=GEN,
        store_revision=revision,
        run=RunIds(active_run_id=active, last_clean_shutdown_run_id=clean),
    )


def watering_record(intent_at: datetime) -> ZoneRecord:
    return ZoneRecord(
        state=ControllerState.WATERING,
        enabled=True,
        daily=DailyRuntime(intent_at.date(), 0.0),
        session=SessionContext(
            session_id="sess-w",
            owner_run_id="run-a",
            config_fingerprint="fp-any",
            mode=SessionMode.AUTO,
            started_at_utc=intent_at,
            cycle=1,
            pulse_intent_at_utc=intent_at,
            pulse_commanded_at_utc=intent_at,
            pulse_confirmed_at_utc=intent_at,
            pulse_ends_at_utc=intent_at + timedelta(seconds=300),
        ),
    )


def soaking_record(
    fingerprint: str,
    owner: str = "run-a",
    soak_ends: datetime | None = None,
) -> ZoneRecord:
    soak = soak_ends if soak_ends is not None else NOW + timedelta(minutes=10)
    off = soak - timedelta(seconds=1200)
    return ZoneRecord(
        state=ControllerState.SOAKING,
        enabled=True,
        daily=DailyRuntime(NOW.date(), 300.0),
        session=SessionContext(
            session_id="sess-s",
            owner_run_id=owner,
            config_fingerprint=fingerprint,
            mode=SessionMode.AUTO,
            started_at_utc=off - timedelta(minutes=10),
            cycle=1,
            session_runtime_s=300.0,
            pulse_intent_at_utc=off - timedelta(minutes=6),
            pulse_commanded_at_utc=off - timedelta(minutes=5),
            pulse_confirmed_at_utc=off - timedelta(minutes=5),
            off_confirmed_at_utc=off,
            soak_ends_at_utc=soak,
            recheck_not_before_utc=soak,
            recheck_grace_deadline_at_utc=soak + timedelta(seconds=7200),
        ),
    )


def current_fingerprint() -> str:
    return config_fingerprint(
        zone_config_from_subentry(ZONE_DATA), str(dt_util.get_default_time_zone())
    )


async def settle(hass, cycles: int = 12) -> None:
    import asyncio

    for _ in range(cycles):
        await asyncio.sleep(0)
        await hass.async_block_till_done()


async def advance(env, seconds: float) -> None:
    env.freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(env.hass, dt_util.utcnow())
    await settle(env.hass)


async def start_runtime(hass, entry) -> EntryRuntime:
    runtime = EntryRuntime(hass, entry)
    await runtime.async_initialize()
    await settle(hass)
    return runtime


@pytest.fixture
async def env(hass, hass_storage, freezer):
    freezer.move_to(START_AT)
    switch = ScriptedSwitch(hass)
    await hass.async_block_till_done()
    yield SimpleNamespace(hass=hass, storage=hass_storage, freezer=freezer, switch=switch)


class TestFirstInstallAndIdentity:
    async def test_first_install_transaction(self, env) -> None:
        entry = make_entry(env.hass, initialized=False)
        runtime = await start_runtime(env.hass, entry)
        assert runtime.setup_classification is SetupClassification.FIRST_INSTALL
        # §23.5 step 5: the flag update happened only after verification.
        assert entry.data[CONF_RUNTIME_STORE_INITIALIZED] is True
        zone_id = zone_subentry_id(entry)
        assert runtime.controllers[zone_id].state is ControllerState.IDLE
        assert runtime.slots.snapshot().grants_enabled
        await runtime.async_unload()

    async def test_interrupted_initialization_completes_flag(self, env) -> None:
        entry = make_entry(env.hass, initialized=False)
        seed_store(env.storage, entry, store_snapshot({}, active=None, clean=None))
        runtime = await start_runtime(env.hass, entry)
        assert runtime.setup_classification is SetupClassification.INTERRUPTED_INITIALIZATION
        assert entry.data[CONF_RUNTIME_STORE_INITIALIZED] is True
        await runtime.async_unload()

    async def test_initial_write_failure_fails_setup_and_keeps_flag_false(
        self, env, monkeypatch
    ) -> None:
        entry = make_entry(env.hass, initialized=False)

        async def failing(self):
            raise StoreWriteVerificationError("injected")

        monkeypatch.setattr(SafetyStore, "async_first_initialize", failing)
        runtime = EntryRuntime(env.hass, entry)
        with pytest.raises(ConfigEntryNotReady):
            await runtime.async_initialize()
        assert entry.data[CONF_RUNTIME_STORE_INITIALIZED] is False
        assert not runtime.slots.snapshot().grants_enabled  # LC12/PI7
        assert env.switch.on_calls == 0

    async def test_integrity_loss_blocks_and_exhausts_today(self, env) -> None:
        entry = make_entry(env.hass, initialized=True)  # store absent
        runtime = await start_runtime(env.hass, entry)
        assert runtime.setup_classification is SetupClassification.INTEGRITY_LOSS
        zone_id = zone_subentry_id(entry)
        controller = runtime.controllers[zone_id]
        assert controller.state is ControllerState.FAULT
        assert controller.active_fault is FaultCode.RESTORED_FROM_UNSAFE_STATE
        assert controller.daily.runtime_s == 3600.0  # exhausted (PI3/PI10)
        # Neither AUTO nor MANUAL can start.
        env.hass.states.async_set(SENSOR, "5")
        await settle(env.hass)
        assert env.switch.on_calls == 0
        refused = await controller.async_manual_start(600.0)
        assert refused.transition_id == "T41"
        await runtime.async_unload()

    async def test_run_id_write_failure_never_watering_capable(self, env, monkeypatch) -> None:
        entry = make_entry(env.hass, initialized=True)
        seed_store(env.storage, entry, store_snapshot({}))

        async def failing(self, new_id):
            raise StoreWriteVerificationError("injected")

        monkeypatch.setattr(SafetyStore, "async_begin_new_run", failing)
        runtime = EntryRuntime(env.hass, entry)
        with pytest.raises(ConfigEntryNotReady):
            await runtime.async_initialize()
        assert not runtime.slots.snapshot().grants_enabled
        assert env.switch.on_calls == 0

    async def test_lc12_setup_failure_still_reconciles_hazard(self, env, monkeypatch) -> None:
        """Setup failure after readable config attempts defensive OFF."""
        entry = make_entry(env.hass, initialized=True)
        zone_id = zone_subentry_id(entry)
        env.switch.set_state("on")  # persisted WATERING and hardware ON
        await env.hass.async_block_till_done()
        seed_store(
            env.storage,
            entry,
            store_snapshot({zone_id: watering_record(NOW - timedelta(minutes=30))}),
        )

        async def failing(self, new_id):
            raise StoreWriteVerificationError("injected")

        monkeypatch.setattr(SafetyStore, "async_begin_new_run", failing)
        runtime = EntryRuntime(env.hass, entry)
        with pytest.raises(ConfigEntryNotReady):
            await runtime.async_initialize()
        assert env.switch.off_calls >= 1  # §24.4 minimal defensive OFF
        assert env.switch.on_calls == 0


class TestPersistedWateringRecovery:
    async def test_stage4_intent_only_crash_before_or_after_dispatch_never_resumes(
        self, env
    ) -> None:
        """ND12 W/X: durable intent covers both indistinguishable crashes."""
        entry = make_entry(env.hass, initialized=True)
        zone_id = zone_subentry_id(entry)
        intent = NOW - timedelta(minutes=20)
        record = watering_record(intent)
        assert record.session is not None
        record = record.evolve(
            session=record.session.evolve(
                pulse_commanded_at_utc=None,
                pulse_confirmed_at_utc=None,
            )
        )
        seed_store(env.storage, entry, store_snapshot({zone_id: record}))

        runtime = await start_runtime(env.hass, entry)
        controller = runtime.controllers[zone_id]
        summary = controller.last_summary
        assert env.switch.on_calls == 0
        assert controller.session is None
        assert summary is not None
        assert summary.reason is CompletionReason.RESTART_RECOVERY
        assert summary.runtime_estimated
        assert (
            summary.runtime_estimation_reason
            is RuntimeEstimationReason.RESTART_FOUND_OFF_UNKNOWN_STOP
        )
        assert summary.runtime_s == pytest.approx(1200.0)
        await runtime.async_unload()

    async def test_pi12_found_on_defensive_off_and_estimate(self, env) -> None:
        entry = make_entry(env.hass, initialized=True)
        zone_id = zone_subentry_id(entry)
        intent = NOW - timedelta(minutes=30)
        env.switch.set_state("on")
        await env.hass.async_block_till_done()
        seed_store(env.storage, entry, store_snapshot({zone_id: watering_record(intent)}))
        runtime = await start_runtime(env.hass, entry)
        controller = runtime.controllers[zone_id]
        assert env.switch.off_calls >= 1  # defensive OFF commanded
        assert controller.state is ControllerState.IDLE  # T48 finalized
        summary = controller.last_summary
        assert summary is not None
        assert summary.reason is CompletionReason.RESTART_RECOVERY
        assert summary.runtime_estimated
        assert summary.runtime_estimation_reason is RuntimeEstimationReason.RESTART_FOUND_ON
        # Estimated from intent through OFF confirmation: >= 30 minutes.
        assert summary.runtime_s >= 1800.0
        assert controller.session is None  # never resumed (I13)
        assert env.switch.on_calls == 0
        await runtime.async_unload()

    async def test_pi13_found_off_estimates_to_reconciliation(self, env) -> None:
        entry = make_entry(env.hass, initialized=True)
        zone_id = zone_subentry_id(entry)
        intent = NOW - timedelta(minutes=45)
        seed_store(env.storage, entry, store_snapshot({zone_id: watering_record(intent)}))
        runtime = await start_runtime(env.hass, entry)
        controller = runtime.controllers[zone_id]
        summary = controller.last_summary
        assert summary is not None
        assert (
            summary.runtime_estimation_reason
            is RuntimeEstimationReason.RESTART_FOUND_OFF_UNKNOWN_STOP
        )
        # Intent -> reconciliation time (45 min), never the scheduled 5-min
        # pulse end (PI13).
        assert summary.runtime_s == pytest.approx(2700.0)
        assert controller.daily.runtime_s == pytest.approx(2700.0)
        assert env.switch.on_calls == 0
        await runtime.async_unload()

    async def test_pi14_unproven_actuator_blocks_and_faults(self, env) -> None:
        entry = make_entry(env.hass, initialized=True)
        zone_id = zone_subentry_id(entry)
        env.switch.set_state("unavailable")
        env.switch.off_behavior = "silent"
        await env.hass.async_block_till_done()
        seed_store(
            env.storage,
            entry,
            store_snapshot({zone_id: watering_record(NOW - timedelta(minutes=10))}),
        )
        runtime = await start_runtime(env.hass, entry)
        controller = runtime.controllers[zone_id]
        # OFF attempts were made; grants must not be possible while the
        # blocker remains.
        assert env.switch.off_calls >= 1
        assert (zone_id, BlockerReason.INTEGRATION_OFF_UNCONFIRMED) in (
            runtime.slots.blockers()
        ) or (zone_id, BlockerReason.ACTUATOR_NOT_PROVEN_OFF) in runtime.slots.blockers()
        # Let the bounded OFF attempts run out: T49 latches the fault with
        # open accounting and the blocker retained.
        for _ in range(3):
            await advance(env, 30)
        assert controller.state is ControllerState.FAULT
        assert controller.active_fault is FaultCode.ACTUATOR_OFF_TIMEOUT
        assert (zone_id, BlockerReason.INTEGRATION_OFF_UNCONFIRMED) in (runtime.slots.blockers())
        await runtime.async_unload()

    async def test_pi15_large_downtime_exhausts_budget(self, env) -> None:
        entry = make_entry(env.hass, initialized=True)
        zone_id = zone_subentry_id(entry)
        intent = NOW - timedelta(days=2)
        seed_store(env.storage, entry, store_snapshot({zone_id: watering_record(intent)}))
        runtime = await start_runtime(env.hass, entry)
        controller = runtime.controllers[zone_id]
        summary = controller.last_summary
        assert summary is not None
        assert summary.runtime_s == pytest.approx(2 * 86400.0)  # never undercounted
        # Today's charge alone exceeds the 3600 s budget: AUTO refused.
        env.hass.states.async_set(SENSOR, "5")
        await settle(env.hass)
        assert env.switch.on_calls == 0
        decision = await controller.async_evaluate()
        assert decision.guard_result is not None
        assert "G-DAY" in decision.guard_result.failed_guards
        await runtime.async_unload()


class TestSoakingAdoption:
    async def test_lc5_clean_run_adopts_soaking(self, env) -> None:
        entry = make_entry(env.hass, initialized=True)
        zone_id = zone_subentry_id(entry)
        record = soaking_record(current_fingerprint(), owner="run-a")
        seed_store(
            env.storage, entry, store_snapshot({zone_id: record}, active="run-a", clean="run-a")
        )
        runtime = await start_runtime(env.hass, entry)
        controller = runtime.controllers[zone_id]
        assert runtime.soaking_adoptions[zone_id] is True
        assert controller.state is ControllerState.SOAKING
        session = controller.session
        assert session is not None
        # LC10: only the owner changed; identity and timing preserved.
        assert session.owner_run_id == runtime.run_id
        original = record.session
        assert original is not None
        assert session.session_id == original.session_id
        assert session.started_at_utc == original.started_at_utc
        assert session.cycle == original.cycle
        assert session.session_runtime_s == original.session_runtime_s
        assert session.soak_ends_at_utc == original.soak_ends_at_utc
        assert session.recheck_grace_deadline_at_utc == original.recheck_grace_deadline_at_utc
        assert session.config_fingerprint == original.config_fingerprint
        # The rebase was persisted before activation.
        persisted = runtime.store.data.zones[zone_id].session
        assert persisted is not None and persisted.owner_run_id == runtime.run_id
        assert env.switch.on_calls == 0  # adoption never creates a pulse
        await runtime.async_unload()

    async def test_lc6_second_clean_run_adopts_again(self, env) -> None:
        entry = make_entry(env.hass, initialized=True)
        zone_id = zone_subentry_id(entry)
        record = soaking_record(current_fingerprint(), owner="run-a")
        seed_store(
            env.storage, entry, store_snapshot({zone_id: record}, active="run-a", clean="run-a")
        )
        run_b = await start_runtime(env.hass, entry)
        assert run_b.soaking_adoptions[zone_id] is True
        # Run B shuts down cleanly.
        await run_b.async_handle_ha_stop(None)
        run_b.process_stopping = True
        await run_b.async_unload()
        # Run C starts and adopts the same soak from clean Run B.
        run_c = await start_runtime(env.hass, entry)
        assert run_c.soaking_adoptions[zone_id] is True
        controller = run_c.controllers[zone_id]
        assert controller.state is ControllerState.SOAKING
        assert controller.session is not None
        assert controller.session.session_id == "sess-s"
        assert controller.session.owner_run_id == run_c.run_id
        await run_c.async_unload()

    async def test_lc7_crashed_intermediate_run_rejects(self, env) -> None:
        entry = make_entry(env.hass, initialized=True)
        zone_id = zone_subentry_id(entry)
        record = soaking_record(current_fingerprint(), owner="run-b")
        # Run B persisted its active ID but crashed before clean marking.
        seed_store(
            env.storage, entry, store_snapshot({zone_id: record}, active="run-b", clean="run-a")
        )
        runtime = await start_runtime(env.hass, entry)
        controller = runtime.controllers[zone_id]
        assert runtime.soaking_adoptions[zone_id] is False
        assert controller.state is ControllerState.IDLE  # T51
        assert controller.last_summary is not None
        assert controller.last_summary.reason is CompletionReason.RESTART_RECOVERY
        await runtime.async_unload()

    async def test_lc8_fingerprint_change_prevents_rebase(self, env) -> None:
        entry = make_entry(env.hass, initialized=True)
        zone_id = zone_subentry_id(entry)
        record = soaking_record("stale-fingerprint", owner="run-a")
        seed_store(
            env.storage, entry, store_snapshot({zone_id: record}, active="run-a", clean="run-a")
        )
        runtime = await start_runtime(env.hass, entry)
        assert runtime.soaking_adoptions[zone_id] is False
        # No rebase was persisted: the session was terminated instead.
        persisted = runtime.store.data.zones[zone_id]
        assert persisted.session is None
        await runtime.async_unload()

    async def test_lc9_rebase_failure_prohibits_setup(self, env, monkeypatch) -> None:
        entry = make_entry(env.hass, initialized=True)
        zone_id = zone_subentry_id(entry)
        record = soaking_record(current_fingerprint(), owner="run-a")
        seed_store(
            env.storage, entry, store_snapshot({zone_id: record}, active="run-a", clean="run-a")
        )

        async def failing(self, zone_id, new_run_id):
            raise StoreWriteVerificationError("injected")

        monkeypatch.setattr(SafetyStore, "async_rebase_soaking_owner_for_record", failing)
        runtime = EntryRuntime(env.hass, entry)
        with pytest.raises(ConfigEntryNotReady):
            await runtime.async_initialize()
        assert not runtime.slots.snapshot().grants_enabled
        assert env.switch.on_calls == 0

    async def test_lc11_offline_expired_soak_faults_stale(self, env) -> None:
        """Both deadlines passed offline; the only report predates the soak
        deadline and must never be used (§25.3): SENSOR_STALE."""
        entry = make_entry(env.hass, initialized=True)
        zone_id = zone_subentry_id(entry)
        # The last report happened before the stored soak deadline.
        env.freezer.move_to("2026-08-21 08:00:00+00:00")
        env.hass.states.async_set(SENSOR, "33")
        await env.hass.async_block_till_done()
        env.freezer.move_to(START_AT)
        record = soaking_record(
            current_fingerprint(), owner="run-a", soak_ends=NOW - timedelta(hours=3)
        )
        seed_store(
            env.storage, entry, store_snapshot({zone_id: record}, active="run-a", clean="run-a")
        )
        runtime = await start_runtime(env.hass, entry)
        controller = runtime.controllers[zone_id]
        assert runtime.soaking_adoptions[zone_id] is True
        assert controller.state is ControllerState.FAULT
        assert controller.active_fault is FaultCode.SENSOR_STALE
        assert env.switch.on_calls == 0  # rebase alone never creates a pulse
        await runtime.async_unload()

    async def test_lc11_offline_expired_soak_unavailable_sensor(self, env) -> None:
        """With the sensor entirely absent, the §18.4 explicit fault path
        applies at the grace re-check (T30)."""
        entry = make_entry(env.hass, initialized=True)
        zone_id = zone_subentry_id(entry)
        record = soaking_record(
            current_fingerprint(), owner="run-a", soak_ends=NOW - timedelta(hours=3)
        )
        seed_store(
            env.storage, entry, store_snapshot({zone_id: record}, active="run-a", clean="run-a")
        )
        runtime = await start_runtime(env.hass, entry)
        controller = runtime.controllers[zone_id]
        assert controller.state is ControllerState.FAULT
        assert controller.active_fault is FaultCode.SENSOR_UNAVAILABLE
        assert env.switch.on_calls == 0
        await runtime.async_unload()

    async def test_lc11_offline_soak_with_grace_remaining_waits(self, env) -> None:
        entry = make_entry(env.hass, initialized=True)
        zone_id = zone_subentry_id(entry)
        record = soaking_record(
            current_fingerprint(), owner="run-a", soak_ends=NOW - timedelta(minutes=30)
        )
        seed_store(
            env.storage, entry, store_snapshot({zone_id: record}, active="run-a", clean="run-a")
        )
        runtime = await start_runtime(env.hass, entry)
        controller = runtime.controllers[zone_id]
        assert controller.state is ControllerState.SOAKING  # waiting in grace
        # A report at/after the stored soak deadline decides normally.
        env.hass.states.async_set(SENSOR, "45")
        await settle(env.hass)
        assert controller.state is ControllerState.IDLE
        assert controller.last_summary is not None
        assert controller.last_summary.reason is CompletionReason.TARGET_REACHED
        await runtime.async_unload()

    async def test_untrusted_when_actuator_not_proven_off(self, env) -> None:
        entry = make_entry(env.hass, initialized=True)
        zone_id = zone_subentry_id(entry)
        env.switch.set_state("unavailable")
        await env.hass.async_block_till_done()
        record = soaking_record(current_fingerprint(), owner="run-a")
        seed_store(
            env.storage, entry, store_snapshot({zone_id: record}, active="run-a", clean="run-a")
        )
        runtime = await start_runtime(env.hass, entry)
        assert runtime.soaking_adoptions[zone_id] is False
        await runtime.async_unload()


class TestShutdownAndReload:
    async def _start_watering(self, env, runtime, zone_id) -> None:
        env.hass.states.async_set(SENSOR, "27")
        await settle(env.hass)
        assert runtime.controllers[zone_id].state is ControllerState.WATERING

    async def test_lc4_full_shutdown(self, env) -> None:
        entry = make_entry(env.hass, initialized=False)
        runtime = await start_runtime(env.hass, entry)
        zone_id = zone_subentry_id(entry)
        await self._start_watering(env, runtime, zone_id)
        await runtime.async_handle_ha_stop(None)
        await settle(env.hass)
        controller = runtime.controllers[zone_id]
        # WATERING stopped with the shutdown reason and one OFF.
        assert controller.last_summary is not None
        assert controller.last_summary.reason is CompletionReason.HOME_ASSISTANT_SHUTDOWN
        assert env.switch.off_calls == 1
        # Clean marking happened only after safety persistence.
        run = runtime.store.data.run
        assert run.active_run_id == runtime.run_id
        assert run.previous_run_was_clean
        await runtime.async_unload()

    async def test_lc4_shutdown_preserves_soaking(self, env) -> None:
        entry = make_entry(env.hass, initialized=True)
        zone_id = zone_subentry_id(entry)
        record = soaking_record(current_fingerprint(), owner="run-a")
        seed_store(
            env.storage, entry, store_snapshot({zone_id: record}, active="run-a", clean="run-a")
        )
        runtime = await start_runtime(env.hass, entry)
        await runtime.async_handle_ha_stop(None)
        await settle(env.hass)
        persisted = runtime.store.data.zones[zone_id]
        assert persisted.state is ControllerState.SOAKING  # T37 preserved
        assert persisted.session is not None
        assert runtime.store.data.run.previous_run_was_clean
        await runtime.async_unload()

    async def test_lc3_generic_reload_terminates_and_keeps_run_ids(self, env) -> None:
        entry = make_entry(env.hass, initialized=False)
        runtime = await start_runtime(env.hass, entry)
        zone_id = zone_subentry_id(entry)
        await self._start_watering(env, runtime, zone_id)
        run_before = runtime.store.data.run
        await runtime.async_unload()
        await settle(env.hass)
        controller_summary = runtime.store.data.zones[zone_id].last_session_summary
        assert controller_summary is not None
        assert controller_summary.reason is CompletionReason.CONFIG_RELOAD
        # §24.2: entry reload never changes run IDs or marks clean.
        assert runtime.store.data.run == run_before
        assert not runtime.store.data.run.previous_run_was_clean

    async def test_lc3_reconfigure_prepares_with_config_changed(self, env) -> None:
        entry = make_entry(env.hass, initialized=False)
        runtime = await start_runtime(env.hass, entry)
        zone_id = zone_subentry_id(entry)
        await self._start_watering(env, runtime, zone_id)
        await runtime.async_prepare_reconfigure(zone_id)
        await settle(env.hass)
        controller = runtime.controllers[zone_id]
        assert controller.state is ControllerState.IDLE
        assert controller.last_summary is not None
        assert controller.last_summary.reason is CompletionReason.CONFIG_CHANGED
        assert env.switch.off_calls == 1
        await runtime.async_unload()

    async def test_prepare_reconfigure_for_unknown_zone_is_noop(self, env) -> None:
        entry = make_entry(env.hass, initialized=False)
        runtime = await start_runtime(env.hass, entry)
        await runtime.async_prepare_reconfigure("missing-zone")
        await runtime.async_prepare_delete("missing-zone")
        await runtime.async_unload()

    async def test_shutdown_fallback_cancels_and_best_effort_off(self, env) -> None:
        entry = make_entry(env.hass, initialized=False)
        runtime = await start_runtime(env.hass, entry)
        zone_id = zone_subentry_id(entry)
        await self._start_watering(env, runtime, zone_id)
        env.switch.off_behavior = "silent"
        runtime.shutdown_off_budget_s = 0  # immediate bounded fallback
        await runtime.async_handle_ha_stop(None)
        await settle(env.hass)
        # The fallback still attempted OFF through the same actuator path.
        assert env.switch.off_calls >= 1
        # Clean marking reflects that the handler completed honestly.
        assert runtime.store.data.run.previous_run_was_clean
        await runtime.async_unload()


class TestStartupResourceSafety:
    async def test_er12_external_on_before_setup_blocks_grants(self, env) -> None:
        """Startup finds a configured actuator ON: no forced OFF, blocker
        populated, and no AUTO/MANUAL grant occurs (ER6/ER12)."""
        entry = make_entry(env.hass, initialized=False)
        env.switch.set_state("on")
        await env.hass.async_block_till_done()
        runtime = await start_runtime(env.hass, entry)
        zone_id = zone_subentry_id(entry)
        record_id = runtime.bindings[zone_id].safety_record_id
        assert env.switch.off_calls == 0  # respected, never counter-commanded
        assert (record_id, BlockerReason.EXTERNAL_FLOW) in runtime.slots.blockers()
        env.hass.states.async_set(SENSOR, "5")
        await settle(env.hass)
        assert env.switch.on_calls == 0  # no grant while occupied
        # Proven OFF releases the key; a fresh evaluation may then start.
        env.switch.set_state("off")
        await settle(env.hass)
        assert runtime.slots.blockers() == frozenset()
        await runtime.controllers[zone_id].async_evaluate()
        await settle(env.hass)
        assert env.switch.on_calls == 1
        await runtime.async_unload()

    async def test_startup_unknown_actuator_adds_not_proven_off(self, env) -> None:
        entry = make_entry(env.hass, initialized=False)
        env.switch.set_state("unknown")
        await env.hass.async_block_till_done()
        runtime = await start_runtime(env.hass, entry)
        zone_id = zone_subentry_id(entry)
        record_id = runtime.bindings[zone_id].safety_record_id
        assert (record_id, BlockerReason.ACTUATOR_NOT_PROVEN_OFF) in runtime.slots.blockers()
        await runtime.async_unload()

    async def test_setup_entry_and_unload_via_module_api(self, env) -> None:
        from unittest.mock import AsyncMock, patch

        from custom_components.moisture_loop import async_setup_entry, async_unload_entry

        entry = make_entry(env.hass, initialized=False)
        # Platform forwarding needs HA's own setup machinery; the flow tests
        # cover it end-to-end. Here the lifecycle orchestration is under test.
        with (
            patch.object(
                env.hass.config_entries, "async_forward_entry_setups", AsyncMock()
            ) as forward,
            patch.object(
                env.hass.config_entries,
                "async_unload_platforms",
                AsyncMock(return_value=True),
            ),
        ):
            assert await async_setup_entry(env.hass, entry)
            runtime = entry.runtime_data
            assert isinstance(runtime, EntryRuntime)
            forward.assert_awaited_once()
            assert await async_unload_entry(env.hass, entry)


class TestRuntimeEdges:
    """Remaining deterministic lifecycle edges."""

    async def test_async_setup_returns_true(self, env) -> None:
        from custom_components.moisture_loop import async_setup

        assert await async_setup(env.hass, {}) is True

    async def test_reconstruction_write_failure_fails_setup(self, env, monkeypatch) -> None:
        entry = make_entry(env.hass, initialized=True)  # store absent -> loss

        async def failing(self, budgets, date_local):
            raise StoreWriteVerificationError("injected")

        monkeypatch.setattr(SafetyStore, "async_reconstruct_after_integrity_loss", failing)
        runtime = EntryRuntime(env.hass, entry)
        with pytest.raises(ConfigEntryNotReady):
            await runtime.async_initialize()
        assert not runtime.slots.snapshot().grants_enabled

    async def test_defensive_reconciliation_edges(self, env) -> None:
        entry = make_entry(env.hass, initialized=True)
        zone_id = zone_subentry_id(entry)
        runtime = EntryRuntime(env.hass, entry)
        # Store not loaded: nothing to do.
        await runtime._defensive_reconciliation()
        # Loaded store with: one non-watering zone, one watering zone whose
        # config is missing, and one watering zone with a proven-off switch.
        seed_store(
            env.storage,
            entry,
            store_snapshot(
                {
                    zone_id: ZoneRecord(ControllerState.IDLE, True),
                    "orphan-zone": watering_record(NOW - timedelta(minutes=5)),
                }
            ),
        )
        await runtime.store.async_classify_setup(True)
        await runtime._defensive_reconciliation()
        assert env.switch.off_calls == 0  # nothing hazardous to command
        # Watering zone with the real switch ON: OFF is attempted; a raising
        # service is tolerated (best effort). A fresh runtime is needed
        # because HA's Store caches its first load.
        seed_store(
            env.storage,
            entry,
            store_snapshot({zone_id: watering_record(NOW - timedelta(minutes=5))}),
        )
        runtime2 = EntryRuntime(env.hass, entry)
        await runtime2.store.async_classify_setup(True)
        env.switch.set_state("on")
        await env.hass.async_block_till_done()

        async def raising_off(call):
            env.switch.off_calls += 1
            raise RuntimeError("scripted OFF failure")

        env.hass.services.async_register("switch", "turn_off", raising_off)
        await runtime2._defensive_reconciliation()
        assert env.switch.off_calls == 1
        # Already proven OFF: no command is issued.
        env.switch.set_state("off")
        await env.hass.async_block_till_done()
        await runtime2._defensive_reconciliation()
        assert env.switch.off_calls == 1

    async def test_non_zone_subentry_is_ignored(self, env) -> None:
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_RUNTIME_STORE_GENERATION_ID: GEN,
                CONF_RUNTIME_STORE_INITIALIZED: False,
            },
            subentries_data=[
                ConfigSubentryData(
                    data=ZONE_DATA, subentry_type="zone", title="Bed", unique_id=None
                ),
                ConfigSubentryData(
                    data={}, subentry_type="other", title="Not a zone", unique_id=None
                ),
            ],
        )
        entry.add_to_hass(env.hass)
        runtime = await start_runtime(env.hass, entry)
        assert len(runtime.controllers) == 1
        await runtime.async_unload()

    async def test_session_structure_validation(self, env) -> None:
        base = soaking_record(current_fingerprint()).session
        assert base is not None
        assert EntryRuntime._session_structure_valid(base)
        manual = base.evolve(mode=SessionMode.MANUAL)
        assert not EntryRuntime._session_structure_valid(manual)
        missing = base.evolve(soak_ends_at_utc=None)
        assert not EntryRuntime._session_structure_valid(missing)
        disordered = base.evolve(
            recheck_not_before_utc=base.soak_ends_at_utc + timedelta(seconds=1)
        )
        assert not EntryRuntime._session_structure_valid(disordered)
        no_off = base.evolve(off_confirmed_at_utc=None)
        assert not EntryRuntime._session_structure_valid(no_off)

    async def test_passive_listener_window(self, env) -> None:
        """ER12: live observation is keyed by canonical record identity."""
        entry = make_entry(env.hass, initialized=False)
        runtime = await start_runtime(env.hass, entry)
        zone_id = zone_subentry_id(entry)
        record_id = runtime.bindings[zone_id].safety_record_id
        env.switch.set_state("on")
        await settle(env.hass)
        assert (record_id, BlockerReason.EXTERNAL_FLOW) in runtime.slots.blockers()
        env.switch.set_state("unknown")
        await settle(env.hass)
        assert (record_id, BlockerReason.EXTERNAL_FLOW) in runtime.slots.blockers()
        env.switch.set_state("off")  # proven OFF adds nothing here
        await settle(env.hass)
        await runtime.async_unload()
        await runtime.slots.async_remove_blocker(record_id, BlockerReason.EXTERNAL_FLOW)
        await runtime.slots.async_remove_blocker(record_id, BlockerReason.ACTUATOR_NOT_PROVEN_OFF)
        env.switch.set_state("on")
        await settle(env.hass)
        assert runtime.slots.blockers() == frozenset()  # listeners removed

    async def test_stop_handler_is_once_only(self, env) -> None:
        entry = make_entry(env.hass, initialized=False)
        runtime = await start_runtime(env.hass, entry)
        await runtime.async_handle_ha_stop(None)
        revision = runtime.store.data.store_revision
        await runtime.async_handle_ha_stop(None)  # re-entry guard
        assert runtime.store.data.store_revision == revision
        await runtime.async_unload()

    async def test_shutdown_persists_resting_zone(self, env) -> None:
        entry = make_entry(env.hass, initialized=False)
        runtime = await start_runtime(env.hass, entry)
        zone_id = zone_subentry_id(entry)
        await runtime.async_handle_ha_stop(None)
        persisted = runtime.store.data.zones[zone_id]
        assert persisted.state is ControllerState.IDLE
        assert runtime.store.data.run.previous_run_was_clean
        await runtime.async_unload()

    async def test_clean_marking_failure_is_fail_safe(self, env, monkeypatch) -> None:
        entry = make_entry(env.hass, initialized=False)
        runtime = await start_runtime(env.hass, entry)

        async def failing(self):
            raise StoreWriteVerificationError("injected")

        monkeypatch.setattr(SafetyStore, "async_mark_clean_shutdown", failing)
        await runtime.async_handle_ha_stop(None)  # must not raise
        # The run stays unclean: exactly the crash-equivalent safe outcome.
        assert not runtime.store.data.run.previous_run_was_clean
        await runtime.async_unload()

    async def test_await_off_budget_without_watering(self, env) -> None:
        entry = make_entry(env.hass, initialized=False)
        runtime = await start_runtime(env.hass, entry)
        zone_id = zone_subentry_id(entry)
        controller = runtime.controllers[zone_id]
        await runtime._await_off_within_budget(controller)  # idle: no-op
        await runtime.async_unload()

    async def test_shutdown_fallback_with_raising_off(self, env) -> None:
        entry = make_entry(env.hass, initialized=False)
        runtime = await start_runtime(env.hass, entry)
        zone_id = zone_subentry_id(entry)
        env.hass.states.async_set(SENSOR, "27")
        await settle(env.hass)
        assert runtime.controllers[zone_id].state is ControllerState.WATERING

        async def raising_off(call):
            env.switch.off_calls += 1
            raise RuntimeError("scripted OFF failure")

        env.hass.services.async_register("switch", "turn_off", raising_off)
        runtime.shutdown_off_budget_s = 0
        await runtime.async_handle_ha_stop(None)
        await settle(env.hass)
        assert env.switch.off_calls >= 1  # best effort attempted
        await runtime.async_unload()

    async def test_fallback_without_session_task(self, env) -> None:
        entry = make_entry(env.hass, initialized=False)
        runtime = await start_runtime(env.hass, entry)
        zone_id = zone_subentry_id(entry)
        env.hass.states.async_set(SENSOR, "27")
        await settle(env.hass)
        controller = runtime.controllers[zone_id]
        assert controller.state is ControllerState.WATERING
        # The owner task is gone (forced teardown); the fallback still makes
        # the best-effort OFF call without a task to cancel.
        task = controller._session_task
        if task is not None:
            task.cancel()
            await settle(env.hass)
        controller._session_task = None
        controller._off_operation = None
        runtime.shutdown_off_budget_s = 0
        before = env.switch.off_calls
        await runtime._await_off_within_budget(controller)
        assert env.switch.off_calls == before + 1
        await runtime.async_unload()

    async def test_prepare_reconfigure_idle_and_soaking(self, env) -> None:
        entry = make_entry(env.hass, initialized=True)
        zone_id = zone_subentry_id(entry)
        record = soaking_record(current_fingerprint(), owner="run-a")
        seed_store(
            env.storage,
            entry,
            store_snapshot({zone_id: record}, active="run-a", clean="run-a"),
        )
        runtime = await start_runtime(env.hass, entry)
        controller = runtime.controllers[zone_id]
        assert controller.state is ControllerState.SOAKING
        await runtime.async_prepare_reconfigure(zone_id)
        await settle(env.hass)
        assert controller.state is ControllerState.IDLE  # T39
        assert controller.last_summary is not None
        assert controller.last_summary.reason is CompletionReason.CONFIG_CHANGED
        # Idle zone: preparation is a no-op.
        await runtime.async_prepare_reconfigure(zone_id)
        await runtime.async_unload()
