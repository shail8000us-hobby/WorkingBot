"""
conftest.py — SSDH sealed test infrastructure

Provides a SelectSelector-backed event loop for each test to avoid
kqueue fd corruption on macOS (same fix as MMM tests conftest).
"""

import asyncio
import selectors
import pytest


@pytest.fixture(autouse=True)
def fresh_event_loop():
    """Replace default kqueue loop with a SelectSelector loop before each test."""
    selector = selectors.SelectSelector()
    loop = asyncio.SelectorEventLoop(selector)
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    asyncio.set_event_loop(None)
