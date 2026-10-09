"""Critical cleanup sequencing for optimizer rollback."""

# ruff: noqa: S101, INP001
from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import measure  # pyright: ignore[reportImplicitRelativeImport]
import pytest

if TYPE_CHECKING:
    import pathlib


@pytest.mark.parametrize("reset_exit", [0, 128])
def test_restore_requires_successful_reset_before_clean(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    reset_exit: int,
) -> None:
    """A failed tracked-tree reset cannot trigger untracked-file deletion."""
    calls: list[tuple[str, ...]] = []

    def git_result(root: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
        assert root == tmp_path
        calls.append(args)
        if args == ("rev-parse", "--show-toplevel"):
            return subprocess.CompletedProcess(args, 0, str(tmp_path), "")
        if args == ("reset", "--hard", "HEAD"):
            return subprocess.CompletedProcess(args, reset_exit, "", "reset refused\n")
        assert args == ("clean", "-fd")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(measure, "_git", git_result)
    result = measure.restore(tmp_path.parent / "memory", tmp_path, tmp_path.parent / "home")

    assert result == {
        "restored": reset_exit == 0,
        "reason": "reset refused" if reset_exit else None,
    }
    expected = [("rev-parse", "--show-toplevel"), ("reset", "--hard", "HEAD")]
    if reset_exit == 0:
        expected.append(("clean", "-fd"))
    assert calls == expected
