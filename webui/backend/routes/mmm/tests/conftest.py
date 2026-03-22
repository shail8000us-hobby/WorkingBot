"""
conftest.py — MMM sealed test infrastructure

Provides a fresh asyncio event loop backed by SelectSelector for each test.

WHY THIS IS NEEDED
------------------
On macOS with Python 3.9, the default event loop uses KqueueSelector. When
pytest-asyncio tests run alongside tests that call asyncio.run() or
asyncio.get_event_loop(), the kqueue file descriptor can be corrupted between
tests in the same process. Symptoms:

  - TypeError: changelist must be an iterable of select.kevent objects
    (test_sealed_mmm_atm_shield.py — uses asyncio.run())
  - RuntimeError: There is no current event loop in thread 'MainThread'.
    (test_sealed_mmm_pending_orders.py — uses asyncio.get_event_loop())
  - KeyError: '32 is not registered'
    (test_sealed_mmm_margin_guardian_async.py — uses @pytest.mark.asyncio)

FIX
---
Before each test: set an event loop policy that creates SelectorEventLoop
with SelectSelector (poll-based, no kqueue). This avoids the kqueue fd reuse
problem entirely. The fixture is autouse so it applies to every test in this
directory without modifying any sealed test file.
"""

import asyncio
import selectors
import pytest


class _SelectSelectorPolicy(asyncio.DefaultEventLoopPolicy):
    """Event loop policy that creates SelectSelector loops — no kqueue."""

    def new_event_loop(self):
        return asyncio.SelectorEventLoop(selectors.SelectSelector())


def pytest_configure(config):
    """Set SelectSelector policy globally at session start.

    Runs before any fixture or test. This prevents kqueue loops from being
    created anywhere in the process — including by test files in sibling
    directories (e.g. options_strategy/tests/) that run before mmm/tests/.
    """
    asyncio.set_event_loop_policy(_SelectSelectorPolicy())


@pytest.fixture(autouse=True)
def _fresh_event_loop():
    """Give every test a clean, kqueue-free event loop."""
    loop = asyncio.new_event_loop()  # policy is already _SelectSelectorPolicy
    asyncio.set_event_loop(loop)
    yield loop
    try:
        loop.close()
    except Exception:
        pass
    asyncio.set_event_loop(None)
