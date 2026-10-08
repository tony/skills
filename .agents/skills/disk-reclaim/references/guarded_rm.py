#!/usr/bin/env python3
"""Check, list, and optionally delete one approved path.

Usage: guarded_rm.py --scope DIR [--keeper DIR ...] [--delete] TARGET

Resolves TARGET with realpath and refuses (exit 2) when it is missing, is
or contains the scope root, lies outside SCOPE, or is, contains, or lies
inside a KEEPER, or holds a directory on another device. Otherwise prints
the resolved target, its size, and up to 50 top-level entries (exit 0).
Only --delete removes it; symlinks inside the tree are unlinked, never
followed.
"""

# pyright: reportAny=false, reportUnusedCallResult=false

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_REFUSED = 2
LIST_LIMIT = 50


def contains(parent: str, child: str) -> bool:
    """Return True when child equals parent or lies beneath it."""
    return os.path.commonpath([parent, child]) == parent


def refusal(target: str, scope: str, keepers: list[str]) -> str | None:
    """Return why a resolved target must not be removed, else None."""
    if not os.path.lexists(target):
        return "target does not exist"
    if contains(target, scope):
        return "target is or contains the approved scope"
    if not contains(scope, target):
        return "target resolves outside the approved scope"
    for keeper in keepers:
        if contains(keeper, target) or contains(target, keeper):
            return f"target overlaps a keeper ({keeper})"
    return crossing_mount(target)


def crossing_mount(target: str) -> str | None:
    """Return a refusal when a directory under target is on another device."""
    if Path(target).is_symlink() or not Path(target).is_dir():
        return None
    dev = os.lstat(target).st_dev
    for root, dirs, _files in os.walk(target):
        for name in dirs:
            path = str(Path(root) / name)
            try:
                crosses = os.lstat(path).st_dev != dev
            except OSError:
                continue
            if crosses:
                return f"target holds a mount point or other filesystem ({path})"
    return None


def size_of(path: str) -> int:
    """Sum allocated bytes under path without following symlinks."""
    total = 0
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            try:
                total += (Path(root) / name).lstat().st_blocks * 512
            except OSError:
                continue
    return total


def human(nbytes: int) -> str:
    """Format bytes as GiB at or above 1 GiB, else MiB or KiB."""
    if nbytes >= 2**30:
        return f"{nbytes / 2**30:.2f} GiB"
    if nbytes >= 2**20:
        return f"{nbytes / 2**20:.1f} MiB"
    return f"{nbytes / 2**10:.0f} KiB"


def main(argv: list[str]) -> int:
    """Run the guard and return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--keeper", action="append", default=[])
    parser.add_argument("--delete", action="store_true")
    parser.add_argument("target")
    args = parser.parse_args(argv[1:])
    target = os.path.realpath(args.target)
    scope = os.path.realpath(args.scope)
    keepers = [os.path.realpath(k) for k in args.keeper]
    reason = refusal(target, scope, keepers)
    if reason:
        print(f"REFUSED - {reason}: {target}")
        return EXIT_REFUSED
    print(f"target: {target}")
    if Path(target).is_dir():
        print(f"size: {human(size_of(target))}")
        names: list[str] = sorted(entry.name for entry in os.scandir(target))
        for name in names[:LIST_LIMIT]:
            print(f"  {name}")
        if len(names) > LIST_LIMIT:
            print(f"  ... {len(names) - LIST_LIMIT} more")
    if not args.delete:
        print("OK - re-run with --delete after checking nothing holds it open")
        return EXIT_OK
    if Path(target).is_dir() and not Path(target).is_symlink():
        shutil.rmtree(target)
    else:
        Path(target).unlink()
    print("DELETED")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
