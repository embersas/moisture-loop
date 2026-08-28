"""Removed-actuator tombstone recovery (SPECIFICATION.md §26.4, TB13-TB17, PI28).

These tests reproduce the exact published-0.1.0 failure: a retained safety
record whose durable actuator registry row was deleted keeps an
``actuator_not_proven_off`` blocker forever, and because that blocker is the
entry-wide I19 water-resource fence, every otherwise-healthy zone is
permanently unable to water with no supported recovery.

The reproduction deliberately drives the real Add-zone subentry flow and the
real Enabled switch entity, because the defect was invisible to unit-level
controller calls: every zone guard passed and the zone simply queued forever.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

pytest.importorskip("homeassistant")

from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from custom_components.moisture_loop.const import DOMAIN
from custom_components.moisture_loop.models import (
    BlockerReason,
    ControllerState,
    FaultCode,
    IdentityStatus,
    MoistureClassification,
    PossibleFlowOwner,
    RuntimeLifecycle,
)
from custom_components.moisture_loop.repairs import (
    ISSUE_TOMBSTONE_ACTUATOR_MISSING,
    async_create_fix_flow,
    record_issue_id,
)

SENSOR = "sensor.recovery_moisture"
IDENTITY = {"name": "Zone A", "moisture_sensor": SENSOR}
THRESHOLDS = {
    "start_threshold": 30.0,
    "target_threshold": 40.0,
    "pulse_duration": 300,
    "soak_duration": 1200,
}
LIMITS = {
    "max_cycles": 4,
    "max_session_runtime": 1800,
    "max_daily_runtime": 3600,
    "min_session_interval": 21600,
    "sensor_max_age": 7200,
    "actuator_confirm_timeout": 30,
    "manual_max_duration": 1800,
}

TOMBSTONE_RECORD = "tombstone-record"
TOMBSTONE_LINEAGE = "tombstone-lineage"
TOMBSTONE_HISTORY = "tombstone-history"


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations):
    return


async def settle(hass) -> None:
    await hass.async_block_till_done()
    for _ in range(20):
        await asyncio.sleep(0)
    await hass.async_block_till_done()


class Harness:
    """Zone A built through the real flows, plus a seedable tombstone B."""

    def __init__(self, hass) -> None:
        self.hass = hass
        self.entry = None
        self.subentry_id = None
        self.calls = {"on": 0, "off": 0}
        self.actuator = None
        self.tombstone_entity = None
        self.tombstone_registry_id = None

    @property
    def runtime(self):
        return self.entry.runtime_data

    @property
    def record_id(self) -> str:
        return self.runtime.bindings[self.subentry_id].safety_record_id

    def enabled_switch(self) -> str:
        return self._entity("switch", "enabled")

    def problem_sensor(self) -> str:
        return self._entity("binary_sensor", "problem")

    def status_sensor(self) -> str:
        return self._entity("sensor", "status")

    def _entity(self, domain: str, key: str) -> str:
        registry = er.async_get(self.hass)
        unique_id = f"{self.subentry_id}_{key}"
        entity_id = registry.async_get_entity_id(domain, DOMAIN, unique_id)
        assert entity_id is not None, f"missing {domain} entity for {key}"
        return entity_id


@pytest.fixture
async def harness(hass):
    """Zone A: dry, fresh, proven-closed actuator, created DISABLED (LC14)."""
    env = Harness(hass)
    registry = er.async_get(hass)
    actuator = registry.async_get_or_create(
        "valve", "test", "recovery-valve", suggested_object_id="recovery_valve"
    )
    env.actuator = actuator.entity_id

    async def open_valve(call) -> None:
        env.calls["on"] += 1
        hass.states.async_set(
            actuator.entity_id, "open", {"supported_features": 3}, context=call.context
        )

    async def close_valve(call) -> None:
        env.calls["off"] += 1
        hass.states.async_set(
            actuator.entity_id, "closed", {"supported_features": 3}, context=call.context
        )

    hass.services.async_register("valve", "open_valve", open_valve)
    hass.services.async_register("valve", "close_valve", close_valve)

    # VALID, fresh, strictly below the 30% start threshold, set BEFORE the
    # zone exists: the live defect had no post-enable report at all.
    hass.states.async_set(SENSOR, "15")
    hass.states.async_set(actuator.entity_id, "closed", {"supported_features": 3})

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    env.entry = result["result"]

    result = await hass.config_entries.subentries.async_init(
        (env.entry.entry_id, "zone"), context={"source": "user"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**IDENTITY, "actuator": actuator.entity_id}
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], THRESHOLDS)
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], LIMITS)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await settle(hass)
    env.subentry_id = next(iter(env.entry.subentries))
    return env


async def seed_removed_tombstone(env, *, delete_registry_row: bool = True) -> str:
    """Create retained record B, then delete its durable registry identity.

    B is entirely unrelated to Zone A: a different record, lineage, history,
    and actuator. That is the whole point — its hazard must fence Zone A.
    """
    registry = er.async_get(env.hass)
    entry = registry.async_get_or_create(
        "switch", "test", "removed-actuator", suggested_object_id="removed_actuator"
    )
    env.tombstone_entity = entry.entity_id
    env.tombstone_registry_id = entry.id
    env.hass.states.async_set(entry.entity_id, "off")
    await settle(env.hass)

    live_record_id = env.record_id
    registry_id = entry.id
    entity_id = entry.entity_id

    def _seed(data):
        records = dict(data.safety_records)
        histories = dict(data.zone_histories)
        template = records[live_record_id]
        histories[TOMBSTONE_HISTORY] = replace(
            histories[template.zone_history_id],
            zone_history_id=TOMBSTONE_HISTORY,
            active_subentry_id=None,
            previous_subentry_ids=("retired-subentry",),
        )
        records[TOMBSTONE_RECORD] = template.evolve(
            safety_record_id=TOMBSTONE_RECORD,
            safety_lineage_id=TOMBSTONE_LINEAGE,
            zone_history_id=TOMBSTONE_HISTORY,
            zone_id="retired-zone",
            active_subentry_id=None,
            previous_subentry_ids=("retired-subentry",),
            runtime_lifecycle=RuntimeLifecycle.DELETE_PENDING,
            applied_config=None,
            actuator_identity=replace(
                template.actuator_identity,
                registry_entry_id=registry_id,
                last_known_entity_id=entity_id,
                domain="switch",
                off_service="switch.turn_off",
                identity_status=IdentityStatus.REGISTRY_CONFIRMED,
            ),
            blocker_reasons=(),
            possible_flow_owner=None,
            identity_incident=None,
            actuator_fault=None,
            acknowledgement_required=False,
        )
        return records, histories

    await env.runtime.store.async_reconcile(_seed)
    if delete_registry_row:
        # The exact live condition: the durable registry row is GONE, so no
        # actuator assessment can ever be produced for this identity again.
        registry.async_remove(entity_id)
        env.hass.states.async_remove(entity_id)
    await settle(env.hass)
    return registry_id


async def reload_entry(env) -> None:
    await env.hass.config_entries.async_reload(env.entry.entry_id)
    await settle(env.hass)


def tombstone_issue(env):
    return ir.async_get(env.hass).async_get_issue(
        DOMAIN,
        record_issue_id(env.entry.entry_id, TOMBSTONE_RECORD, ISSUE_TOMBSTONE_ACTUATOR_MISSING),
    )


async def enable_zone_a(env) -> None:
    """Enable through the real switch entity, exactly as the user did."""
    await env.hass.services.async_call(
        "switch", "turn_on", {"entity_id": env.enabled_switch()}, blocking=True
    )
    await settle(env.hass)
    for _ in range(40):
        if env.calls["on"]:
            break
        await asyncio.sleep(0)
        await env.hass.async_block_till_done()


async def run_fix_flow(env, *, data=None, user_input=None):
    issue = tombstone_issue(env)
    flow = await async_create_fix_flow(
        env.hass,
        record_issue_id(env.entry.entry_id, TOMBSTONE_RECORD, ISSUE_TOMBSTONE_ACTUATOR_MISSING),
        data if data is not None else issue.data,
    )
    flow.hass = env.hass
    form = await flow.async_step_init()
    result = await flow.async_step_confirm(
        {"actuator_removed_off": True} if user_input is None else user_input
    )
    await settle(env.hass)
    return form, result


class TestExact010Reproduction:
    """TB16/TB17: the published-0.1.0 permanent global no-water state."""

    async def test_removed_tombstone_fences_a_healthy_zone_then_recovers(self, harness) -> None:
        env = harness
        await seed_removed_tombstone(env)
        await reload_entry(env)

        record_id = env.record_id
        runtime = env.runtime
        controller = runtime.controllers[env.subentry_id]

        # 6: reconciliation raises the conservative hazard for B alone.
        retained = runtime.store.data.safety_records[TOMBSTONE_RECORD]
        assert retained.runtime_lifecycle is RuntimeLifecycle.DELETE_PENDING
        assert retained.actuator_identity.identity_status is IdentityStatus.MISSING
        assert BlockerReason.ACTUATOR_NOT_PROVEN_OFF in retained.blocker_reasons
        assert (TOMBSTONE_RECORD, BlockerReason.ACTUATOR_NOT_PROVEN_OFF) in runtime.slots.blockers()
        # Zone A itself is perfectly healthy: the fence is entirely foreign.
        assert runtime.store.data.safety_records[record_id].blocker_reasons == ()

        # 2-3: every Zone A AUTO input is satisfied before the enable.
        assert controller.observation.classification is MoistureClassification.VALID
        assert controller.observation.value < controller.config.start_threshold
        assert controller.assessment.available and controller.assessment.proven_off

        # 7: enable through the real Enabled switch entity.
        await enable_zone_a(env)

        # 8-10: normal evaluation ran, queued for the slot, and never watered.
        assert controller.enabled is True
        assert controller.state is ControllerState.IDLE
        assert env.subentry_id in runtime.slots.snapshot().queue
        assert runtime.slots.owner is None
        assert controller.session is None
        assert env.calls["on"] == 0
        status = env.hass.states.get(env.status_sensor())
        assert status.attributes["waiting_for_slot"] is True

        # 11: the zone reports a problem instead of a misleading OK.
        assert env.hass.states.get(env.problem_sensor()).state == "on"

        # 12: the Repair for B is offered and is fixable.
        issue = tombstone_issue(env)
        assert issue is not None
        assert issue.is_fixable
        assert issue.severity is ir.IssueSeverity.ERROR

        # 13: acknowledge the exact record/lineage.
        form, result = await run_fix_flow(env)
        assert form["type"] is FlowResultType.FORM
        assert result["type"] is FlowResultType.CREATE_ENTRY

        # 14: durable operator proof, bound to the exact absent identity.
        acknowledged = runtime.store.data.safety_records[TOMBSTONE_RECORD]
        ack = acknowledged.removed_actuator_ack
        assert ack is not None
        assert ack.registry_entry_id == env.tombstone_registry_id
        assert ack.last_known_entity_id == env.tombstone_entity
        assert ack.acknowledged_at_utc.tzinfo is not None

        # 15: the blocker and the retained hazard clear; history is kept.
        assert acknowledged.blocker_reasons == ()
        assert acknowledged.runtime_lifecycle is RuntimeLifecycle.RETIRED
        assert acknowledged.possible_flow_owner is None
        assert runtime.slots.blockers_empty()
        assert TOMBSTONE_HISTORY in runtime.store.data.zone_histories

        # 16: the Repair clears.
        assert tombstone_issue(env) is None

        # 17-18: the ALREADY-QUEUED request is reconsidered and Zone A waters
        # with no Check now, no new moisture report, and no re-enable.
        for _ in range(60):
            if env.calls["on"]:
                break
            await asyncio.sleep(0)
            await env.hass.async_block_till_done()
        assert env.calls["on"] == 1
        assert controller.state is ControllerState.WATERING
        assert runtime.slots.owner == env.subentry_id
        assert env.hass.states.get(env.problem_sensor()).state == "off"

    async def test_manual_watering_is_fenced_by_the_same_global_blocker(self, harness) -> None:
        """Step 12: manual watering is protected identically before recovery."""
        env = harness
        await seed_removed_tombstone(env)
        await reload_entry(env)
        controller = env.runtime.controllers[env.subentry_id]
        await controller.async_set_enabled(True)
        await settle(env.hass)

        await controller.async_manual_start(600.0)
        await settle(env.hass)
        assert controller.state is not ControllerState.WATERING
        assert controller.session is None
        assert env.calls["on"] == 0


class TestRestartDurability:
    """TB14: a Repair dismissal that returns on restart is not a fix."""

    async def test_acknowledgement_survives_reload_and_does_not_reappear(self, harness) -> None:
        env = harness
        await seed_removed_tombstone(env)
        await reload_entry(env)
        await run_fix_flow(env)
        assert env.runtime.slots.blockers_empty()

        # The registry row is still absent after the reload; only the durable
        # operator proof may keep the hazard from being re-raised.
        await reload_entry(env)
        registry = er.async_get(env.hass)
        assert registry.async_get(env.tombstone_registry_id) is None

        record = env.runtime.store.data.safety_records[TOMBSTONE_RECORD]
        assert record.removed_actuator_ack is not None
        assert record.blocker_reasons == ()
        assert record.runtime_lifecycle is RuntimeLifecycle.RETIRED
        assert record.identity_incident is None
        assert env.runtime.slots.blockers_empty()
        assert tombstone_issue(env) is None
        assert env.hass.states.get(env.problem_sensor()).state == "off"
        assert env.calls["on"] == 0

    async def test_a_returning_registry_identity_revokes_the_proof(self, harness) -> None:
        """The proof is bound to the exact absent identity, not to the record."""
        env = harness
        await seed_removed_tombstone(env)
        await reload_entry(env)
        await run_fix_flow(env)
        assert env.runtime.slots.blockers_empty()

        # Re-point the retained identity at a DIFFERENT durable registry row.
        registry = er.async_get(env.hass)
        replacement = registry.async_get_or_create(
            "switch", "test", "replacement-actuator", suggested_object_id="replacement_actuator"
        )
        env.hass.states.async_set(replacement.entity_id, "unavailable")

        def _repoint(data):
            records = dict(data.safety_records)
            record = records[TOMBSTONE_RECORD]
            records[TOMBSTONE_RECORD] = record.evolve(
                actuator_identity=replace(
                    record.actuator_identity,
                    registry_entry_id=replacement.id,
                    last_known_entity_id=replacement.entity_id,
                ),
            )
            return records, dict(data.zone_histories)

        await env.runtime.store.async_reconcile(_repoint)
        await reload_entry(env)

        record = env.runtime.store.data.safety_records[TOMBSTONE_RECORD]
        # The stale proof no longer covers this identity, so the fence returns.
        assert not record.removed_actuator_ack.covers(record.actuator_identity)
        assert BlockerReason.ACTUATOR_NOT_PROVEN_OFF in record.blocker_reasons
        assert not env.runtime.slots.blockers_empty()


class TestNegativeSafetyMatrix:
    """TB13/TB15: every refusal path, and no side effect on success."""

    async def test_unavailable_and_unknown_actuators_are_never_recoverable(self, harness) -> None:
        env = harness
        registry_id = await seed_removed_tombstone(env, delete_registry_row=False)
        for state in ("unavailable", "unknown"):
            env.hass.states.async_set(env.tombstone_entity, state)
            await reload_entry(env)
            record = env.runtime.store.data.safety_records[TOMBSTONE_RECORD]
            # Fails closed, exactly as before: the registry row still exists.
            assert BlockerReason.ACTUATOR_NOT_PROVEN_OFF in record.blocker_reasons
            assert er.async_get(env.hass).async_get(registry_id) is not None
            assert (
                env.runtime.removed_actuator_recovery_context(TOMBSTONE_RECORD, TOMBSTONE_LINEAGE)
                is None
            )
            issue = tombstone_issue(env)
            if issue is not None:
                assert not issue.is_fixable

    async def test_reappearing_identity_is_not_recoverable(self, harness) -> None:
        env = harness
        await seed_removed_tombstone(env)
        await reload_entry(env)
        assert (
            env.runtime.removed_actuator_recovery_context(TOMBSTONE_RECORD, TOMBSTONE_LINEAGE)
            is not None
        )
        # Recreating the entity restores a resolvable durable identity.
        registry = er.async_get(env.hass)
        restored = registry.async_get_or_create(
            "switch", "test", "removed-actuator", suggested_object_id="removed_actuator"
        )

        def _repoint(data):
            records = dict(data.safety_records)
            record = records[TOMBSTONE_RECORD]
            records[TOMBSTONE_RECORD] = record.evolve(
                actuator_identity=replace(record.actuator_identity, registry_entry_id=restored.id),
            )
            return records, dict(data.zone_histories)

        await env.runtime.store.async_reconcile(_repoint)
        assert (
            env.runtime.removed_actuator_recovery_context(TOMBSTONE_RECORD, TOMBSTONE_LINEAGE)
            is None
        )

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("possible_flow_owner", PossibleFlowOwner.INTEGRATION),
            ("actuator_fault", FaultCode.ACTUATOR_OFF_TIMEOUT),
        ],
    )
    async def test_unresolved_flow_or_fault_refuses(self, harness, field, value) -> None:
        env = harness
        await seed_removed_tombstone(env)
        await reload_entry(env)

        def _degrade(data):
            records = dict(data.safety_records)
            changes = {field: value}
            if field == "actuator_fault":
                changes["acknowledgement_required"] = True
            records[TOMBSTONE_RECORD] = records[TOMBSTONE_RECORD].evolve(**changes)
            return records, dict(data.zone_histories)

        await env.runtime.store.async_reconcile(_degrade)
        assert (
            env.runtime.removed_actuator_recovery_context(TOMBSTONE_RECORD, TOMBSTONE_LINEAGE)
            is None
        )

    async def test_active_record_can_never_be_acknowledged(self, harness) -> None:
        """The escape hatch is only ever offered for a retained record."""
        env = harness
        await seed_removed_tombstone(env)
        await reload_entry(env)
        assert env.runtime.removed_actuator_recovery_context(env.record_id, "any-lineage") is None

    async def test_record_and_lineage_mismatch_refuse_visibly(self, harness) -> None:
        env = harness
        await seed_removed_tombstone(env)
        await reload_entry(env)
        issue = tombstone_issue(env)

        _form, result = await run_fix_flow(
            env, data={**issue.data, "safety_lineage_id": "stale-lineage"}
        )
        assert result["errors"]["base"] == "record_removal_not_confirmed"

        _form, result = await run_fix_flow(
            env, data={**issue.data, "safety_record_id": "missing-record"}
        )
        assert result["errors"]["base"] == "record_removal_not_confirmed"
        assert tombstone_issue(env) is not None
        assert not env.runtime.slots.blockers_empty()

    async def test_unchecked_confirmation_is_refused(self, harness) -> None:
        """The operator must actively assert it; the box is never pre-checked."""
        env = harness
        await seed_removed_tombstone(env)
        await reload_entry(env)

        form, result = await run_fix_flow(env, user_input={"actuator_removed_off": False})
        assert form["data_schema"]({})["actuator_removed_off"] is False
        assert result["errors"]["base"] == "record_confirmation_required"
        assert env.runtime.store.data.safety_records[TOMBSTONE_RECORD].removed_actuator_ack is None
        assert not env.runtime.slots.blockers_empty()

    async def test_acknowledgement_commands_no_actuator(self, harness) -> None:
        env = harness
        await seed_removed_tombstone(env)
        await reload_entry(env)
        # Zone A stays disabled, so nothing may water after the blocker clears.
        off_before = env.calls["off"]
        await run_fix_flow(env)
        assert env.calls["on"] == 0
        assert env.calls["off"] == off_before
        assert env.runtime.controllers[env.subentry_id].state is ControllerState.DISABLED
        assert env.hass.states.get(env.actuator).state == "closed"

    async def test_other_blockers_remain_effective(self, harness) -> None:
        """Clearing one lineage never clears another key (ER8, I19)."""
        env = harness
        await seed_removed_tombstone(env)
        await reload_entry(env)
        record_id = env.record_id

        def _independent(data):
            records = dict(data.safety_records)
            records[record_id] = records[record_id].evolve(
                blocker_reasons=(BlockerReason.EXTERNAL_FLOW,),
                possible_flow_owner=PossibleFlowOwner.EXTERNAL,
            )
            return records, dict(data.zone_histories)

        await env.runtime.store.async_reconcile(_independent)
        await env.runtime._republish_record_blockers()
        await run_fix_flow(env)

        assert env.runtime.store.data.safety_records[TOMBSTONE_RECORD].removed_actuator_ack
        assert (record_id, BlockerReason.EXTERNAL_FLOW) in env.runtime.slots.blockers()
        assert not env.runtime.slots.blockers_empty()
        assert env.calls["on"] == 0


class TestDisableReleasesTheSlot:
    """A disabled zone must not keep a live claim on the shared resource."""

    async def test_disable_withdraws_a_queued_slot_request(self, harness) -> None:
        env = harness
        await seed_removed_tombstone(env)
        await reload_entry(env)
        await enable_zone_a(env)
        assert env.subentry_id in env.runtime.slots.snapshot().queue

        await env.hass.services.async_call(
            "switch", "turn_off", {"entity_id": env.enabled_switch()}, blocking=True
        )
        await settle(env.hass)
        assert env.subentry_id not in env.runtime.slots.snapshot().queue

        # Recovery must not then hand the slot to a disabled zone.
        await run_fix_flow(env)
        assert env.runtime.slots.blockers_empty()
        assert env.runtime.slots.owner is None
        assert env.calls["on"] == 0


class TestSchemaUpgrade:
    """PI28: schema 2 upgrades additively and preserves every safety fact."""

    async def test_schema2_payload_upgrades_without_losing_state(self, harness) -> None:
        from custom_components.moisture_loop.const import (
            PRIOR_STORE_SCHEMA_VERSION,
            STORE_SCHEMA_VERSION,
        )
        from custom_components.moisture_loop.models import (
            migrate_schema2_to_schema3,
            store_data_to_dict,
        )

        env = harness
        await seed_removed_tombstone(env)
        await reload_entry(env)
        current = env.runtime.store.data

        payload = store_data_to_dict(current)
        payload["version"] = PRIOR_STORE_SCHEMA_VERSION
        for record in payload["safety_records"].values():
            record.pop("removed_actuator_ack")

        upgraded = migrate_schema2_to_schema3(payload)
        assert upgraded.version == STORE_SCHEMA_VERSION
        assert upgraded.generation_id == current.generation_id
        assert upgraded.zone_histories == current.zone_histories
        assert set(upgraded.safety_records) == set(current.safety_records)
        for record_id, record in upgraded.safety_records.items():
            # Additive only: no operator proof is ever invented by migration.
            assert record.removed_actuator_ack is None
            assert record == current.safety_records[record_id].evolve(removed_actuator_ack=None)
