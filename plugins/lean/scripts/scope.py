#!/usr/bin/env python3
"""List the files and line ranges a branch added or changed.

Prints one ``path<TAB>start-end[,start-end...]`` line per file, from the
merge base with the trunk ref (default), the index (``--staged``), or the
whole tree (``--all``, ranges omitted). Exits 2 with a message on stderr
when no trunk ref exists or nothing changed.
"""

# ruff: noqa: S603
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import argparse
import re
import subprocess
import sys

_HUNK = re.compile(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],  # noqa: S607
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
            path = line[6:]
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

    if args.all:
        for name in _git("ls-files").splitlines():
            print(name)
        return 0

    if args.staged:
        diff = _git("diff", "--cached", "-U0", "--no-color", "--diff-filter=d")
    else:
        trunk = trunk_ref()
        if trunk is None:
            print("no trunk ref (origin/HEAD, main, master) found", file=sys.stderr)
            return 2
        base = _git("merge-base", "HEAD", trunk).strip()
        diff = _git("diff", base, "-U0", "--no-color", "--diff-filter=d")

    ranges = parse_ranges(diff)
    if not ranges:
        print("no changed files", file=sys.stderr)
        return 2
    for name, spans in ranges.items():
        print(f"{name}\t{','.join(f'{a}-{b}' for a, b in spans)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
