"""Critical branch discovery and non-converting checkout checks."""

# ruff: noqa: S101, INP001, D103, SLF001, PLR2004
# pyright: reportAny=false, reportExplicitAny=false, reportUnusedCallResult=false
# pyright: reportPrivateUsage=false
import argparse
import base64
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import consumer_inventory as inventory  # pyright: ignore[reportImplicitRelativeImport]
import pytest


def _reader(entries: int = 10000, byte_limit: int = 4 * 1024 * 1024) -> inventory._Reader:
    return inventory._Reader(entries, byte_limit, 10)


def _snapshot(
    repo: Path,
    branch: str = "main",
    *,
    read: list[str] | None = None,
    require_checkout: bool = False,
    expect_commit: str | None = None,
) -> dict[str, Any]:
    args = argparse.Namespace(
        repo=repo,
        ref="refs/heads/" + branch,
        read=["package.json", "AGENTS.md"] if read is None else read,
        require_checkout=require_checkout,
        expect_commit=expect_commit,
    )
    return inventory._snapshot(_reader(), args)


def _git(repo: Path, *args: str) -> bytes:
    executable = shutil.which("git")
    assert executable is not None
    return subprocess.run(  # noqa: S603
        [executable, *args],
        cwd=repo,
        capture_output=True,
        check=True,
        timeout=1,
    ).stdout


@pytest.fixture
def git_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("GIT_"):
            monkeypatch.delenv(key)
    for key, value in {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_AUTHOR_NAME": "Fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": "2026-10-09T00:00:00Z",
        "GIT_COMMITTER_DATE": "2026-10-09T00:00:00Z",
    }.items():
        monkeypatch.setenv(key, value)


def _repo(path: Path, metadata: Path | None = None) -> None:
    path.mkdir(parents=True)
    separate = [] if metadata is None else ["--separate-git-dir", str(metadata)]
    _git(path, "init", "--template=", "--initial-branch=main", *separate)
    (path / "package.json").write_bytes(b'{"dependencies":{"example-pkg":"1.0"}}\n')
    (path / "AGENTS.md").write_bytes(b"Run the main gate.\n")
    (path / ".gitignore").write_bytes(b"user.keep\n")
    (path / "user.keep").write_bytes(b"ignored bytes\n")
    _git(path, "add", "--", "package.json", "AGENTS.md", ".gitignore")
    _git(path, "commit", "-m", "base")


def _files(root: Path) -> dict[str, object]:
    found: dict[str, object] = {}
    pending = [root]
    while pending:
        path = pending.pop()
        metadata = path.lstat()
        if stat.S_ISDIR(metadata.st_mode):
            with os.scandir(path) as listing:
                pending.extend(Path(entry.path) for entry in listing)
            content: bytes | str | None = None
        elif stat.S_ISLNK(metadata.st_mode):
            content = str(path.readlink())
        elif stat.S_ISREG(metadata.st_mode):
            content = path.read_bytes()
        else:
            pytest.fail(f"unsupported observation entry: {path}")
        found[str(path.relative_to(root))] = (
            metadata.st_mode,
            metadata.st_ino,
            metadata.st_nlink,
            content,
        )
    return found


def test_nul_parsers_preserve_bytes_and_reject_truncation() -> None:
    oid = b"a" * 40
    path = b"nested/name\n\xff.toml"
    tree = inventory._tree(b"100644 blob " + oid + b"\t" + path + b"\0")
    index = inventory._index(b"h 100644 " + oid + b" 0\t" + path + b"\0")
    assert index[0]["flag"] == "h"
    assert os.fsencode(tree[0]["path"]) == os.fsencode(index[0]["path"]) == path
    assert os.fsencode(json.loads(json.dumps(tree))[0]["path"]) == path
    with pytest.raises(inventory._ReadError, match="truncated"):
        inventory._tree(b"100644 blob " + oid + b"\t" + path)


def test_limits_bound_files_and_git_without_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "large").write_bytes(b"1234")
    before = _files(tmp_path)
    with pytest.raises(inventory._ReadError, match="byte limit"):
        inventory._working(_reader(byte_limit=3), root, "large", "a" * 40)
    assert not inventory._inventory(_reader(entries=1), [root])["complete"]
    monkeypatch.setenv("GIT_DIR", str(root))
    with pytest.raises(inventory._ReadError, match="environment"):
        _reader().git(root, "rev-parse", "HEAD")
    assert _files(tmp_path) == before


def test_deadline_and_stat_failure_are_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deadlines: list[float] = []

    def execute(
        _argv: list[str],
        _cwd: Path,
        _env: dict[str, str],
        _limit: int,
        deadline: float,
    ) -> bytes:
        deadlines.append(deadline)
        return b""

    def refuse(_path: Path) -> os.stat_result:
        raise PermissionError

    monkeypatch.setattr(time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(inventory, "_execute", execute)
    inventory._Reader(100, 100, 0.25).git(tmp_path, "rev-parse", "HEAD")
    assert deadlines == [100.25]
    monkeypatch.setattr(Path, "lstat", refuse)
    assert not inventory._inventory(_reader(), [tmp_path])["complete"]
    with pytest.raises(PermissionError):
        _files(tmp_path)


@pytest.mark.integration(
    reason="a successful subprocess with a read warning must remain incomplete"
)
def test_successful_read_with_diagnostics_is_not_complete(tmp_path: Path) -> None:
    before = _files(tmp_path)
    with pytest.raises(inventory._ReadError, match="exited 0 with diagnostic: warning: unreadable"):
        inventory._execute(
            [sys.executable, "-c", "import sys; sys.stderr.write('warning: unreadable directory')"],
            tmp_path,
            dict(os.environ),
            1024,
            time.monotonic() + 1,
        )
    assert _files(tmp_path) == before


@pytest.mark.integration(reason="reads committed deep, separate-Git and maintained-worktree inputs")
def test_inventory_preserves_branch_only_and_separate_roots(
    tmp_path: Path,
    git_environment: None,
) -> None:
    del git_environment
    repo = tmp_path / ".hidden/nested/deep/primary"
    separate = tmp_path / "separate\ncheckout"
    linked = tmp_path / "maintained"
    _repo(repo)
    _repo(separate, tmp_path / "metadata")
    _git(repo, "checkout", "-b", "maintenance")
    (repo / "packages/deep/widget").mkdir(parents=True)
    manifest = "packages/deep/widget/package.json"
    (repo / manifest).write_bytes(b'{"dependencies":{"branch-only":"2.0"}}\n')
    (repo / "AGENTS.md").write_bytes(b"Run the maintenance gate.\n")
    _git(repo, "add", "--", manifest, "AGENTS.md")
    _git(repo, "commit", "-m", "maintained inputs")
    _git(repo, "checkout", "main")
    _git(repo, "worktree", "add", str(linked), "maintenance")
    before = _files(tmp_path)
    rows = inventory._inventory(_reader(), [tmp_path, linked])
    assert rows["complete"], rows
    assert {row["root"] for row in rows["repositories"]} == {str(repo), str(separate), str(linked)}
    assert len({row["common_dir"] for row in rows["repositories"]}) == 2
    main = _snapshot(repo)
    maintenance = _snapshot(repo, "maintenance", read=[manifest, "AGENTS.md"])
    assert main["complete"]
    assert maintenance["complete"]
    assert main["commit"] != maintenance["commit"]
    assert b"branch-only" in base64.b64decode(maintenance["inputs"][0]["base64"])
    assert _snapshot(linked, "maintenance", require_checkout=True)["complete"]
    assert _files(tmp_path) == before
    scope = inventory._inventory(_reader(), [linked])
    assert [row["root"] for row in scope["repositories"]] == [str(linked)]


@pytest.mark.integration(reason="verifies immutable approval and actual hidden working bytes")
def test_approval_staged_and_hidden_working_changes(
    tmp_path: Path,
    git_environment: None,
) -> None:
    del git_environment
    repo = tmp_path / "consumer"
    _repo(repo)
    approved = _snapshot(repo)
    before = _files(tmp_path)
    unchanged = _snapshot(repo, expect_commit=approved["commit"], require_checkout=True)
    assert unchanged["complete"], unchanged
    assert _files(tmp_path) == before
    (repo / "AGENTS.md").write_bytes(b"Run a fresh gate.\n")
    _git(repo, "add", "--", "AGENTS.md")
    before = _files(tmp_path)
    staged = _snapshot(repo, require_checkout=True)
    assert not staged["complete"]
    assert staged["checkout"]["staged"][0]["path"] == "AGENTS.md"
    assert _files(tmp_path) == before
    _git(repo, "commit", "-m", "new gate")
    changed = _snapshot(repo, expect_commit=approved["commit"], require_checkout=True)
    assert not changed["complete"]
    assert "approval" in changed["omissions"][0]["reason"]
    _git(repo, "update-index", "--assume-unchanged", "AGENTS.md")
    (repo / "AGENTS.md").write_bytes(b"Hidden gate edit.\n")
    before = _files(tmp_path)
    hidden = _snapshot(repo, require_checkout=True)
    assert not hidden["complete"]
    assert hidden["checkout"]["unstaged"][0]["path"] == "AGENTS.md"
    assert _files(tmp_path) == before
    _git(repo, "update-index", "--skip-worktree", "AGENTS.md")
    before = _files(tmp_path)
    sparse = _snapshot(repo, require_checkout=True)
    assert not sparse["complete"]
    assert sparse["checkout"]["sparse"]
    assert sparse["checkout"]["unstaged"][0]["path"] == "AGENTS.md"
    assert _files(tmp_path) == before


@pytest.mark.integration(
    reason="checks applicable and unused filters with whole-fixture preservation"
)
def test_filter_rows_validate_without_executing_conversion(
    tmp_path: Path,
    git_environment: None,
) -> None:
    del git_environment
    repo = tmp_path / "consumer"
    _repo(repo)
    target = repo / "tracked.txt"
    target.write_bytes(b"first contents\n")
    (repo / ".gitattributes").write_bytes(b"tracked.txt filter=identity\n")
    _git(repo, "add", "--", "tracked.txt", ".gitattributes")
    _git(repo, "commit", "-m", "filter target")
    sentinel = tmp_path / "filter-invoked"
    driver = tmp_path / "filter.sh"
    driver.write_text(f'#!/bin/sh\nprintf invoked > "{sentinel}"\ncat\n')
    driver.chmod(0o755)
    _git(repo, "config", "filter.identity.clean", str(driver))
    _git(repo, "config", "filter.identity.required", "true")
    _git(repo, "config", "filter.unused.process", str(driver))
    assert (
        _git(repo, "check-attr", "filter", "--", "tracked.txt")
        == b"tracked.txt: filter: identity\n"
    )
    metadata = target.stat()
    os.utime(target, ns=(metadata.st_atime_ns, metadata.st_mtime_ns + 2_000_000_000))
    before = _files(tmp_path)
    clean = _snapshot(repo, require_checkout=True)
    assert clean["complete"], clean
    assert _files(tmp_path) == before
    assert not sentinel.exists()
    target.write_bytes(b"other contents\n")
    assert len(target.read_bytes()) == len(b"first contents\n")
    before = _files(tmp_path)
    changed = _snapshot(repo, require_checkout=True)
    assert not changed["complete"]
    assert changed["checkout"]["unstaged"][0]["path"] == "tracked.txt"
    assert _files(tmp_path) == before
    assert not sentinel.exists()
    _git(repo, "config", "filter.identity.process", str(driver))
    before = _files(tmp_path)
    process = _snapshot(repo, require_checkout=True)
    assert not process["complete"]
    assert _files(tmp_path) == before


@pytest.mark.integration(
    reason="classifies transformed bytes and executable modes without normalization"
)
def test_transformed_bytes_and_modes_are_not_claimed_equal(
    tmp_path: Path,
    git_environment: None,
) -> None:
    del git_environment
    repo = tmp_path / "consumer"
    _repo(repo)
    target = repo / "AGENTS.md"
    target.write_bytes(b"Run the main gate.\r\n")
    _git(repo, "config", "core.autocrlf", "true")
    before = _files(tmp_path)
    result = _snapshot(repo, require_checkout=True)
    assert not result["complete"]
    assert "transformation" in result["checkout"]["unstaged"][0]["reason"]
    assert _files(tmp_path) == before
    target.write_bytes(b"Run the main gate.\n")
    target.chmod(0o755)
    before = _files(tmp_path)
    modes = _snapshot(repo, require_checkout=True)
    assert not modes["complete"]
    assert modes["checkout"]["unstaged"] == [
        {"path": "AGENTS.md", "reason": "executable mode differs"}
    ]
    assert _files(tmp_path) == before


@pytest.mark.integration(
    reason="preserves distinct submodule inventory and missing checkout omissions"
)
def test_submodule_boundary_stays_explicit(tmp_path: Path, git_environment: None) -> None:
    del git_environment
    parent, child = tmp_path / "parent", tmp_path / "child"
    _repo(parent)
    _repo(child)
    _git(parent, "-c", "protocol.file.allow=always", "submodule", "add", str(child), "module")
    _git(parent, "commit", "-am", "submodule")
    uninitialized = tmp_path / "uninitialized"
    _git(tmp_path, "clone", "--no-recurse-submodules", str(parent), str(uninitialized))
    before = _files(tmp_path)
    rows = inventory._inventory(_reader(), [parent])
    assert rows["complete"], rows
    assert len(rows["repositories"]) == 2
    assert len({row["common_dir"] for row in rows["repositories"]}) == 2
    assert _snapshot(parent)["complete"]
    result = _snapshot(uninitialized)
    assert not result["complete"]
    assert "submodule checkout unverified" in result["omissions"][0]["reason"]
    checkout = _snapshot(parent, require_checkout=True)
    assert not checkout["complete"]
    assert checkout["checkout"]["unsupported"] == [
        {"path": "module", "reason": "non-regular index entry"}
    ]
    assert _files(tmp_path) == before


@pytest.mark.integration(reason="walks a real checkout that holds file and directory symlinks")
def test_inventory_covers_file_links_and_in_root_directory_links(
    tmp_path: Path,
    git_environment: None,
) -> None:
    del git_environment
    root, outside = tmp_path / "root", tmp_path / "outside"
    repo = root / "proj"
    _repo(repo)
    outside.mkdir()
    (repo / "CLAUDE.md").symlink_to("AGENTS.md")
    (repo / ".venv/lib").mkdir(parents=True)
    (repo / ".venv/lib64").symlink_to("lib")
    (repo / ".venv/python").symlink_to("/usr/bin/env")
    (repo / "dangling").symlink_to("absent")
    rows = inventory._inventory(_reader(), [root])
    assert rows["complete"], rows["omissions"]
    assert [row["root"] for row in rows["repositories"]] == [str(repo)]
    (repo / "escape").symlink_to(outside)
    rows = inventory._inventory(_reader(), [root])
    assert not rows["complete"]
    assert [o["reason"] for o in rows["omissions"]] == [
        "symlink to a directory outside the scanned roots was not traversed"
    ]


@pytest.mark.integration(reason="validates a checkout whose index holds a symlink")
def test_checkout_validates_tracked_symlinks_by_target(
    tmp_path: Path,
    git_environment: None,
) -> None:
    del git_environment
    repo = tmp_path / "proj"
    _repo(repo)
    (repo / "CLAUDE.md").symlink_to("AGENTS.md")
    _git(repo, "add", "--", "CLAUDE.md")
    _git(repo, "commit", "-m", "link")
    result = _snapshot(repo, require_checkout=True)
    assert result["complete"], result["omissions"]
    assert result["symlinks"] == ["CLAUDE.md"]
    assert result["boundaries"] == []
    (repo / "CLAUDE.md").unlink()
    (repo / "CLAUDE.md").symlink_to("package.json")
    result = _snapshot(repo, require_checkout=True)
    assert not result["complete"]
    assert result["checkout"]["unstaged"] == [
        {"path": "CLAUDE.md", "reason": "symlink target differs"}
    ]
    refused = _snapshot(repo, read=["CLAUDE.md"])
    assert "requested input is a symlink" in refused["omissions"][0]["reason"]


def test_call_budget_is_a_flag_and_not_a_fixed_second(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deadlines: list[float] = []

    def execute(_a: list[str], _c: Path, _e: dict[str, str], _l: int, deadline: float) -> bytes:
        deadlines.append(deadline)
        return b""

    monkeypatch.setattr(time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(inventory, "_execute", execute)
    inventory._Reader(100, 100, 30, 5.0).git(tmp_path, "rev-parse", "HEAD")
    inventory._Reader(100, 100, 30).git(tmp_path, "rev-parse", "HEAD")
    assert deadlines == [105.0, 101.0]


@pytest.mark.integration(reason="walks a tree that holds a virtualenv and node_modules")
def test_inventory_skips_virtualenvs_and_node_modules_but_reports_them(
    tmp_path: Path,
    git_environment: None,
) -> None:
    del git_environment
    root = tmp_path / "root"
    repo = root / "proj"
    _repo(repo)
    site = repo / ".venv/lib/python3/site-packages/pkg"
    site.mkdir(parents=True)
    (repo / ".venv/pyvenv.cfg").write_text("home = /usr/bin\n")
    for number in range(200):
        (site / f"mod{number}.py").write_text("")
    (repo / "node_modules/dep").mkdir(parents=True)
    rows = inventory._inventory(_reader(entries=100), [root])
    assert rows["complete"], rows["omissions"]
    assert {(item["reason"], Path(item["path"]).name) for item in rows["skipped"]} == {
        ("virtual environment", ".venv"),
        ("installed npm packages", "node_modules"),
    }
    everything = inventory._inventory(_reader(entries=100), [root], include_dependencies=True)
    assert not everything["complete"]
    assert everything["skipped"] == []
