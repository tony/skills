#!/usr/bin/env python3
"""List the files and line ranges a branch added or changed.

Prints one ``path<TAB>start-end[,start-end...]`` line per file, from the
merge base with the trunk ref (default), the index (``--staged``), or the
whole tree (``--all``, ranges omitted). Paths are relative to the current
directory. Untracked files outside ignore rules count as added in full on a
branch run. Lockfiles, vendored trees, and files marked linguist-generated
or linguist-vendored are left out. ``--paths P...`` resolves each path or
glob to ``path<TAB>tracked|untracked|deleted`` instead. Exits 2 with a message on
stderr outside a git repository, when no trunk ref or merge base exists,
when a path matches no file, or when nothing changed.
"""

# ruff: noqa: S603
# pyright: reportAny=false, reportUnusedCallResult=false
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

_HUNK = re.compile(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@")
_ESCAPE = re.compile(r"\\(?:([0-7]{3})|(.))")
_LOCKFILES = frozenset(
    {
        "package-lock.json",
        "npm-shrinkwrap.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "bun.lockb",
        "uv.lock",
        "poetry.lock",
        "Pipfile.lock",
        "Cargo.lock",
        "Gemfile.lock",
        "composer.lock",
        "go.sum",
    }
)
_VENDORED_DIRS = frozenset({"vendor", "node_modules", "third_party"})
_BINARY_SNIFF = 8192


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


def _git_z(*args: str) -> list[str]:
    return [n for n in _git(*args).split("\0") if n]


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
    candidates = ["origin/main", "origin/master", "main", "master"]
    if _ok("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"):
        candidates.insert(0, _git("symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip())
    for ref in candidates:
        if _ok("rev-parse", "--verify", "--quiet", ref):
            return ref
    return None


def _unquote(path: str) -> str:
    r"""Undo git's C-style quoting of a path with control characters.

    >>> _unquote('"a\\tb.py"')
    'a\tb.py'
    >>> _unquote("plain.py")
    'plain.py'
    """
    if not (len(path) > 1 and path[0] == path[-1] == '"'):
        return path
    simple = {"t": "\t", "n": "\n", '"': '"', "\\": "\\"}

    def sub(m: re.Match[str]) -> str:
        return chr(int(m.group(1), 8)) if m.group(1) else simple.get(m.group(2), m.group(2))

    return _ESCAPE.sub(sub, path[1:-1])


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
        if line.startswith(("+++ b/", '+++ "b/')):
            raw = line[4:].rstrip("\t")
            path = _unquote(raw.replace('"b/', '"', 1) if raw.startswith('"') else raw[2:])
            out[path] = []
            continue
        m = _HUNK.match(line)
        if m and path:
            start = int(m.group(1))
            count = 1 if m.group(2) is None else int(m.group(2))
            if count:
                out[path].append((start, start + count - 1))
    return out


def _generated(top: str, names: list[str]) -> set[str]:
    """Return the names marked linguist-generated or linguist-vendored."""
    if not names:
        return set()
    cmd = [
        "git",
        "-C",
        top,
        "check-attr",
        "-z",
        "--stdin",
        "linguist-generated",
        "linguist-vendored",
    ]
    raw = subprocess.run(
        cmd,
        input="\0".join(names) + "\0",
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")
    return {raw[i] for i in range(0, len(raw) - 2, 3) if raw[i + 2] in ("set", "true")}


def _keep(top: str, names: list[str]) -> list[str]:
    """Drop lockfiles, vendored trees, and attribute-marked generated files."""
    kept = [
        n
        for n in names
        if Path(n).name not in _LOCKFILES and not _VENDORED_DIRS.intersection(Path(n).parts[:-1])
    ]
    skip = _generated(top, kept)
    return [n for n in kept if n not in skip]


def _added_in_full(path: Path) -> int | None:
    """Count the lines of a text file, or None when it is unreadable or binary."""
    try:
        with path.open("rb") as fh:
            if b"\0" in fh.read(_BINARY_SNIFF):
                return None
            fh.seek(0)
            return sum(1 for _ in fh)
    except OSError:
        return None


class _Halt(Exception):  # noqa: N818
    """A refusal whose message is the one-line reason."""


def _scan(top: str, *, staged: bool) -> tuple[str, list[str]]:
    """Return the zero-context diff and the untracked names for the chosen mode."""
    if staged:
        return _git("-C", top, *_DIFF[:1], "--cached", *_DIFF[1:]), []
    trunk = trunk_ref()
    if trunk is None:
        msg = "no trunk ref (origin/HEAD, main, master) found"
        raise _Halt(msg)
    try:
        base = _git("merge-base", "HEAD", trunk).strip()
    except subprocess.CalledProcessError:
        msg = f"no merge base with {trunk}"
        raise _Halt(msg) from None
    diff = _git("-C", top, *_DIFF[:1], base, *_DIFF[1:])
    return diff, _git_z("-C", top, "ls-files", "-z", "--others", "--exclude-standard")


def _resolve(patterns: list[str]) -> int:
    """Print ``path<TAB>tracked|untracked|deleted`` per match, or fail on a miss."""
    rows: list[tuple[str, str]] = []
    for pat in patterns:
        tracked = _git_z("ls-files", "-z", "--", pat)
        fresh = _git_z("ls-files", "-z", "--others", "--exclude-standard", "--", pat)
        found = [(n, "tracked" if Path(n).exists() else "deleted") for n in tracked]
        found += [(n, "untracked") for n in fresh]
        if not found and Path(pat).is_file():
            found = [(pat, "untracked")]
        if not found:
            print(f"not a file: {pat}", file=sys.stderr)
            return 2
        rows.extend((os.path.relpath(Path.cwd() / n), state) for n, state in found)
    for name, state in sorted(dict.fromkeys(rows)):
        print(f"{name}\t{state}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true", help="staged changes only")
    mode.add_argument("--all", action="store_true", help="every tracked file")
    mode.add_argument("--paths", nargs="+", metavar="PATH", help="resolve paths or globs")
    args = p.parse_args(argv)

    try:
        top = _git("rev-parse", "--show-toplevel").strip()
    except subprocess.CalledProcessError:
        print("not inside a git repository", file=sys.stderr)
        return 2

    def rel(name: str) -> str:
        return os.path.relpath(Path(top, name))

    if args.paths:
        return _resolve(args.paths)

    if args.all:
        names = _keep(top, _git_z("-C", top, "ls-files", "-z"))
        for name in names:
            print(rel(name))
        return 0

    try:
        diff, untracked = _scan(top, staged=args.staged)
    except _Halt as halt:
        print(halt, file=sys.stderr)
        return 2

    ranges = parse_ranges(diff)
    for name in untracked:
        count = _added_in_full(Path(top, name)) if Path(top, name).is_file() else None
        if count is None:
            print(f"skipped (binary or unreadable): {rel(name)!r}", file=sys.stderr)
            continue
        ranges[name] = [(1, count)] if count else []
    kept = set(_keep(top, list(ranges)))
    ranges = {n: r for n, r in ranges.items() if n in kept}
    if not ranges:
        print("no changed files", file=sys.stderr)
        return 2
    for name, spans in ranges.items():
        print(f"{rel(name)}\t{','.join(f'{a}-{b}' for a, b in spans)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
