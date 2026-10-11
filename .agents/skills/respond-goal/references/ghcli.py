"""Run ``gh`` and ``git`` for the respond scripts.

Shared so every script reports a failed call the same way: a ``GhError`` whose
message is the tool's own stderr.
"""

# ruff: noqa: S603, INP001
from __future__ import annotations

import json
import subprocess
from typing import Callable


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
    return json.loads(raw) if raw.strip() else []
