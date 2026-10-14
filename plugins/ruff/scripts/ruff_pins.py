#!/usr/bin/env python3
"""Find where a repository pins ruff, read what it resolves, and time a cooldown.

``sites DIR`` prints ``path<TAB>line<TAB>text`` for each line in a pin-bearing
file (project metadata, requirements, pre-commit, tool-version managers,
Dockerfiles, CI workflows, ``package.json``, editor and container
configuration) that names ruff with a version, plus the ``rev:`` line under a
ruff pre-commit repository. ``.git``, ``.venv`` and ``node_modules`` are skipped.

``locked DIR [--target V]`` prints ``file<TAB>version`` for each lockfile entry
or ``==`` pin that resolves ruff, with ``<TAB>behind|current|ahead`` against
``--target``. A version that is not dotted numbers prints with an ``error``
status, the other rows still print, and the exit status is 2.

``arguments TEXT...`` splits the skill's argument string, given as one word or
as separate tokens, and prints it as JSON:
``version``, ``root``, ``repo``, ``owner``, ``branch`` and the boolean flags.

``scope [--root DIR] [--repo P...] [--owner N...] [--branch B] [--cwd DIR]``
prints ``path<TAB>slug<TAB>owner<TAB>ruff<TAB>pins<TAB>branch<TAB>worktree`` per git
repository: the walked ``--root`` repositories, the ``--repo`` paths or slugs,
else ``--cwd``. ``owner`` is ``yes``/``no`` against ``--owner`` (``-`` without
it), ``ruff`` lists the ruff configuration files at any depth (comma-separated
paths) or ``none``, ``pins`` counts pin lines, ``branch`` and ``worktree`` are
``exists`` or ``none`` (a worktree on the branch or in a directory of that name). A ``--repo`` that
matches nothing prints ``unresolved`` in the slug column and exits 2.

``lapse --version V --cooldown 7d [--filename-contains S]... [--json FILE]``
reads the package index JSON (stdin by default) and prints the latest upload
time of the release's files and that time plus the cooldown, in UTC. Exits 2
when the release or a matching file is missing.
"""

# ruff: noqa: S603, S607
# pyright: reportAny=false, reportExplicitAny=false, reportUnusedCallResult=false
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shlex
import subprocess
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


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    return done.stdout.strip() if done.returncode == 0 else ""


def parse_slug(url: str) -> str:
    """Return ``owner/name`` from a git remote URL, or ``""``.

    >>> parse_slug("git@github.com:tony/skills.git")
    'tony/skills'
    >>> parse_slug("https://github.com/tony/skills")
    'tony/skills'
    """
    match = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$", url)
    return f"{match.group(1)}/{match.group(2)}" if match else ""


def _repos_under(root: Path) -> list[Path]:
    found: list[Path] = []
    for here, dirs, _ in os.walk(root):
        if (Path(here) / ".git").exists():
            found.append(Path(here))
            dirs[:] = []
        else:
            dirs[:] = sorted(d for d in dirs if d not in _SKIP)
    return found


def _configs(repo: Path) -> list[str]:
    """Return the tracked or trackable ruff configuration files, relative to ``repo``."""
    listing = _git(repo, "ls-files", "--cached", "--others", "--exclude-standard")
    found: list[str] = []
    for name in listing.splitlines():
        path = Path(name)
        if path.name in ("ruff.toml", ".ruff.toml"):
            found.append(name)
        elif path.name == "pyproject.toml" and (repo / path).is_file():
            text = (repo / path).read_text(encoding="utf-8", errors="replace")
            if "[tool.ruff" in text:
                found.append(name)
    return sorted(found)


def _worktree_for(repo: Path, branch: str) -> bool:
    """Return whether a worktree has ``branch`` checked out or sits in a directory of that name."""
    if not branch:
        return False
    for block in _git(repo, "worktree", "list", "--porcelain").split("\n\n"):
        lines = block.splitlines()
        if f"branch refs/heads/{branch}" in lines:
            return True
        if lines and lines[0].startswith("worktree ") and Path(lines[0][9:]).name == branch:
            return True
    return False


def scope(
    roots: Sequence[str],
    repos: Sequence[str],
    owners: Sequence[str],
    branch: str,
    cwd: str,
) -> tuple[list[tuple[str, ...]], bool]:
    """Return the scope rows and whether any ``--repo`` went unresolved."""
    found = [r for root in roots for r in _repos_under(Path(root))]
    chosen: list[Path] = list(found)
    unresolved = False
    rows: list[tuple[str, ...]] = []
    for name in repos:
        path = Path(name)
        match = [r for r in found if parse_slug(_git(r, "remote", "get-url", "origin")) == name]
        if (path / ".git").exists():
            chosen.append(path)
        elif match:
            chosen.extend(match)
        else:
            rows.append((name, "unresolved", "-", "-", "-", "-", "-"))
            unresolved = True
    if not roots and not repos:
        chosen.append(Path(cwd))
    for repo in dict.fromkeys(r.resolve() for r in chosen):
        remote = _git(repo, "remote", "get-url", "origin") or _git(
            repo, "remote", "get-url", _git(repo, "remote").split("\n")[0] or "origin"
        )
        slug = parse_slug(remote)
        wanted = {o.lower() for o in owners}
        owned = "-" if not owners else "yes" if slug.split("/")[0].lower() in wanted else "no"
        exists = bool(branch) and bool(_git(repo, "rev-parse", "--verify", f"refs/heads/{branch}"))
        configs = _configs(repo)
        rows.append(
            (
                str(repo),
                slug or "-",
                owned,
                ",".join(configs) or "none",
                str(len(sites(str(repo)))),
                "exists" if exists else "none",
                "exists" if _worktree_for(repo, branch) else "none",
            )
        )
    return rows, unresolved


_FLAGS = ("adopt_defaults", "audit_only", "push", "pr", "no_changelog")


def parse_arguments(words: Sequence[str]) -> dict[str, Any]:
    """Return the skill's arguments as a dict; argparse exits 2 on an unknown flag.

    >>> parse_arguments(["0.13.1", "--repo", "a", "b", "--push"])["repo"]
    ['a', 'b']
    """
    parser = argparse.ArgumentParser(prog="arguments")
    parser.add_argument("version", nargs="?")
    parser.add_argument("--root")
    parser.add_argument("--repo", nargs="+", default=[])
    parser.add_argument("--owner", nargs="+", default=[])
    parser.add_argument("--branch")
    for flag in _FLAGS:
        parser.add_argument("--" + flag.replace("_", "-"), action="store_true")
    return vars(parser.parse_intermixed_args(list(words)))


def main(argv: list[str]) -> int:
    """Run one subcommand."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sites").add_argument("dir")
    lock = sub.add_parser("locked")
    lock.add_argument("dir")
    lock.add_argument("--target")
    sub.add_parser("arguments").add_argument("text", nargs="*")
    where = sub.add_parser("scope")
    where.add_argument("--root", action="append", default=[])
    where.add_argument("--repo", nargs="+", default=[])
    where.add_argument("--owner", nargs="+", default=[])
    where.add_argument("--branch", default="")
    where.add_argument("--cwd", default=".")
    when = sub.add_parser("lapse")
    when.add_argument("--version", required=True)
    when.add_argument("--cooldown", required=True)
    when.add_argument("--filename-contains", action="append", default=[])
    when.add_argument("--json", help="index JSON file; stdin when omitted")
    if argv[:1] == ["arguments"]:
        rest = argv[1:]
        words = shlex.split(rest[0]) if len(rest) == 1 else rest
        print(json.dumps(parse_arguments(words)))
        return 0
    args = parser.parse_args(argv)
    failed = False
    try:
        if args.command == "sites":
            for path, number, text in sites(args.dir):
                print(f"{path}\t{number}\t{text}")
        elif args.command == "scope":
            rows, failed = scope(args.root, args.repo, args.owner, args.branch, args.cwd)
            for row in rows:
                print("\t".join(row))
        elif args.command == "locked":
            for path, version in locked(args.dir):
                try:
                    status = f"\t{compare(version, args.target)}" if args.target else ""
                except ValueError as err:
                    status = "\terror"
                    sys.stderr.write(f"{path}: {err}\n")
                    failed = True
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
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
