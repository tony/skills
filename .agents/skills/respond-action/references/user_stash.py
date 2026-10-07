#!/usr/bin/env python3
"""Stash and restore the user's uncommitted work around a run.

``save`` stashes tracked and untracked changes and prints the stash commit SHA;
it exits 1 and prints nothing when no stash was created. ``restore <sha>``
applies that stash, then drops it only when the apply was clean; on a conflict
the stash stays and its SHA is printed.
"""

# ruff: noqa: S603, S607
# pyright: reportUnusedCallResult=false
from __future__ import annotations

import subprocess
import sys

_RESTORE_ARGS = 2


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], check=False, capture_output=True, text=True)


def save() -> int:
    """Stash everything and print the new stash's SHA."""
    before = _git("rev-parse", "--verify", "--quiet", "refs/stash").stdout.strip()
    pushed = _git("stash", "push", "--include-untracked", "--message", "respond-action")
    after = _git("rev-parse", "--verify", "--quiet", "refs/stash").stdout.strip()
    if pushed.returncode != 0 or not after or after == before:
        sys.stderr.write(pushed.stderr or "nothing to stash\n")
        return 1
    sys.stdout.write(after + "\n")
    return 0


def restore(sha: str) -> int:
    """Apply stash ``sha``; drop it after a clean apply, keep it otherwise."""
    listing = _git("stash", "list", "--format=%H").stdout.split()
    if sha not in listing:
        sys.stderr.write(f"stash {sha} not found\n")
        return 1
    applied = _git("stash", "apply", sha)
    if applied.returncode != 0:
        sys.stderr.write(applied.stdout + applied.stderr)
        sys.stdout.write(f"kept stash {sha}\n")
        return 1
    _git("stash", "drop", f"stash@{{{listing.index(sha)}}}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run ``save`` or ``restore <sha>``."""
    args = sys.argv[1:] if argv is None else argv
    if args == ["save"]:
        return save()
    if len(args) == _RESTORE_ARGS and args[0] == "restore":
        return restore(args[1])
    sys.stderr.write("usage: user_stash.py save | restore <sha>\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
