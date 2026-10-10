"""Publication and identity checks against owned bare remotes."""

# ruff: noqa: S101, INP001, D103, PLR2004, S603, S607
# pyright: reportAny=false, reportExplicitAny=false, reportUnusedCallResult=false
from __future__ import annotations

import io
import json
import os
import stat
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

import publish  # pyright: ignore[reportImplicitRelativeImport]
import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.integration


class Fixture(NamedTuple):
    """An owned working repository with two bare remotes."""

    root: Path
    work: Path
    origin: Path
    other: Path


@pytest.fixture(autouse=True)
def _git_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in list(os.environ):
        if key.startswith("GIT_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for who in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{who}_NAME", "Fixture")
        monkeypatch.setenv(f"GIT_{who}_EMAIL", "fixture@example.invalid")


def git(repo: Path, *args: str, check: bool = True) -> str:
    run = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    if check and run.returncode:
        raise AssertionError(run.stderr)
    return run.stdout.strip()


def cli(repo: Path, *args: str) -> tuple[int, dict[str, Any]]:
    out = io.StringIO()
    with redirect_stdout(out):
        status = publish.main(["--repo", str(repo), "--timeout", "30", *args])
    return status, json.loads(out.getvalue())


@pytest.fixture
def fx(tmp_path: Path) -> Fixture:
    origin, other, work = tmp_path / "origin.git", tmp_path / "other.git", tmp_path / "work"
    for bare in (origin, other):
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    (work / "version.txt").write_text("1\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "base")
    git(work, "remote", "add", "origin", str(origin))
    git(work, "push", "-q", "origin", "main")
    return Fixture(tmp_path, work, origin, other)


def release_commit(fx: Fixture, *, content: str = "2\n") -> tuple[str, str]:
    base = git(fx.work, "rev-parse", "HEAD")
    (fx.work / "version.txt").write_text(content)
    git(fx.work, "add", "version.txt")
    git(fx.work, "commit", "-q", "-m", "Tag v2")
    return base, git(fx.work, "rev-parse", "HEAD")


def tag(fx: Fixture, commit: str) -> str:
    status, record = cli(fx.work, "tag", "--tag", "v2", "--commit", commit)
    assert status == 0, record
    return str(record["tag_object"])


def branch_args(fx: Fixture, commit: str, url: Path | str | None = None) -> list[str]:
    return [
        "--remote", "origin", "--branch", "main", "--commit", commit,
        "--approved-url", str(url or fx.origin),
    ]  # fmt: skip


def tag_args(fx: Fixture, commit: str, obj: str, url: Path | str | None = None) -> list[str]:
    return [
        "--remote", "origin", "--tag", "v2", "--commit", commit, "--tag-object", obj,
        "--approved-url", str(url or fx.origin),
    ]  # fmt: skip


def refs(bare: Path) -> dict[str, str]:
    lines = git(bare, "for-each-ref", "--format=%(objectname) %(refname)").splitlines()
    return {line.split(" ")[1]: line.split(" ")[0] for line in lines}


def test_branch_push_ignores_tag_mappings_and_follow_tags(fx: Fixture) -> None:
    git(fx.work, "config", "remote.origin.push", "refs/tags/*:refs/tags/*")
    git(fx.work, "config", "push.followTags", "true")
    _, commit = release_commit(fx)
    tag(fx, commit)
    status, record = cli(fx.work, "push-branch", *branch_args(fx, commit))
    assert status == 0, record
    assert record["outcome"] == "verified"
    assert refs(fx.origin) == {"refs/heads/main": commit}


def test_tag_push_uses_explicit_destination_and_reads_object_and_peeled(fx: Fixture) -> None:
    git(fx.work, "config", "remote.origin.push", "refs/tags/v2:refs/tags/different-name")
    base, commit = release_commit(fx)
    obj = tag(fx, commit)
    status, record = cli(fx.work, "push-tag", *tag_args(fx, commit, obj))
    assert status == 0, record
    assert refs(fx.origin) == {"refs/heads/main": base, "refs/tags/v2": obj}
    assert record["remote_refs"] == {"refs/tags/v2": obj, "refs/tags/v2^{}": commit}


def test_distinct_pushurl_is_the_approved_endpoint(fx: Fixture) -> None:
    git(fx.work, "config", "remote.origin.pushurl", str(fx.other))
    _, commit = release_commit(fx)
    status, record = cli(fx.work, "push-branch", *branch_args(fx, commit))
    assert status == 1
    assert "differs from the approved URL" in record["reason"]
    status, shown = cli(fx.work, "inspect", "--remote", "origin")
    assert shown["push_url"] == str(fx.other)
    assert shown["same_endpoint"] is False
    status, record = cli(fx.work, "push-branch", *branch_args(fx, commit, fx.other))
    assert status == 0, record
    assert refs(fx.other) == {"refs/heads/main": commit}
    assert refs(fx.origin)["refs/heads/main"] != commit


def test_multiple_push_urls_refuse_before_any_write(fx: Fixture) -> None:
    git(fx.work, "config", "--add", "remote.origin.pushurl", str(fx.origin))
    git(fx.work, "config", "--add", "remote.origin.pushurl", str(fx.other))
    _, commit = release_commit(fx)
    status, record = cli(fx.work, "push-branch", *branch_args(fx, commit))
    assert status == 1
    assert "2 push URLs" in record["reason"]
    assert refs(fx.other) == {}


@pytest.mark.parametrize(
    ("setting", "value", "reason"),
    [
        ("url.file:///elsewhere/.pushInsteadOf", "ZZ", None),
        ("remote.origin.mirror", "true", "changes what a push sends"),
        ("push.pushOption", "ci.skip", "changes what a push sends"),
    ],
)
def test_unsafe_configuration_refuses(
    fx: Fixture, setting: str, value: str, reason: str | None
) -> None:
    git(fx.work, "config", setting, value)
    if reason is None:
        git(fx.work, "config", "remote.origin.url", "ZZ" + str(fx.origin))
        git(fx.work, "config", "url.file://.pushInsteadOf", "ZZ")
        git(fx.work, "config", "--unset", "url.file:///elsewhere/.pushInsteadOf")
    _, commit = release_commit(fx)
    status, record = cli(fx.work, "push-branch", *branch_args(fx, commit))
    assert status == 1, record
    assert reason is None or reason in record["reason"]
    assert refs(fx.origin)["refs/heads/main"] != commit


def test_credentials_in_url_refuse(fx: Fixture) -> None:
    git(fx.work, "config", "remote.origin.url", "https://user:secret@example.invalid/r.git")
    status, record = cli(fx.work, "inspect", "--remote", "origin")
    assert status == 1
    assert "secret" not in json.dumps(record)


def test_same_subject_wrong_commit_and_hook_changed_tree_are_refused(fx: Fixture) -> None:
    status, gated = cli(fx.work, "worktree-tree")
    assert status == 0
    base = git(fx.work, "rev-parse", "HEAD")
    (fx.work / "version.txt").write_text("2\n")
    status, gated = cli(fx.work, "worktree-tree")
    git(fx.work, "add", "version.txt")
    hook = fx.work / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nprintf 9 > version.txt\ngit add version.txt\n")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    git(fx.work, "commit", "-q", "-m", "Tag v2")
    status, record = cli(
        fx.work, "verify-commit", "--parent", base, "--tree", gated["tree"], "--branch", "main"
    )
    assert status == 1
    assert record["outcome"] == "tree-differs"
    status, record = cli(
        fx.work, "verify-commit", "--parent", "0" * 40, "--tree", record["tree"], "--branch", "main"
    )
    assert status == 1
    assert "synchronized base" in record["reason"]


def test_verified_commit_binds_gated_bytes(fx: Fixture) -> None:
    base = git(fx.work, "rev-parse", "HEAD")
    (fx.work / "version.txt").write_text("2\n")
    _, gated = cli(fx.work, "worktree-tree")
    git(fx.work, "add", "version.txt")
    git(fx.work, "commit", "-q", "-m", "Tag v2")
    status, record = cli(
        fx.work, "verify-commit", "--parent", base, "--tree", gated["tree"], "--branch", "main"
    )
    assert status == 0, record
    (fx.work / "stray.txt").write_text("x")
    status, record = cli(
        fx.work, "verify-commit", "--parent", base, "--tree", gated["tree"], "--branch", "main"
    )
    assert status == 1
    assert record["reason"] == "the tree is not clean"


def test_rejected_push_and_failing_hook_report_failure_without_moving_remote(fx: Fixture) -> None:
    other = fx.root / "clone"
    subprocess.run(["git", "clone", "-q", str(fx.origin), str(other)], check=True)
    (other / "x").write_text("x")
    git(other, "add", "x")
    git(other, "commit", "-q", "-m", "diverge")
    git(other, "push", "-q", "origin", "main")
    before = refs(fx.origin)
    _, commit = release_commit(fx)
    status, record = cli(fx.work, "push-branch", *branch_args(fx, commit))
    assert status == 3
    assert record["outcome"] == "push-failed"
    assert refs(fx.origin) == before

    hook = fx.work / ".git" / "hooks" / "pre-push"
    hook.write_text('#!/bin/sh\necho "hook refused $1" >&2\nexit 1\n')
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    status, record = cli(fx.work, "push-branch", *branch_args(fx, commit))
    assert status == 3
    assert "hook refused origin" in record["push"]["stderr"]
    assert refs(fx.origin) == before


def test_unreadable_remote_is_not_absence(fx: Fixture) -> None:
    gone = fx.root / "gone.git"
    git(fx.work, "config", "remote.origin.url", str(gone))
    _, commit = release_commit(fx)
    status, record = cli(fx.work, "push-branch", *branch_args(fx, commit, gone))
    assert status == 1
    assert "unconfirmed" in record["reason"]


def test_signing_failure_creates_no_tag(fx: Fixture) -> None:
    git(fx.work, "config", "tag.gpgSign", "true")
    git(fx.work, "config", "gpg.program", "/bin/false")
    _, commit = release_commit(fx)
    status, record = cli(fx.work, "tag", "--tag", "v2", "--commit", commit)
    assert status == 3
    assert record["outcome"] == "tag-failed"
    assert record["tag_created"] is False


def test_existing_tags_are_never_adopted_or_overwritten(fx: Fixture) -> None:
    _, commit = release_commit(fx)
    git(fx.work, "tag", "-a", "v2", "-m", "old", "HEAD~1")
    status, record = cli(fx.work, "tag", "--tag", "v2", "--commit", commit)
    assert status == 1
    assert "already exists" in record["reason"]
    git(fx.work, "tag", "-d", "v2")
    obj = tag(fx, commit)
    git(fx.work, "push", "-q", "origin", f"{commit}:refs/tags/v2")
    status, record = cli(fx.work, "push-tag", *tag_args(fx, commit, obj))
    assert status == 1
    assert "different" in record["reason"]


def test_republish_of_verified_ref_is_idempotent_and_status_is_read_only(fx: Fixture) -> None:
    _, commit = release_commit(fx)
    assert cli(fx.work, "push-branch", *branch_args(fx, commit))[0] == 0
    status, record = cli(fx.work, "push-branch", *branch_args(fx, commit))
    assert (status, record["outcome"]) == (0, "already-published")
    status, record = cli(fx.work, "status-branch", *branch_args(fx, commit))
    assert (status, record["outcome"]) == (0, "present")


def test_validators_reject_malformed_input(fx: Fixture) -> None:
    status, record = cli(fx.work, "tag", "--tag", "v2", "--commit", "HEAD")
    assert status == 1
    assert "object id" in record["reason"]
    status, record = cli(fx.work, "inspect", "--remote", "bad name")
    assert status == 1
    assert publish.main(["bogus"]) == 2


def test_worktree_tree_leaves_index_untouched(fx: Fixture) -> None:
    (fx.work / "version.txt").write_text("changed\n")
    before = git(fx.work, "diff", "--cached", "--name-only")
    status, record = cli(fx.work, "worktree-tree")
    assert status == 0
    assert git(fx.work, "diff", "--cached", "--name-only") == before == ""
    assert git(fx.work, "cat-file", "-t", record["tree"]) == "tree"


def test_helper_is_executable() -> None:
    mode: Callable[[Path], int] = lambda p: p.stat().st_mode  # noqa: E731
    assert mode(Path(publish.__file__)) & stat.S_IXUSR
