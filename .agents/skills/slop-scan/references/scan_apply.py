#!/usr/bin/env python3
"""Apply one reviewed scan finding in an isolated worktree, or verify the tip.

Read ``commits.json`` and ``gates.json`` from the scan run directory. Each
commit entry names one tracked file, its patch, subject, and body. Each gate
has a name and shell command, run from the isolated repository root.
"""

# ruff: noqa: EM101, TRY003
# pyright: reportAny=false, reportExplicitAny=false, reportUnusedCallResult=false

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Generator


class RefusedError(Exception):
    """The requested operation cannot preserve the current checkout."""


def _environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if key not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX"}
    }


def _git(
    repo: Path, *args: str, index: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[bytes]:
    env = _environment()
    if index is not None:
        env["GIT_INDEX_FILE"] = str(index)
    return subprocess.run(  # noqa: S603
        ["git", "--literal-pathspecs", "-C", str(repo), *args],  # noqa: S607
        env=env,
        capture_output=True,
        check=check,
    )


def _text(repo: Path, *args: str) -> str:
    return os.fsdecode(_git(repo, *args).stdout).strip()


def _expect_tip(repo: Path, branch: str, expected: str) -> None:
    if _text(repo, "symbolic-ref", "-q", "HEAD") != branch:
        raise RefusedError("the checked-out branch changed; review the series again")
    if _text(repo, "rev-parse", "HEAD") != expected:
        raise RefusedError("HEAD changed; review the series again")


def _clean_target(repo: Path, name: str, expected: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise RefusedError("the finding must name one repository-relative file")
    target = repo / name
    if any((repo / parent).is_symlink() for parent in path.parents):
        raise RefusedError("the finding's parent directories must not be symlinks")
    if not target.resolve().is_relative_to(repo) or not stat.S_ISREG(target.lstat().st_mode):
        raise RefusedError("the finding must name a regular tracked file")
    tree = _git(repo, "ls-tree", "-z", expected, "--", name).stdout
    indexed = _git(repo, "ls-files", "--stage", "-z", "--", name).stdout
    if not tree or not indexed:
        raise RefusedError("the finding must name a tracked file")
    mode, _, blob = tree.split(b"\t", 1)[0].split()
    staged_mode, staged_blob, stage = indexed.split(b"\t", 1)[0].split()
    if stage != b"0" or (mode, blob) != (staged_mode, staged_blob):
        raise RefusedError("the finding's file has staged user changes; keep it advisory")
    expected_bytes = _git(repo, "cat-file", "blob", blob.decode("ascii")).stdout
    executable = bool(target.stat().st_mode & stat.S_IXUSR)
    if target.read_bytes() != expected_bytes or executable != (mode == b"100755"):
        raise RefusedError("the finding's file has user changes; keep it advisory")


@contextmanager
def _cleanup(resource: str | Path) -> Generator[None]:
    try:
        yield
    except OSError as exc:
        print(f"scan_apply: cleanup failed; inspect {resource}: {exc}", file=sys.stderr)


@contextmanager
def _worktree(repo: Path, expected: str) -> Generator[Path]:
    temporary = Path(tempfile.mkdtemp(prefix="slop-scan-"))
    scratch = temporary / "worktree"
    try:
        _git(repo, "worktree", "add", "--detach", str(scratch), expected)
        yield scratch
    finally:
        with _cleanup(temporary):
            removed = _git(repo, "worktree", "remove", "--force", str(scratch), check=False)
            if removed.returncode and scratch.exists():
                print(f"scan_apply: scratch cleanup failed; inspect {scratch}", file=sys.stderr)
            else:
                temporary.rmdir()


def _gates(scratch: Path, gates: list[dict[str, str]]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for gate in gates:
        done = subprocess.run(  # noqa: S603
            ["sh", "-c", gate["command"]],  # noqa: S607
            cwd=scratch,
            env=_environment(),
            capture_output=True,
            check=False,
        )
        results.append(
            {
                "name": gate["name"],
                "exit_code": done.returncode,
                "stdout": os.fsdecode(done.stdout),
                "stderr": os.fsdecode(done.stderr),
            }
        )
        if done.returncode:
            return {"status": "gate-failed", "gates": results}
    return {"status": "verified", "gates": results}


def _publish(  # noqa: PLR0913
    repo: Path, scratch: Path, *, branch: str, expected: str, candidate: str, name: str, patch: Path
) -> dict[str, Any]:
    recovery = "refs/heads/slop-scan-recovery-" + uuid.uuid4().hex
    _git(scratch, "update-ref", recovery, candidate, "")
    index = Path(_text(repo, "rev-parse", "--path-format=absolute", "--git-path", "index"))
    lock = index.with_name(index.name + ".lock")
    result: dict[str, Any] = {
        "status": "refused",
        "recovery_branch": recovery.removeprefix("refs/heads/"),
    }
    acquired = False
    applied = False
    try:
        with lock.open("xb"):
            acquired = True
            fd, temporary = tempfile.mkstemp(prefix="slop-index-", dir=index.parent)
            os.close(fd)
            isolated_index = Path(temporary)
            try:
                _expect_tip(repo, branch, expected)
                _clean_target(repo, name, expected)
                shutil.copyfile(index, isolated_index)
                # Git apply checks cached stat data even when the file's bytes match.
                _git(repo, "update-index", "-q", "--refresh", index=isolated_index)
                _git(repo, "apply", "--index", str(patch), index=isolated_index)
                applied = True
                updated = _git(
                    scratch,
                    "update-ref",
                    "-m",
                    "slop: apply scan finding",
                    branch,
                    candidate,
                    expected,
                    check=False,
                )
                if updated.returncode:
                    undone = _git(
                        repo,
                        "apply",
                        "--reverse",
                        "--index",
                        str(patch),
                        index=isolated_index,
                        check=False,
                    )
                    result["status"] = "refused" if undone.returncode == 0 else "recovery-needed"
                    result["error"] = os.fsdecode(updated.stderr)
                    return result
                isolated_index.replace(index)
            finally:
                with _cleanup(isolated_index):
                    isolated_index.unlink(missing_ok=True)
    except (RefusedError, OSError, subprocess.CalledProcessError) as exc:
        if applied:
            result["status"] = "recovery-needed"
        result["error"] = str(exc)
        if isinstance(exc, FileExistsError) and not acquired:
            result["error"] = (
                "the index is locked by another Git operation; retry after it finishes"
            )
        return result
    finally:
        # Only this process may remove the lock it acquired.
        if acquired:
            with _cleanup(lock):
                lock.unlink(missing_ok=True)
    removed = False
    with _cleanup(recovery):
        removed = (
            _git(scratch, "update-ref", "-d", recovery, candidate, check=False).returncode == 0
        )
    result = {"status": "committed", "commit": candidate}
    if not removed:
        result["recovery_branch"] = recovery.removeprefix("refs/heads/")
    return result


def _strings(value: object, keys: tuple[str, ...]) -> dict[str, str]:
    if not isinstance(value, dict):
        raise RefusedError("each finding and gate must be a JSON object")
    fields = cast("dict[str, object]", value)
    result: dict[str, str] = {}
    for key in keys:
        field = fields.get(key)
        if not isinstance(field, str):
            raise RefusedError("each finding and gate field must be a string")
        result[key] = field
    return result


def _entry(run_dir: Path, number: int) -> dict[str, str]:
    raw: object = json.loads((run_dir / "commits.json").read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise RefusedError("commits.json must be a list")
    entries = cast("list[object]", raw)
    if not 0 <= number < len(entries):
        raise RefusedError("the finding index is outside commits.json")
    entry = _strings(entries[number], ("file", "patch", "subject", "body"))
    if not entry["subject"].strip() or "\n" in entry["subject"]:
        raise RefusedError("the commit subject must be one nonempty line")
    return entry


def _load_gates(run_dir: Path) -> list[dict[str, str]]:
    raw: object = json.loads((run_dir / "gates.json").read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise RefusedError("gates.json must be a list")
    gates = [_strings(value, ("name", "command")) for value in cast("list[object]", raw)]
    if any(not gate["command"].strip() for gate in gates):
        raise RefusedError("gate commands must be nonempty")
    return gates


def _verify_candidate(repo: Path, candidate: str, gates: list[dict[str, str]]) -> dict[str, Any]:
    with _worktree(repo, candidate) as scratch:
        result = _gates(scratch, gates)
        changed = _git(scratch, "diff", "HEAD", "--name-only").stdout
        if result["status"] == "verified" and (
            changed or _text(scratch, "rev-parse", "HEAD") != candidate
        ):
            result["status"] = "gate-modified"
            result["error"] = "gates changed the candidate; review the patch before retrying"
            result["changed_files"] = os.fsdecode(changed)
        return result


def _source(args: argparse.Namespace) -> tuple[Path, str]:
    repo = Path(_text(Path.cwd(), "rev-parse", "--show-toplevel")).resolve()
    if Path.home().resolve().is_relative_to(repo):
        raise RefusedError("the repository root contains the home directory")
    branch = _text(repo, "symbolic-ref", "-q", "HEAD")
    _expect_tip(repo, branch, args.expected_head)
    for name in ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD"):
        if Path(_text(repo, "rev-parse", "--path-format=absolute", "--git-path", name)).exists():
            raise RefusedError("finish the active Git operation before applying scan findings")
    if not args.allow_dirty and _git(repo, "status", "--porcelain").stdout:
        raise RefusedError("the working tree is dirty; commit or stash, or pass --allow-dirty")
    return repo, branch


def _run(args: argparse.Namespace) -> dict[str, Any]:
    repo, branch = _source(args)
    run_dir = args.run_dir.resolve()
    gates = _load_gates(run_dir)
    entry = None if args.verify else _entry(run_dir, args.entry)
    if not entry:
        verified = _verify_candidate(repo, args.expected_head, gates)
        _expect_tip(repo, branch, args.expected_head)
        return verified
    _clean_target(repo, entry["file"], args.expected_head)
    with _worktree(repo, args.expected_head) as scratch:
        patch = (run_dir / entry["patch"]).resolve()
        if not patch.is_relative_to(run_dir) or not patch.is_file():
            raise RefusedError("the finding's patch must be a file inside its run directory")
        _git(scratch, "apply", "--index", str(patch))
        changed = _git(scratch, "diff", "--cached", "--name-only", "-z").stdout.split(b"\0")[:-1]
        if changed != [os.fsencode(entry["file"])]:
            raise RefusedError("the patch must change only its named file")
        result = _gates(scratch, gates)
        if result["status"] != "verified":
            return result
        target = scratch / entry["file"]
        if not target.exists() or target.is_symlink():
            raise RefusedError("a scan finding cannot delete a file or replace it with a symlink")
        _git(scratch, "add", "--", entry["file"])
        if not _git(scratch, "diff", "--cached", "--name-only", "--", entry["file"]).stdout:
            return {"status": "no-op", "gates": result["gates"]}
        gated_tree = _text(scratch, "write-tree")
        gate_side_effects = bool(
            _git(scratch, "diff", "--name-only").stdout
            or _git(scratch, "ls-files", "--others", "--exclude-standard").stdout
        )
        with tempfile.TemporaryDirectory(prefix="slop-message-") as temporary:
            message = Path(temporary) / "message"
            message.write_text(entry["subject"] + "\n\n" + entry["body"] + "\n", encoding="utf-8")
            committed = _git(
                scratch, "commit", "--only", "-F", str(message), "--", entry["file"], check=False
            )
        if committed.returncode:
            return {
                "status": "hook-failed",
                "error": os.fsdecode(committed.stderr),
                "gates": result["gates"],
            }
        candidate = _text(scratch, "rev-parse", "HEAD")
        changed = _git(scratch, "diff", "--name-only", "-z", args.expected_head, candidate).stdout
        if changed != os.fsencode(entry["file"]) + b"\0":
            raise RefusedError("a commit hook changed files outside the approved finding")
        if _text(scratch, "rev-parse", "HEAD^") != args.expected_head:
            raise RefusedError("a commit hook changed the expected history")
        _git(scratch, "restore", "--source", candidate, "--staged", "--", entry["file"])
        _clean_target(scratch, entry["file"], candidate)
        if gate_side_effects or _text(scratch, "rev-parse", "HEAD^{tree}") != gated_tree:
            checked = _verify_candidate(repo, candidate, gates)
            result["gates"].extend(checked["gates"])
            if checked["status"] != "verified":
                return {**checked, "status": "gate-failed", "gates": result["gates"]}
        candidate_patch = run_dir / (".candidate-" + uuid.uuid4().hex + ".patch")
        candidate_patch.write_bytes(
            _git(scratch, "diff", "--binary", args.expected_head, candidate).stdout
        )
        try:
            published = _publish(
                repo,
                scratch,
                branch=branch,
                expected=args.expected_head,
                candidate=candidate,
                name=entry["file"],
                patch=candidate_patch,
            )
            return {**published, "gates": result["gates"]}
        finally:
            with _cleanup(candidate_patch):
                candidate_patch.unlink()


def main(argv: list[str] | None = None) -> int:
    """Print one JSON result and return zero only for a completed operation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--entry", type=int)
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = _run(args)
    except (RefusedError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        result = {"status": "refused", "error": str(exc)}
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result["status"] in {"committed", "no-op", "verified"} else 1


if __name__ == "__main__":
    sys.exit(main())
