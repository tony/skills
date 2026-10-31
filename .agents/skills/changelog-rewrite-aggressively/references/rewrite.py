#!/usr/bin/env python3
"""Back up a branch and drop its pure changelog commits.

Usage:
    rewrite.py partition --base REF --file PATH
    rewrite.py drop --base REF --file PATH SHA [SHA ...]

``partition`` prints JSON listing the branch commits that touch PATH, each
marked ``pure`` (touches only PATH) or ``mixed``. ``drop`` creates a
``changelog-rewrite-backup-<UTC time>`` branch, rebases the named pure commits
out onto the merge-base, and checks that no code changed. Failed checks use a
non-destructive restore; conflicts and overlapping edits stay available for
recovery. Both print one JSON object; ``"ok": false`` carries ``reason`` and
exits 1. File paths are relative to the repository root.
"""

# ruff: noqa: EM101, EM102, TRY003, PTH100
# pyright: reportAny=false, reportUnusedCallResult=false

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import final

BACKUP_PREFIX = "changelog-rewrite-backup-"
ABBREV_MIN = 4


@final
class RewriteError(Exception):
    """A precondition or invariant failed; ``backup`` names the safety branch."""

    def __init__(self, reason: str, backup: str | None = None, recovery: str | None = None) -> None:
        super().__init__(reason)
        self.reason: str = reason
        self.backup: str | None = backup
        self.recovery: str | None = recovery


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run git in the current directory and capture text output."""
    done = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        text=True,
        errors="surrogateescape",
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
    todo = Path(path).read_text(encoding="utf-8", errors="surrogateescape")
    Path(path).write_text(
        todo_lines(todo, drop_csv.split(",")), encoding="utf-8", errors="surrogateescape"
    )


def branch_commits(base: str, file: str) -> list[dict[str, object]]:
    """List commits in ``base..HEAD`` touching ``file``, oldest first."""
    shas = out(
        "log", "--reverse", "--format=%H", f"{base}..HEAD", "--", f":(top,literal){file}"
    ).split()
    commits: list[dict[str, object]] = []
    for sha in shas:
        files = git("diff-tree", "--no-commit-id", "--no-renames", "--name-only", "-r", "-z", sha)
        commits.append(
            {
                "sha": sha,
                "short": out("rev-parse", "--short", sha),
                "subject": out("show", "--no-patch", "--format=%s", sha),
                "pure": files.stdout.split("\0")[:-1] == [file],
            },
        )
    return commits


def _in_progress() -> bool:
    """Whether git owns an unfinished history operation in this worktree."""
    return any(
        Path(out("rev-parse", "--git-path", marker)).exists()
        for marker in (
            "rebase-merge",
            "rebase-apply",
            "MERGE_HEAD",
            "CHERRY_PICK_HEAD",
            "REVERT_HEAD",
        )
    )


def preconditions(base: str) -> str:
    """Raise when the tree, HEAD, or history shape makes a rewrite unsafe."""
    root = Path.cwd().resolve()
    home = Path.home().resolve()
    if root == home or root in home.parents:
        raise RewriteError("the repository root is the home directory or an ancestor")
    if out("status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none"):
        raise RewriteError("the working tree has uncommitted changes")
    if git("symbolic-ref", "-q", "HEAD", check=False).returncode != 0:
        raise RewriteError("HEAD is detached")
    branch = out("symbolic-ref", "HEAD")
    base_ref = out("rev-parse", "--symbolic-full-name", base)
    base_branch = base_ref.removeprefix("refs/heads/")
    if base_ref.startswith("refs/remotes/"):
        base_branch = base_ref.split("/", 3)[-1]
    if branch == f"refs/heads/{base_branch}":
        raise RewriteError("the current branch is the base branch")
    if _in_progress():
        raise RewriteError("a rebase, merge, cherry-pick, or revert is in progress")
    if out("rev-list", "--merges", f"{base}..HEAD"):
        raise RewriteError("a merge commit sits between the base and HEAD")
    ignored = set(
        git("ls-files", "--others", "--ignored", "--exclude-standard", "-z").stdout.split("\0")
    )
    ignored.discard("")
    if ignored:
        touched = set(
            git(
                "log", "--format=", "--name-only", "-z", "--no-renames", f"{base}..HEAD"
            ).stdout.split("\0")
        )
        parents = {str(parent) for name in touched for parent in PurePosixPath(name).parents}
        if ignored.intersection(touched | parents) or any(
            str(parent) in touched for name in ignored for parent in PurePosixPath(name).parents
        ):
            raise RewriteError(
                "ignored files overlap paths replayed by the rewrite; move them aside first"
            )
    return branch


def _fail(reason: str, backup: str, branch: str) -> None:
    """Restore only when git can preserve edits; keep new commits reachable."""
    if _in_progress():
        raise RewriteError(
            f"{reason}; the operation is still in progress, with its files intact", backup
        )
    if out("rev-parse", "HEAD") == out("rev-parse", backup):
        raise RewriteError(f"{reason}; the branch remains at the backup", backup)
    recovery = backup.replace(BACKUP_PREFIX, "changelog-rewrite-result-", 1)
    if git("branch", recovery, check=False).returncode != 0:
        raise RewriteError(
            f"{reason}; a recovery ref could not be created, so no restore ran", backup
        )
    if out("status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none"):
        raise RewriteError(
            f"{reason}; new edits and their staging were left intact, so no restore ran",
            backup,
            recovery,
        )
    if git("symbolic-ref", "-q", "HEAD", check=False).stdout.strip() != branch:
        raise RewriteError(
            f"{reason}; the checked-out branch changed, so no restore ran", backup, recovery
        )
    restored = git("reset", "--keep", backup, check=False)
    if restored.returncode != 0 or out("rev-parse", "HEAD") != out("rev-parse", backup):
        raise RewriteError(
            f"{reason}; overlapping edits prevented restoration and remain intact", backup, recovery
        )
    raise RewriteError(
        f"{reason}; the backup was restored and new edits were kept", backup, recovery
    )


def drop(base: str, file: str, shas: list[str]) -> dict[str, object]:
    """Back up, rebase ``shas`` out, and verify the code is unchanged."""
    branch = preconditions(base)
    by_sha = {str(c["sha"]): c for c in branch_commits(base, file)}
    full: list[str] = []
    for sha in shas:
        resolved = out("rev-parse", "--verify", f"{sha}^{{commit}}")
        commit = by_sha.get(resolved)
        if commit is None or not commit["pure"]:
            raise RewriteError(f"{sha} is not a pure changelog commit on this branch")
        full.append(resolved)
    full = list(dict.fromkeys(full))

    merge_base = out("merge-base", base, "HEAD")
    tip = out("rev-parse", "HEAD")
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S%fZ")
    backup = f"{BACKUP_PREFIX}{stamp}"
    git("update-ref", f"refs/heads/{backup}", tip, "")

    me = shlex.quote(os.path.abspath(__file__))
    editor = f"{shlex.quote(sys.executable)} {me} _todo {','.join(full)}"
    env = {**os.environ, "GIT_SEQUENCE_EDITOR": editor}
    done = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "git",
            "-c",
            "rebase.abbreviateCommands=false",
            "-c",
            "rebase.updateRefs=false",
            "-c",
            "rebase.autoStash=false",
            "-c",
            "rebase.instructionFormat=%s",
            "rebase",
            "-i",
            "--no-autosquash",
            merge_base,
        ],
        capture_output=True,
        text=True,
        errors="surrogateescape",
        env=env,
        check=False,
    )
    if done.returncode != 0:
        _fail("the rebase failed", backup, branch)

    code_diff = git(
        "diff",
        "--name-only",
        backup,
        "HEAD",
        "--",
        ":/",
        f":(top,literal,exclude){file}",
        check=False,
    )
    if code_diff.returncode != 0 or code_diff.stdout.strip():
        _fail("the rewrite changed code", backup, branch)
    remaining = out("rev-list", f"{merge_base}..HEAD").split()
    expected = len(out("rev-list", f"{merge_base}..{backup}").split()) - len(set(full))
    if len(remaining) != expected or set(full).intersection(remaining):
        _fail("the rewrite did not remove exactly the requested commits", backup, branch)
    mixed = any(not c["pure"] for c in by_sha.values())
    if (
        not mixed
        and git(
            "diff", "--quiet", merge_base, "HEAD", "--", f":(top,literal){file}", check=False
        ).returncode
    ):
        _fail("changelog edits remain after the drop", backup, branch)
    if out("status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none"):
        _fail("new uncommitted edits appeared during the rewrite", backup, branch)

    return {
        "ok": True,
        "backup": backup,
        "backup_tip": tip,
        "merge_base": merge_base,
        "dropped": len(full),
        "mixed_remaining": mixed,
    }


def _root_file(file: str) -> str:
    """Resolve commands at the repository root and reject paths outside it."""
    os.chdir(out("rev-parse", "--show-toplevel"))
    path = PurePosixPath(file)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise RewriteError("the changelog path must be relative to the repository root")
    return path.as_posix()


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
        args.file = _root_file(args.file)
        if args.cmd == "partition":
            result: dict[str, object] = {
                "ok": True,
                "commits": branch_commits(args.base, args.file),
            }
        else:
            result = drop(args.base, args.file, args.shas)
    except RewriteError as exc:
        print(
            json.dumps(
                {"ok": False, "reason": exc.reason, "backup": exc.backup, "recovery": exc.recovery}
            )
        )
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
