#!/usr/bin/env python3
"""Owned scratch worktrees, bound patches, and the commit gate.

`03-execute` and `01-benchmark` change files only inside a scratch worktree this
script created. Every mutating command refuses a directory that has no
ownership marker, so the user's checkout, index and branches are never written.
Each command prints one JSON object on stdout. Exit codes: 0 success, 1 a
reported failure (the JSON says why), 2 a usage error. Standard library only.

Commands: inputs, stale, exists, start, finish, reset, capture, apply, gate, landed.
Run ``isolate.py <command> --help`` for arguments.
"""

# pyright: reportAny=false, reportExplicitAny=false, reportUnusedCallResult=false
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import typing as t

if t.TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

OWNER = "owner.json"
TREE = "tree"
PREFIX = "pytest-optimizer."


def _git(
    cwd: pathlib.Path | str,
    *args: str,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(  # noqa: S603
        ["git", "-C", str(cwd), *args],  # noqa: S607
        capture_output=True,
        check=False,
        env=None if env is None else {**os.environ, **env},
    )


def _text(proc: subprocess.CompletedProcess[bytes]) -> str:
    return proc.stdout.decode("utf-8", "replace").strip()


def _err(proc: subprocess.CompletedProcess[bytes], default: str) -> str:
    return proc.stderr.decode("utf-8", "replace").strip() or default


def _names(proc: subprocess.CompletedProcess[bytes]) -> list[str]:
    return [n.decode("utf-8", "replace") for n in proc.stdout.split(b"\0") if n]


def _toplevel(path: pathlib.Path) -> pathlib.Path | None:
    proc = _git(path, "rev-parse", "--show-toplevel")
    return pathlib.Path(_text(proc)).resolve() if proc.returncode == 0 else None


def owner_of(tree: pathlib.Path) -> tuple[dict[str, t.Any] | None, str]:
    """Return the ownership record for a scratch worktree, or why it is not owned.

    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as d:
    ...     owner_of(pathlib.Path(d))[1]
    'not a scratch worktree this tool created'
    """
    tree = tree.resolve()
    marker = tree.parent / OWNER
    if tree.name != TREE or not marker.is_file():
        return None, "not a scratch worktree this tool created"
    try:
        record = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, "ownership record unreadable"
    if pathlib.Path(str(record.get("tree"))).resolve() != tree or _toplevel(tree) != tree:
        return None, "ownership record does not match this worktree"
    return record, ""


def inputs(cwd: pathlib.Path) -> dict[str, t.Any]:
    """Digest HEAD plus every tracked and untracked byte that can change a test run.

    Covers the whole repository even when ``cwd`` is a subdirectory. Ignored
    files are outside the digest: gitignored caches and environments are not
    source the suite is judged on.

    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as d:
    ...     r = pathlib.Path(d)
    ...     _ = _git(r, "init", "-q")
    ...     out = inputs(r)
    >>> (out["dirty"], out["untracked"])
    (False, 0)
    """
    head = _text(_git(cwd, "rev-parse", "--verify", "--quiet", "HEAD"))
    diff = _git(cwd, "diff", "HEAD", "--binary", "--no-ext-diff", "--no-textconv").stdout
    top = _toplevel(cwd) or cwd.resolve()
    digest = hashlib.sha256()
    for part in (head.encode(), diff):
        digest.update(part)
        digest.update(b"\0")
    found = sorted(_names(_git(top, "ls-files", "-o", "--exclude-standard", "-z")))
    for name in found:
        path = top / name
        digest.update(name.encode())
        digest.update(b"\0")
        try:
            body = path.readlink().as_posix().encode() if path.is_symlink() else path.read_bytes()
        except OSError:
            body = b"<unreadable>"
        digest.update(hashlib.sha256(body).digest())
    return {
        "head": head,
        "digest": digest.hexdigest(),
        "dirty": bool(diff) or bool(found),
        "untracked": len(found),
    }


def start(
    repo: pathlib.Path,
    base: str,
    branch: str | None = None,
    *,
    existing: bool = False,
    export: bool = False,
) -> dict[str, t.Any]:
    """Create an owned scratch worktree at ``base``; the user's checkout is not touched.

    With ``branch`` the worktree is on a new branch (or the named existing one);
    without it the worktree is detached. ``export`` copies ``base`` into a fresh
    one-commit repository for hosts that refuse ``git worktree add``, including
    files marked ``export-ignore``. ``workdir`` is where ``repo`` sits inside
    the tree, for a project that lives in a subdirectory.
    """
    top = _toplevel(repo)
    if top is None:
        return {"ok": False, "reason": "not a git repository"}
    home = pathlib.Path.home().resolve()
    if top == home or top in home.parents:
        return {"ok": False, "reason": "the repository root is or contains the home directory"}
    sha = _text(_git(top, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"))
    if not sha:
        return {"ok": False, "reason": f"base {base} is not a commit"}
    scratch = pathlib.Path(tempfile.mkdtemp(prefix=PREFIX)).resolve()
    tree = scratch / TREE
    if export:
        proc = _export(top, sha, tree)
    elif branch is None:
        proc = _git(top, "worktree", "add", "--detach", str(tree), sha)
    elif existing:
        _drop_lost_records(top, branch)
        proc = _git(top, "worktree", "add", str(tree), branch)
    else:
        proc = _git(top, "worktree", "add", "-b", branch, str(tree), sha)
    if proc.returncode != 0:
        shutil.rmtree(scratch, ignore_errors=True)
        return {"ok": False, "reason": _err(proc, "git worktree add failed")}
    record = {"tree": str(tree), "repo": str(top), "branch": branch, "export": export}
    (scratch / OWNER).write_text(json.dumps(record), encoding="utf-8")
    try:
        workdir = tree / repo.resolve().relative_to(top)
    except ValueError:
        workdir = tree
    return {
        "ok": True,
        "dir": str(scratch),
        "tree": str(tree),
        "workdir": str(workdir),
        "branch": branch,
        "base": sha,
    }


def _drop_lost_records(top: pathlib.Path, branch: str) -> None:
    """Forget this tool's own worktree records for ``branch`` whose directory is gone.

    A repository-wide ``git worktree prune`` would also drop records of
    worktrees the user moved or unmounted, so only matching records go.
    """
    common = _text(_git(top, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    for admin in (pathlib.Path(common) / "worktrees").glob("*"):
        try:
            where = pathlib.Path((admin / "gitdir").read_text(encoding="utf-8").strip()).parent
            head = (admin / "HEAD").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        mine = where.name == TREE and where.parent.name.startswith(PREFIX)
        if mine and not where.exists() and head == f"ref: refs/heads/{branch}":
            shutil.rmtree(admin, ignore_errors=True)


def _export(top: pathlib.Path, sha: str, tree: pathlib.Path) -> subprocess.CompletedProcess[bytes]:
    """Copy every file of ``sha`` (``export-ignore`` included) into a new repository."""
    tree.mkdir()
    with tempfile.TemporaryDirectory(prefix=PREFIX) as holder:
        index = {"GIT_INDEX_FILE": str(pathlib.Path(holder) / "index")}
        for args in (("read-tree", sha), ("checkout-index", "-a", f"--prefix={tree}/")):
            step = _git(top, *args, env=index)
            if step.returncode != 0:
                return step
    for args in (
        ("init", "-q"),
        ("add", "-A"),
        (
            "-c",
            "user.name=pytest-optimizer",
            "-c",
            "user.email=none@invalid",
            "commit",
            "-q",
            "-m",
            "base",
        ),
    ):
        step = _git(tree, *args)
        if step.returncode != 0:
            return step
    return subprocess.CompletedProcess([], 0, b"", b"")


def finish(scratch: pathlib.Path, drop_branch_at: str | None = None) -> dict[str, t.Any]:
    """Remove one owned scratch directory; other worktrees and branches stay.

    The result branch survives unless ``drop_branch_at`` names the commit it was
    cut from and the branch still points there (a run that applied nothing).

    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as d:
    ...     finish(pathlib.Path(d))["removed"]
    False
    """
    scratch = scratch.resolve()
    tree = scratch / TREE
    marker = scratch / OWNER
    if not scratch.name.startswith(PREFIX) or not marker.is_file():
        return {"removed": False, "reason": "not a scratch directory this tool created"}
    try:
        record = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"removed": False, "reason": "ownership record unreadable"}
    if tree.exists() and not record.get("export"):
        proc = _git(record["repo"], "worktree", "remove", "--force", str(tree))
        if proc.returncode != 0:
            return {"removed": False, "reason": _err(proc, "git worktree remove failed")}
    shutil.rmtree(scratch, ignore_errors=True)
    dropped = False
    branch = record.get("branch")
    if branch and drop_branch_at and not record.get("export"):
        repo = record["repo"]
        tip = _text(_git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"))
        base = _text(_git(repo, "rev-parse", "--verify", "--quiet", f"{drop_branch_at}^{{commit}}"))
        if tip and tip == base:
            dropped = _git(repo, "branch", "-D", branch).returncode == 0
    return {"removed": not scratch.exists(), "branch_dropped": dropped, "reason": None}


def reset(tree: pathlib.Path, to: str = "HEAD") -> dict[str, t.Any]:
    """Discard changes inside an owned worktree only; refuse any other directory.

    Runs ``git clean`` only after the reset succeeds.

    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as d:
    ...     reset(pathlib.Path(d))["ok"]
    False
    """
    record, why = owner_of(tree)
    if record is None:
        return {"ok": False, "reason": why}
    proc = _git(tree, "reset", "--hard", to)
    if proc.returncode != 0:
        return {"ok": False, "reason": _err(proc, "git reset failed")}
    proc = _git(tree, "clean", "-fd")
    return {
        "ok": proc.returncode == 0,
        "reason": None if proc.returncode == 0 else _err(proc, "git clean failed"),
    }


def capture(tree: pathlib.Path, out: pathlib.Path) -> dict[str, t.Any]:
    """Write the worktree's change against HEAD as a binary patch; bind it by hash.

    Run it right after applying a candidate and before any command that can
    create files, since every untracked file enters the patch.
    """
    record, why = owner_of(tree)
    if record is None:
        return {"ok": False, "reason": why}
    if _git(tree, "add", "-A").returncode != 0:
        return {"ok": False, "reason": "could not stage the change"}
    diff = _git(tree, "diff", "--cached", "--binary", "--no-ext-diff", "--no-textconv", "HEAD")
    paths = sorted(
        _names(_git(tree, "diff", "--cached", "--name-only", "--no-renames", "-z", "HEAD"))
    )
    _git(tree, "reset", "-q")
    if diff.returncode != 0 or not diff.stdout:
        return {"ok": False, "reason": "the worktree has no change against HEAD"}
    out.write_bytes(diff.stdout)
    return {
        "ok": True,
        "patch": str(out),
        "sha256": hashlib.sha256(diff.stdout).hexdigest(),
        "paths": paths,
    }


def apply(  # noqa: PLR0911
    tree: pathlib.Path,
    patch: pathlib.Path,
    sha256: str,
    files: Sequence[str],
) -> dict[str, t.Any]:
    """Apply a hash-bound patch to a clean owned worktree and stage exactly ``files``."""
    record, why = owner_of(tree)
    if record is None:
        return {"ok": False, "reason": why}
    try:
        body = patch.read_bytes()
    except OSError as exc:
        return {"ok": False, "reason": f"patch unreadable: {exc.strerror}"}
    if hashlib.sha256(body).hexdigest() != sha256:
        return {"ok": False, "reason": "patch bytes differ from the recorded hash"}
    if _git(tree, "status", "--porcelain", "--untracked-files=all").stdout:
        return {"ok": False, "reason": "the scratch worktree is not clean"}
    check = _git(tree, "apply", "--check", "--index", str(patch))
    if check.returncode != 0:
        return {"ok": False, "reason": _err(check, "patch does not apply")}
    applied = _git(tree, "apply", "--index", str(patch))
    if applied.returncode != 0:
        reset(tree)
        return {"ok": False, "reason": _err(applied, "patch failed to apply")}
    staged = sorted(_names(_git(tree, "diff", "--cached", "--name-only", "--no-renames", "-z")))
    if staged != sorted(set(files)):
        reset(tree)
        return {"ok": False, "reason": "patch paths differ from the plan's files", "paths": staged}
    return {"ok": True, "paths": staged}


def gate(tree: pathlib.Path, files: Sequence[str]) -> dict[str, t.Any]:
    """Check that the staged bytes are exactly ``files`` and nothing else changed.

    On success returns the tree and parent a commit must have; ``landed``
    compares against them after the commit and its hooks have run.
    """
    record, why = owner_of(tree)
    if record is None:
        return {"ok": False, "reason": why}
    staged = sorted(_names(_git(tree, "diff", "--cached", "--name-only", "--no-renames", "-z")))
    loose = sorted(
        {
            *_names(_git(tree, "diff", "--name-only", "--no-renames", "-z")),
            *_names(_git(tree, "ls-files", "-o", "--exclude-standard", "-z")),
        },
    )
    if staged != sorted(set(files)):
        return {"ok": False, "reason": "staged paths differ from the plan's files", "paths": staged}
    if loose:
        return {"ok": False, "reason": "the run changed paths outside the plan", "paths": loose}
    written = _git(tree, "write-tree")
    if written.returncode != 0:
        return {"ok": False, "reason": _err(written, "could not write the index tree")}
    return {
        "ok": True,
        "tree": _text(written),
        "parent": _text(_git(tree, "rev-parse", "HEAD")),
        "reason": None,
    }


def landed(tree: pathlib.Path, parent: str, tree_sha: str) -> dict[str, t.Any]:
    """Check HEAD is one commit on ``parent`` holding exactly the gated tree."""
    record, why = owner_of(tree)
    if record is None:
        return {"ok": False, "reason": why}
    head = _text(_git(tree, "rev-parse", "--verify", "--quiet", "HEAD"))
    up = _text(_git(tree, "rev-parse", "--verify", "--quiet", "HEAD^"))
    if not head or up != parent:
        return {"ok": False, "reason": "HEAD is not one commit on the gated parent", "head": head}
    if _text(_git(tree, "rev-parse", "HEAD^{tree}")) != tree_sha:
        return {"ok": False, "reason": "committed tree differs from the gated tree", "head": head}
    return {"ok": True, "reason": None, "head": head}


def _load(path: pathlib.Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _load_dict(path: pathlib.Path) -> dict[str, t.Any] | None:
    data = _load(path)
    return t.cast("dict[str, t.Any]", data) if isinstance(data, dict) else None


def _load_list(path: pathlib.Path) -> list[dict[str, t.Any]] | None:
    data = _load(path)
    return t.cast("list[dict[str, t.Any]]", data) if isinstance(data, list) else None


def _approval_error(memory: pathlib.Path, state: Mapping[str, t.Any]) -> str | None:
    """Return why ``plan.json`` is not the plan the user approved, or None."""
    if not state.get("completed", {}).get("plan"):
        return "the plan was never approved"
    try:
        digest = hashlib.sha256((memory / "plan.json").read_bytes()).hexdigest()
    except OSError:
        return "plan.json is missing or unreadable"
    return None if digest == state.get("plan_hash") else "the plan changed after approval"


def stale(  # noqa: PLR0911
    memory: pathlib.Path,
    cwd: pathlib.Path,
    phase: str,
    command: str | None = None,
    pytest_version: str | None = None,
) -> dict[str, t.Any]:
    """Report the first reason the scan's evidence no longer describes this checkout.

    ``phase`` is the phase about to run: ``benchmark``, ``plan`` or ``execute``.
    ``rerun`` names the phase that repairs the first failure.

    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as d:
    ...     stale(pathlib.Path(d), pathlib.Path(d), "plan")["reason"]
    'state.json is missing or unreadable'
    """
    state = _load_dict(memory / "state.json")
    if state is None:
        return {"ok": False, "reason": "state.json is missing or unreadable", "rerun": "00-scan"}
    if phase == "execute":
        approved = _approval_error(memory, state)
        if approved is not None:
            return {"ok": False, "reason": approved, "rerun": "02-plan"}
    rerun = "00-scan --force"
    if not state.get("env_token"):
        return {"ok": False, "reason": "the scan recorded no environment token", "rerun": rerun}
    if state.get("dirty"):
        return {"ok": False, "reason": "the scan ran on a dirty tree", "rerun": rerun}
    head = _text(_git(cwd, "rev-parse", "--verify", "--quiet", "HEAD"))
    if head != state.get("base_head"):
        return {"ok": False, "reason": "HEAD differs from the scan's commit", "rerun": rerun}
    if phase == "benchmark":
        found = inputs(cwd)
        if found["digest"] != state.get("inputs_digest"):
            return {
                "ok": False,
                "reason": "the working tree differs from the scan's",
                "rerun": rerun,
            }
        base = _load_dict(memory / "baseline.json") or {}
        if command is not None and base.get("test_command") not in (None, command):
            return {
                "ok": False,
                "reason": "the test command differs from the scan's",
                "rerun": rerun,
            }
        recorded = base.get("pytest_version")
        if pytest_version is not None and recorded not in (None, pytest_version):
            return {
                "ok": False,
                "reason": "the pytest version differs from the scan's",
                "rerun": rerun,
            }
        return {"ok": True, "reason": None}
    name = "benchmarks.json" if phase == "plan" else "plan.json"
    entries = _load_list(memory / name)
    if entries is None:
        return {"ok": False, "reason": f"{name} is missing or unreadable", "rerun": "00-scan"}
    for entry in entries:
        if phase == "plan" and entry.get("verdict") != "validated":
            continue
        if entry.get("env_token") != state["env_token"]:
            return {
                "ok": False,
                "reason": f"{entry.get('id')} has a different token",
                "rerun": rerun,
            }
        if not entry.get("patch_sha256"):
            return {
                "ok": False,
                "reason": f"{entry.get('id')} has no patch hash",
                "rerun": "01-benchmark --force",
            }
        if phase == "plan" and entry.get("base_head") != head:
            return {
                "ok": False,
                "reason": f"{entry.get('id')} was cut from another commit",
                "rerun": rerun,
            }
    return {"ok": True, "reason": None}


def exists(
    cwd: pathlib.Path, files: Sequence[str], patch: pathlib.Path | None = None
) -> dict[str, t.Any]:
    """List the ``files`` absent at HEAD, except those ``patch`` creates.

    Paths are relative to the repository root.
    """
    created: set[str] = set()
    if patch is not None:
        lines = patch.read_bytes().decode("utf-8", "replace").splitlines()
        for before, after in zip(lines, lines[1:]):
            if before == "--- /dev/null" and after.startswith("+++ b/"):
                created.add(after[len("+++ b/") :])
    missing = [
        f
        for f in files
        if f not in created and _git(cwd, "cat-file", "-e", f"HEAD:{f}").returncode != 0
    ]
    return {
        "ok": not missing,
        "missing": missing,
        "reason": None if not missing else "absent at HEAD",
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("inputs", help="digest of HEAD and every tracked or untracked byte")
    p.add_argument("--cwd", default=".")

    p = sub.add_parser("stale", help="check the scan's evidence still describes this checkout")
    p.add_argument("--memory-dir", required=True)
    p.add_argument("--cwd", default=".")
    p.add_argument("--phase", required=True, choices=("benchmark", "plan", "execute"))
    p.add_argument("--command", dest="test_command", help="the resolved test command")
    p.add_argument("--pytest-version", help="version the project's runner reports")

    p = sub.add_parser("exists", help="list planned files absent at HEAD")
    p.add_argument("--cwd", default=".")
    p.add_argument("--patch", help="a patch whose created files count as present")
    p.add_argument("--file", dest="files", action="append", default=[], required=True)

    p = sub.add_parser("start", help="create an owned scratch worktree")
    p.add_argument("--repo", default=".")
    p.add_argument("--base", required=True, help="commit the worktree starts from")
    p.add_argument("--branch", help="new branch for the worktree; detached when absent")
    p.add_argument("--existing", action="store_true", help="--branch already exists")
    p.add_argument("--export", action="store_true", help="copy files instead of a worktree")

    p = sub.add_parser("finish", help="remove one owned scratch directory")
    p.add_argument("--dir", required=True)
    p.add_argument("--drop-branch-at", help="also delete the result branch if it still points here")

    p = sub.add_parser("reset", help="discard changes inside an owned worktree")
    p.add_argument("--cwd", required=True)
    p.add_argument("--to", default="HEAD")

    p = sub.add_parser("capture", help="write the worktree change as a hash-bound patch")
    p.add_argument("--cwd", required=True)
    p.add_argument("--out", required=True)

    p = sub.add_parser("apply", help="apply a hash-bound patch and stage its files")
    p.add_argument("--cwd", required=True)
    p.add_argument("--patch", required=True)
    p.add_argument("--sha256", required=True)
    p.add_argument("--file", dest="files", action="append", default=[], required=True)

    p = sub.add_parser("gate", help="check the staged bytes before committing")
    p.add_argument("--cwd", required=True)
    p.add_argument("--file", dest="files", action="append", default=[], required=True)

    p = sub.add_parser("landed", help="check the commit holds the gated tree")
    p.add_argument("--cwd", required=True)
    p.add_argument("--parent", required=True)
    p.add_argument("--tree", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch one command."""
    args = build_parser().parse_args(argv)
    cmd = args.command
    path = pathlib.Path
    if cmd == "inputs":
        out = inputs(path(args.cwd))
    elif cmd == "stale":
        out = stale(
            path(args.memory_dir),
            path(args.cwd),
            args.phase,
            args.test_command,
            args.pytest_version,
        )
    elif cmd == "exists":
        out = exists(path(args.cwd), args.files, path(args.patch) if args.patch else None)
    elif cmd == "start":
        out = start(
            path(args.repo), args.base, args.branch, existing=args.existing, export=args.export
        )
    elif cmd == "finish":
        out = finish(path(args.dir), args.drop_branch_at)
    elif cmd == "reset":
        out = reset(path(args.cwd), args.to)
    elif cmd == "capture":
        out = capture(path(args.cwd), path(args.out))
    elif cmd == "apply":
        out = apply(path(args.cwd), path(args.patch), args.sha256, args.files)
    elif cmd == "gate":
        out = gate(path(args.cwd), args.files)
    else:
        out = landed(path(args.cwd), args.parent, args.tree)
    print(json.dumps(out, sort_keys=True))
    return 0 if out.get("ok", out.get("removed", True)) else 1


if __name__ == "__main__":
    sys.exit(main())
