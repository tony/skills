"""Redundancy proof: fail-closed behavior."""

# ruff: noqa: S101, INP001, D103, TC003
# pyright: reportAny=false, reportUnusedCallResult=false

from __future__ import annotations

import os
from pathlib import Path

import pytest
import redundancy  # pyright: ignore[reportImplicitRelativeImport]


def run(cand: Path, keep: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = redundancy.main(["redundancy.py", str(cand), str(keep)])
    return code, capsys.readouterr().out


def tree(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


def test_subset_is_redundant(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cand = tree(tmp_path / "c", {"a": "1", "d/b": "2"})
    keep = tree(tmp_path / "k", {"a": "1", "d/b": "2", "extra": "3"})
    code, out = run(cand, keep, capsys)
    assert code == redundancy.EXIT_REDUNDANT
    assert "REDUNDANT" in out


def test_disjoint_is_not_redundant(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cand = tree(tmp_path / "c", {"a": "1"})
    keep = tree(tmp_path / "k", {"b": "1"})
    code, out = run(cand, keep, capsys)
    assert code == redundancy.EXIT_NOT_REDUNDANT
    assert "NOT REDUNDANT" in out


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory modes")
def test_unreadable_candidate_subtree_is_inconclusive(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cand = tree(tmp_path / "c", {"a": "1", "secret/only-copy": "2"})
    keep = tree(tmp_path / "k", {"a": "1"})
    (cand / "secret").chmod(0)
    try:
        code, out = run(cand, keep, capsys)
    finally:
        (cand / "secret").chmod(0o700)
    assert code == redundancy.EXIT_INCONCLUSIVE
    assert "INCONCLUSIVE" in out
    assert "REDUNDANT\n" not in out.replace("NOT REDUNDANT", "")


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file modes")
def test_unreadable_file_is_inconclusive(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cand = tree(tmp_path / "c", {"a": "1", "b": "2"})
    keep = tree(tmp_path / "k", {"a": "1", "b": "2"})
    (cand / "b").chmod(0)
    try:
        code, out = run(cand, keep, capsys)
    finally:
        (cand / "b").chmod(0o600)
    assert code == redundancy.EXIT_INCONCLUSIVE
    assert "UNREADABLE" in out


def test_listing_error_is_inconclusive(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    cand = tree(tmp_path / "c", {"a": "1", "sub/b": "2"})
    keep = tree(tmp_path / "k", {"a": "1"})
    real = os.scandir

    def deny(path: str | os.PathLike[str] = ".") -> object:
        if str(path).endswith("sub"):
            raise PermissionError(13, "Permission denied", str(path))
        return real(path)

    monkeypatch.setattr(os, "scandir", deny)
    code, out = run(cand, keep, capsys)
    assert code == redundancy.EXIT_INCONCLUSIVE
    assert "UNREADABLE" in out


def test_missing_candidate_is_inconclusive(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    keep = tree(tmp_path / "k", {"a": "1"})
    code, _ = run(tmp_path / "nope", keep, capsys)
    assert code == redundancy.EXIT_INCONCLUSIVE
