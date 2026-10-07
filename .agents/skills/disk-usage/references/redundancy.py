#!/usr/bin/env python3
"""Prove whether a candidate directory holds anything its keeper lacks.

Usage: redundancy.py CANDIDATE KEEPER

Compares relative path sets (files and symlinks) and prints the shared and
unique counts with sizes. Exit status: 0 REDUNDANT, 1 NOT REDUNDANT,
2 INCONCLUSIVE. Any unreadable entry in either tree is INCONCLUSIVE, never
REDUNDANT, because a subtree that cannot be listed cannot be proved empty.
"""

# pyright: reportAny=false

from __future__ import annotations

import os
import sys
from pathlib import Path

EXIT_REDUNDANT = 0
EXIT_NOT_REDUNDANT = 1
EXIT_INCONCLUSIVE = 2
ARGC = 3


def scan(root: str) -> tuple[dict[str, int], list[str], int]:
    """Return ({relpath: lstat size}, errors, empty directory count).

    >>> import tempfile
    >>> d = tempfile.mkdtemp()
    >>> open(os.path.join(d, "a"), "w").write("xy")
    2
    >>> scan(d)[0]
    {'a': 2}
    >>> scan(os.path.join(d, "missing"))[1] != []
    True
    """
    entries: dict[str, int] = {}
    errors: list[str] = []
    empty_dirs = 0

    def on_error(err: OSError) -> None:
        errors.append(f"{err.filename}: {err.strerror}")

    if not Path(root).is_dir():
        return entries, [f"{root}: not a directory"], 0
    for dirpath, dirnames, filenames in os.walk(root, onerror=on_error):
        if not dirnames and not filenames:
            empty_dirs += 1
        linked = [d for d in dirnames if (Path(dirpath) / d).is_symlink()]
        for name in filenames + linked:
            full = Path(dirpath) / name
            try:
                size = full.lstat().st_size
            except OSError as err:
                errors.append(f"{full}: {err.strerror}")
                continue
            entries[str(full.relative_to(root))] = size
    return entries, errors, empty_dirs


def gib(n: int) -> str:
    """Format a byte count as GiB."""
    return f"{n / 2**30:.2f} GiB"


def main(argv: list[str]) -> int:
    """Run the proof and return the exit status."""
    if len(argv) != ARGC:
        print(__doc__, file=sys.stderr)
        return EXIT_INCONCLUSIVE
    cand, cand_errors, cand_empty = scan(argv[1])
    keep, keep_errors, _ = scan(argv[2])
    errors = cand_errors + keep_errors
    shared = cand.keys() & keep.keys()
    only_c = cand.keys() - keep.keys()
    print(f"candidate entries: {len(cand)}")
    print(f"shared with keeper: {len(shared)} ({gib(sum(cand[p] for p in shared))})")
    print(f"UNIQUE to candidate: {len(only_c)} ({gib(sum(cand[p] for p in only_c))})")
    print(f"empty directories not compared: {cand_empty}")
    if errors:
        print(f"UNREADABLE: {len(errors)} entries could not be read")
        for line in errors[:20]:
            print(f"  {line}")
        print("INCONCLUSIVE - fix access or report the proof as failed")
        return EXIT_INCONCLUSIVE
    if only_c:
        print("NOT REDUNDANT - candidate holds unique data")
        return EXIT_NOT_REDUNDANT
    print("REDUNDANT (path sets only; confirm contents with rsync -rcn)")
    return EXIT_REDUNDANT


if __name__ == "__main__":
    sys.exit(main(sys.argv))
