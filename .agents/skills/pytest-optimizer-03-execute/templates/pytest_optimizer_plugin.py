"""Opt-in pytest plugin: per-fixture setup timing.

pytest core has no per-fixture timer. A ``setup`` row in ``--durations`` is the
whole setup chain for one test item, and a shared higher-scope fixture is billed
to the first item that triggers it. This plugin wraps ``pytest_fixture_setup`` to
attribute setup cost to the *individual* fixture, then prints the slowest
fixtures (aggregated by definition: name, scope and defining conftest or module)
in the terminal summary -- filling the one gap the stock durations table cannot.

Load it from the rootdir ``conftest.py`` with
``pytest_plugins = ["pytest_optimizer_plugin"]`` (pytest rejects ``pytest_plugins``
in any other conftest), or register it under ``[project.entry-points.pytest11]``.
Remove it once you have the timings you need; it adds a small per-fixture overhead.

Notes
-----
- Only cache *misses* are timed: pytest reuses a fixture's ``cached_result``
  within its scope, so a session-scoped fixture is timed once. A parametrized
  fixture is set up again whenever its parameter changes, so its count can
  exceed one even at session scope.
- A fixture overridden in a nearer conftest or module is a different
  definition and gets its own row.
- Under xdist the timings accumulate in the workers while the summary hook runs
  only in the controller, so no table prints; profile serially.
"""

from __future__ import annotations

import time
import typing as t
from collections import defaultdict

import pytest

# (fixture_name, scope, defining node id) -> list of per-setup wall seconds
_TIMINGS: dict[tuple[str, str, str], list[float]] = defaultdict(list)


def pytest_sessionstart(session: pytest.Session) -> None:
    """Forget earlier sessions when pytest runs more than once in one process."""
    _TIMINGS.clear()


@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(
    fixturedef: pytest.FixtureDef[t.Any],
    request: pytest.FixtureRequest,
) -> t.Generator[None, t.Any, None]:
    """Record the wall time of one fixture's setup."""
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    key = (fixturedef.argname, str(fixturedef.scope), fixturedef.baseid or "(plugin)")
    _TIMINGS[key].append(elapsed)


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Print the slowest fixtures by total setup time."""
    if not _TIMINGS:
        return

    limit = int(config.getini("optimizer_fixture_timing_limit") or 20)
    rows = [
        (sum(samples), len(samples), name, scope, base)
        for (name, scope, base), samples in _TIMINGS.items()
    ]
    rows.sort(reverse=True)  # by total time descending

    tr = terminalreporter
    tr.write_sep("=", "slowest fixtures (setup, by total time)")
    tr.write_line(f"{'total':>8}  {'n':>4}  {'each':>8}  scope     fixture (defined in)")
    for total, count, name, scope, base in rows[:limit]:
        each = total / count if count else 0.0
        tr.write_line(
            f"{total:8.3f}  {count:4d}  {each:8.3f}  {scope:<8}  {name} ({base or 'rootdir'})"
        )


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the limit ini so projects can widen/narrow the table."""
    parser.addini(
        "optimizer_fixture_timing_limit",
        help="Max rows in the slowest-fixtures table (default 20).",
        default="20",
    )
