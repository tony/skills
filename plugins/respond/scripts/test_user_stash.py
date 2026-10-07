"""Tests for user_stash.py against a temporary repository."""

# ruff: noqa: S101, S603, S607, INP001, PLR2004
# pyright: reportUnusedCallResult=false
from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import user_stash  # pyright: ignore[reportImplicitRelativeImport]

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.txt").write_text("one\n")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_save_restore_round_trip_drops_stash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Edits and untracked files come back and the stash list is empty."""
    repo = _repo(tmp_path)
    (repo / "a.txt").write_text("edited\n")
    (repo / "new.txt").write_text("new\n")
    monkeypatch.chdir(repo)
    assert user_stash.main(["save"]) == 0
    sha = capsys.readouterr().out.strip()
    assert len(sha) == 40
    assert _git(repo, "status", "--porcelain") == ""
    assert user_stash.main(["restore", sha]) == 0
    assert (repo / "a.txt").read_text() == "edited\n"
    assert (repo / "new.txt").exists()
    assert _git(repo, "stash", "list") == ""


def test_save_on_clean_tree_prints_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A clean tree creates no stash, so there is no SHA to report."""
    monkeypatch.chdir(_repo(tmp_path))
    assert user_stash.main(["save"]) == 1
    assert capsys.readouterr().out == ""


def test_restore_conflict_keeps_stash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A refused apply leaves the stash in place and names it."""
    repo = _repo(tmp_path)
    (repo / "a.txt").write_text("user edit\n")
    monkeypatch.chdir(repo)
    assert user_stash.main(["save"]) == 0
    sha = capsys.readouterr().out.strip()
    (repo / "a.txt").write_text("fix\n")
    _git(repo, "commit", "-q", "-am", "fix")
    assert user_stash.main(["restore", sha]) == 1
    assert f"kept stash {sha}" in capsys.readouterr().out
    assert sha in _git(repo, "stash", "list", "--format=%H")
