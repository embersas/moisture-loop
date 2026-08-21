"""Global watering SlotManager (SPECIFICATION.md §21, §11.4, §22.3).

Integration-wide FIFO serialization of watering ownership plus the
deterministic water-resource blocker set keyed by ``(zone_id, reason)``.
v0.1 permits at most one integration-commanded flowing zone, and no zone may
be commanded ON while any configured actuator is observed or conservatively
believed to be flowing, regardless of who initiated that flow (I19, I21).

Pure asyncio module: no homeassistant imports. The zone controller feeds
actuator observations in as blocker updates and consumes grants as
``SlotGranted`` events; every guard is re-run by the grantee when a grant is
offered, and a declined offer releases ownership so the next queued zone is
offered (§14 note after T59).

Grant rule: a request is granted only when grants are enabled (startup
reconciliation complete, §25.1), there is no owner, and the blocker set is
empty. Blocker updates and grant decisions serialize on one lock, so one
zone's OFF evidence can never clear another zone/reason key or race a grant
(ER8, ER12).
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field

from .models import BlockerReason

BlockerKey = tuple[str, BlockerReason]


@dataclass
class SlotRequest:
    """One zone's pending slot request; ``granted`` resolves on the offer."""

    zone_id: str
    granted: asyncio.Future[None] = field(default_factory=asyncio.Future)

    @property
    def pending(self) -> bool:
        return not self.granted.done()


@dataclass(frozen=True, slots=True)
class SlotSnapshot:
    """Diagnostics-ready view (§33.2): owner, queue order, sorted blockers."""

    owner: str | None
    queue: tuple[str, ...]
    blockers: tuple[BlockerKey, ...]
    grants_enabled: bool


class SlotManager:
    """FIFO watering-slot owner and keyed conservative blocker set."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._owner: str | None = None
        self._queue: deque[SlotRequest] = deque()
        self._blockers: set[BlockerKey] = set()
        # No grant is possible until startup reconciliation completes and
        # every configured actuator has been classified (§21, §25.1, ER6).
        self._grants_enabled = False

    # -- observation / blocker updates --------------------------------------

    async def async_add_blocker(self, zone_id: str, reason: BlockerReason) -> None:
        """Add one keyed blocker. Idempotent; never affects other keys."""
        async with self._lock:
            self._blockers.add((zone_id, reason))

    async def async_remove_blocker(self, zone_id: str, reason: BlockerReason) -> None:
        """Remove exactly one keyed blocker on proven terminal OFF evidence.

        Removing a key that is not present is a no-op. One zone/reason's
        removal can never clear another key (§21, ER8); a grant follows only
        if the whole set is now empty and no owner remains.
        """
        async with self._lock:
            self._blockers.discard((zone_id, reason))
            self._try_grant_locked()

    def blockers(self) -> frozenset[BlockerKey]:
        """Current keyed blocker set (immutable copy)."""
        return frozenset(self._blockers)

    def blockers_empty(self) -> bool:
        return not self._blockers

    # -- lifecycle -----------------------------------------------------------

    async def async_enable_grants(self) -> None:
        """Allow grants after §25.1 startup reconciliation completes."""
        async with self._lock:
            self._grants_enabled = True
            self._try_grant_locked()

    async def async_disable_grants(self) -> None:
        """Stop offering new grants (shutdown/reload); ownership is untouched."""
        async with self._lock:
            self._grants_enabled = False

    # -- FIFO ownership --------------------------------------------------------

    async def async_request(self, zone_id: str) -> SlotRequest:
        """Queue a slot request; returns the pending/granted handle.

        A zone has at most one live request: repeated requests return the
        existing handle. If the zone already owns the slot, the returned
        handle is already granted.
        """
        async with self._lock:
            if self._owner == zone_id:
                request = SlotRequest(zone_id)
                request.granted.set_result(None)
                return request
            for queued in self._queue:
                if queued.zone_id == zone_id:
                    return queued
            request = SlotRequest(zone_id)
            self._queue.append(request)
            self._try_grant_locked()
            return request

    async def async_cancel_request(self, zone_id: str) -> None:
        """Withdraw a queued request (termination/reload cleanup)."""
        async with self._lock:
            self._queue = deque(r for r in self._queue if r.zone_id != zone_id)

    async def async_release(self, zone_id: str) -> bool:
        """Release ownership after proven terminal OFF (§21).

        Only the current owner is released; anything else is a no-op so a
        stale caller can never free another zone's slot. Returns whether a
        release happened.
        """
        async with self._lock:
            if self._owner != zone_id:
                return False
            self._owner = None
            self._try_grant_locked()
            return True

    async def async_requeue_tail(self, zone_id: str) -> SlotRequest | None:
        """Release after a soaking pulse and requeue at the tail (§21).

        Allows fair pulse interleaving across simultaneously dry zones. If
        the zone was not the owner, nothing is released or queued.
        """
        async with self._lock:
            if self._owner != zone_id:
                return None
            self._owner = None
            request = SlotRequest(zone_id)
            self._queue.append(request)
            self._try_grant_locked()
            return request

    @property
    def owner(self) -> str | None:
        return self._owner

    def snapshot(self) -> SlotSnapshot:
        return SlotSnapshot(
            owner=self._owner,
            queue=tuple(r.zone_id for r in self._queue),
            blockers=tuple(sorted(self._blockers, key=lambda k: (k[0], k[1].value))),
            grants_enabled=self._grants_enabled,
        )

    # -- grant decision (always under the lock) ------------------------------

    def _try_grant_locked(self) -> None:
        """Offer the slot to the queue head when every condition holds.

        Requires: grants enabled, no owner, empty blocker set, non-empty
        queue. The grantee re-runs every zone guard on the offer and must
        release (decline) if any fails; release triggers the next offer.
        """
        if not self._grants_enabled:
            return
        if self._owner is not None:
            return
        if self._blockers:
            return
        while self._queue:
            request = self._queue.popleft()
            if request.granted.cancelled():
                continue
            self._owner = request.zone_id
            request.granted.set_result(None)
            return
