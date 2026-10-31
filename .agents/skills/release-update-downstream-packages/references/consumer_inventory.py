#!/usr/bin/env python3
"""Read repository inventories and immutable branch inputs without checkout.

``inventory ROOT...`` includes nested and hidden directories, except virtual
environments (a directory holding ``pyvenv.cfg``) and ``node_modules``, which it lists
under ``skipped``; ``--include-dependencies`` scans them. ``snapshot --repo
ROOT --ref refs/heads/BRANCH --read PATH...`` returns the complete commit tree
and requested blobs. Add ``--expect-commit OID --require-checkout`` to compare
the selected tree, index and every tracked regular file's actual bytes/mode.
No worktree normalization or project filter runs. A raw-byte difference may be
an edit or a content transformation; neither counts as validated equality.
JSON paths round-trip through os.fsencode; blob bytes use base64. Exit 1 means
incomplete or stale evidence, 2 means usage failure. POSIX process groups are
required. Repository inventory does not identify dependencies semantically.
"""

import argparse
import base64
import contextlib
import hashlib
import json
import math
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, NoReturn, final

_REDIRECTS = {
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_NAMESPACE",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS",
    "GIT_SHALLOW_FILE",
    "GIT_REPLACE_REF_BASE",
    "GIT_CEILING_DIRECTORIES",
}
_OID = re.compile(rb"[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")
_REGULAR = {"100644", "100755"}
_SYMLINK = "120000"
_SHA1_HEX_LENGTH = 40


class _ReadError(Exception):
    """A read cannot establish the requested evidence."""


def _fail(message: str) -> NoReturn:
    raise _ReadError(message)


def _execute(argv: list[str], cwd: Path, env: dict[str, str], limit: int, deadline: float) -> bytes:
    if os.name != "posix":
        _fail("read-only process cleanup requires POSIX process groups")
    timeout_message = (
        "Git read exceeded its time budget; --max-seconds bounds the run and "
        "--max-call-seconds bounds each Git call"
    )
    if time.monotonic() >= deadline:
        _fail(timeout_message)
    with subprocess.Popen(  # noqa: S603
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    ) as process:
        stdout, stderr = bytearray(), bytearray()
        try:
            with selectors.DefaultSelector() as selector:
                for stream, output in ((process.stdout, stdout), (process.stderr, stderr)):
                    if stream is not None:
                        selector.register(stream, selectors.EVENT_READ, output)
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        _fail(timeout_message)
                    for key, _ in selector.select(remaining):
                        chunk = os.read(key.fd, min(65536, limit + 1))
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        key.data.extend(chunk)
                        if len(stdout) + len(stderr) > limit:
                            _fail("Git output exceeded the byte limit")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _fail(timeout_message)
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as error:
            raise _ReadError(timeout_message) from error
        finally:
            # Git may spawn a lazy fetch; terminate the owned group even on exit.
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        if process.returncode or stderr:
            diagnostic = stderr.decode("utf-8", "replace").strip()
            _fail(f"Git read exited {process.returncode} with diagnostic: {diagnostic}")
        return bytes(stdout)


@final
class _Reader:
    def __init__(
        self, max_entries: int, max_bytes: int, max_seconds: float, call_seconds: float = 1.0
    ) -> None:
        self.call_seconds = call_seconds
        self.entries = max_entries
        self.remaining_bytes = max_bytes
        self.deadline = time.monotonic() + max_seconds

    def tick(self) -> None:
        self.entries -= 1
        if self.entries < 0 or time.monotonic() >= self.deadline:
            _fail("inventory resource limit reached; coverage is incomplete")

    def git(self, root: Path, *args: str) -> bytes:
        self.tick()
        if self.remaining_bytes <= 0:
            _fail("reads exhausted the total byte limit")
        redirected = sorted(
            key
            for key, value in os.environ.items()
            if value and (key in _REDIRECTS or key.startswith("GIT_TRACE"))
        )
        if redirected:
            _fail("repository-redirecting environment: " + ", ".join(redirected))
        env = dict(os.environ)
        env.update(
            GIT_ALLOW_PROTOCOL="",
            GIT_OPTIONAL_LOCKS="0",
            GIT_NO_REPLACE_OBJECTS="1",
            GIT_TERMINAL_PROMPT="0",
            GIT_TRACE2="0",
            GIT_TRACE2_EVENT="0",
            GIT_TRACE2_PERF="0",
        )
        result = _execute(
            [
                "git",
                "--no-pager",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.untrackedCache=false",
                *args,
            ],
            root,
            env,
            self.remaining_bytes,
            min(self.deadline, time.monotonic() + self.call_seconds),
        )
        self.remaining_bytes -= len(result)
        return result


def _line(data: bytes) -> str:
    if not data.endswith(b"\n"):
        _fail("Git did not return a complete path/ref record")
    return os.fsdecode(data[:-1])


def _physical(path: Path) -> Path:
    if ".." in path.parts:
        _fail("parent traversal requires an explicit physical root without '..'")
    absolute = Path(os.path.abspath(path))  # noqa: PTH100
    for part in (*reversed(absolute.parents), absolute):
        metadata = part.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            _fail(f"symlink boundary requires an explicit physical root: {part}")
        if not stat.S_ISDIR(metadata.st_mode):
            _fail(f"not a directory: {part}")
    return absolute


def _identity(reader: _Reader, root: Path) -> dict[str, Any]:
    actual = Path(_line(reader.git(root, "rev-parse", "--show-toplevel")))
    if actual != root:
        _fail(f"Git working root differs from requested checkout: {actual}")
    private = _line(reader.git(root, "rev-parse", "--absolute-git-dir"))
    common = _line(reader.git(root, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    refs: dict[str, str] = {}
    for line in reader.git(
        root, "for-each-ref", "--format=%(refname)%00%(objectname)"
    ).splitlines():
        ref, oid = line.split(b"\0")
        if not _OID.fullmatch(oid):
            _fail("invalid ref object identity")
        refs[os.fsdecode(ref)] = oid.decode("ascii")
    return {
        "root": str(root),
        "git_dir": private,
        "common_dir": common,
        "refs": refs,
        "replacement_refs_ignored": [ref for ref in refs if ref.startswith("refs/replace/")],
    }


def _check_symlink(path: Path, roots: list[str]) -> None:
    """Accept a link that cannot hide a repository: to a file, nowhere, or inside a scanned root."""
    try:
        target = path.stat()
    except OSError:
        return
    if not stat.S_ISDIR(target.st_mode):
        return
    real = os.path.realpath(path)
    if not any(os.path.commonpath([real, root]) == root for root in roots):
        _fail("symlink to a directory outside the scanned roots was not traversed")


def _without_dependencies(
    path: Path, names: set[str], entries: list[str], skipped: list[dict[str, str]]
) -> list[str] | None:
    """Return the entries to walk, or None to skip a virtualenv; record what is skipped."""
    if "pyvenv.cfg" in names:
        skipped.append({"path": str(path), "reason": "virtual environment"})
        return None
    if "node_modules" in names:
        skipped.append({"path": str(path / "node_modules"), "reason": "installed npm packages"})
        return [name for name in entries if name != "node_modules"]
    return entries


def _checkout_identity(reader: _Reader, path: Path) -> dict[str, Any]:
    marker = (path / ".git").lstat()
    if not (stat.S_ISDIR(marker.st_mode) or stat.S_ISREG(marker.st_mode)):
        _fail("unsupported .git entry type")
    return _identity(reader, path)


def _unclassified(found: list[Path], administrative: set[Path]) -> list[dict[str, str]]:
    return [
        {
            "path": str(path),
            "reason": "Git administrative or bare directory has no validated checkout",
        }
        for path in found
        if path not in administrative
    ]


def _listing(reader: _Reader, path: Path) -> list[str]:
    entries: list[str] = []
    with os.scandir(path) as listing:
        for entry in listing:
            reader.tick()
            entries.append(entry.name)
    return entries


def _inventory(
    reader: _Reader, roots: list[Path], *, include_dependencies: bool = False
) -> dict[str, Any]:
    result: dict[str, Any] = {"roots": [], "repositories": [], "omissions": [], "skipped": []}
    seen: set[tuple[int, int]] = set()
    pending: list[Path] = []
    administrative: set[Path] = set()
    unclassified_git: list[Path] = []
    for root in roots:
        try:
            physical = _physical(root)
            result["roots"].append(str(physical))
            pending.append(physical)
        except (OSError, _ReadError) as error:
            result["omissions"].append({"path": str(root), "reason": str(error)})
    while pending:
        path = pending.pop()
        try:
            reader.tick()
            if path in administrative:
                continue
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                _check_symlink(path, result["roots"])
                continue
            if not stat.S_ISDIR(metadata.st_mode):
                continue
            identity = (metadata.st_dev, metadata.st_ino)
            if identity in seen:
                continue
            seen.add(identity)
            entries = _listing(reader, path)
            names = set(entries)
            if not include_dependencies:
                kept = _without_dependencies(path, names, entries, result["skipped"])
                if kept is None:
                    continue
                entries = kept
            if ".git" in names:
                repo = _checkout_identity(reader, path)
                result["repositories"].append(repo)
                administrative.update((Path(repo["git_dir"]), Path(repo["common_dir"])))
            elif {"HEAD", "objects", "refs"} <= names:
                unclassified_git.append(path)
                continue
            pending.extend(path / name for name in entries if name != ".git")
        except (OSError, ValueError, _ReadError) as error:
            result["omissions"].append({"path": str(path), "reason": str(error)})
            if reader.entries < 0 or time.monotonic() >= reader.deadline:
                result["omissions"].append(
                    {"reason": "remaining paths unvisited", "count": len(pending)}
                )
                break
    result["omissions"].extend(_unclassified(unclassified_git, administrative))
    result["complete"] = not result["omissions"]
    return result


def _records(data: bytes) -> list[bytes]:
    if data and not data.endswith(b"\0"):
        _fail("truncated Git NUL output")
    return data.split(b"\0")[:-1]


def _path(value: bytes) -> str:
    if not value or value.startswith(b"/") or b".." in value.split(b"/"):
        _fail("invalid Git entry path")
    return os.fsdecode(value)


def _tree(data: bytes) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for record in _records(data):
        header, path = record.split(b"\t", 1)
        mode, kind, oid = header.split(b" ")
        if not _OID.fullmatch(oid):
            _fail("invalid Git tree object identity")
        entries.append(
            {
                "path": _path(path),
                "mode": mode.decode("ascii"),
                "type": kind.decode("ascii"),
                "oid": oid.decode("ascii"),
            }
        )
    return entries


def _index(data: bytes) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for record in _records(data):
        header, path = record.split(b"\t", 1)
        flag, mode, oid, stage = header.split(b" ")
        if not _OID.fullmatch(oid) or stage not in {b"0", b"1", b"2", b"3"}:
            _fail("invalid Git index entry")
        entries.append(
            {
                "path": _path(path),
                "mode": mode.decode("ascii"),
                "oid": oid.decode("ascii"),
                "stage": stage.decode("ascii"),
                "flag": flag.decode("ascii"),
            }
        )
    return entries


def _working(reader: _Reader, root: Path, name: str, oid: str) -> dict[str, Any]:
    path = root / name
    _physical(path.parent)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        _fail("working entry is not a regular file")
    if before.st_size > reader.remaining_bytes:
        _fail("working bytes exceed the total byte limit")
    digest = hashlib.new(
        "sha1" if len(oid) == _SHA1_HEX_LENGTH else "sha256", usedforsecurity=False
    )
    digest.update(b"blob " + str(before.st_size).encode("ascii") + b"\0")
    content_digest = hashlib.sha256()
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    size = 0
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if opened != before:
            _fail("working entry changed before read")
        while True:
            reader.tick()
            chunk = stream.read(min(65536, reader.remaining_bytes + 1))
            reader.remaining_bytes -= len(chunk)
            if reader.remaining_bytes < 0:
                _fail("working bytes exceed the total byte limit")
            if not chunk:
                break
            digest.update(chunk)
            content_digest.update(chunk)
            size += len(chunk)
        after = os.fstat(stream.fileno())
    observed = path.lstat()
    for metadata in (after, observed):
        if any(
            getattr(metadata, field) != getattr(before, field)
            for field in ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
        ):
            _fail("working entry changed during read")
    if size != before.st_size:
        _fail("working entry length changed during read")
    return {
        "path": name,
        "oid": digest.hexdigest(),
        "sha256": content_digest.hexdigest(),
        "mode": "100755" if before.st_mode & stat.S_IXUSR else "100644",
        "bytes": size,
    }


def _working_link(reader: _Reader, root: Path, name: str, oid: str) -> dict[str, Any]:
    path = root / name
    _physical(path.parent)
    if not stat.S_ISLNK(path.lstat().st_mode):
        _fail("working entry is not a symlink")
    target = os.fsencode(path.readlink())
    reader.tick()
    digest = hashlib.new(
        "sha1" if len(oid) == _SHA1_HEX_LENGTH else "sha256", usedforsecurity=False
    )
    digest.update(b"blob " + str(len(target)).encode("ascii") + b"\0" + target)
    return {
        "path": name,
        "oid": digest.hexdigest(),
        "sha256": hashlib.sha256(target).hexdigest(),
        "mode": _SYMLINK,
        "bytes": len(target),
    }


def _checkout(
    reader: _Reader,
    root: Path,
    entries: list[dict[str, str]],
    ref: str,
    commit: str,
) -> dict[str, Any]:
    branch = _line(reader.git(root, "symbolic-ref", "HEAD"))
    head = _line(reader.git(root, "rev-parse", "--verify", "HEAD"))
    index_command = ("ls-files", "--cached", "--stage", "-v", "-z", "--sparse")
    raw_index = reader.git(root, *index_command)
    index = _index(raw_index)
    result: dict[str, Any] = {
        "method": "index-and-working-bytes",
        "branch": branch,
        "head": head,
        "index": index,
        "staged": [],
        "working": [],
        "unstaged": [],
        "unsupported": [],
        "sparse": [],
        "untracked": [],
        "complete": False,
    }
    if branch != ref or head != commit:
        result["unsupported"].append(
            {"reason": "checkout branch or HEAD differs from selected row"}
        )
    tree = {entry["path"]: entry for entry in entries}
    indexed: set[str] = set()
    for entry in index:
        reader.tick()
        name = entry["path"]
        indexed.add(name)
        if entry["stage"] != "0":
            result["unsupported"].append({"path": name, "reason": "unmerged index stage"})
            continue
        if name not in tree or any(tree[name][key] != entry[key] for key in ("mode", "oid")):
            result["staged"].append({"path": name, "reason": "index differs from selected commit"})
        if entry["flag"].upper() == "S" or entry["mode"] == "040000":
            result["sparse"].append({"path": name, "reason": "skip-worktree or sparse index entry"})
        if entry["mode"] not in _REGULAR and entry["mode"] != _SYMLINK:
            result["unsupported"].append({"path": name, "reason": "non-regular index entry"})
            continue
        try:
            link = entry["mode"] == _SYMLINK
            working = (_working_link if link else _working)(reader, root, name, entry["oid"])
            result["working"].append(working)
            if working["oid"] != entry["oid"]:
                reason = (
                    "symlink target differs"
                    if link
                    else "raw bytes differ; edit or content transformation unresolved"
                )
                result["unstaged"].append({"path": name, "reason": reason})
            if working["mode"] != entry["mode"]:
                result["unstaged"].append({"path": name, "reason": "executable mode differs"})
        except (OSError, _ReadError) as error:
            result["unsupported"].append({"path": name, "reason": str(error)})
            if (
                reader.entries < 0
                or reader.remaining_bytes < 0
                or time.monotonic() >= reader.deadline
            ):
                break
    result["staged"].extend(
        {"path": name, "reason": "selected commit path is absent from index"}
        for name in tree
        if name not in indexed
    )
    result["untracked"] = [
        _path(name)
        for name in _records(reader.git(root, "ls-files", "--others", "--exclude-standard", "-z"))
    ]
    if reader.git(root, *index_command) != raw_index:
        result["unsupported"].append({"reason": "index entries changed during validation"})
    if (
        _line(reader.git(root, "symbolic-ref", "HEAD")) != branch
        or _line(reader.git(root, "rev-parse", "--verify", "HEAD")) != head
    ):
        result["unsupported"].append({"reason": "checkout moved during validation"})
    result["complete"] = not any(
        result[key] for key in ("staged", "unstaged", "unsupported", "sparse", "untracked")
    )
    return result


def _boundary_omission(root: Path, boundary: dict[str, str]) -> dict[str, str] | None:
    name = boundary["path"]
    if boundary["mode"] != "160000":
        return {"path": name, "reason": "non-regular tree entry needs separate inspection"}
    try:
        checkout = _physical(root / name)
        marker = (checkout / ".git").lstat()
        if not (stat.S_ISDIR(marker.st_mode) or stat.S_ISREG(marker.st_mode)):
            _fail("unsupported submodule metadata")
    except (OSError, _ReadError) as error:
        return {"path": name, "reason": f"submodule checkout unverified: {error}"}
    return None


def _snapshot(reader: _Reader, args: argparse.Namespace) -> dict[str, Any]:
    result: dict[str, Any] = {"ref": args.ref, "inputs": [], "omissions": []}
    try:
        root = _physical(args.repo)
        result["repository"] = _identity(reader, root)
        if not args.ref.startswith(("refs/heads/", "refs/remotes/")):
            _fail("select an exact refs/heads/ or refs/remotes/ branch")
        reader.git(root, "check-ref-format", args.ref)
        commit = _line(
            reader.git(root, "rev-parse", "--verify", "--end-of-options", args.ref + "^{commit}")
        )
        result["commit"] = commit
        entries = _tree(reader.git(root, "ls-tree", "-r", "-z", "--full-tree", commit))
        result["tree"] = entries
        links = [entry["path"] for entry in entries if entry["mode"] == _SYMLINK]
        result["symlinks"] = links
        result["boundaries"] = [
            entry
            for entry in entries
            if entry["mode"] not in _REGULAR and entry["mode"] != _SYMLINK
        ]
        for boundary in result["boundaries"]:
            omission = _boundary_omission(root, boundary)
            if omission is not None:
                result["omissions"].append(omission)
        selected = {entry["path"]: entry for entry in entries}
        for name in args.read:
            reader.tick()
            if name in links:
                _fail(f"requested input is a symlink; read its target path instead: {name}")
            if name not in selected or selected[name]["mode"] not in _REGULAR:
                _fail(f"requested input is missing or not a regular blob: {name}")
            content = reader.git(root, "cat-file", "blob", selected[name]["oid"])
            result["inputs"].append(
                {
                    **selected[name],
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "base64": base64.b64encode(content).decode("ascii"),
                }
            )
        if args.require_checkout:
            if not args.read:
                _fail("checkout validation requires explicit --read inputs")
            checkout = _checkout(reader, root, entries, args.ref, commit)
            result["checkout"] = checkout
            observed = {item["path"]: item for item in checkout["working"]}
            for item in result["inputs"]:
                if item["path"] in observed:
                    item["working_sha256"] = observed[item["path"]]["sha256"]
            if not checkout["complete"]:
                _fail("checkout is not byte-identical to the selected row; inspect classifications")
        if args.expect_commit is not None and commit != args.expect_commit:
            _fail("branch commit changed; reread inputs and obtain renewed approval")
        if _line(reader.git(root, "rev-parse", "--verify", args.ref + "^{commit}")) != commit:
            _fail("branch moved during snapshot")
    except (OSError, ValueError, _ReadError) as error:
        result["omissions"].append({"reason": str(error)})
    result["complete"] = not result["omissions"]
    return result


def main(argv: list[str] | None = None) -> int:
    """Print read-only JSON evidence; incomplete results return 1."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-entries", type=int, default=100000)
    parser.add_argument("--max-bytes", type=int, default=4 * 1024 * 1024)
    parser.add_argument("--max-seconds", type=float, default=10)
    parser.add_argument("--max-call-seconds", type=float, default=1.0)
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory")
    inventory.add_argument("roots", nargs="+", type=Path)
    inventory.add_argument("--include-dependencies", action="store_true")
    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("--repo", required=True, type=Path)
    snapshot.add_argument("--ref", required=True)
    snapshot.add_argument("--read", action="append", default=[])
    snapshot.add_argument("--expect-commit")
    snapshot.add_argument("--require-checkout", action="store_true")
    args = parser.parse_args(argv)
    limits = (args.max_entries, args.max_bytes, args.max_seconds, args.max_call_seconds)
    if min(limits) <= 0 or not all(math.isfinite(v) for v in limits[2:]):
        parser.error("resource limits must be positive")
    reader = _Reader(*limits)
    result = (
        _inventory(reader, args.roots, include_dependencies=args.include_dependencies)
        if args.command == "inventory"
        else _snapshot(reader, args)
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
