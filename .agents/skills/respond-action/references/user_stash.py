#!/usr/bin/env python3
"""Stash and restore the user's uncommitted work around a run.

``save`` stashes tracked and untracked changes and prints the stash commit SHA.
Exit 0 stashed, 1 nothing to stash (prints nothing), 3 ``git stash`` failed
(stderr says why).

``restore <sha>`` refuses (exit 1, tree untouched, stash kept) when a stashed
path also changed since the save. Otherwise it applies the stash with
``--index`` so staged state returns;
when ``--index`` cannot apply it retries without, then drops the stash only
after a clean apply. On a conflict the stash stays and its SHA is printed.

``paths <sha>`` prints the stash's paths as a JSON array. ``verify [<sha>]``
exits 1 and prints the difference when the working tree's changed paths are not
exactly the stash's (none, without a SHA).
"""

# ruff: noqa: S603, S607
# pyright: reportUnusedCallResult=false
from __future__ import annotations

import json
import subprocess
import sys

from repo_state import changed_paths  # pyright: ignore[reportImplicitRelativeImport]

_SHA_ARGS = 2


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], check=False, capture_output=True, text=True)


def save() -> int:
    """Stash everything and print the new stash's SHA."""
    before = _git("rev-parse", "--verify", "--quiet", "refs/stash").stdout.strip()
    pushed = _git("stash", "push", "--include-untracked", "--message", "respond-action")
    after = _git("rev-parse", "--verify", "--quiet", "refs/stash").stdout.strip()
    if pushed.returncode != 0:
        sys.stderr.write(pushed.stderr or "git stash failed\n")
        return 3
    if not after or after == before:
        sys.stderr.write("nothing to stash\n")
        return 1
    sys.stdout.write(after + "\n")
    return 0


def overlap(sha: str) -> list[str]:
    """Return stash paths that changed since the save, or exist untracked now."""
    held = set(stash_paths(sha))
    moved = {
        p for p in _git("diff", "--name-only", "-z", f"{sha}^1", "HEAD").stdout.split("\0") if p
    }
    return sorted(held & (moved | set(changed_paths())))


def restore(sha: str) -> int:
    """Apply stash ``sha``; drop it after a clean apply, keep it otherwise.

    Refuses, leaving the tree untouched and the stash kept, when a stashed path
    also changed since the save.
    """
    listing = _git("stash", "list", "--format=%H").stdout.split()
    if sha not in listing:
        sys.stderr.write(f"stash {sha} not found\n")
        return 1
    clash = overlap(sha)
    if clash:
        sys.stderr.write(f"stash overlaps changes since the save: {', '.join(clash)}\n")
        sys.stdout.write(f"kept stash {sha}\n")
        return 1
    applied = _git("stash", "apply", "--index", sha)
    if applied.returncode != 0 and not _git("diff", "--name-only", "--diff-filter=U").stdout:
        sys.stderr.write("staged state not restored: --index did not apply\n")
        applied = _git("stash", "apply", sha)
    if applied.returncode != 0:
        sys.stderr.write(applied.stdout + applied.stderr)
        sys.stdout.write(f"kept stash {sha}\n")
        return 1
    _git("stash", "drop", f"stash@{{{listing.index(sha)}}}")
    return 0


def stash_paths(sha: str) -> list[str]:
    """Return every path a stash holds, untracked files included."""
    tracked = _git("diff", "--name-only", "-z", f"{sha}^1", sha).stdout
    paths = {p for p in tracked.split("\0") if p}
    if _git("rev-parse", "--verify", "--quiet", f"{sha}^3").returncode == 0:
        untracked = _git("ls-tree", "-r", "--name-only", "-z", f"{sha}^3").stdout
        paths |= {p for p in untracked.split("\0") if p}
    return sorted(paths)


def verify(sha: str | None) -> int:
    """Compare the working tree's changed paths with the stash's."""
    want: set[str] = set(stash_paths(sha)) if sha else set()
    have = set(changed_paths())
    if want == have:
        return 0
    diff = {"unexpected": sorted(have - want), "missing": sorted(want - have)}
    sys.stdout.write(json.dumps(diff) + "\n")
    return 1


def main(argv: list[str] | None = None) -> int:
    """Run ``save``, ``restore``, ``paths``, or ``verify``."""
    args = sys.argv[1:] if argv is None else argv
    if args == ["save"]:
        return save()
    if len(args) == _SHA_ARGS and args[0] == "restore":
        return restore(args[1])
    if len(args) == _SHA_ARGS and args[0] == "paths":
        sys.stdout.write(json.dumps(stash_paths(args[1])) + "\n")
        return 0
    if args[:1] == ["verify"] and len(args) <= _SHA_ARGS:
        return verify(args[1] if len(args) == _SHA_ARGS else None)
    sys.stderr.write("usage: user_stash.py save | restore <sha> | paths <sha> | verify [<sha>]\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
