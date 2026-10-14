#!/usr/bin/env python3
"""Find where a repository pins ruff, read what it resolves, and time a cooldown.

``sites DIR`` prints ``path<TAB>line<TAB>text`` for each line in a pin-bearing
file (project metadata, requirements, pre-commit, tool-version managers,
Dockerfiles, CI workflows, ``package.json``, editor and container
configuration) that names ruff with a version, plus the ``rev:`` line under a
ruff pre-commit repository. ``.git``, ``.venv`` and ``node_modules`` are skipped.

``locked DIR [--target V]`` prints ``file<TAB>version`` for each lockfile entry
or ``==`` pin that resolves ruff, with ``<TAB>behind|current|ahead`` against
``--target``. Exits 2 on a version that is not dotted numbers.

``lapse --version V --cooldown 7d [--filename-contains S]... [--json FILE]``
reads the package index JSON (stdin by default) and prints the latest upload
time of the release's files and that time plus the cooldown, in UTC. Exits 2
when the release or a matching file is missing.
"""

# pyright: reportAny=false, reportExplicitAny=false, reportUnusedCallResult=false
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

_SKIP = {".git", ".venv", "node_modules"}
_PIN_NAMES = (
    "pyproject.toml",
    ".pre-commit-config.yaml",
    ".tool-versions",
    "package.json",
    "mise.toml",
    ".mise.toml",
    "flake.nix",
)
_PIN_DIRS = (".github", ".vscode", ".devcontainer", "requirements")
_RUFF_VERSION = re.compile(r"ruff\b.*\d+\.\d+", re.IGNORECASE)
_LOCK_ENTRY = re.compile(r'^name = "ruff"\nversion = "([^"]+)"', re.MULTILINE)
_REQ_PIN = re.compile(r"^\s*ruff\s*==\s*([0-9][^\s;#]*)", re.MULTILINE | re.IGNORECASE)
_LOCKFILES = ("uv.lock", "poetry.lock", "pdm.lock")


def _is_pin_file(rel: Path) -> bool:
    if rel.name in _PIN_NAMES or rel.parts[0] in _PIN_DIRS:
        return True
    return any(
        fnmatch.fnmatch(rel.name, p)
        for p in ("requirements*.txt", "constraints*.txt", "Dockerfile*")
    )


def _walk(root: str) -> list[Path]:
    found: list[Path] = []
    for here, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP)
        found.extend(Path(here, n).relative_to(root) for n in sorted(names))
    return found


def sites(root: str) -> list[tuple[str, int, str]]:
    """Return ``(path, line, text)`` for each line that pins ruff under ``root``."""
    rows: list[tuple[str, int, str]] = []
    for rel in _walk(root):
        if not _is_pin_file(rel):
            continue
        try:
            lines = Path(root, rel).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        in_ruff_repo = False
        for number, line in enumerate(lines, 1):
            if re.match(r"\s*-?\s*repo:", line):
                in_ruff_repo = "ruff" in line.lower()
            elif (in_ruff_repo and re.match(r"\s*rev:", line)) or _RUFF_VERSION.search(line):
                rows.append((rel.as_posix(), number, line.strip()))
    return rows


def _numbers(version: str) -> tuple[int, ...]:
    """Return the dotted numbers of ``version``.

    >>> _numbers("0.16.10")
    (0, 16, 10)
    """
    if not re.fullmatch(r"v?\d+(\.\d+)*", version):
        msg = f"not a dotted numeric version: {version}"
        raise ValueError(msg)
    return tuple(int(part) for part in version.lstrip("v").split("."))


def compare(version: str, target: str) -> str:
    """Return ``behind``, ``current`` or ``ahead`` for ``version`` against ``target``.

    >>> compare("0.9.0", "0.16.10")
    'behind'
    >>> compare("0.16", "0.16.0")
    'current'
    """
    a, b = _numbers(version), _numbers(target)
    width = max(len(a), len(b))
    a, b = a + (0,) * (width - len(a)), b + (0,) * (width - len(b))
    return "behind" if a < b else "ahead" if a > b else "current"


def locked(root: str) -> list[tuple[str, str]]:
    """Return ``(file, version)`` for each lockfile entry or ``==`` pin of ruff."""
    rows: list[tuple[str, str]] = []
    for rel in _walk(root):
        if rel.name in _LOCKFILES:
            pattern = _LOCK_ENTRY
        elif fnmatch.fnmatch(rel.name, "requirements*.txt") or fnmatch.fnmatch(
            rel.name, "constraints*.txt"
        ):
            pattern = _REQ_PIN
        else:
            continue
        text = Path(root, rel).read_text(encoding="utf-8", errors="replace")
        rows.extend((rel.as_posix(), m.group(1)) for m in pattern.finditer(text))
    return rows


def _parse_cooldown(text: str) -> timedelta:
    """Return the duration of ``7d``, ``36h`` or ``90m``.

    >>> _parse_cooldown("7d")
    datetime.timedelta(days=7)
    """
    match = re.fullmatch(r"(\d+)([dhm])", text)
    if not match:
        msg = f"cooldown must look like 7d, 36h or 90m: {text}"
        raise ValueError(msg)
    unit = {"d": "days", "h": "hours", "m": "minutes"}[match.group(2)]
    return timedelta(**{unit: int(match.group(1))})


def _when(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(timezone.utc)


def lapse(
    index: dict[str, Any], version: str, cooldown: timedelta, contains: Sequence[str]
) -> tuple[datetime, datetime]:
    """Return the latest upload time of the matching files and when the cooldown lapses."""
    files = index.get("releases", {}).get(version, [])
    times = [
        _when(f["upload_time_iso_8601"])
        for f in files
        if all(s in f.get("filename", "") for s in contains)
    ]
    if not times:
        msg = f"no file of {version} matches {list(contains)}" if files else f"no release {version}"
        raise LookupError(msg)
    latest = max(times)
    return latest, latest + cooldown


def main(argv: list[str]) -> int:
    """Run one subcommand."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sites").add_argument("dir")
    lock = sub.add_parser("locked")
    lock.add_argument("dir")
    lock.add_argument("--target")
    when = sub.add_parser("lapse")
    when.add_argument("--version", required=True)
    when.add_argument("--cooldown", required=True)
    when.add_argument("--filename-contains", action="append", default=[])
    when.add_argument("--json", help="index JSON file; stdin when omitted")
    args = parser.parse_args(argv)
    try:
        if args.command == "sites":
            for path, number, text in sites(args.dir):
                print(f"{path}\t{number}\t{text}")
        elif args.command == "locked":
            for path, version in locked(args.dir):
                status = f"\t{compare(version, args.target)}" if args.target else ""
                print(f"{path}\t{version}{status}")
        else:
            raw = Path(args.json).read_text(encoding="utf-8") if args.json else sys.stdin.read()
            latest, lapses = lapse(
                json.loads(raw),
                args.version,
                _parse_cooldown(args.cooldown),
                args.filename_contains,
            )
            print(f"latest upload\t{latest.isoformat()}\nlapses\t{lapses.isoformat()}")
    except (ValueError, LookupError) as err:
        sys.stderr.write(f"{err}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
