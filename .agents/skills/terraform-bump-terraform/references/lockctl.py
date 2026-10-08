#!/usr/bin/env python3
"""Deterministic helpers for Terraform and OpenTofu lock-file work.

Usage:
    lockctl.py state LOCK
    lockctl.py drop LOCK SOURCE
    lockctl.py stable [COUNT] < versions
    lockctl.py platforms
    lockctl.py diff [--allow SOURCE]... BEFORE AFTER

state      print source, selected version and h1 hash count, tab separated,
           one line per provider block in file order.
drop       remove one provider block in place; print "dropped" or "absent".
stable     read versions on stdin, print the newest COUNT stable ones
           (default 3), oldest first.
platforms  print each tracked CI or task file's `providers lock -platform=`
           values, including files git has not yet tracked.
diff       compare two locks provider by provider; BEFORE and AFTER are
           files or `<rev>:<path>` git objects. Print one line per
           difference (source, status, then version/h1-count before and
           after) and exit 1 when a provider outside --allow changed or
           disappeared, or any provider's h1 count dropped. `--allow '*'`
           permits every provider's version to move.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_BLOCK = re.compile(r'^provider "([^"]+)" \{')
_VERSION = re.compile(r'^\s*version\s*=\s*"([^"]+)"')
_H1 = re.compile(r'^\s*"h1:')
_STABLE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_PLATFORM = re.compile(r"-platform[= ]([A-Za-z0-9_]+)")
_MAX_SCAN_BYTES = 1_000_000
_CI_OR_TASK = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(^|/)\.github/(workflows|actions)/.+\.ya?ml$",
        r"(^|/)\.gitlab-ci\.ya?ml$",
        r"(^|/)\.gitlab/.+\.ya?ml$",
        r"(^|/)\.circleci/.+\.ya?ml$",
        r"(^|/)azure-pipelines\.ya?ml$",
        r"(^|/)\.buildkite/.+",
        r"(^|/)Jenkinsfile[^/]*$",
        r"(^|/)bitbucket-pipelines\.yml$",
        r"(^|/)[^/]*(makefile|\.mk|justfile)$",
        r"(^|/)Taskfile\.ya?ml$",
    )
)
_DEFAULT_COUNT = 3
_ARGS_PER_DIFF = 2


def state(text: str) -> list[tuple[str, str, int]]:
    r"""Return (source, version, h1 count) per provider block.

    >>> lock = (
    ...     'provider "r/a/b" {\n  version = "1.0.0"\n  hashes = [\n'
    ...     '    "h1:x=",\n    "h1:y=",\n    "zh:z",\n  ]\n}\n'
    ...     'provider "r/a/c" {\n  version = "2.0.0"\n  hashes = [\n'
    ...     '    "h1:q=",\n  ]\n}\n'
    ... )
    >>> state(lock)
    [('r/a/b', '1.0.0', 2), ('r/a/c', '2.0.0', 1)]
    """
    rows: list[tuple[str, str, int]] = []
    source = ""
    version = ""
    count = 0
    for line in text.splitlines():
        match = _BLOCK.match(line)
        if match:
            source, version, count = match.group(1), "", 0
        elif source and line.startswith("}"):
            rows.append((source, version, count))
            source = ""
        elif source:
            found = _VERSION.match(line)
            if found:
                version = found.group(1)
            elif _H1.match(line):
                count += 1
    return rows


def drop(text: str, source: str) -> tuple[str, bool]:
    r"""Remove the block for `source` and the blank line after it.

    >>> lock = 'provider "a" {\n  version = "1"\n}\n\nprovider "b" {\n}\n'
    >>> drop(lock, "a")
    ('provider "b" {\n}\n', True)
    >>> drop(lock, "b")
    ('provider "a" {\n  version = "1"\n}\n', True)
    >>> drop(lock, "c")[1]
    False
    """
    out: list[str] = []
    skipping = False
    dropped = False
    after = False
    for line in text.splitlines(keepends=True):
        match = _BLOCK.match(line)
        if not skipping and not dropped and match and match.group(1) == source:
            skipping = dropped = True
        elif skipping:
            if line.startswith("}"):
                skipping, after = False, True
        elif after and line.strip() == "":
            after = False
        else:
            after = False
            out.append(line)
    if after and out and out[-1].strip() == "":
        _ = out.pop()
    return "".join(out), dropped


def stable(versions: list[str], count: int) -> list[str]:
    """Return the newest `count` x.y.z versions, oldest first.

    >>> stable(["1.10.0", "1.9.5", "1.11.0-rc1", "1.2.0", "bad"], 2)
    ['1.9.5', '1.10.0']
    """
    keyed = sorted(
        (tuple(int(p) for p in m.groups()), v) for v in versions if (m := _STABLE.match(v.strip()))
    )
    return [v.strip() for _, v in keyed[-count:]]


def platforms(text: str) -> list[str]:
    r"""Return platform names from `providers lock` commands.

    >>> cmd = "terraform providers lock \\\n  -platform=linux_amd64 \\\n  -platform=darwin_arm64\n"
    >>> platforms(cmd)
    ['linux_amd64', 'darwin_arm64']
    >>> platforms("terraform init -platform=nope")
    []
    """
    joined = re.sub(r"\\\r?\n", " ", text)
    found: list[str] = []
    for line in joined.splitlines():
        if re.search(r"providers\s+lock\b", line):
            found.extend(_PLATFORM.findall(line))
    return found


def _fmt(entry: tuple[str, int] | None) -> str:
    return "-" if entry is None else f"{entry[0]}/{entry[1]}"


def diff(
    before: list[tuple[str, str, int]],
    after: list[tuple[str, str, int]],
    allow: frozenset[str],
) -> tuple[list[str], bool]:
    r"""Return report lines and whether any difference is unexpected.

    >>> old = [("a", "1.0.0", 3), ("b", "2.0.0", 1)]
    >>> diff(old, old, frozenset())
    ([], False)
    >>> diff(old, [("a", "1.1.0", 3), ("b", "2.0.0", 1)], frozenset({"a"}))
    (['a\tmoved\t1.0.0/3\t1.1.0/3'], False)
    >>> diff(old, [("a", "1.1.0", 1), ("b", "2.0.0", 1)], frozenset({"a"}))[1]
    True
    >>> diff(old, [("a", "1.0.0", 3), ("b", "2.1.0", 1)], frozenset({"a"}))[1]
    True
    >>> diff(old, [("a", "1.0.0", 3)], frozenset({"*"}))
    (['b\tremoved\t2.0.0/1\t-'], True)
    """
    old = {s: (v, n) for s, v, n in before}
    new = {s: (v, n) for s, v, n in after}
    lines: list[str] = []
    bad = False
    for source in list(old) + [s for s in new if s not in old]:
        was, now = old.get(source), new.get(source)
        if was == now:
            continue
        ok = "*" in allow or source in allow
        if now is None:
            status, fail = "removed", True
        elif was is None:
            status, fail = "added", not ok
        elif now[1] < was[1]:
            status, fail = "count-dropped", True
        elif ok and now[0] != was[0]:
            status, fail = "moved", False
        else:
            status, fail = "changed", not ok
        bad = bad or fail
        lines.append(f"{source}\t{status}\t{_fmt(was)}\t{_fmt(now)}")
    return lines, bad


def _load(arg: str) -> str:
    path = Path(arg)
    if path.is_file():
        return path.read_text()
    if ":" in arg:
        out = subprocess.run(  # noqa: S603
            ["git", "show", arg],  # noqa: S607
            capture_output=True,
            check=True,
        ).stdout
        return out.decode()
    raise FileNotFoundError(arg)


def _diff_command(rest: list[str]) -> int:
    allow: set[str] = set()
    files: list[str] = []
    it = iter(rest)
    for arg in it:
        if arg == "--allow":
            allow.add(next(it, ""))
        else:
            files.append(arg)
    if len(files) != _ARGS_PER_DIFF or "" in allow:
        _ = sys.stderr.write(__doc__ or "")
        return 2
    try:
        before, after = (state(_load(f)) for f in files)
    except (OSError, subprocess.CalledProcessError) as exc:
        _ = sys.stderr.write(f"cannot read lock: {exc}\n")
        return 2
    lines, bad = diff(before, after, frozenset(allow))
    if lines:
        print("\n".join(lines))
    return 1 if bad else 0


def _write_atomic(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w") as handle:
            _ = handle.write(text)
        _ = Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],  # noqa: S607
        capture_output=True,
        check=True,
    ).stdout
    return [p for p in out.decode().split("\0") if p]


def main(argv: list[str]) -> int:
    """Run one subcommand; return the process exit status."""
    args = argv[1:]
    cmd, rest = (args[0], args[1:]) if args else ("", [])
    if cmd == "state" and len(rest) == 1:
        for source, version, count in state(Path(rest[0]).read_text()):
            print(f"{source}\t{version}\t{count}")
        return 0
    if cmd == "drop" and len(rest[1:]) == 1:
        path = Path(rest[0])
        text, dropped = drop(path.read_text(), rest[1])
        if dropped:
            _write_atomic(path, text)
        print("dropped" if dropped else "absent")
        return 0
    if cmd == "stable" and len(rest) <= 1 and (not rest or rest[0].isdigit()):
        count = int(rest[0]) if rest else _DEFAULT_COUNT
        print("\n".join(stable(sys.stdin.read().split(), count)))
        return 0
    if cmd == "platforms" and not rest:
        return _print_platforms()
    if cmd == "diff":
        return _diff_command(rest)
    _ = sys.stderr.write(__doc__ or "")
    return 2


def _print_platforms() -> int:
    for name in _tracked_files():
        if not any(p.search(name) for p in _CI_OR_TASK):
            continue
        path = Path(name)
        if not path.is_file() or path.stat().st_size > _MAX_SCAN_BYTES:
            continue
        try:
            found = platforms(path.read_text())
        except UnicodeDecodeError:
            continue
        if found:
            print(f"{name}\t{','.join(dict.fromkeys(found))}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
