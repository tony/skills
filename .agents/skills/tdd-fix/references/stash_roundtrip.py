#!/usr/bin/env python3
"""Stash and restore the working tree by the stash commit's identity.

Usage:
    stash_roundtrip.py push
    stash_roundtrip.py restore SHA

``push`` stashes tracked and untracked changes under a unique message and
prints the full SHA of the stash commit it created. It exits 1 and prints
nothing on stdout when no stash was created.

``restore`` applies the stash commit SHA, then drops the one list entry whose
SHA matches. Stash entries are shared by every linked worktree, so another
worktree may push or pop between the two calls; the entry's position is
never trusted. A failed apply leaves the entry in place and exits 1.
"""

# ruff: noqa: EM102, TRY003

import re
import subprocess
import sys
import uuid

FULL_SHA = re.compile(r"[0-9a-f]{40}\Z")


def git(*args: str) -> subprocess.CompletedProcess[str]:
    """Run git and return the completed process."""
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


def entries() -> list[tuple[str, str]]:
    """Return ``(sha, subject)`` for every stash entry, newest first."""
    done = git("stash", "list", "--format=%H %gs")
    if done.returncode != 0:
        raise SystemExit(f"git stash list failed (exit {done.returncode}): {done.stderr.strip()}")
    rows = [line.split(" ", 1) for line in done.stdout.splitlines() if line]
    return [(sha, subject) for sha, subject in rows]


def push() -> int:
    """Stash everything under a unique message and print the new SHA."""
    tag = f"tdd-xfail-{uuid.uuid4().hex}"
    done = git("stash", "push", "--include-untracked", "--message", tag)
    if done.returncode != 0:
        raise SystemExit(f"git stash push failed (exit {done.returncode}): {done.stderr.strip()}")
    found = [sha for sha, subject in entries() if subject.endswith(tag)]
    if len(found) != 1:
        print("nothing stashed", file=sys.stderr)
        return 1
    print(found[0])
    return 0


def restore(sha: str) -> int:
    """Apply stash commit ``sha``, then drop only the entry with that SHA."""
    if not FULL_SHA.match(sha) or sha not in [s for s, _ in entries()]:
        raise SystemExit(f"no stash entry with SHA {sha}")
    done = git("stash", "apply", sha)
    if done.returncode != 0:
        print(done.stdout + done.stderr, end="", file=sys.stderr)
        print(f"apply failed; stash {sha} kept", file=sys.stderr)
        return 1
    for i, (found, _) in enumerate(entries()):
        if found == sha:
            dropped = git("stash", "drop", f"stash@{{{i}}}")
            if dropped.returncode != 0 or sha not in dropped.stdout:
                raise SystemExit(f"drop did not remove {sha}: {dropped.stderr.strip()}")
            break
    print(f"restored {sha}")
    return 0


def main() -> int:
    """Dispatch the subcommand."""
    argv = sys.argv[1:]
    if argv == ["push"]:
        return push()
    if len(argv) == 2 and argv[0] == "restore":  # noqa: PLR2004
        return restore(argv[1])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
