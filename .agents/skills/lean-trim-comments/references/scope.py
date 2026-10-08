#!/usr/bin/env python3
"""List the files and line ranges a branch added or changed.

Prints one ``path<TAB>start-end[,start-end...]`` line per file, from the
merge base with the trunk ref (default), the index (``--staged``), or the
whole tree (``--all``, ranges omitted). Paths are relative to the current
directory. Untracked files outside ignore rules count as added in full on a
branch run. Exits 2 with a message on stderr
outside a git repository, when no trunk ref or merge base exists, or nothing
changed.
"""

# ruff: noqa: S603
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

_HUNK = re.compile(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@")


_DIFF = (
    "diff",
    "-U0",
    "--no-color",
    "--no-ext-diff",
    "--no-textconv",
    "--src-prefix=a/",
    "--dst-prefix=b/",
    "--diff-filter=d",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.quotePath=off", *args],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _ok(*args: str) -> bool:
    return (
        subprocess.run(
            ["git", *args],  # noqa: S607
            check=False,
            capture_output=True,
        ).returncode
        == 0
    )


def trunk_ref() -> str | None:
    """Return the trunk ref: the remote default branch, else main or master."""
    if _ok("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"):
        return _git("symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip()
    for ref in ("origin/main", "origin/master", "main", "master"):
        if _ok("rev-parse", "--verify", "--quiet", ref):
            return ref
    return None


def parse_ranges(diff: str) -> dict[str, list[tuple[int, int]]]:
    r"""Map each path in a zero-context diff to its added line ranges.

    >>> d = "\n".join(
    ...     ["+++ b/a.py", "@@ -1,2 +3,2 @@", "@@ -9 +12 @@", "+++ b/c.py", "@@ -1 +1,0 @@"]
    ... )
    >>> parse_ranges(d)
    {'a.py': [(3, 4), (12, 12)], 'c.py': []}
    """
    out: dict[str, list[tuple[int, int]]] = {}
    path = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:].rstrip("\t")
            out[path] = []
            continue
        m = _HUNK.match(line)
        if m and path:
            start = int(m.group(1))
            count = 1 if m.group(2) is None else int(m.group(2))
            if count:
                out[path].append((start, start + count - 1))
    return out


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true", help="staged changes only")
    mode.add_argument("--all", action="store_true", help="every tracked file")
    args = p.parse_args(argv)

    try:
        top = _git("rev-parse", "--show-toplevel").strip()
    except subprocess.CalledProcessError:
        print("not inside a git repository", file=sys.stderr)
        return 2

    def rel(name: str) -> str:
        return os.path.relpath(Path(top, name))

    if args.all:
        for name in _git("-C", top, "ls-files").splitlines():
            print(rel(name))
        return 0

    untracked: list[str] = []
    if args.staged:
        diff = _git("-C", top, *_DIFF[:1], "--cached", *_DIFF[1:])
    else:
        trunk = trunk_ref()
        if trunk is None:
            print("no trunk ref (origin/HEAD, main, master) found", file=sys.stderr)
            return 2
        try:
            base = _git("merge-base", "HEAD", trunk).strip()
        except subprocess.CalledProcessError:
            print(f"no merge base with {trunk}", file=sys.stderr)
            return 2
        diff = _git("-C", top, *_DIFF[:1], base, *_DIFF[1:])
        untracked = _git("-C", top, "ls-files", "--others", "--exclude-standard").splitlines()

    ranges = parse_ranges(diff)
    for name in untracked:
        path = Path(top, name)
        if not path.is_file():
            continue
        count = len(path.read_bytes().splitlines())
        ranges[name] = [(1, count)] if count else []
    if not ranges:
        print("no changed files", file=sys.stderr)
        return 2
    for name, spans in ranges.items():
        print(f"{rel(name)}\t{','.join(f'{a}-{b}' for a, b in spans)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
