"""Owned-repository tests for ``commit_lint.py``."""

# ruff: noqa: S101, S603, S607, INP001
import subprocess
import typing as t

import commit_lint
import pytest

if t.TYPE_CHECKING:
    from pathlib import Path


def _commit(repo: Path, message: str) -> None:
    _ = subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "commit",
            "--quiet",
            "--allow-empty",
            "--message",
            message,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def test_bad_commit_exits_nonzero_with_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A long subject in the range fails with the commit and the reason."""
    _ = subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    _commit(tmp_path, "base")
    _commit(tmp_path, "x" * 70)
    monkeypatch.chdir(tmp_path)
    assert commit_lint.main(["HEAD~1"]) == 1
    assert "subject is 70 chars (max 64)" in capsys.readouterr().out


def test_good_range_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A well-formed commit exits zero."""
    _ = subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    _commit(tmp_path, "base")
    _commit(tmp_path, "scope(fix) Short\n\nwhy: A.\n\nwhat:\n- B")
    monkeypatch.chdir(tmp_path)
    assert commit_lint.main(["HEAD~1"]) == 0


def test_unknown_base_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unresolvable base exits non-zero instead of passing an empty range."""
    _ = subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    _commit(tmp_path, "base")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        _ = commit_lint.main(["no-such-ref"])
    assert exc.value.code == 1
    assert "cannot list commits in no-such-ref..HEAD" in capsys.readouterr().err
