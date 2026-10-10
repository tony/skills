#!/usr/bin/env python3
"""Bind a release commit to its gated bytes and publish it to one approved remote.

Subcommands, each printing one JSON record on stdout:

``inspect``       Show the push endpoint of a remote and the state of the refs.
``worktree-tree`` Hash the tracked working bytes as a tree, to bind to gates.
``verify-commit`` Require HEAD to be the one-parent release commit with that tree.
``tag``           Create an annotated tag at an explicit commit and read it back.
``push-branch``   Push ``<commit>:refs/heads/<branch>`` and read the remote back.
``push-tag``      Push ``<tag-object>:refs/tags/<tag>`` and read the remote back.
``status-branch``, ``status-tag``  Read the remote ref without writing.

Exit status: 0 verified, 1 refused before any write, 2 usage, 3 the push
failed, 4 outcome unverified or unknown (timeout, failed or mismatched readback).

Pushes name the remote, so hooks see its name, and carry one source:destination
refspec, ``--no-follow-tags`` and ``--recurse-submodules=no``. Signing, hooks
and configuration stay the user's; failures are reported, never bypassed.
A refusal or failed push changes no remote ref this script did not name.
"""

# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

_OID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_REMOTE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SECRET_URL = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.-]*)://[^/@]*:[^/@]*@")
_HTTP_USER = re.compile(r"^https?://[^/@]*@", re.IGNORECASE)
_LIMIT = 4000
_REFUSED, _USAGE, _PUSH_FAILED, _UNVERIFIED = 1, 2, 3, 4


class _Run(NamedTuple):
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False


class Refusal(Exception):  # noqa: N818
    """A precondition failed before any write."""


def _git(repo: Path, args: list[str], timeout: float, env: dict[str, str] | None = None) -> _Run:
    argv = ["git", "-C", str(repo), *args]
    child_env = dict(os.environ, GIT_TERMINAL_PROMPT="0", **(env or {}))
    try:
        process = subprocess.Popen(  # noqa: S603
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=child_env,
            start_new_session=True,
        )
    except OSError as error:
        return _Run(None, "", str(error), timed_out=False)
    try:
        out, err = process.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        out, err = process.communicate()
        timed_out = True
    return _Run(
        process.returncode,
        out.decode("utf-8", "replace")[:_LIMIT],
        err.decode("utf-8", "replace")[:_LIMIT],
        timed_out,
    )


def _must(repo: Path, args: list[str], timeout: float, what: str) -> str:
    run = _git(repo, args, timeout)
    if run.returncode != 0 or run.timed_out:
        detail = "timed out" if run.timed_out else run.stderr.strip()
        message = f"{what} failed: {detail}"
        raise Refusal(message)
    return run.stdout


def _oid(value: str, label: str) -> str:
    if not _OID.match(value):
        message = f"{label} must be a full lowercase object id"
        raise Refusal(message)
    return value


def _ref_name(repo: Path, kind: str, name: str, timeout: float) -> str:
    ref = f"refs/{kind}/{name}"
    if name.startswith("-") or _git(repo, ["check-ref-format", ref], timeout).returncode != 0:
        message = f"{name!r} is not a valid {kind[:-1]} name"
        raise Refusal(message)
    return ref


def push_url(repo: Path, remote: str, timeout: float) -> str:
    """Return the single effective push URL of ``remote`` or raise Refusal."""
    if not _REMOTE.match(remote):
        message = f"{remote!r} is not a plain remote name"
        raise Refusal(message)
    urls = _must(repo, ["remote", "get-url", "--push", "--all", remote], timeout, "push URL").split(
        "\n"
    )
    urls = [url for url in urls if url]
    if len(urls) != 1:
        message = f"remote {remote} has {len(urls)} push URLs; exactly one is supported"
        raise Refusal(message)
    url = urls[0]
    if _SECRET_URL.match(url) or _HTTP_USER.match(url):
        message = "the push URL embeds credentials; use a credential helper or SSH key"
        raise Refusal(message)
    config = _git(
        repo,
        [
            "config",
            "--get-regexp",
            rf"^(push\.pushoption|remote\.{re.escape(remote)}\.(mirror|pushoption))$",
        ],
        timeout,
    )
    if config.returncode not in (0, 1) or config.timed_out:
        message = "could not read the push configuration"
        raise Refusal(message)
    for line in config.stdout.splitlines():
        key, _, value = line.partition(" ")
        if key.endswith("pushoption") or value.lower() in ("true", "yes", "on", "1"):
            message = f"configuration {key} changes what a push sends"
            raise Refusal(message)
    rewritten = _must(repo, ["ls-remote", "--get-url", url], timeout, "URL rewrite check").strip()
    if rewritten != url:
        message = (
            "a URL rewrite rule applies to the push URL, so readback would use another endpoint"
        )
        raise Refusal(message)
    return url


def _remote_refs(
    repo: Path, url: str, patterns: list[str], timeout: float
) -> tuple[str, dict[str, str]]:
    """Return ("ok"|"error", ref -> oid) for exact ref names from ``ls-remote``."""
    run = _git(repo, ["ls-remote", "--", url, *patterns], timeout)
    if run.returncode != 0 or run.timed_out:
        return "error", {}
    refs: dict[str, str] = {}
    for line in run.stdout.splitlines():
        oid, _, ref = line.partition("\t")
        if ref in patterns:
            refs[ref] = oid
    return "ok", refs


def _local_oid(repo: Path, rev: str, timeout: float) -> str | None:
    run = _git(repo, ["rev-parse", "--verify", "--quiet", rev], timeout)
    return run.stdout.strip() if run.returncode == 0 and not run.timed_out else None


def inspect(repo: Path, remote: str, timeout: float) -> dict[str, object]:
    """Describe the remote's push endpoint and the repository's HEAD."""
    url = push_url(repo, remote, timeout)
    fetch = _must(repo, ["remote", "get-url", remote], timeout, "fetch URL").strip()
    head = _local_oid(repo, "HEAD^{commit}", timeout)
    branch = _git(repo, ["symbolic-ref", "-q", "HEAD"], timeout).stdout.strip()
    return {
        "outcome": "inspected",
        "remote": remote,
        "push_url": url,
        "fetch_url": fetch,
        "same_endpoint": url == fetch,
        "head": head,
        "head_ref": branch,
    }


def worktree_tree(repo: Path, also: list[str], timeout: float) -> dict[str, object]:
    """Hash the tracked working-tree bytes (plus ``also`` paths) without touching the index."""
    top = Path(_must(repo, ["rev-parse", "--show-toplevel"], timeout, "toplevel").strip())
    with tempfile.TemporaryDirectory() as scratch:
        env = {"GIT_INDEX_FILE": str(Path(scratch) / "index")}
        steps = [["read-tree", "HEAD"], ["add", "-u", "--", ":/"]]
        steps += [["add", "--", path] for path in also]
        for step in steps:
            run = _git(top, step, timeout, env)
            if run.returncode != 0 or run.timed_out:
                message = f"git {step[0]} failed: {run.stderr.strip()}"
                raise Refusal(message)
        run = _git(top, ["write-tree"], timeout, env)
    if run.returncode != 0 or run.timed_out:
        message = f"git write-tree failed: {run.stderr.strip()}"
        raise Refusal(message)
    return {"outcome": "hashed", "tree": run.stdout.strip()}


def verify_commit(
    repo: Path, parent: str, tree: str, branch: str, timeout: float
) -> tuple[dict[str, object], int]:
    """Require HEAD to be a one-parent commit on ``branch`` with ``tree`` and no tracked changes."""
    _oid(parent, "--parent")
    _oid(tree, "--tree")
    ref = _ref_name(repo, "heads", branch, timeout)
    head = _local_oid(repo, "HEAD^{commit}", timeout)
    current = _git(repo, ["symbolic-ref", "-q", "HEAD"], timeout).stdout.strip()
    parents = _must(repo, ["rev-list", "--parents", "-n", "1", "HEAD"], timeout, "rev-list").split()
    committed = _local_oid(repo, "HEAD^{tree}", timeout)
    status = _must(
        repo, ["status", "--porcelain=v1", "-z", "--untracked-files=no"], timeout, "status"
    )
    record: dict[str, object] = {"commit": head, "tree": committed, "parents": parents[1:]}
    if current != ref or head is None:
        return {**record, "outcome": "refused", "reason": f"HEAD is not on {ref}"}, _REFUSED
    if parents[1:] != [parent]:
        return {
            **record,
            "outcome": "refused",
            "reason": "HEAD is not a single commit on the recorded synchronized base",
        }, _REFUSED
    if status:
        return {
            **record,
            "outcome": "refused",
            "reason": "tracked files differ from HEAD",
        }, _REFUSED
    if committed != tree:
        return {
            **record,
            "outcome": "tree-differs",
            "reason": (
                "the committed tree differs from the gated tree; rerun every required gate "
                "against the committed tree before tagging or pushing"
            ),
        }, _REFUSED
    return {**record, "outcome": "verified"}, 0


def tag(repo: Path, name: str, commit: str, timeout: float) -> tuple[dict[str, object], int]:
    """Create an annotated tag at ``commit`` and read its object and target back."""
    ref = _ref_name(repo, "tags", name, timeout)
    _oid(commit, "--commit")
    if _local_oid(repo, ref, timeout) is not None:
        message = f"{ref} already exists locally; it is never moved or reused"
        raise Refusal(message)
    if _git(repo, ["cat-file", "-e", f"{commit}^{{commit}}"], timeout).returncode != 0:
        message = "--commit is not a commit in this repository"
        raise Refusal(message)
    run = _git(repo, ["tag", "-a", name, "-m", name, commit], timeout)
    if run.returncode != 0 or run.timed_out:
        return {
            "outcome": "tag-failed",
            "reason": "timed out" if run.timed_out else run.stderr.strip(),
            "tag_created": _local_oid(repo, ref, timeout) is not None,
        }, _PUSH_FAILED
    obj = _local_oid(repo, ref, timeout)
    peeled = _local_oid(repo, f"{ref}^{{commit}}", timeout)
    kind = _git(repo, ["cat-file", "-t", ref], timeout).stdout.strip()
    ok = obj is not None and kind == "tag" and peeled == commit
    return {
        "outcome": "tagged" if ok else "tag-mismatch",
        "tag": name,
        "tag_object": obj,
        "commit": peeled,
    }, 0 if ok else _UNVERIFIED


class Target(NamedTuple):
    """One ref to publish: ``kind`` is ``heads`` or ``tags``."""

    remote: str
    approved_url: str
    kind: str
    name: str
    commit: str
    tag_object: str | None

    @property
    def ref(self) -> str:
        """Full destination ref name."""
        return f"refs/{self.kind}/{self.name}"

    @property
    def source(self) -> str:
        """Object id pushed: the commit for a branch, the tag object for a tag."""
        return self.commit if self.kind == "heads" else self.tag_object or ""

    def matches(self, refs: dict[str, str]) -> bool:
        """Whether ``refs`` hold exactly this target (tag: object and peeled commit)."""
        if refs.get(self.ref) != self.source:
            return False
        return self.kind == "heads" or refs.get(self.ref + "^{}") == self.commit


def _observe(repo: Path, url: str, target: Target, timeout: float) -> tuple[str, dict[str, str]]:
    ref = target.ref
    return _remote_refs(repo, url, [ref, ref + "^{}"] if target.kind == "tags" else [ref], timeout)


def _preflight(
    repo: Path, target: Target, timeout: float, *, write: bool
) -> tuple[str, dict[str, str]]:
    """Validate the target against local and remote state; return the URL and remote refs."""
    _ref_name(repo, target.kind, target.name, timeout)
    _oid(target.commit, "--commit")
    _oid(target.source, "--tag-object" if target.kind == "tags" else "--commit")
    url = push_url(repo, target.remote, timeout)
    if url != target.approved_url:
        message = "the push URL differs from the approved URL"
        raise Refusal(message)
    local = _local_oid(repo, target.ref, timeout)
    if target.kind == "heads" and write and local != target.commit:
        message = f"local {target.ref} is not the release commit"
        raise Refusal(message)
    if target.kind == "tags" and (
        local != target.source
        or _local_oid(repo, f"{target.ref}^{{commit}}", timeout) != target.commit
    ):
        message = f"local {target.ref} is not the recorded tag object at the release commit"
        raise Refusal(message)
    state, before = _observe(repo, url, target, timeout)
    if state == "error":
        message = "the remote ref could not be read, so its absence is unconfirmed"
        raise Refusal(message)
    if write and target.kind == "tags" and target.ref in before and not target.matches(before):
        message = f"the remote already has a different {target.ref}; it is never overwritten"
        raise Refusal(message)
    return url, before


def publish(
    repo: Path, target: Target, timeout: float, *, write: bool = True
) -> tuple[dict[str, object], int]:
    """Push one ref (``write``) or only read it back, then verify the remote."""
    url, before = _preflight(repo, target, timeout, write=write)
    record: dict[str, object] = {
        "remote": target.remote,
        "push_url": url,
        "ref": target.ref,
        "source": target.source,
    }
    if write and target.matches(before):
        return {**record, "outcome": "already-published", "remote_refs": before}, 0
    pushed = None
    if write:
        args = ["push", "--no-follow-tags", "--recurse-submodules=no", target.remote]
        pushed = _git(repo, [*args, f"{target.source}:{target.ref}"], timeout)
        record["push"] = {
            "returncode": pushed.returncode,
            "timed_out": pushed.timed_out,
            "stderr": pushed.stderr.strip(),
        }
    state, after = _observe(repo, url, target, timeout)
    record["remote_refs"] = after
    if state == "error":
        return {**record, "outcome": "unverified", "reason": "readback failed"}, _UNVERIFIED
    verified = target.matches(after)
    if pushed is not None and pushed.timed_out:
        return {**record, "outcome": "unknown", "remote_matches": verified}, _UNVERIFIED
    if pushed is not None and pushed.returncode != 0:
        return {**record, "outcome": "push-failed", "remote_matches": verified}, _PUSH_FAILED
    if not verified:
        return {**record, "outcome": "unverified", "reason": "remote ref differs"}, _UNVERIFIED
    return {**record, "outcome": "verified" if write else "present"}, 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--repo", type=Path, default=Path())
    parser.add_argument("--timeout", type=float, default=120.0)
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, *flags: str) -> argparse.ArgumentParser:
        child = sub.add_parser(name)
        for flag in flags:
            child.add_argument(flag, required=True)
        return child

    add("inspect", "--remote")
    add("worktree-tree").add_argument("--also", action="append", default=[])
    add("verify-commit", "--parent", "--tree", "--branch")
    add("tag", "--tag", "--commit")
    for name in ("push-branch", "status-branch"):
        add(name, "--remote", "--branch", "--commit", "--approved-url")
    for name in ("push-tag", "status-tag"):
        add(name, "--remote", "--tag", "--commit", "--tag-object", "--approved-url")
    return parser


def _dispatch(args: argparse.Namespace) -> tuple[dict[str, object], int]:
    repo, timeout, cmd = args.repo, args.timeout, args.command
    if cmd == "inspect":
        return inspect(repo, args.remote, timeout), 0
    if cmd == "worktree-tree":
        return worktree_tree(repo, args.also, timeout), 0
    if cmd == "verify-commit":
        return verify_commit(repo, args.parent, args.tree, args.branch, timeout)
    if cmd == "tag":
        return tag(repo, args.tag, args.commit, timeout)
    kind = "heads" if cmd.endswith("branch") else "tags"
    target = Target(
        args.remote,
        args.approved_url,
        kind,
        args.branch if kind == "heads" else args.tag,
        args.commit,
        None if kind == "heads" else args.tag_object,
    )
    return publish(repo, target, timeout, write=cmd.startswith("push"))


def main(argv: list[str]) -> int:
    """Run the command line; return the exit status."""
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exit_error:
        return _USAGE if exit_error.code else 0
    try:
        record, status = _dispatch(args)
    except Refusal as refusal:
        record, status = {"outcome": "refused", "reason": str(refusal)}, _REFUSED
    sys.stdout.write(json.dumps(record, indent=2) + "\n")
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
