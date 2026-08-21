"""Shared test configuration.

This module must not import homeassistant: the pure-layer CI job runs
without homeassistant installed, and every HA-dependent test module guards
itself with ``pytest.importorskip("homeassistant")`` at module level (see
DEVELOPMENT.md). HA harness fixtures come from
pytest-homeassistant-custom-component in the HA environments.

Windows local-development accommodation: the HA test harness blocks socket
creation (allowing only unix sockets), but Windows asyncio event loops
require an AF_INET socketpair, so the harness cannot start at all under
that block. On win32 only, the block is neutralized. CI runs on Linux and
keeps the full socket block, so the no-network guarantee is still enforced
on every push; no test in this repository performs network I/O.
"""

from __future__ import annotations

import sys

if sys.platform == "win32":
    import asyncio

    import pytest

    # aiodns (pulled in by the HA harness) requires a SelectorEventLoop on
    # Windows; the Proactor default cannot run the harness fixtures.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    @pytest.fixture(scope="session")
    def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
        return asyncio.WindowsSelectorEventLoopPolicy()

    try:
        import pytest_socket
    except ImportError:
        pytest_socket = None

    if pytest_socket is not None:

        def _disable_socket_noop(allow_unix_socket: bool = False) -> None:
            pytest_socket.enable_socket()

        pytest_socket.disable_socket = _disable_socket_noop

    try:
        import homeassistant  # noqa: F401 - only to detect the HA harness env
    except ImportError:
        pass
    else:
        from collections.abc import Generator
        from unittest.mock import MagicMock, patch

        @pytest.fixture(scope="session")
        def mock_zeroconf_resolver() -> Generator[object]:
            """Windows override: the harness fixture builds an aiodns
            resolver, which cannot run on Windows event loops. Substitute an
            inert mock resolver; no test resolves real DNS anyway."""
            resolver = MagicMock()
            resolver.real_close = resolver.close
            patcher = patch(
                "homeassistant.helpers.aiohttp_client._async_make_resolver",
                return_value=resolver,
            )
            patcher.start()
            try:
                yield patcher
            finally:
                patcher.stop()
