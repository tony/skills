#!/usr/bin/env python3
"""Prove whether a candidate directory holds anything its keeper lacks.

Usage: redundancy.py CANDIDATE KEEPER

Compares relative path sets (files and symlinks), then the SHA-256 of every
shared regular file and the target of every shared symlink. Prints the
shared, unique, and differing counts with sizes. Exit status: 0 REDUNDANT
(no unique path and no content difference), 1 NOT REDUNDANT, 2 INCONCLUSIVE.
Any entry in either tree that cannot be listed or opened
is INCONCLUSIVE, never REDUNDANT, because content that cannot be read
cannot be proved duplicated. The same directory (including a symlink alias)
or one tree inside the other is also INCONCLUSIVE: it proves nothing.
"""

# pyright: reportAny=false

from __future__ import annotations

import hashlib
import os
import stat
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
                st = full.lstat()
                if stat.S_ISREG(st.st_mode):
                    with full.open("rb") as handle:
                        _ = handle.read(1)
                size = st.st_size
            except OSError as err:
                errors.append(f"{full}: {err.strerror}")
                continue
            entries[str(full.relative_to(root))] = size
    return entries, errors, empty_dirs


def digest(root: str, rel: str) -> str:
    """Return a content fingerprint: file SHA-256 or symlink target.

    >>> import tempfile
    >>> d = tempfile.mkdtemp()
    >>> open(os.path.join(d, "a"), "w").write("xy")
    2
    >>> digest(d, "a") == digest(d, "a")
    True
    """
    full = Path(root) / rel
    if full.is_symlink():
        return f"link:{full.readlink()}"
    sha = hashlib.sha256()
    with full.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return "sha256:" + sha.hexdigest()


def differing(cand: str, keep: str, shared: set[str]) -> tuple[list[str], list[str]]:
    """Return (paths whose content differs, read errors) among shared paths."""
    diff: list[str] = []
    errors: list[str] = []
    for rel in sorted(shared):
        try:
            if digest(cand, rel) != digest(keep, rel):
                diff.append(rel)
        except OSError as err:
            errors.append(f"{rel}: {err.strerror}")
    return diff, errors


def gib(n: int) -> str:
    """Format a byte count as GiB."""
    return f"{n / 2**30:.2f} GiB"


def overlap(cand: str, keep: str) -> str | None:
    """Return why the two paths are not independent trees, else None."""
    rc, rk = Path(cand).resolve(), Path(keep).resolve()
    if rc == rk or (rc.exists() and rk.exists() and rc.samefile(rk)):
        return "candidate and keeper are the same directory"
    if rc.is_relative_to(rk):
        return "candidate is inside the keeper"
    if rk.is_relative_to(rc):
        return "keeper is inside the candidate"
    return None


def main(argv: list[str]) -> int:
    """Run the proof and return the exit status."""
    if len(argv) != ARGC:
        print(__doc__, file=sys.stderr)
        return EXIT_INCONCLUSIVE
    reason = overlap(argv[1], argv[2])
    if reason:
        print(f"INCONCLUSIVE - {reason}; the proof compares two independent trees")
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
    diff: list[str] = []
    if not errors:
        diff, hash_errors = differing(argv[1], argv[2], shared)
        errors += hash_errors
        print(f"shared paths with different content: {len(diff)}")
        for rel in diff[:20]:
            print(f"  {rel}")
    if errors:
        print(f"UNREADABLE: {len(errors)} entries could not be read")
        for line in errors[:20]:
            print(f"  {line}")
        print("INCONCLUSIVE - fix access or report the proof as failed")
        return EXIT_INCONCLUSIVE
    if only_c or diff:
        print("NOT REDUNDANT - candidate holds unique paths or differing content")
        return EXIT_NOT_REDUNDANT
    print("REDUNDANT - every candidate path exists in the keeper with identical content")
    return EXIT_REDUNDANT


if __name__ == "__main__":
    sys.exit(main(sys.argv))
