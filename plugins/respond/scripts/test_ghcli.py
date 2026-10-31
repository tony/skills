"""Tests for the concurrent helpers in ghcli.py."""

# ruff: noqa: S101, INP001, PLR2004
import asyncio
import threading
import time

import ghcli
import pytest
from ghcli import GhError


def test_gather_keeps_call_order() -> None:
    """Results follow the call order, not the finish order."""

    def slow() -> str:
        time.sleep(0.05)
        return "slow"

    assert asyncio.run(ghcli.gather([slow, lambda: "fast"])) == ["slow", "fast"]


def test_gather_respects_limit() -> None:
    """No more than ``limit`` calls run at once."""
    lock = threading.Lock()
    running = 0
    peak = 0

    def call() -> int:
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        time.sleep(0.02)
        with lock:
            running -= 1
        return 1

    assert sum(asyncio.run(ghcli.gather([call] * 6, limit=2))) == 6
    assert 1 <= peak <= 2


def test_gather_raises_first_failure_unwrapped() -> None:
    """A failing call surfaces as ``GhError``, not an ``ExceptionGroup``."""

    def failing() -> str:
        msg = "gh auth login"
        raise GhError(msg)

    with pytest.raises(GhError, match="gh auth login"):
        asyncio.run(ghcli.gather([lambda: "ok", failing]))
