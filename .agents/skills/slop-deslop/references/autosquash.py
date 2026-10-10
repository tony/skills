#!/usr/bin/env python3
"""Run ``git rebase -i --autosquash`` over a baseline, unattended.

Usage: autosquash.py --baseline SHA [--abort-on-conflict] [--force-rewrite-pushed]
       autosquash.py --baseline SHA --check-published

Exit codes: 0 the rebase completed; 10 it stopped on a conflict (aborted
when ``--abort-on-conflict`` is set, otherwise left paused for the conflict
loop); 1 any other failure, with git's stderr passed through; 2 refused before
touching anything (merge commits in range, or a published range without
``--force-rewrite-pushed``).

``--check-published`` rewrites nothing. It prints ``published: <n> of <m>
commits, on <refs>`` when any remote-tracking ref contains a commit of
``SHA..HEAD`` (pushed with or without ``-u``), else ``local-only``, and
exits 0 either way.
"""

# pyright: reportAny=false, reportUnusedCallResult=false

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

EXIT_CONFLICT = 10
EXIT_REFUSED = 2


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
        if path and Path(path).is_dir():
            return True
    return False


def published(baseline: str) -> tuple[int, int, list[str]]:
    """Return (published, total, remote refs) for the commits in ``baseline..HEAD``."""
    rng = f"{baseline}..HEAD"
    everything = _git("rev-list", rng).stdout.split()
    unpublished = set(_git("rev-list", rng, "--not", "--remotes").stdout.split())
    pushed = [c for c in everything if c not in unpublished]
    if not pushed:
        return 0, len(everything), []
    refs = _git(
        "for-each-ref", "refs/remotes", "--contains", pushed[0], "--format=%(refname:short)"
    ).stdout.split()
    return len(pushed), len(everything), [r for r in refs if not r.endswith("/HEAD")]


def main(argv: list[str] | None = None) -> int:
    """Run the rebase; return the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--abort-on-conflict", action="store_true")
    parser.add_argument("--check-published", action="store_true")
    parser.add_argument("--force-rewrite-pushed", action="store_true")
    args = parser.parse_args(argv)

    if args.check_published:
        count, total, refs = published(args.baseline)
        if count:
            print(f"published: {count} of {total} commits, on {' '.join(refs)}")
        else:
            print("local-only")
        return 0

    if _git("rev-list", "--merges", f"{args.baseline}..HEAD").stdout.split():
        sys.stderr.write("autosquash: the range holds merge commits; nothing was rewritten\n")
        return EXIT_REFUSED
    count, total, refs = published(args.baseline)
    if count and not args.force_rewrite_pushed:
        on = " ".join(refs)
        sys.stderr.write(f"autosquash: {count} of {total} commits are on {on}; nothing rewritten\n")
        return EXIT_REFUSED

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
