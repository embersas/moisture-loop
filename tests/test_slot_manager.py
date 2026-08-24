"""Slice 5 tests: SlotManager FIFO ownership and keyed blockers (§21, §22.3).

Pure asyncio: runs with no homeassistant installed; deterministic
futures/events, no real sleeps. Covers the manager-level portions of
ER1-ER8 and ER12; controller integration completes in Slice 7 and startup
interleaving in Slice 8.
"""

from __future__ import annotations

import asyncio

import pytest

from custom_components.soilsync.models import BlockerReason
from custom_components.soilsync.slot_manager import SlotManager

EXTERNAL = BlockerReason.EXTERNAL_FLOW
OFF_UNCONFIRMED = BlockerReason.INTEGRATION_OFF_UNCONFIRMED
NOT_PROVEN = BlockerReason.ACTUATOR_NOT_PROVEN_OFF


async def enabled_manager() -> SlotManager:
    manager = SlotManager()
    await manager.async_enable_grants()
    return manager


class TestStartupGating:
    async def test_er6_no_grant_before_reconciliation_completes(self) -> None:
        manager = SlotManager()
        request = await manager.async_request("zone-b")
        assert request.pending
        assert manager.owner is None
        await manager.async_enable_grants()
        assert not request.pending
        assert manager.owner == "zone-b"

    async def test_startup_blocker_populated_before_enable_is_never_missed(self) -> None:
        """ER12 manager portion: pre-enable occupancy blocks the first grant."""
        manager = SlotManager()
        await manager.async_add_blocker("zone-a", NOT_PROVEN)
        request = await manager.async_request("zone-b")
        await manager.async_enable_grants()
        assert request.pending  # blocker visible before any grant
        await manager.async_remove_blocker("zone-a", NOT_PROVEN)
        assert not request.pending

    async def test_disable_grants_stops_offers_but_keeps_owner(self) -> None:
        manager = await enabled_manager()
        first = await manager.async_request("zone-a")
        assert not first.pending
        await manager.async_disable_grants()
        second = await manager.async_request("zone-b")
        await manager.async_release("zone-a")
        assert second.pending  # no new offer while disabled
        await manager.async_enable_grants()
        assert not second.pending

    @pytest.mark.parametrize("flag", ["dirty", "reconciling", "failed"])
    async def test_i18_reconciliation_barrier_blocks_each_failure_state(self, flag: str) -> None:
        manager = await enabled_manager()
        await manager.async_set_reconciliation_barrier(**{flag: True})
        request = await manager.async_request("zone-a")
        assert request.pending
        assert manager.owner is None
        snapshot = manager.snapshot()
        assert not snapshot.admission_open
        snapshot_field = {
            "dirty": "reconciliation_dirty",
            "reconciling": "reconciling",
            "failed": "reconciliation_failed",
        }[flag]
        assert getattr(snapshot, snapshot_field)
        await manager.async_set_reconciliation_barrier(**{flag: False})
        assert not request.pending
        assert manager.owner == "zone-a"

    async def test_barrier_closure_keeps_owner_and_exact_blockers(self) -> None:
        manager = await enabled_manager()
        await manager.async_request("zone-a")
        await manager.async_add_blocker("record-retained", EXTERNAL)
        await manager.async_set_reconciliation_barrier(dirty=True, reconciling=True)
        assert manager.owner == "zone-a"
        assert manager.blockers() == {("record-retained", EXTERNAL)}
        await manager.async_release("zone-a")
        queued = await manager.async_request("zone-b")
        await manager.async_set_reconciliation_barrier(dirty=False, reconciling=False)
        assert queued.pending
        await manager.async_remove_blocker("record-retained", EXTERNAL)
        assert not queued.pending


class TestFifoOwnership:
    async def test_single_owner_and_fifo_order(self) -> None:
        manager = await enabled_manager()
        a = await manager.async_request("zone-a")
        b = await manager.async_request("zone-b")
        c = await manager.async_request("zone-c")
        assert not a.pending
        assert b.pending and c.pending
        assert manager.owner == "zone-a"
        await manager.async_release("zone-a")
        assert not b.pending
        assert manager.owner == "zone-b"
        await manager.async_release("zone-b")
        assert not c.pending
        assert manager.owner == "zone-c"

    async def test_release_by_non_owner_is_refused(self) -> None:
        manager = await enabled_manager()
        await manager.async_request("zone-a")
        assert not await manager.async_release("zone-b")
        assert manager.owner == "zone-a"
        assert await manager.async_release("zone-a")

    async def test_requeue_tail_after_soak(self) -> None:
        """§21: soaking zones release and requeue at the tail."""
        manager = await enabled_manager()
        await manager.async_request("zone-a")
        b = await manager.async_request("zone-b")
        requeued = await manager.async_requeue_tail("zone-a")
        assert requeued is not None
        assert not b.pending  # B interleaves its pulse
        assert manager.owner == "zone-b"
        assert manager.snapshot().queue == ("zone-a",)
        await manager.async_release("zone-b")
        assert not requeued.pending
        assert manager.owner == "zone-a"

    async def test_requeue_tail_by_non_owner_is_refused(self) -> None:
        manager = await enabled_manager()
        await manager.async_request("zone-a")
        assert await manager.async_requeue_tail("zone-b") is None
        assert manager.owner == "zone-a"

    async def test_duplicate_request_returns_same_handle(self) -> None:
        manager = SlotManager()
        first = await manager.async_request("zone-a")
        second = await manager.async_request("zone-a")
        assert first is second
        assert manager.snapshot().queue == ("zone-a",)

    async def test_request_while_owner_is_already_granted(self) -> None:
        manager = await enabled_manager()
        await manager.async_request("zone-a")
        again = await manager.async_request("zone-a")
        assert not again.pending

    async def test_cancel_request_removes_from_queue(self) -> None:
        manager = await enabled_manager()
        await manager.async_request("zone-a")
        await manager.async_request("zone-b")
        c = await manager.async_request("zone-c")
        await manager.async_cancel_request("zone-b")
        assert manager.snapshot().queue == ("zone-c",)
        await manager.async_release("zone-a")
        assert not c.pending

    async def test_cancelled_future_is_skipped_on_offer(self) -> None:
        manager = await enabled_manager()
        await manager.async_request("zone-a")
        b = await manager.async_request("zone-b")
        c = await manager.async_request("zone-c")
        b.granted.cancel()
        await manager.async_release("zone-a")
        assert manager.owner == "zone-c"
        assert not c.pending

    async def test_declined_offer_passes_to_next(self) -> None:
        """Guards failed on the offer: the grantee releases; next is offered."""
        manager = await enabled_manager()
        a = await manager.async_request("zone-a")
        b = await manager.async_request("zone-b")
        assert not a.pending
        await manager.async_release("zone-a")  # decline
        assert not b.pending
        assert manager.owner == "zone-b"


class TestKeyedBlockers:
    async def test_keys_are_safety_records_not_requesting_zone_ids(self) -> None:
        manager = await enabled_manager()
        await manager.async_add_blocker("safety-record-a", EXTERNAL)
        request = await manager.async_request("current-subentry-b")
        assert request.pending
        assert manager.snapshot().blockers == (("safety-record-a", EXTERNAL),)
        await manager.async_remove_blocker("current-subentry-b", EXTERNAL)
        assert request.pending
        await manager.async_remove_blocker("safety-record-a", EXTERNAL)
        assert not request.pending

    async def test_empty_safety_record_id_is_rejected(self) -> None:
        manager = await enabled_manager()
        with pytest.raises(ValueError, match="safety_record_id"):
            await manager.async_add_blocker("", EXTERNAL)

    async def test_persistence_failure_retains_live_blocker_and_prevents_grant(self) -> None:
        calls: list[tuple[str, BlockerReason, bool]] = []
        fail = True

        async def persist(record_id: str, reason: BlockerReason, active: bool) -> None:
            calls.append((record_id, reason, active))
            if fail:
                raise RuntimeError("write failed")

        manager = SlotManager(persist)
        await manager.async_enable_grants()
        with pytest.raises(RuntimeError, match="write failed"):
            await manager.async_add_blocker("record-a", EXTERNAL)
        assert manager.blockers() == {("record-a", EXTERNAL)}
        request = await manager.async_request("zone-b")
        assert request.pending
        assert calls == [("record-a", EXTERNAL, True)]
        fail = False
        await manager.async_add_blocker("record-a", EXTERNAL)
        assert calls == [
            ("record-a", EXTERNAL, True),
            ("record-a", EXTERNAL, True),
        ]
        assert request.pending
        await manager.async_remove_blocker("record-a", EXTERNAL)
        assert not request.pending

    async def test_failed_persisted_removal_cannot_release_or_grant(self) -> None:
        fail_removal = False

        async def persist(_record_id: str, _reason: BlockerReason, active: bool) -> None:
            if not active and fail_removal:
                raise RuntimeError("remove failed")

        manager = SlotManager(persist)
        await manager.async_enable_grants()
        await manager.async_add_blocker("record-a", EXTERNAL)
        request = await manager.async_request("zone-b")
        fail_removal = True
        with pytest.raises(RuntimeError, match="remove failed"):
            await manager.async_remove_blocker("record-a", EXTERNAL)
        assert manager.blockers() == {("record-a", EXTERNAL)}
        assert request.pending

    async def test_er1_external_flow_blocks_other_zone(self) -> None:
        manager = await enabled_manager()
        await manager.async_add_blocker("zone-a", EXTERNAL)
        b = await manager.async_request("zone-b")
        assert b.pending
        # ER3: proven OFF removes that zone's key and permits the grant.
        await manager.async_remove_blocker("zone-a", EXTERNAL)
        assert not b.pending

    async def test_er4_two_external_flows_both_required_off(self) -> None:
        manager = await enabled_manager()
        await manager.async_add_blocker("zone-a", EXTERNAL)
        await manager.async_add_blocker("zone-c", EXTERNAL)
        b = await manager.async_request("zone-b")
        await manager.async_remove_blocker("zone-a", EXTERNAL)
        assert b.pending  # first OFF cannot release global occupancy
        await manager.async_remove_blocker("zone-c", EXTERNAL)
        assert not b.pending

    async def test_er5_blocker_retained_without_off_proof(self) -> None:
        """Only an explicit proven-OFF removal clears a key; nothing else."""
        manager = await enabled_manager()
        await manager.async_add_blocker("zone-a", EXTERNAL)
        await manager.async_add_blocker("zone-a", EXTERNAL)  # idempotent
        b = await manager.async_request("zone-b")
        await manager.async_release("zone-a")  # unrelated no-op
        await manager.async_cancel_request("zone-a")
        assert b.pending
        assert manager.blockers() == {("zone-a", EXTERNAL)}

    async def test_er7_reasons_coexist_and_release_independently(self) -> None:
        manager = await enabled_manager()
        await manager.async_add_blocker("zone-a", OFF_UNCONFIRMED)
        await manager.async_add_blocker("zone-a", EXTERNAL)
        await manager.async_add_blocker("zone-b", EXTERNAL)
        req = await manager.async_request("zone-c")
        await manager.async_remove_blocker("zone-a", EXTERNAL)
        assert manager.blockers() == {
            ("zone-a", OFF_UNCONFIRMED),
            ("zone-b", EXTERNAL),
        }
        assert req.pending
        await manager.async_remove_blocker("zone-b", EXTERNAL)
        assert manager.blockers() == {("zone-a", OFF_UNCONFIRMED)}
        assert req.pending
        await manager.async_remove_blocker("zone-a", OFF_UNCONFIRMED)
        assert not req.pending

    async def test_er8_one_key_can_never_clear_another(self) -> None:
        manager = await enabled_manager()
        keys = [
            ("zone-a", EXTERNAL),
            ("zone-a", OFF_UNCONFIRMED),
            ("zone-b", EXTERNAL),
            ("zone-c", NOT_PROVEN),
        ]
        for zone, reason in keys:
            await manager.async_add_blocker(zone, reason)
        # Removing a non-existent zone/reason combination clears nothing.
        await manager.async_remove_blocker("zone-b", OFF_UNCONFIRMED)
        await manager.async_remove_blocker("zone-d", EXTERNAL)
        assert manager.blockers() == set(keys)
        # Each exact key releases only itself.
        await manager.async_remove_blocker("zone-a", EXTERNAL)
        assert manager.blockers() == set(keys) - {("zone-a", EXTERNAL)}

    async def test_grant_never_occurs_while_any_blocker_remains(self) -> None:
        manager = await enabled_manager()
        await manager.async_add_blocker("zone-x", NOT_PROVEN)
        grants: list[str] = []

        async def zone(zone_id: str) -> None:
            request = await manager.async_request(zone_id)
            await request.granted
            assert manager.blockers_empty(), "granted while blocked!"
            grants.append(zone_id)
            await manager.async_release(zone_id)

        tasks = [asyncio.create_task(zone(f"zone-{i}")) for i in range(4)]
        await asyncio.sleep(0)  # let requests queue deterministically
        assert grants == []
        await manager.async_remove_blocker("zone-x", NOT_PROVEN)
        await asyncio.gather(*tasks)
        assert sorted(grants) == [f"zone-{i}" for i in range(4)]


class TestAdversarialInterleavings:
    async def test_er8_adversarial_interleaving_with_requests(self) -> None:
        manager = await enabled_manager()
        observed: list[tuple[str, frozenset]] = []

        async def watering_zone(zone_id: str) -> None:
            request = await manager.async_request(zone_id)
            await request.granted
            observed.append((zone_id, manager.blockers()))
            await manager.async_release(zone_id)

        async def external_actor() -> None:
            await manager.async_add_blocker("zone-ext", EXTERNAL)
            await asyncio.sleep(0)
            await manager.async_add_blocker("zone-ext2", EXTERNAL)
            await asyncio.sleep(0)
            await manager.async_remove_blocker("zone-ext", EXTERNAL)
            await asyncio.sleep(0)
            await manager.async_remove_blocker("zone-ext2", EXTERNAL)

        tasks = [asyncio.create_task(watering_zone(f"zone-{i}")) for i in range(3)]
        await external_actor()
        await asyncio.gather(*tasks)
        # Every grant happened with an empty blocker set.
        for zone_id, blockers in observed:
            assert blockers == frozenset(), f"{zone_id} granted while {blockers}"

    async def test_at_most_one_concurrent_owner(self) -> None:
        """I21: serialized ownership under concurrent request/release load."""
        manager = await enabled_manager()
        active = 0
        max_active = 0

        async def zone(zone_id: str) -> None:
            nonlocal active, max_active
            request = await manager.async_request(zone_id)
            await request.granted
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0)  # deterministic yield while "flowing"
            active -= 1
            await manager.async_release(zone_id)

        await asyncio.gather(*(zone(f"zone-{i}") for i in range(10)))
        assert max_active == 1
        assert manager.owner is None

    async def test_snapshot_contents(self) -> None:
        manager = await enabled_manager()
        await manager.async_add_blocker("zone-b", EXTERNAL)
        await manager.async_add_blocker("zone-a", OFF_UNCONFIRMED)
        await manager.async_request("zone-c")
        await manager.async_request("zone-d")
        snap = manager.snapshot()
        assert snap.owner is None
        assert snap.queue == ("zone-c", "zone-d")
        assert snap.blockers == (
            ("zone-a", OFF_UNCONFIRMED),
            ("zone-b", EXTERNAL),
        )
        assert snap.grants_enabled is True
