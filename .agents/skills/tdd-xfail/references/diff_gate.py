#!/usr/bin/env python3
"""Check that the working tree holds only the files the next commit may stage.

Usage:
    diff_gate.py test-only   --pattern GLOB [--pattern GLOB ...]
    diff_gate.py source-only --pattern GLOB [--pattern GLOB ...]

Run it inside the repository. Each GLOB names test files, relative to the
repository root; ``**/`` matches zero or more directories and ``*`` stays
inside one path component. ``test-only`` prints every changed file that
matches no pattern; ``source-only`` prints every changed file that matches a
pattern. Output is empty and the exit status 0 when the gate passes;
otherwise the offending paths print one per line and the status is 1.
Any Git failure or diagnostic stops the gate with status 1 and an incomplete
observation message on stderr, including Git's exit status and diagnostic.
A tracked file flagged skip-worktree or assume-unchanged hides edits from
``git status``, so any such flag stops the gate the same way.
Untracked build caches (``__pycache__/``, ``.pytest_cache/``, ``.mypy_cache/``,
``.ruff_cache/``, ``node_modules/.cache/``, ``*.pyc``) never count.
"""

# ruff: noqa: EM102, TRY003
# pyright: reportAny=false, reportUnusedCallResult=false

import argparse
import itertools
import re
import subprocess
import sys

CACHE_DIRS = ("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache")


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a path glob into an anchored regular expression.

    >>> bool(glob_to_regex("**/test_*.py").match("test_a.py"))
    True
    >>> bool(glob_to_regex("**/test_*.py").match("pkg/sub/test_a.py"))
    True
    >>> bool(glob_to_regex("tests/**").match("tests/a/b.py"))
    True
    >>> bool(glob_to_regex("tests/*.py").match("tests/a/b.py"))
    False
    """
    parts: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            parts.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            parts.append(".*")
            i += 2
        elif pattern[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(parts) + r"\Z")


def is_cache(path: str) -> bool:
    """Return True for an untracked build-cache path.

    >>> is_cache("pkg/__pycache__/a.cpython-312.pyc")
    True
    >>> is_cache("web/node_modules/.cache/x.json")
    True
    >>> is_cache("pkg/a.py")
    False
    """
    parts = path.split("/")
    if path.endswith(".pyc") or any(p in CACHE_DIRS for p in parts):
        return True
    return any(a == "node_modules" and b == ".cache" for a, b in itertools.pairwise(parts))


def hidden_paths() -> list[str]:
    """List tracked paths flagged skip-worktree or assume-unchanged."""
    done = subprocess.run(
        ["git", "ls-files", "-v", "-z"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0 or done.stderr:
        raise SystemExit(f"git ls-files incomplete (exit {done.returncode}): {done.stderr.strip()}")
    return [e[2:] for e in done.stdout.split("\0") if e[:1] == "S" or e[:1].islower()]


def changed_paths() -> list[str]:
    """List modified, staged, and untracked paths, minus untracked caches."""
    done = subprocess.run(
        ["git", "status", "--porcelain", "-z", "--untracked-files=all"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0 or done.stderr:
        raise SystemExit(f"git status incomplete (exit {done.returncode}): {done.stderr.strip()}")
    paths: list[str] = []
    fields = done.stdout.split("\0")
    i = 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:  # noqa: PLR2004
            continue
        status, path = entry[:2], entry[3:]
        if "R" in status or "C" in status:
            paths.append(path)
            path = fields[i] if i < len(fields) else path
            i += 1
        if status == "??" and is_cache(path):
            continue
        paths.append(path)
    hidden = hidden_paths()
    if hidden:
        raise SystemExit("git status cannot see flagged paths: " + ", ".join(hidden))
    return paths


def offenders(mode: str, patterns: list[str], paths: list[str]) -> list[str]:
    """Return the paths that break the gate for ``mode``.

    >>> offenders("test-only", ["**/test_*.py"], ["test_a.py", "a.py"])
    ['a.py']
    >>> offenders("source-only", ["**/test_*.py"], ["test_a.py", "a.py"])
    ['test_a.py']
    """
    regexes = [glob_to_regex(p) for p in patterns]
    is_test = [any(r.match(p) for r in regexes) for p in paths]
    want_test = mode == "source-only"
    return [p for p, t in zip(paths, is_test, strict=True) if t == want_test]


def main() -> int:
    """Parse arguments, run the gate, and print offenders."""
    parser = argparse.ArgumentParser(
        description="Check which changed files the next commit may stage."
    )
    parser.add_argument("mode", choices=["test-only", "source-only"])
    parser.add_argument("--pattern", action="append", required=True)
    args = parser.parse_args()
    bad = offenders(args.mode, args.pattern, changed_paths())
    for path in bad:
        print(path)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
