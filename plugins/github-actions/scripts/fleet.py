#!/usr/bin/env python3
"""Deterministic scope and git-state checks for the GitHub Actions skills.

``discover ROOT [--owner NAME]...`` prints one JSON object per
git repository under ROOT with its remote slug, owner, fork flag, and whether
it is in scope. ``worktree PATH`` prints whether a checkout needs a throwaway
worktree and why. ``branch PATH BASE NAME [--subject S]...`` picks the branch
name to commit on: NAME if free, NAME itself when it holds only approved
subjects and no other worktree has it, otherwise NAME-2, NAME-3. ``pushable
PATH BASE [--made SHA]... [--subject S]...`` exits 0 when every commit in
BASE..HEAD was made this run or has an approved subject, and 1 otherwise.
BASE is ``<remote>/<default>``.
"""

# ruff: noqa: S603, S607, PLR2004, EM101, EM102, TRY003
# pyright: reportUnusedCallResult=false, reportAny=false, reportExplicitAny=false
# pyright: reportPrivateUsage=false, reportImplicitOverride=false
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, final

import pins  # pyright: ignore[reportImplicitRelativeImport]

OWNER = re.compile(r"[A-Za-z0-9_.-]+", re.ASCII)
MAX_BRANCH_SUFFIX = 50
MIN_SHA = 7


@final
class RefusalError(Exception):
    """A usage error reported as one line on stderr."""


def _git(path: str, *args: str, check: bool = True) -> str:
    done = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, check=False)
    if done.returncode and check:
        raise SystemExit((done.stderr.strip().splitlines() or ["git failed"])[0])
    return done.stdout if not done.returncode else ""


def _is_fork(slug: str) -> bool | None:
    done = subprocess.run(
        ["gh", "repo", "view", f"https://github.com/{slug}", "--json", "isFork"],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return bool(json.loads(done.stdout)["isFork"]) if done.returncode == 0 else None
    except ValueError, KeyError, TypeError:
        return None


def _repos_under(root: str) -> list[str]:
    found: list[str] = []
    for here, dirs, _files in os.walk(root):
        if (Path(here) / ".git").exists():
            found.append(here)
            dirs.clear()
        else:
            dirs[:] = sorted(d for d in dirs if d != "node_modules")
    return sorted(found)


def discover(root: str, owners: list[str]) -> list[dict[str, Any]]:
    """Describe each git repository under ``root`` and whether it is in scope."""
    wanted = {o.lower() for o in owners}
    rows: list[dict[str, Any]] = []
    for path in _repos_under(root):
        row: dict[str, Any] = {"path": path, "slug": None, "owner": None, "fork": None}
        try:
            remote = pins._remote(path)  # noqa: SLF001
            row["slug"] = pins._slug_from_remote(path, remote)  # noqa: SLF001
        except SystemExit as err:
            rows.append({**row, "in_scope": False, "reason": str(err.code)})
            continue
        row["owner"] = row["slug"].split("/")[0]
        row["fork"] = _is_fork(row["slug"])
        if wanted and row["owner"].lower() not in wanted:
            row.update(in_scope=False, reason="owner not in --owner")
        elif row["fork"] is None:
            row.update(in_scope=False, reason="fork status could not be checked")
        elif row["fork"]:
            row.update(in_scope=False, reason="repository is a fork")
        else:
            row.update(in_scope=True, reason="")
        rows.append(row)
    return rows


def _default_branch(path: str, remote: str, override: str | None) -> str:
    if override:
        return override
    head = _git(path, "symbolic-ref", "--short", "-q", f"refs/remotes/{remote}/HEAD", check=False)
    if not head.strip():
        raise SystemExit(f"{remote}/HEAD is unset; run git remote set-head {remote} --auto")
    return head.strip().removeprefix(f"{remote}/")


def worktree_need(path: str, override: str | None = None) -> dict[str, Any]:
    """Report whether commits from this checkout need a throwaway worktree."""
    remote = pins._remote(path)  # noqa: SLF001
    default = _default_branch(path, remote, override)
    reasons: list[str] = []
    current = _git(path, "symbolic-ref", "--short", "-q", "HEAD", check=False).strip()
    if not current:
        reasons.append("detached HEAD")
    elif current != default:
        reasons.append(f"checked out on {current}, not {default}")
    if _git(path, "status", "--porcelain", "--untracked-files=all").strip():
        reasons.append("uncommitted or untracked files")
    relation = "absent"
    if _git(path, "rev-parse", "--verify", "-q", f"refs/heads/{default}", check=False).strip():
        counts = _git(
            path, "rev-list", "--left-right", "--count", f"{default}...{remote}/{default}"
        )
        ahead, behind = (int(n) for n in counts.split())
        relation = (
            "same" if not ahead and not behind
            else "ahead" if not behind
            else "behind" if not ahead
            else "diverged"
        )  # fmt: skip
        if relation != "same":
            reasons.append(f"local {default} is {relation} of {remote}/{default}")
    return {
        "need": bool(reasons),
        "reasons": reasons,
        "remote": remote,
        "default": default,
        "relation": relation,
    }


def _checked_out(path: str) -> set[str]:
    listing = _git(path, "worktree", "list", "--porcelain")
    return {
        line.split(" ", 1)[1].removeprefix("refs/heads/")
        for line in listing.splitlines()
        if line.startswith("branch ")
    }


def _only_subjects(path: str, base: str, branch: str, subjects: set[str]) -> bool:
    log = _git(path, "log", "--format=%s", f"{base}..refs/heads/{branch}")
    return all(line in subjects for line in log.splitlines())


def pick_branch(path: str, base: str, name: str, subjects: set[str]) -> dict[str, Any]:
    """Return the branch to commit on and whether it already exists."""
    if subprocess.run(
        ["git", "check-ref-format", "--branch", name], capture_output=True, check=False
    ).returncode:
        raise RefusalError(f"{name!r} is not a valid branch name")
    busy = _checked_out(path)
    for n in range(1, MAX_BRANCH_SUFFIX + 1):
        candidate = name if n == 1 else f"{name}-{n}"
        exists = _git(path, "rev-parse", "--verify", "-q", f"refs/heads/{candidate}", check=False)
        if not exists.strip():
            return {"branch": candidate, "reuse": False}
        if candidate not in busy and _only_subjects(path, base, candidate, subjects):
            return {"branch": candidate, "reuse": True}
    raise SystemExit(f"{name}: no free branch name up to suffix {MAX_BRANCH_SUFFIX}")


def pushable(path: str, base: str, made: list[str], subjects: set[str]) -> dict[str, Any]:
    """List the commits a push would publish and the ones not made in this run."""
    log = _git(path, "log", "--format=%H%x09%s", f"{base}..HEAD")
    commits = [line.split("\t", 1) for line in log.splitlines()]
    foreign = [
        sha[:MIN_SHA]
        for sha, subject in commits
        if subject not in subjects and not any(sha.startswith(m) for m in made)
    ]
    return {"commits": [c[0] for c in commits], "foreign": foreign}


def _flags(argv: list[str], names: tuple[str, ...]) -> tuple[list[str], dict[str, list[str]]]:
    """Split ``argv`` into positionals and repeated ``--name value`` options."""
    positional: list[str] = []
    options: dict[str, list[str]] = {n: [] for n in names}
    i = 0
    while i < len(argv):
        word = argv[i]
        if word.startswith("--"):
            if word[2:] not in options or i + 1 >= len(argv):
                raise RefusalError(f"unknown or incomplete option {word}")
            options[word[2:]].append(argv[i + 1])
            i += 2
        else:
            positional.append(word)
            i += 1
    return positional, options


def _run(argv: list[str]) -> int:
    cmd, rest = (argv[0], argv[1:]) if argv else ("", [])
    if cmd == "discover":
        pos, opts = _flags(rest, ("owner",))
        if len(pos) != 1 or not Path(pos[0]).is_dir():
            raise RefusalError("discover takes one existing directory")
        if any(not OWNER.fullmatch(o) for o in opts["owner"]):
            raise RefusalError("--owner takes account names")
        for row in discover(pos[0], opts["owner"]):
            print(json.dumps(row))
        return 0
    if cmd == "worktree":
        pos, opts = _flags(rest, ("default",))
        if len(pos) != 1:
            raise RefusalError("worktree takes one checkout path")
        print(json.dumps(worktree_need(pos[0], (opts["default"] or [None])[0])))
        return 0
    if cmd == "branch":
        pos, opts = _flags(rest, ("subject",))
        if len(pos) != 3:
            raise RefusalError("branch takes PATH BASE NAME")
        print(json.dumps(pick_branch(pos[0], pos[1], pos[2], set(opts["subject"]))))
        return 0
    if cmd == "pushable":
        pos, opts = _flags(rest, ("made", "subject"))
        if len(pos) != 2:
            raise RefusalError("pushable takes PATH BASE")
        if any(len(m) < MIN_SHA for m in opts["made"]):
            raise RefusalError(f"--made takes SHAs of at least {MIN_SHA} characters")
        got = pushable(pos[0], pos[1], opts["made"], set(opts["subject"]))
        print(json.dumps(got))
        if not got["commits"]:
            sys.stderr.write("nothing to push\n")
            return 1
        if got["foreign"]:
            sys.stderr.write(f"not made in this run: {' '.join(got['foreign'])}\n")
            return 1
        return 0
    raise RefusalError("unknown command" if cmd else "no command")


def main(argv: list[str]) -> int:
    """Run the CLI."""
    try:
        return _run(argv)
    except RefusalError as err:
        sys.stderr.write(f"{err}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
