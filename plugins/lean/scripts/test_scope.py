"""Tests for scope.py against a throwaway repository."""

# ruff: noqa: S101, S603, INP001, PLR2004
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import scope  # pyright: ignore[reportImplicitRelativeImport]

if TYPE_CHECKING:
    import pathlib

    import pytest


def _run(cwd: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)  # noqa: S607


def test_branch_ranges_cover_only_added_lines(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Untouched lines on a changed file stay out of the ranges."""
    _run(tmp_path, "init", "-q", "-b", "main")
    _run(tmp_path, "config", "user.email", "t@example.com")
    _run(tmp_path, "config", "user.name", "t")
    f = tmp_path / "a.py"
    f.write_text("# old\nx = 1\ny = 2\n")
    _run(tmp_path, "add", ".")
    _run(tmp_path, "commit", "-q", "-m", "base")
    _run(tmp_path, "checkout", "-q", "-b", "topic")
    f.write_text("# old\nx = 1\ny = 2\n# new\nz = 3\n")
    _run(tmp_path, "commit", "-qam", "change")
    monkeypatch.chdir(tmp_path)

    assert scope.main([]) == 0
    assert capsys.readouterr().out == "a.py\t4-5\n"


def test_no_trunk_exits_2(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A repo without a trunk ref halts instead of widening scope."""
    _run(tmp_path, "init", "-q", "-b", "dev")
    monkeypatch.chdir(tmp_path)
    assert scope.main([]) == 2
    assert "no trunk ref" in capsys.readouterr().err


def _topic_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    _run(tmp_path, "init", "-q", "-b", "main")
    _run(tmp_path, "config", "user.email", "t@example.com")
    _run(tmp_path, "config", "user.name", "t")
    f = tmp_path / "a.py"
    f.write_text("x = 1\n# gone\ny = 2\n")
    _run(tmp_path, "add", ".")
    _run(tmp_path, "commit", "-q", "-m", "base")
    return f


def test_all_lists_names_only(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--all prints tracked names with no ranges."""
    _topic_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert scope.main(["--all"]) == 0
    assert capsys.readouterr().out == "a.py\n"


def test_staged_and_deletion_only_range(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A deletion-only hunk prints an empty range; --staged reads the index."""
    f = _topic_repo(tmp_path)
    f.write_text("x = 1\ny = 2\n")
    _run(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)
    assert scope.main(["--staged"]) == 0
    assert capsys.readouterr().out == "a.py\t\n"
