"""Slice 6 tests: moisture adapter and report normalization (§5.2, §10).

HA-harness suite: proves the §39.1 unchanged-report mechanics on the real
minimum release, the classification table, entity filtering, cleanup,
fallback-scan semantics, and registry removal/rename inputs. Skips cleanly
in the pure environment.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("homeassistant")

from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED

from custom_components.moisture_loop.models import (
    ActuatorAssessment,
    MoistureClassification,
    MoistureObservation,
    MoistureReport,
    ResourceAssessment,
    SessionContext,
    SessionMode,
    TransitionInput,
    ZoneConfig,
)
from custom_components.moisture_loop.models import ControllerState as CS
from custom_components.moisture_loop.state_machine import decide
from custom_components.moisture_loop.zone_controller import (
    MoistureAdapter,
    classify_moisture,
)

SENSOR = "sensor.front_bed_moisture"
OTHER_SENSOR = "sensor.other"
MAX_AGE_S = 7200


class Clock:
    """Deterministic injectable clock for normalization."""

    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def make_adapter(hass, sink_list, removed_list=None, renamed_list=None, clock=None):
    return MoistureAdapter(
        hass,
        SENSOR,
        MAX_AGE_S,
        sink=sink_list.append,
        on_removed=lambda: (removed_list or []).append(True),
        on_renamed=(renamed_list.append if renamed_list is not None else None),
        clock=clock,
    )


class TestStateReportedMechanics:
    """§39.1 harness reproduction on the exact minimum release."""

    async def test_identical_second_write_emits_report_and_advances(self, hass) -> None:
        observations: list[MoistureObservation] = []
        change_calls: list[MoistureObservation] = []

        adapter = MoistureAdapter(
            hass,
            SENSOR,
            MAX_AGE_S,
            sink=observations.append,
            on_removed=lambda: None,
        )
        # Track which path delivered by wrapping the handlers' sink calls:
        original_change = adapter._handle_state_change

        def spy_change(event):
            original_change(event)
            change_calls.append(observations[-1])

        adapter._handle_state_change = spy_change  # type: ignore[method-assign]
        adapter.async_start()

        hass.states.async_set(SENSOR, "33", {"unit_of_measurement": "%"})
        await hass.async_block_till_done()
        first_reported = hass.states.get(SENSOR).last_reported
        assert len(observations) == 1

        # Identical state AND identical attributes: current Core emits
        # state_reported, not state_changed.
        hass.states.async_set(SENSOR, "33", {"unit_of_measurement": "%"})
        await hass.async_block_till_done()
        second = hass.states.get(SENSOR)
        assert second.last_reported > first_reported  # last_reported advances
        assert len(observations) == 2  # the report path ran
        assert len(change_calls) == 1  # no ordinary state-change callback
        # The unchanged report is a real observation with the new timestamp.
        assert observations[1].classification is MoistureClassification.VALID
        assert observations[1].value == 33.0
        assert observations[1].reported_at_utc == second.last_reported
        adapter.async_stop()

    async def test_report_observation_can_qualify_post_soak(self, hass) -> None:
        """SR1/SR3 adapter portion: an identical report at/after the soak
        deadline qualifies through the pure recheck path."""
        observations: list[MoistureObservation] = []
        adapter = MoistureAdapter(
            hass, SENSOR, MAX_AGE_S, sink=observations.append, on_removed=lambda: None
        )
        adapter.async_start()
        hass.states.async_set(SENSOR, "33")
        await hass.async_block_till_done()
        hass.states.async_set(SENSOR, "33")  # identical -> state_reported
        await hass.async_block_till_done()
        obs = observations[-1]
        assert obs.reported_at_utc is not None
        soak_ends = obs.reported_at_utc  # report exactly at the deadline
        config = _config()
        session = SessionContext(
            session_id="s",
            owner_run_id="r",
            config_fingerprint="f",
            mode=SessionMode.AUTO,
            started_at_utc=obs.reported_at_utc - timedelta(minutes=30),
            cycle=1,
            session_runtime_s=300.0,
            soak_ends_at_utc=soak_ends,
            recheck_not_before_utc=soak_ends,
            recheck_grace_deadline_at_utc=soak_ends + timedelta(seconds=MAX_AGE_S),
        )
        decision = decide(
            TransitionInput(
                now_utc=obs.reported_at_utc,
                config=config,
                state=CS.SOAKING,
                enabled=True,
                session=session,
                active_fault=None,
                secondary_fault=None,
                observation=obs,
                daily_runtime_s=0.0,
                last_session_end_utc=None,
                actuator=ActuatorAssessment(True, True, False),
                resource=ResourceAssessment(True, True),
                armed_watchdog=None,
                event=MoistureReport(obs),
            )
        )
        assert decision.transition_id == "T25"  # 33 < target 40: next pulse

    async def test_entity_filtering(self, hass) -> None:
        """Only the configured entity's writes reach the callbacks."""
        observations: list[MoistureObservation] = []
        adapter = MoistureAdapter(
            hass, SENSOR, MAX_AGE_S, sink=observations.append, on_removed=lambda: None
        )
        adapter.async_start()
        hass.states.async_set(OTHER_SENSOR, "50")
        hass.states.async_set(OTHER_SENSOR, "50")  # would be a report
        await hass.async_block_till_done()
        assert observations == []
        hass.states.async_set(SENSOR, "20")
        await hass.async_block_till_done()
        assert len(observations) == 1
        adapter.async_stop()

    async def test_stop_unsubscribes(self, hass) -> None:
        observations: list[MoistureObservation] = []
        adapter = MoistureAdapter(
            hass, SENSOR, MAX_AGE_S, sink=observations.append, on_removed=lambda: None
        )
        adapter.async_start()
        assert adapter.started
        adapter.async_start()  # idempotent
        hass.states.async_set(SENSOR, "20")
        await hass.async_block_till_done()
        assert len(observations) == 1
        adapter.async_stop()
        assert not adapter.started
        hass.states.async_set(SENSOR, "25")
        hass.states.async_set(SENSOR, "25")
        await hass.async_block_till_done()
        assert len(observations) == 1

    async def test_callbacks_never_call_services(self, hass) -> None:
        """Adapter callbacks are observation-only; no service call occurs."""
        calls: list = []

        async def record(call) -> None:
            calls.append(call)

        hass.services.async_register("switch", "turn_on", record)
        hass.services.async_register("switch", "turn_off", record)
        observations: list[MoistureObservation] = []
        adapter = MoistureAdapter(
            hass, SENSOR, MAX_AGE_S, sink=observations.append, on_removed=lambda: None
        )
        adapter.async_start()
        hass.states.async_set(SENSOR, "5")  # far below any threshold
        hass.states.async_set(SENSOR, "5")
        await hass.async_block_till_done()
        assert observations  # events were processed
        assert calls == []  # water was never commanded


class TestFallbackScan:
    async def test_scan_uses_stored_last_reported_not_scan_time(self, hass) -> None:
        clock = Clock(datetime(2026, 8, 21, 12, 0, tzinfo=UTC))
        observations: list[MoistureObservation] = []
        adapter = make_adapter(hass, observations, clock=clock)
        hass.states.async_set(SENSOR, "33")
        await hass.async_block_till_done()
        stored = hass.states.get(SENSOR).last_reported
        clock.now = stored + timedelta(hours=1)
        scan = adapter.scan_current()
        assert scan.reported_at_utc == stored  # never the scan time
        assert scan.classification is MoistureClassification.VALID
        # Beyond max age the same stored report classifies STALE: the scan
        # cannot manufacture freshness (§10.3).
        clock.now = stored + timedelta(seconds=MAX_AGE_S) + timedelta(seconds=1)
        stale_scan = adapter.scan_current()
        assert stale_scan.classification is MoistureClassification.STALE
        assert stale_scan.reported_at_utc == stored

    async def test_scan_of_absent_entity_is_unavailable(self, hass) -> None:
        adapter = make_adapter(hass, [])
        scan = adapter.scan_current()
        assert scan.classification is MoistureClassification.UNAVAILABLE


class TestRegistryTracking:
    async def test_removal_produces_invalid_configuration_input(self, hass) -> None:
        removed: list[bool] = []
        adapter = MoistureAdapter(
            hass, SENSOR, MAX_AGE_S, sink=lambda o: None, on_removed=lambda: removed.append(True)
        )
        adapter.async_start()
        hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED, {"action": "remove", "entity_id": SENSOR}
        )
        await hass.async_block_till_done()
        assert removed == [True]

    async def test_rename_is_reported_but_never_self_applied(self, hass) -> None:
        """The adapter reports a rename; only its owner may re-point it.

        SPEC 23.2 item 1/25.1.1: equivalence needs an exact Registry UUID
        match, which the adapter cannot perform.  It therefore hands the
        candidate entity ID upward and leaves its own addressing untouched.
        """
        renamed: list[str] = []
        adapter = MoistureAdapter(
            hass,
            SENSOR,
            MAX_AGE_S,
            sink=lambda o: None,
            on_removed=lambda: None,
            on_renamed=renamed.append,
        )
        adapter.async_start()
        hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED,
            {
                "action": "update",
                "entity_id": "sensor.new_name",
                "old_entity_id": SENSOR,
                "changes": {},
            },
        )
        await hass.async_block_till_done()
        assert renamed == ["sensor.new_name"]
        assert adapter.entity_id == SENSOR

    async def test_rename_without_owner_callback_changes_nothing(self, hass) -> None:
        """Without a verifying owner the adapter never guesses new addressing."""
        observations: list[MoistureObservation] = []
        adapter = MoistureAdapter(
            hass, SENSOR, MAX_AGE_S, sink=observations.append, on_removed=lambda: None
        )
        assert adapter.entity_id == SENSOR
        adapter.async_start()
        hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED,
            {
                "action": "update",
                "entity_id": "sensor.new_name",
                "old_entity_id": SENSOR,
                "changes": {},
            },
        )
        await hass.async_block_till_done()
        assert adapter.entity_id == SENSOR
        # The original entity is still the only observed source.
        hass.states.async_set("sensor.new_name", "41")
        await hass.async_block_till_done()
        assert observations == []
        hass.states.async_set(SENSOR, "42")
        await hass.async_block_till_done()
        assert [o.value for o in observations] == [42.0]

    async def test_rebind_moves_observation_without_a_gap(self, hass) -> None:
        """A verified rebind observes the new entity and drops the old one."""
        observations: list[MoistureObservation] = []
        adapter = MoistureAdapter(
            hass, SENSOR, MAX_AGE_S, sink=observations.append, on_removed=lambda: None
        )
        adapter.async_start()
        adapter.async_rebind("sensor.renamed_moisture")
        assert adapter.entity_id == "sensor.renamed_moisture"
        hass.states.async_set("sensor.renamed_moisture", "37")
        await hass.async_block_till_done()
        assert [o.value for o in observations] == [37.0]
        hass.states.async_set(SENSOR, "12")
        await hass.async_block_till_done()
        assert [o.value for o in observations] == [37.0]
        # Rebinding to the same entity ID is a no-op and never duplicates.
        adapter.async_rebind("sensor.renamed_moisture")
        hass.states.async_set("sensor.renamed_moisture", "38")
        await hass.async_block_till_done()
        assert [o.value for o in observations] == [37.0, 38.0]

    async def test_unrelated_update_is_ignored(self, hass) -> None:
        renamed: list[str] = []
        adapter = MoistureAdapter(
            hass,
            SENSOR,
            MAX_AGE_S,
            sink=lambda o: None,
            on_removed=lambda: None,
            on_renamed=renamed.append,
        )
        adapter.async_start()
        hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED,
            {"action": "update", "entity_id": SENSOR, "changes": {"name": "x"}},
        )
        await hass.async_block_till_done()
        assert renamed == []


class TestClassificationTable:
    """§10.2 classification through the shared normalization path."""

    NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=UTC)

    def _state(self, hass, value: str):
        hass.states.async_set(SENSOR, value)
        return hass.states.get(SENSOR)

    async def test_absent_entity_is_unavailable(self, hass) -> None:
        obs = classify_moisture(None, None, self.NOW, MAX_AGE_S)
        assert obs.classification is MoistureClassification.UNAVAILABLE
        assert obs.value is None
        obs.validate()

    async def test_unavailable_state(self, hass) -> None:
        state = self._state(hass, "unavailable")
        obs = classify_moisture(state, state.last_reported, self.NOW, MAX_AGE_S)
        assert obs.classification is MoistureClassification.UNAVAILABLE
        obs.validate()

    @pytest.mark.parametrize(
        "raw", ["unknown", "soggy", "", "nan", "inf", "-inf", "-0.1", "100.1", "1e6"]
    )
    async def test_invalid_values(self, hass, raw: str) -> None:
        state = self._state(hass, raw)
        now = state.last_reported
        obs = classify_moisture(state, state.last_reported, now, MAX_AGE_S)
        assert obs.classification is MoistureClassification.INVALID, raw
        obs.validate()

    @pytest.mark.parametrize("raw", ["0", "100", "0.0", "33.3"])
    async def test_valid_boundaries(self, hass, raw: str) -> None:
        state = self._state(hass, raw)
        now = state.last_reported
        obs = classify_moisture(state, state.last_reported, now, MAX_AGE_S)
        assert obs.classification is MoistureClassification.VALID, raw
        assert obs.value == float(raw)
        assert obs.age_s == 0.0
        obs.validate()

    async def test_freshness_boundary_exact(self, hass) -> None:
        """SR12 adapter portion: equality at max age is fresh; older stale."""
        state = self._state(hass, "33")
        reported = state.last_reported
        at_boundary = classify_moisture(
            state, reported, reported + timedelta(seconds=MAX_AGE_S), MAX_AGE_S
        )
        assert at_boundary.classification is MoistureClassification.VALID
        past_boundary = classify_moisture(
            state,
            reported,
            reported + timedelta(seconds=MAX_AGE_S) + timedelta(microseconds=1),
            MAX_AGE_S,
        )
        assert past_boundary.classification is MoistureClassification.STALE
        past_boundary.validate()

    async def test_missing_report_time_is_conservatively_invalid(self, hass) -> None:
        state = self._state(hass, "33")
        obs = classify_moisture(state, None, self.NOW, MAX_AGE_S)
        assert obs.classification is MoistureClassification.INVALID
        obs.validate()

    async def test_age_never_negative(self, hass) -> None:
        state = self._state(hass, "33")
        reported = state.last_reported
        obs = classify_moisture(state, reported, reported - timedelta(seconds=5), MAX_AGE_S)
        assert obs.age_s == 0.0


def _config() -> ZoneConfig:
    return ZoneConfig(
        name="Front bed",
        moisture_sensor=SENSOR,
        actuator="switch.front_bed_valve",
        start_threshold=30.0,
        target_threshold=40.0,
        pulse_duration_s=300,
        soak_duration_s=1200,
        max_cycles=4,
        max_session_runtime_s=1800,
        max_daily_runtime_s=3600,
        min_session_interval_s=21600,
        sensor_max_age_s=MAX_AGE_S,
        actuator_confirm_timeout_s=30,
        manual_max_duration_s=1800,
    )
