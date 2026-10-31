#!/usr/bin/env python3
"""Rebase with pinned recovery refs and index-preserving dirty-state restore.

``inspect --onto REF`` is read-only. ``start --onto REF`` begins a replay;
``continue`` resumes resolved conflicts. ``restore`` reapplies the retained
stash after a manual abort or a blocked restore. ``restore --resolved`` records
the user's completed resolution without changing files. Every command emits
one JSON object. Recovery refs and stashes are never deleted.
"""

# ruff: noqa: EM101, EM102, TRY003
# pyright: reportAny=false, reportUnusedCallResult=false

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath


class StopError(Exception):
    """A replay cannot proceed without changing or risking user work."""


@dataclass
class Replay:
    """Durable identity of one replay and its retained user changes."""

    branch: str
    tip: str
    base: str
    target: str
    target_oid: str
    upstream: str
    overlap: list[str]
    token: str = ""
    backup: str = ""
    stash: str = ""
    stash_ref: str = ""
    phase: str = "ready"
    outcome: str = ""
    resolution_paths: list[str] = field(default_factory=list)


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        text=True,
        errors="surrogateescape",
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if check and result.returncode:
        raise StopError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result


def _out(*args: str) -> str:
    return _git(*args).stdout.strip()


def _names(*args: str) -> set[str]:
    return {PurePosixPath(name).as_posix() for name in _git(*args).stdout.split("\0") if name}


def _git_path(name: str) -> Path:
    return Path(_out("rev-parse", "--git-path", name))


def _operation() -> Path | None:
    return next(
        (path for name in ("rebase-merge", "rebase-apply") if (path := _git_path(name)).exists()),
        None,
    )


def _dirty() -> bool:
    return bool(_out("status", "--porcelain", "--untracked-files=no", "--ignore-submodules=none"))


def _save(replay: Replay) -> None:
    path = _git_path("rebase-safety.json")
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(replay)), encoding="utf-8")
    temporary.replace(path)


def _load() -> Replay | None:
    path = _git_path("rebase-safety.json")
    return Replay(**json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None


def _recorded_replay() -> Replay:
    replay = _load()
    if replay is None:
        raise StopError("there is no recorded replay to resume")
    return replay


def _enter_repository() -> None:
    os.chdir(_out("rev-parse", "--show-toplevel"))
    root, home = Path.cwd().resolve(), Path.home().resolve()
    if root == home or root in home.parents:
        raise StopError("the repository root contains the home directory")


def _guard_untracked_paths(paths: set[str]) -> None:
    unknown = _names("ls-files", "--others", "-z")
    parents = {str(parent) for name in paths for parent in PurePosixPath(name).parents}
    if unknown.intersection(paths | parents) or any(
        str(parent) in paths for name in unknown for parent in PurePosixPath(name).parents
    ):
        raise StopError(
            "untracked or ignored files overlap saved or replayed paths; move them aside first"
        )


def _guard_untracked(base: str, tip: str, target: str) -> None:
    _guard_untracked_paths(
        _names("log", "--format=", "--no-renames", "--name-only", "-z", f"{base}..{tip}")
        | _names("diff", "--no-renames", "--name-only", "-z", base, target)
    )


def _inspect(target: str) -> Replay:
    branch = _out("branch", "--show-current")
    if not branch:
        raise StopError("HEAD is detached")
    if _operation() or any(
        _git_path(name).exists() for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD")
    ):
        raise StopError("a history operation is already in progress")
    target_oid = _out("rev-parse", "--verify", f"{target}^{{commit}}")
    target_ref = _out("rev-parse", "--symbolic-full-name", target)
    target_branch = target_ref.removeprefix("refs/heads/")
    if target_ref.startswith("refs/remotes/"):
        target_branch = target_ref.split("/", 3)[-1]
    if branch == target_branch:
        raise StopError("the current branch is the target branch")
    tip = _out("rev-parse", "HEAD")
    base = _out("merge-base", tip, target_oid)
    if base == target_oid:
        raise StopError("the branch is already up to date")
    if base == tip:
        raise StopError("the branch only needs a fast-forward")
    if _out("rev-list", "--merges", f"{base}..{tip}"):
        raise StopError("the branch contains merge commits")
    branch_files = _names("diff", "--no-renames", "--name-only", "-z", base, tip)
    target_files = _names("diff", "--no-renames", "--name-only", "-z", base, target_oid)
    _guard_untracked(base, tip, target_oid)
    upstream = _git("rev-parse", "--abbrev-ref", "@{upstream}", check=False).stdout.strip()
    return Replay(
        branch, tip, base, target, target_oid, upstream, sorted(branch_files & target_files)
    )


def _identify_stash(replay: Replay) -> None:
    """Find this operation's stash even when another stash was pushed later."""
    lines = _git("stash", "list", "--format=%H %gs").stdout.splitlines()
    matches = [line.split(" ", 1)[0] for line in lines if line.endswith(f": {replay.token}")]
    if len(matches) != 1:
        raise StopError("the saved stash could not be identified; recovery refs were retained")
    replay.stash = matches[0]
    _git("update-ref", replay.stash_ref, replay.stash)
    _save(replay)


def _restore(replay: Replay, *, resolved: bool = False) -> None:
    if _operation():
        raise StopError("the rebase is still in progress; resolve it or explicitly abort first")
    if _out("branch", "--show-current") != replay.branch:
        raise StopError("the checked-out branch changed; saved edits were retained")
    head = _out("rev-parse", "HEAD")
    if _git("merge-base", "--is-ancestor", replay.target_oid, head, check=False).returncode == 0:
        replay.outcome = "rebased"
    elif head == replay.tip:
        replay.outcome = "aborted"
    else:
        raise StopError("the branch tip is unexpected; saved edits were retained")
    if replay.phase == "complete":
        return
    if resolved:
        if replay.phase not in {"restore_conflict", "restore_blocked", "restoring"}:
            raise StopError("there is no pending saved-edit restoration to acknowledge")
        if _names("diff", "--name-only", "--diff-filter=U", "-z"):
            raise StopError("saved-edit conflicts remain unresolved")
    elif replay.stash:
        if replay.phase == "saving":
            _identify_stash(replay)
        if replay.phase == "restore_conflict":
            raise StopError(
                "resolve the saved edits, then acknowledge them with restore --resolved"
            )
        replay.phase = "restore_blocked"
        _save(replay)
        if _dirty():
            raise StopError(
                "new tracked edits block restoration; both their state and the stash are kept"
            )
        _guard_untracked_paths(
            _names("diff", "--no-renames", "--name-only", "-z", f"{replay.stash}^", replay.stash)
            | _names(
                "diff", "--no-renames", "--name-only", "-z", f"{replay.stash}^", f"{replay.stash}^2"
            )
        )
        replay.phase = "restoring"
        _save(replay)
        applied = _git("stash", "apply", "--index", replay.stash, check=False)
        if applied.returncode:
            replay.phase = "restore_conflict"
            _save(replay)
            raise StopError("restoring saved edits or staging conflicted; the exact stash is kept")
    replay.phase = "complete"
    _save(replay)


def _pre_rebase(replay: Replay) -> None:
    replay.phase = "hook_running"
    _save(replay)
    hook = _git(
        "hook", "run", "--ignore-missing", "pre-rebase", "--", replay.target_oid, check=False
    )
    replay.phase = "hook_blocked"
    _save(replay)
    if _out("rev-parse", "HEAD") != replay.tip or _out("branch", "--show-current") != replay.branch:
        raise StopError(
            "the pre-rebase hook changed the branch; its commits and saved edits are kept"
        )
    if _dirty():
        replay.phase = "restore_blocked"
        _save(replay)
        raise StopError("the pre-rebase hook made tracked edits; preserve them before restoring")
    _guard_untracked(replay.base, replay.tip, replay.target_oid)
    if hook.returncode:
        _restore(replay)
        raise StopError(f"the pre-rebase hook failed: {hook.stderr.strip()}")
    replay.phase = "rebasing"
    _save(replay)


def _execute(replay: Replay, *, resume: bool = False) -> None:
    if not resume:
        _pre_rebase(replay)
    # The pre-rebase hook already ran before the last dirty-state check.
    args = (
        ("--continue",)
        if resume
        else ("--no-verify", "--no-autostash", "--no-fork-point", replay.target_oid)
    )
    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "git",
            "-c",
            "rebase.updateRefs=false",
            "-c",
            "rebase.autoStash=false",
            "-c",
            "rebase.abbreviateCommands=false",
            "rebase",
            *args,
        ],
        env={**os.environ, "GIT_EDITOR": "true"},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        errors="surrogateescape",
        check=False,
    )
    if _operation():
        replay.phase = "rebase_conflict"
        replay.resolution_paths = sorted(
            _names(
                "diff-tree",
                "--no-commit-id",
                "--no-renames",
                "--name-only",
                "-r",
                "-z",
                "REBASE_HEAD",
            )
            | _names("diff", "--name-only", "--diff-filter=U", "-z")
        )
        _save(replay)
        raise StopError(
            "the rebase stopped; resolve the conflict or hook failure before continuing"
        )
    replay.phase = "rebase_finished"
    _save(replay)
    _restore(replay)
    if result.returncode:
        raise StopError("the rebase failed; inspect the retained recovery state")


def _start(target: str) -> Replay:
    previous = _load()
    if previous and previous.phase != "complete":
        raise StopError("the previous replay still needs recovery")
    replay = _inspect(target)
    replay.token = f"rebase-safety-{uuid.uuid4().hex}"
    replay.backup = replay.token.replace("safety", "backup", 1)
    replay.stash_ref = f"refs/rebase-safety/{replay.token}/edits"
    _git("update-ref", f"refs/heads/{replay.backup}", replay.tip, "")
    replay.phase = "saving"
    _save(replay)
    replay.stash = _out("stash", "create", replay.token)
    if replay.stash:
        _git("update-ref", replay.stash_ref, replay.stash, "")
    _save(replay)
    if replay.stash:
        _git("stash", "push", "--quiet", "--message", replay.token)
        _identify_stash(replay)
    if (
        _dirty()
        or _out("rev-parse", "HEAD") != replay.tip
        or _out("branch", "--show-current") != replay.branch
    ):
        raise StopError("the repository changed while saving edits; recovery state was retained")
    replay.phase = "rebasing"
    _save(replay)
    _execute(replay)
    return replay


def _continue(replay: Replay) -> None:
    operation = _operation()
    if operation is None:
        _restore(replay)
        return
    if (
        (operation / "head-name").read_text().strip() != f"refs/heads/{replay.branch}"
        or (operation / "orig-head").read_text().strip() != replay.tip
        or (operation / "onto").read_text().strip() != replay.target_oid
    ):
        raise StopError("the active rebase is not the recorded operation")
    if _names("diff", "--name-only", "--diff-filter=U", "-z"):
        raise StopError("conflict markers remain in the index; resolve and stage only those files")
    _guard_untracked(replay.base, replay.tip, replay.target_oid)
    staged = _names("diff", "--cached", "--name-only", "-z")
    if staged - set(replay.resolution_paths):
        raise StopError(
            "unrelated staged files would be committed; leave them out before continuing"
        )
    if _git("diff", "--quiet", check=False).returncode:
        raise StopError(
            "unstaged edits appeared during the rebase; preserve them before continuing"
        )
    _execute(replay, resume=True)


def main(argv: list[str]) -> int:
    """Dispatch the small replay protocol and return its current recovery facts."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "start"):
        commands.add_parser(name).add_argument("--onto", required=True)
    commands.add_parser("continue")
    commands.add_parser("restore").add_argument("--resolved", action="store_true")
    args = parser.parse_args(argv)
    previous_token = ""
    try:
        _enter_repository()
        if args.command == "inspect":
            print(json.dumps({"ok": True, **asdict(_inspect(args.onto))}))
            return 0
        with _git_path("rebase-safety.lock").open("a+") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise StopError("another rebase helper is running") from exc
            previous = _load()
            previous_token = previous.token if previous else ""
            if args.command == "start":
                replay = _start(args.onto)
            else:
                replay = _recorded_replay()
                if args.command == "continue":
                    _continue(replay)
                else:
                    _restore(replay, resolved=args.resolved)
        print(json.dumps({"ok": True, **asdict(replay)}))
    except (StopError, OSError, ValueError, TypeError) as exc:
        result: dict[str, object] = {"ok": False, "reason": str(exc)}
        try:
            replay = _load()
            if (
                replay
                and args.command != "inspect"
                and (
                    args.command != "start"
                    or replay.phase != "complete"
                    or replay.token != previous_token
                )
            ):
                result.update(asdict(replay))
        except StopError, OSError, ValueError, TypeError:
            pass
        print(json.dumps(result))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
