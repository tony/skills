#!/usr/bin/env python3
"""Measure one filesystem and list the directories above a size floor.

Usage: survey.py PATH [--depth N] [--floor-pct P] [--time-limit S]

Prints JSON: the filesystem holding PATH (total, used, available bytes),
the floor in bytes (P percent of total, default 1), and every directory
within N levels of PATH (default 3) whose size meets the floor, largest
first. Sizes are allocated bytes (st_blocks), each inode is counted once
under the first path in name order, symlinks are never
followed, and the walk stays on PATH's filesystem. Paths that could not
be read are listed under "errors" and their contents are missing from
the sizes. Directories under /mnt are
skipped (listed under "skipped") unless PATH is inside /mnt. When the
time limit (default 90 seconds) runs out or a path cannot be read,
"complete" is false and sizes are lower bounds. The limit is checked
between directory entries, so one blocked system call can overrun it.
"""

# pyright: reportAny=false

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import final

DEFAULT_DEPTH = 3
DEFAULT_FLOOR_PCT = 1.0
DEFAULT_TIME_LIMIT = 90.0
SKIP_ROOT = "/mnt"
BLOCK = 512


@final
class Walker:
    """Accumulate allocated sizes for one filesystem."""

    def __init__(
        self,
        dev: int,
        max_depth: int,
        skip: str | None = None,
        deadline: float = math.inf,
    ) -> None:
        self.dev: int = dev
        self.max_depth: int = max_depth
        self.skip: str | None = skip
        self.deadline: float = deadline
        self.timed_out: bool = False
        self.skipped: list[str] = []
        self.seen: set[tuple[int, int]] = set()
        self.sizes: dict[str, int] = {}
        self.errors: list[str] = []

    def walk(self, path: str, depth: int = 0) -> int:
        """Return the allocated bytes under path; record directory sizes.

        >>> import tempfile
        >>> d = tempfile.mkdtemp()
        >>> os.mkdir(os.path.join(d, "sub"))
        >>> _ = Path(d, "sub", "f").write_bytes(b"x" * 5000)
        >>> os.link(os.path.join(d, "sub", "f"), os.path.join(d, "g"))
        >>> w = Walker(Path(d).stat().st_dev, 3)
        >>> total = w.walk(d)
        >>> sub = os.path.join(d, "sub")
        >>> w.sizes[sub] == os.lstat(sub).st_blocks * 512
        True
        >>> w.sizes[d] == total > w.sizes[sub]
        True
        """
        total = 0
        if time.monotonic() > self.deadline:
            self.timed_out = True
            return total
        try:
            st = os.lstat(path)
            key = (st.st_dev, st.st_ino)
            if key in self.seen:
                self.skipped.append(path)
                return 0
            entries: list[os.DirEntry[str]] = []
            with os.scandir(path) as it:
                for entry in it:
                    if time.monotonic() > self.deadline:
                        self.timed_out = True
                        return total
                    entries.append(entry)
            entries.sort(key=lambda e: e.name)
            self.seen.add(key)
            total += st.st_blocks * BLOCK
        except OSError as err:
            self.errors.append(f"{path}: {err.strerror}")
            return total
        for entry in entries:
            if time.monotonic() > self.deadline:
                self.timed_out = True
                break
            try:
                st = entry.stat(follow_symlinks=False)
                if st.st_dev != self.dev:
                    self.skipped.append(entry.path)
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if self.skip and entry.path == self.skip:
                        self.skipped.append(entry.path)
                    else:
                        total += self.walk(entry.path, depth + 1)
                    continue
                key = (st.st_dev, st.st_ino)
                if key in self.seen:
                    continue
                self.seen.add(key)
                total += st.st_blocks * BLOCK
            except OSError as err:
                self.errors.append(f"{entry.path}: {err.strerror}")
        if depth <= self.max_depth:
            self.sizes[path] = total
        return total


def survey(
    root: str,
    max_depth: int,
    floor_pct: float,
    time_limit: float = DEFAULT_TIME_LIMIT,
    skip: str = SKIP_ROOT,
) -> dict[str, object]:
    """Return the survey of root as a JSON-ready dict."""
    real = os.path.realpath(root)
    inside = real == skip or real.startswith(skip + "/")
    vfs = os.statvfs(real)
    total_bytes = vfs.f_blocks * vfs.f_frsize
    avail = vfs.f_bavail * vfs.f_frsize
    used = total_bytes - vfs.f_bfree * vfs.f_frsize
    floor = int(total_bytes * floor_pct / 100)
    walker = Walker(
        Path(real).stat().st_dev,
        max_depth,
        None if inside else skip,
        time.monotonic() + time_limit,
    )
    _ = walker.walk(real)
    found = sorted(
        ((p, s) for p, s in walker.sizes.items() if s >= floor),
        key=lambda item: item[1],
        reverse=True,
    )
    return {
        "path": real,
        "filesystem": {"total": total_bytes, "used": used, "available": avail},
        "floor": floor,
        "directories": [{"path": p, "bytes": s} for p, s in found],
        "errors": walker.errors,
        "skipped": walker.skipped,
        "complete": not walker.timed_out and not walker.errors,
    }


def main(argv: list[str]) -> int:
    """Run the command line; return the exit status."""
    parser = argparse.ArgumentParser(description="Survey one filesystem.")
    _ = parser.add_argument("path")
    _ = parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    _ = parser.add_argument("--floor-pct", type=float, default=DEFAULT_FLOOR_PCT)
    _ = parser.add_argument("--time-limit", type=float, default=DEFAULT_TIME_LIMIT)
    args = parser.parse_args(argv[1:])
    if args.depth < 0:
        parser.error("--depth must be nonnegative")
    if not math.isfinite(args.time_limit) or args.time_limit < 0:
        parser.error("--time-limit must be finite and nonnegative")
    if not Path(args.path).is_dir():
        _ = sys.stderr.write(f"{args.path}: not a directory\n")
        return 2
    _ = json.dump(
        survey(args.path, args.depth, args.floor_pct, args.time_limit), sys.stdout, indent=2
    )
    _ = sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
