"""Tests for position.py against throwaway repositories."""

# ruff: noqa: S101, S603, S607, INP001, PLR2004
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false
from __future__ import annotations

import json
import os
import subprocess
from typing import TYPE_CHECKING

import position  # pyright: ignore[reportImplicitRelativeImport]
import pytest

if TYPE_CHECKING:
    import pathlib


def _git(cwd: pathlib.Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@example.com",
            "-c",
            "user.name=t",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _repo_with_origin(tmp_path: pathlib.Path) -> pathlib.Path:
    repo = tmp_path / "work"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", "origin.git")
    _git(repo, "remote", "add", "origin", "../origin.git")
    _git(repo, "push", "-q", "-u", "origin", "main")
    _git(repo, "remote", "set-head", "origin", "main")
    return repo


def test_branch_ahead_of_trunk_with_filtered_untracked(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Ahead and behind come from trunk; environment files are filtered."""
    repo = _repo_with_origin(tmp_path)
    _git(repo, "switch", "-q", "-c", "feat/x")
    (repo / "b.txt").write_text("2\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "work")
    (repo / "a.txt").write_text("changed\n")
    (repo / ".zshrc").write_text("x\n")
    (repo / "notes.md").write_text("x\n")
    (repo / "a.stash").write_text("x\n")
    (repo / ".gitmodules").write_text('[submodule "lib"]\n')
    (repo / ".mcp.json").write_text("{}\n")
    monkeypatch.chdir(repo)

    assert position.main([]) == 0
    got = json.loads(capsys.readouterr().out)
    assert got["branch"] == "feat/x"
    assert got["trunk"] == "origin/main"
    assert (got["ahead"], got["behind"]) == (1, 0)
    assert got["base_source"] == "trunk"
    assert got["on_trunk"] is False
    assert got["modified"] == 1
    assert sorted(got["untracked"]) == [".gitmodules", ".mcp.json", "a.stash", "notes.md"]
    assert got["ignored_untracked"] == 1
    assert got["stashes"] == 0


def test_no_origin_head_falls_back_and_reports_source(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A missing origin/HEAD falls back to origin/main and says so."""
    repo = _repo_with_origin(tmp_path)
    _git(repo, "remote", "set-head", "origin", "--delete")
    monkeypatch.chdir(repo)

    assert position.main([]) == 0
    got = json.loads(capsys.readouterr().out)
    assert got["trunk"] == "origin/main"
    assert got["trunk_source"] == "assumed origin/main"
    assert got["on_trunk"] is True


def test_no_trunk_reports_failed_lookup(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """With no trunk and no upstream the base is null, never HEAD."""
    repo = tmp_path / "solo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "dev")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "one")
    monkeypatch.chdir(repo)

    assert position.main([]) == 0
    got = json.loads(capsys.readouterr().out)
    assert got["base"] is None
    assert got["failed"] == ["trunk ref"]


def test_empty_repo_and_dotfile_root_stop_early(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No commits, or a root that is the home directory, ends the sweep."""
    repo = tmp_path / "empty"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    monkeypatch.chdir(repo)
    assert position.main([]) == 0
    assert json.loads(capsys.readouterr().out)["has_commits"] is False

    monkeypatch.setenv("HOME", str(repo))
    assert position.main([]) == 0
    assert json.loads(capsys.readouterr().out)["dotfile_repo"] is True


def test_outside_a_repository_exits_2(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Outside git the script exits 2 with a message."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    assert position.main([]) == 2
    assert "not inside a git repository" in capsys.readouterr().err


def test_staged_rename_counts_once_and_fetch_age_is_separate(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A staged rename is one staged entry; fetch age is not the tip's age."""
    repo = _repo_with_origin(tmp_path)
    _git(repo, "mv", "a.txt", "b.txt")
    monkeypatch.chdir(repo)

    assert position.main([]) == 0
    assert json.loads(capsys.readouterr().out)["last_fetch"] == "unknown"

    _git(repo, "fetch", "-q")
    assert position.main([]) == 0
    got = json.loads(capsys.readouterr().out)
    assert (got["staged"], got["modified"]) == (1, 0)
    assert got["last_fetch"] == "just now"
    assert "trunk_age" not in got


def _run(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    assert position.main([]) == 0
    return json.loads(capsys.readouterr().out)


def test_branch_tracking_trunk_reports_trunk_base(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A branch whose upstream is trunk itself is not a stacked branch."""
    repo = _repo_with_origin(tmp_path)
    _git(repo, "switch", "-q", "-c", "x", "origin/main")
    (repo / "x.txt").write_text("x\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "x")
    monkeypatch.chdir(repo)

    got = _run(capsys)
    assert got["upstream"] == "origin/main"
    assert got["base_source"] == "trunk"
    assert got["ahead"] == 1


def test_stacked_branch_takes_its_parent_as_base(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A branch tracking another branch measures from that parent."""
    repo = _repo_with_origin(tmp_path)
    _git(repo, "switch", "-q", "-c", "parent")
    (repo / "p.txt").write_text("p\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "parent work")
    _git(repo, "push", "-q", "origin", "parent")
    _git(repo, "switch", "-q", "-c", "child")
    _git(repo, "branch", "-q", "--set-upstream-to=origin/parent")
    (repo / "c.txt").write_text("c\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "child work")
    monkeypatch.chdir(repo)

    got = _run(capsys)
    assert got["base_source"] == "upstream"
    assert got["ahead"] == 2
    parent = subprocess.run(
        ["git", "rev-parse", "origin/parent"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert got["base"] == parent


@pytest.mark.parametrize("remote", ["origin", "fork"])
def test_own_published_branch_is_not_a_stack(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    remote: str,
) -> None:
    """Published work stays in the range regardless of the remote's name."""
    repo = _repo_with_origin(tmp_path)
    monkeypatch.chdir(repo)
    trunk = position._git("rev-parse", "origin/main")  # noqa: SLF001
    if remote != "origin":
        _git(repo, "remote", "add", remote, "../origin.git")
    _git(repo, "switch", "-q", "-c", "feature")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "published work")
    _git(repo, "push", "-q", "-u", remote, "feature")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "local work")

    got = _run(capsys)
    assert got["upstream"] == f"{remote}/feature"
    assert got["base_source"] == "trunk"
    assert got["base"] == trunk
    assert got["ahead"] == 2


def test_failed_status_reports_unknown_instead_of_clean(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A malformed index leaves worktree fields unknown without changing bytes."""
    repo = _repo_with_origin(tmp_path)
    index = repo / ".git" / "index"
    index.write_bytes(b"invalid index")
    monkeypatch.chdir(repo)

    got = _run(capsys)
    for field in ("staged", "modified", "conflicts", "untracked", "ignored_untracked"):
        assert got[field] is None
    assert got["failed"] == ["worktree status"]
    assert index.read_bytes() == b"invalid index"


def test_failed_stash_query_reports_unknown(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A failed stash lookup is not evidence that there are no stashes."""
    repo = _repo_with_origin(tmp_path)
    monkeypatch.chdir(repo)
    original = position._git  # noqa: SLF001

    def fail_stash(*args: str, strip: bool = True) -> str | None:
        return None if args == ("stash", "list") else original(*args, strip=strip)

    monkeypatch.setattr(position, "_git", fail_stash)
    got = _run(capsys)
    assert got["stashes"] is None
    assert got["failed"] == ["stash list"]


@pytest.mark.skipif(os.name != "posix", reason="POSIX permits non-UTF-8 path bytes")
def test_untracked_byte_filename_round_trips(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """NUL-delimited paths preserve undecodable bytes and embedded CRLF."""
    repo = _repo_with_origin(tmp_path)
    name = os.fsdecode(b"untracked-\xff\r\n.txt")
    (repo / name).touch()
    index = repo / ".git" / "index"
    before = index.read_bytes()
    monkeypatch.chdir(repo)

    got = _run(capsys)
    assert got["untracked"] == [name]
    assert index.read_bytes() == before


def test_unmerged_paths_count_once_as_conflicts(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A conflicted path is one conflict, not also staged and modified."""
    repo = _repo_with_origin(tmp_path)
    _git(repo, "switch", "-q", "-c", "side")
    (repo / "a.txt").write_text("side\n")
    _git(repo, "commit", "-q", "-am", "side")
    _git(repo, "switch", "-q", "main")
    (repo / "a.txt").write_text("main\n")
    _git(repo, "commit", "-q", "-am", "main")
    merge = subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "merge", "side"],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    assert merge.returncode != 0
    monkeypatch.chdir(repo)

    got = _run(capsys)
    assert (got["conflicts"], got["staged"], got["modified"]) == (1, 0, 0)
