#!/usr/bin/env python3
"""Back up a branch and drop its pure changelog commits.

Usage:
    rewrite.py partition --base REF --file PATH
    rewrite.py drop --base REF --file PATH SHA [SHA ...]

``partition`` prints JSON listing the branch commits that touch PATH, each
marked ``pure`` (touches only PATH) or ``mixed``. ``drop`` creates a
``changelog-rewrite-backup-<UTC time>`` branch, rebases the named pure commits
out onto the merge-base, and checks that no code changed. Any failure restores
the backup. Both print one JSON object; ``"ok": false`` carries ``reason`` and
exits 1.
"""

# ruff: noqa: EM101, EM102, TRY003, PTH100, PTH110, PTH118
# pyright: reportAny=false, reportUnusedCallResult=false

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import final

BACKUP_PREFIX = "changelog-rewrite-backup-"
ABBREV_MIN = 4


@final
class RewriteError(Exception):
    """A precondition or invariant failed; ``backup`` names the safety branch."""

    def __init__(self, reason: str, backup: str | None = None) -> None:
        super().__init__(reason)
        self.reason: str = reason
        self.backup: str | None = backup


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run git in the current directory and capture text output."""
    done = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if check and done.returncode != 0:
        raise RewriteError(f"git {args[0]} failed: {done.stderr.strip()}")
    return done


def out(*args: str) -> str:
    """Return stripped stdout of a git command that must succeed."""
    return git(*args).stdout.strip()


def todo_lines(todo: str, drop: list[str]) -> str:
    r"""Turn the ``pick`` lines of a rebase todo naming a ``drop`` SHA into ``drop``.

    Examples
    --------
    >>> todo_lines("pick abc1234 one\npick def5678 two\n", ["abc1234ffff"])
    'drop abc1234 one\npick def5678 two\n'
    """
    result: list[str] = []
    for line in todo.splitlines(keepends=True):
        parts = line.split(" ", 2)
        if (
            parts[0] == "pick"
            and len(parts) > 1
            and len(parts[1]) >= ABBREV_MIN
            and any(full.startswith(parts[1]) for full in drop)
        ):
            line = "drop " + line[len("pick ") :]  # noqa: PLW2901
        result.append(line)
    return "".join(result)


def edit_todo(path: str, drop_csv: str) -> None:
    """Rewrite a rebase todo file in place; run by git as the sequence editor."""
    todo = Path(path).read_text(encoding="utf-8")
    Path(path).write_text(todo_lines(todo, drop_csv.split(",")), encoding="utf-8")


def branch_commits(base: str, file: str) -> list[dict[str, object]]:
    """List commits in ``base..HEAD`` touching ``file``, oldest first."""
    shas = out("log", "--reverse", "--format=%H", f"{base}..HEAD", "--", file).split()
    commits: list[dict[str, object]] = []
    for sha in shas:
        files = out("show", "--name-only", "--format=", sha).split("\n")
        commits.append(
            {
                "sha": sha,
                "short": out("rev-parse", "--short", sha),
                "subject": out("show", "--no-patch", "--format=%s", sha),
                "pure": [name for name in files if name] == [file],
            },
        )
    return commits


def preconditions(base: str) -> None:
    """Raise when the tree, HEAD, or history shape makes a rewrite unsafe."""
    if out("status", "--porcelain"):
        raise RewriteError("the working tree has uncommitted changes")
    if git("symbolic-ref", "-q", "HEAD", check=False).returncode != 0:
        raise RewriteError("HEAD is detached")
    gitdir = out("rev-parse", "--git-dir")
    for marker in ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD"):
        if os.path.exists(os.path.join(gitdir, marker)):
            raise RewriteError("a rebase, merge, or cherry-pick is in progress")
    if out("rev-list", "--merges", f"{base}..HEAD"):
        raise RewriteError("a merge commit sits between the base and HEAD")


def restore(backup: str) -> None:
    """Abort any rebase and put the branch back on the backup tip."""
    git("rebase", "--abort", check=False)
    if out("rev-parse", "HEAD") != out("rev-parse", backup):
        git("reset", "--hard", backup, check=False)


def drop(base: str, file: str, shas: list[str]) -> dict[str, object]:
    """Back up, rebase ``shas`` out, and verify the code is unchanged."""
    preconditions(base)
    by_sha = {str(c["sha"]): c for c in branch_commits(base, file)}
    full: list[str] = []
    for sha in shas:
        resolved = out("rev-parse", "--verify", f"{sha}^{{commit}}")
        commit = by_sha.get(resolved)
        if commit is None or not commit["pure"]:
            raise RewriteError(f"{sha} is not a pure changelog commit on this branch")
        full.append(resolved)

    merge_base = out("merge-base", base, "HEAD")
    tip = out("rev-parse", "HEAD")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    backup = f"{BACKUP_PREFIX}{stamp}"
    git("branch", backup)

    me = shlex.quote(os.path.abspath(__file__))
    editor = f"{shlex.quote(sys.executable)} {me} _todo {','.join(full)}"
    env = {**os.environ, "GIT_SEQUENCE_EDITOR": editor}
    done = subprocess.run(  # noqa: S603
        ["git", "rebase", "-i", "--no-autosquash", merge_base],  # noqa: S607
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if done.returncode != 0:
        restore(backup)
        raise RewriteError("the rebase failed and was aborted", backup)

    code_diff = git(
        "diff", "--name-only", backup, "HEAD", "--", ".", f":(exclude){file}", check=False
    )
    if code_diff.returncode != 0 or code_diff.stdout.strip():
        restore(backup)
        raise RewriteError("the rewrite changed code; the backup was restored", backup)
    mixed = any(not c["pure"] for c in by_sha.values())
    if not mixed and git("diff", "--quiet", merge_base, "HEAD", "--", file, check=False).returncode:
        restore(backup)
        raise RewriteError("changelog edits remain after the drop; the backup was restored", backup)

    return {
        "ok": True,
        "backup": backup,
        "backup_tip": tip,
        "merge_base": merge_base,
        "dropped": len(full),
        "mixed_remaining": mixed,
    }


def main(argv: list[str]) -> int:
    """Dispatch a subcommand and print its JSON result."""
    if argv[:1] == ["_todo"]:
        edit_todo(argv[2], argv[1])
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("partition", "drop"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--base", required=True)
        cmd.add_argument("--file", required=True)
    sub.choices["drop"].add_argument("shas", nargs="+")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "partition":
            result: dict[str, object] = {
                "ok": True,
                "commits": branch_commits(args.base, args.file),
            }
        else:
            result = drop(args.base, args.file, args.shas)
    except RewriteError as exc:
        print(json.dumps({"ok": False, "reason": exc.reason, "backup": exc.backup}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
