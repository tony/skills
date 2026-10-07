"""Tests for position.py against throwaway repositories."""

# ruff: noqa: S101, S603, S607, INP001, PLR2004
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING

import position  # pyright: ignore[reportImplicitRelativeImport]

if TYPE_CHECKING:
    import pathlib

    import pytest


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
    monkeypatch.chdir(repo)

    assert position.main([]) == 0
    got = json.loads(capsys.readouterr().out)
    assert got["branch"] == "feat/x"
    assert got["trunk"] == "origin/main"
    assert (got["ahead"], got["behind"]) == (1, 0)
    assert got["base_source"] == "trunk"
    assert got["on_trunk"] is False
    assert got["modified"] == 1
    assert sorted(got["untracked"]) == ["a.stash", "notes.md"]
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
