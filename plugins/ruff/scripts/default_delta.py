#!/usr/bin/env python3
"""Measure what a ruff bump and a defaults adoption add to a repository.

Every mode runs ``<ruff command> check`` with fixes and output redirection
disabled; the ruff command follows ``--`` and must end in ``ruff``.

Default mode prints ``code<TAB>configured<TAB>proposed<TAB>delta`` per rule and
a ``total`` line. *Proposed* is the recommended configuration measured in a
scratch copy of the repository: every ``select`` becomes ``extend-select``
(merged into an existing ``extend-select``), so the vendor defaults apply and
the repository's own ``ignore`` and ``per-file-ignores`` stay in force.
Exits 2 when a configuration cannot be rewritten that way.

``--snapshot FILE`` records the findings of the ruff command, with locations.
``--new-since FILE`` prints ``code<TAB>new<TAB>now<TAB>was`` for each code with
a finding at a location the snapshot did not hold: ``new`` counts those
findings, ``now`` all current findings of the code, ``was`` the snapshot's.
"""

# ruff: noqa: S603, S607
# pyright: reportAny=false, reportExplicitAny=false, reportUnusedCallResult=false
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

_CONFIG_NAMES = ("pyproject.toml", "ruff.toml", ".ruff.toml")
_KEY = re.compile(r"[ \t]*([A-Za-z0-9_.\-\"']+)[ \t]*=[ \t]*")
_HEADER = re.compile(r"[ \t]*\[\[?([^\]\n]+)\]\]?[ \t]*(#.*)?$")
_INLINE_SELECT = re.compile(r"\{[^}\n]*(?<![-\w])select\s*=")
_STATS = ("check", "--no-cache", "--statistics", "--output-format", "json")
_FINDINGS = ("check", "--no-cache", "--output-format", "json")


class UnsupportedError(Exception):
    """A configuration this script cannot rewrite or a ruff result it cannot read."""


def counts(statistics_json: str) -> dict[str, int]:
    """Map rule code to finding count from ``--statistics --output-format json``.

    >>> counts('[{"code": "F401", "count": 3}]')
    {'F401': 3}
    """
    text = statistics_json.strip()
    return {row["code"]: row["count"] for row in json.loads(text)} if text else {}


def findings(diagnostics_json: str, cwd: str) -> list[list[object]]:
    """Return ``[file, code, row, column]`` per diagnostic, files relative to ``cwd``.

    >>> d = '[{"code": "F401", "filename": "/r/a.py", "location": {"row": 1, "column": 8}}]'
    >>> findings(d, "/r")
    [['a.py', 'F401', 1, 8]]
    """
    text = diagnostics_json.strip()
    rows: list[dict[str, Any]] = json.loads(text) if text else []
    return [
        [
            os.path.relpath(row["filename"], cwd),
            row["code"] or "syntax-error",
            row["location"]["row"],
            row["location"]["column"],
        ]
        for row in rows
    ]


def new_findings(
    before: Sequence[Sequence[object]], after: Sequence[Sequence[object]]
) -> list[tuple[str, int, int, int]]:
    """Return ``(code, new, now, was)`` for codes with a finding absent from ``before``.

    Equal counts with moved findings still report the move.

    >>> old = [["a.py", "F401", 1, 8]]
    >>> new_findings(old, [["b.py", "F401", 2, 8]])
    [('F401', 1, 1, 1)]
    >>> new_findings(old, old)
    []
    """
    seen = {tuple(row) for row in before}
    codes = sorted({str(row[1]) for row in after})
    rows: list[tuple[str, int, int, int]] = []
    for code in codes:
        now = [tuple(row) for row in after if row[1] == code]
        fresh = sum(1 for row in now if row not in seen)
        was = sum(1 for row in before if row[1] == code)
        if fresh:
            rows.append((code, fresh, len(now), was))
    return rows


def _skip_value(text: str, i: int) -> int:
    """Return the index just past the TOML value that starts at ``text[i]``."""
    depth = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "#":
            end = text.find("\n", i)
            i = n if end < 0 else end
        elif text.startswith(('"""', "'''"), i):
            end = text.find(text[i : i + 3], i + 3)
            i = n if end < 0 else end + 3
        elif c in "\"'":
            i += 1
            while i < n and text[i] not in (c, "\n"):
                i += 2 if c == '"' and text[i] == "\\" else 1
            i += 1
        else:
            if c in "[{":
                depth += 1
            elif c in "]}":
                depth -= 1
                if depth == 0:
                    return i + 1
            elif c == "\n" and depth == 0:
                return i
            i += 1
    return n


def _last_significant(text: str) -> str:
    """Return the last character of ``text`` that is neither space nor comment."""
    last = ""
    i = 0
    while i < len(text):
        if text[i] == "#":
            end = text.find("\n", i)
            i = len(text) if end < 0 else end
        elif text[i] in "\"'":
            last = text[i]
            close = text.find(text[i], i + 1)
            i = len(text) if close < 0 else close + 1
        else:
            last = text[i] if not text[i].isspace() else last
            i += 1
    return last


def _entries(text: str) -> list[tuple[str, int, int, int, int]]:
    """Return ``(dotted key, line start, key end, value start, value end)`` per key."""
    out: list[tuple[str, int, int, int, int]] = []
    section = ""
    i = 0
    n = len(text)
    while i < n:
        end = text.find("\n", i)
        end = n if end < 0 else end
        line = text[i:end]
        header = _HEADER.match(line)
        key = _KEY.match(line)
        if header:
            section = header.group(1).strip().replace(" ", "").replace('"', "")
        elif key:
            name = key.group(1).replace('"', "").replace("'", "")
            start = i + key.end()
            stop = _skip_value(text, start)
            out.append((f"{section}.{name}" if section else name, i, i + key.end(1), start, stop))
            end = text.find("\n", stop) if stop < n else n
            end = n if end < 0 else end
        i = end + 1
    return out


def adopt_defaults(text: str, *, pyproject: bool) -> str:
    r"""Return ``text`` with each ruff ``select`` turned into ``extend-select``.

    >>> adopt_defaults('[tool.ruff.lint]\nselect = ["E"]\nignore = ["F"]\n', pyproject=True)
    '[tool.ruff.lint]\nextend-select = ["E"]\nignore = ["F"]\n'
    >>> adopt_defaults('[lint]\nselect = ["E"]\nextend-select = ["I"]\n', pyproject=False)
    '[lint]\n\nextend-select = [\n"E",\n"I"]\n'
    """
    if _INLINE_SELECT.search(text):
        msg = "select is set in an inline table"
        raise UnsupportedError(msg)
    owners = ("tool.ruff.", "tool.ruff.lint.") if pyproject else ("", "lint.")
    entries = {e[0]: e for e in _entries(text)}
    edits: list[tuple[int, int, str]] = []
    for owner in owners:
        chosen = entries.get(f"{owner}select")
        if chosen is None:
            continue
        _, line, key_end, value, stop = chosen
        body = text[value:stop].strip()
        if not body.startswith("["):
            msg = "select is not a list"
            raise UnsupportedError(msg)
        extended = entries.get(f"{owner}extend-select")
        if extended is None:
            if text[key_end - len("select") : key_end] != "select":
                msg = "select key is quoted"
                raise UnsupportedError(msg)
            edits.append((key_end - len("select"), key_end, "extend-select"))
            continue
        target = text[extended[3] : extended[4]]
        if not target.lstrip().startswith("["):
            msg = "extend-select is not a list"
            raise UnsupportedError(msg)
        eol = text.find("\n", stop)
        edits.append((line, len(text) if eol < 0 else eol, ""))
        inner = body[1:-1].strip()
        if inner:
            at = extended[3] + target.index("[") + 1
            comma = "" if _last_significant(inner) in ("", ",") else ","
            edits.append((at, at, f"\n{inner}{comma}\n"))
    for start, stop, new in sorted(edits, reverse=True):
        text = text[:start] + new + text[stop:]
    return text


def _extends(text: str, *, pyproject: bool) -> list[str]:
    """Return the ruff configuration files the text extends."""
    names = ("tool.ruff.extend",) if pyproject else ("extend",)
    found: list[str] = []
    for name, _, _, start, stop in _entries(text):
        value = text[start:stop].strip()
        if name in names and len(value) > 1 and value[0] in "\"'":
            found.append(value[1:-1])
    return found


def propose(root: Path) -> list[str]:
    """Rewrite every ruff configuration under ``root``; return the files changed."""
    pending = [p for p in root.rglob("*") if p.name in _CONFIG_NAMES and p.is_file()]
    changed: list[str] = []
    done: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in done:
            continue
        done.add(path)
        pyproject = path.name == "pyproject.toml"
        text = path.read_text()
        for base in _extends(text, pyproject=pyproject):
            target = (path.parent / base).resolve()
            if root.resolve() not in (target, *target.parents):
                msg = f"{path.relative_to(root)} extends a configuration outside the repository"
                raise UnsupportedError(msg)
            pending.append(target)
        new = adopt_defaults(text, pyproject=pyproject)
        if new != text:
            path.write_text(new)
            changed.append(str(path.relative_to(root)))
    return sorted(changed)


def _copy(cwd: str, scratch: str) -> None:
    """Copy the files git tracks or could track in ``cwd`` into ``scratch``."""
    listing = subprocess.run(
        ["git", "-C", cwd, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        check=False,
    )
    if listing.returncode:
        msg = "cwd is not a git repository"
        raise UnsupportedError(msg)
    for raw in listing.stdout.split(b"\0"):
        if not raw:
            continue
        source = Path(cwd, os.fsdecode(raw))
        if Path(scratch).resolve() in source.resolve().parents:
            continue
        if source.is_symlink() or source.is_file():
            target = Path(scratch, os.fsdecode(raw))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target, follow_symlinks=False)


def _ruff(cmd: list[str], *args: str, cwd: str, guard: bool = True) -> str:
    environment = os.environ.copy()
    environment.pop("RUFF_OUTPUT_FILE", None)
    done = subprocess.run(
        [*cmd, *args, *(("--no-fix", "--no-fix-only") if guard else ())],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode not in (0, 1):
        sys.stderr.write(done.stderr)
        raise SystemExit(2)
    return done.stdout


def measure(cmd: list[str], cwd: str) -> list[tuple[str, int, int]]:
    """Return ``(code, configured, proposed)`` sorted by code."""
    configured = counts(_ruff(cmd, *_STATS, cwd=cwd))
    with tempfile.TemporaryDirectory() as scratch:
        _copy(cwd, scratch)
        changed = propose(Path(scratch))
        sys.stderr.write(
            f"proposed: select to extend-select in {', '.join(changed) or 'nothing'}\n"
        )
        proposed = counts(_ruff(cmd, *_STATS, cwd=scratch))
    codes = sorted(set(configured) | set(proposed))
    return [(c, configured.get(c, 0), proposed.get(c, 0)) for c in codes]


def snapshot(cmd: list[str], cwd: str, path: str) -> None:
    """Write the ruff command's version and findings to ``path``."""
    version = _ruff(cmd, "--version", cwd=cwd, guard=False).strip()
    rows = findings(_ruff(cmd, *_FINDINGS, cwd=cwd), cwd)
    Path(path).write_text(json.dumps({"version": version, "findings": rows}))


def new_since(cmd: list[str], cwd: str, path: str) -> list[tuple[str, int, int, int]]:
    """Return ``(code, new, now, was)`` against the snapshot at ``path``."""
    saved = json.loads(Path(path).read_text())
    version = _ruff(cmd, "--version", cwd=cwd, guard=False).strip()
    sys.stderr.write(f"baseline {saved['version']}; current {version}\n")
    return new_findings(saved["findings"], findings(_ruff(cmd, *_FINDINGS, cwd=cwd), cwd))


def render(rows: list[tuple[str, int, int]]) -> str:
    """Format rows as tab-separated lines ending in a total.

    >>> render([("F401", 1, 4)]).split()
    ['F401', '1', '4', '3', 'total', '1', '4', '3']
    """
    lines = [f"{c}\t{a}\t{b}\t{b - a}" for c, a, b in rows]
    a_sum = sum(a for _, a, _ in rows)
    b_sum = sum(b for _, _, b in rows)
    lines.append(f"total\t{a_sum}\t{b_sum}\t{b_sum - a_sum}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    """Parse arguments, measure, and print the table."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="repository to measure")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--snapshot", metavar="FILE", help="write current findings to FILE")
    modes.add_argument("--new-since", metavar="FILE", help="list findings absent from a snapshot")
    parser.add_argument("ruff", nargs=argparse.REMAINDER, help="-- <ruff command>")
    args = parser.parse_args(argv)
    cmd = args.ruff[1:] if args.ruff[:1] == ["--"] else args.ruff
    if not cmd:
        parser.error("give the ruff command after --")
    try:
        if args.snapshot:
            snapshot(cmd, args.cwd, args.snapshot)
        elif args.new_since:
            rows = new_since(cmd, args.cwd, args.new_since)
            print("\n".join(f"{c}\t{new}\t{now}\t{was}" for c, new, now, was in rows))
        else:
            print(render(measure(cmd, args.cwd)))
    except UnsupportedError as err:
        sys.stderr.write(f"{err}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
