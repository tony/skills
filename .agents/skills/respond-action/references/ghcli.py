"""Run ``gh`` and ``git`` for the respond scripts.

Shared so every script reports a failed call the same way: a ``GhError`` whose
message is the tool's own stderr.
"""

# ruff: noqa: S603, INP001
import asyncio
import json
import subprocess
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Sequence


class GhError(Exception):
    """``gh`` could not run or exited nonzero without usable output."""


def gh(*args: str, checks: bool = False) -> str:
    """Return ``gh`` stdout; raise ``GhError`` on failure.

    ``gh pr checks`` exits nonzero for failing or pending checks (exit 8 is
    pending, per ``gh pr checks --help``) while still printing them, so
    ``checks=True`` accepts any exit code that came with output.
    """
    try:
        done = subprocess.run(
            ["gh", *args],  # noqa: S607
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        msg = f"gh: {exc}"
        raise GhError(msg) from exc
    if done.returncode == 0 or (checks and done.stdout.strip()):
        return done.stdout
    msg = done.stderr.strip() or f"gh exited {done.returncode}"
    raise GhError(msg)


def pr_checks(pr: str, fields: str, run: Callable[..., str] = gh) -> list[dict[str, str]]:
    """Return a pull request's checks; an empty list when its head has none.

    ``gh pr checks`` fails with no output when nothing is reported, so the
    ``statusCheckRollup`` field of ``gh pr view`` (listed in its ``--help``)
    decides between "no checks" and a real ``gh`` failure.
    """
    try:
        raw = run("pr", "checks", pr, "--json", fields, checks=True)
    except GhError:
        length = ".statusCheckRollup | length"
        rollup = run("pr", "view", pr, "--json", "statusCheckRollup", "--jq", length)
        if rollup.strip() != "0":
            raise
        return []
    if not raw.strip():
        return []
    checks = json.loads(raw)
    if not isinstance(checks, list):
        msg = "gh pr checks: expected a JSON list"
        raise GhError(msg)
    return [{str(k): str(v) for k, v in item.items()} for item in checks]


@asynccontextmanager
async def task_group() -> AsyncGenerator[asyncio.TaskGroup]:
    """Yield a ``TaskGroup`` that raises the first failure as itself, not an ``ExceptionGroup``."""
    try:
        async with asyncio.TaskGroup() as group:
            yield group
    except ExceptionGroup as failure:
        raise failure.exceptions[0] from None


async def gather[T](calls: Sequence[Callable[[], T]], limit: int = 4) -> list[T]:
    """Run blocking calls in threads, at most ``limit`` at once; results keep call order.

    The first failure is raised as itself (not an ``ExceptionGroup``) and
    cancels the calls not yet finished.
    """
    gate = asyncio.Semaphore(limit)

    async def one(call: Callable[[], T]) -> T:
        async with gate:
            return await asyncio.to_thread(call)

    async with task_group() as group:
        tasks = [group.create_task(one(call)) for call in calls]
    return [task.result() for task in tasks]
