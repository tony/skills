#!/usr/bin/env python3
"""Run ``git rebase -i --autosquash`` over a baseline, unattended.

Usage: autosquash.py --baseline SHA [--abort-on-conflict]

Exit codes: 0 the rebase completed; 10 it stopped on a conflict (aborted
when ``--abort-on-conflict`` is set, otherwise left paused for the conflict
loop); 1 any other failure, with git's stderr passed through.
"""

# pyright: reportAny=false, reportUnusedCallResult=false

from __future__ import annotations

import argparse
import os
import subprocess
import sys

EXIT_CONFLICT = 10


def _git(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def unmerged() -> list[str]:
    """Paths with unresolved conflicts."""
    return _git("diff", "--name-only", "--diff-filter=U").stdout.split()


def rebase_in_progress() -> bool:
    """Whether a rebase is paused, resolved through ``--git-path`` for linked worktrees."""
    for name in ("rebase-merge", "rebase-apply"):
        path = _git("rev-parse", "--git-path", name).stdout.strip()
        if path and os.path.isdir(path):
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    """Run the rebase; return the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--abort-on-conflict", action="store_true")
    args = parser.parse_args(argv)

    done = _git(
        "-c",
        "rerere.enabled=true",
        "-c",
        "rerere.autoupdate=true",
        "rebase",
        "-i",
        "--autosquash",
        args.baseline,
        env={**os.environ, "GIT_SEQUENCE_EDITOR": ":"},
    )
    if done.returncode == 0:
        return 0
    if rebase_in_progress() and unmerged():
        print("autosquash: stopped on a conflict in: " + " ".join(unmerged()))
        if args.abort_on_conflict:
            _git("rebase", "--abort")
            print("autosquash: rebase aborted; the branch is unchanged")
        return EXIT_CONFLICT
    sys.stderr.write(done.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
