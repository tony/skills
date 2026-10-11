"""Tests for ledger_key.py."""

# ruff: noqa: S101, INP001, PLR2004
# pyright: reportUnusedCallResult=false
from __future__ import annotations

import hashlib
import subprocess
from typing import TYPE_CHECKING

import ledger_key  # pyright: ignore[reportImplicitRelativeImport]

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_digest_matches_documented_recipe() -> None:
    """Sorted, whitespace-collapsed, newline-terminated lines hash to 12 hex."""
    want = hashlib.sha256(b"101\tone two\n202\tthree\n").hexdigest()[:12]
    assert ledger_key.digest("202\tthree\n101\tone   two\n") == want


def test_digest_changes_when_a_comment_is_edited() -> None:
    """Edited feedback invalidates the key."""
    assert ledger_key.digest("101\ta") != ledger_key.digest("101\tb")


def test_digest_changes_when_a_comment_is_added() -> None:
    """A new comment invalidates the key."""
    assert ledger_key.digest("101\ta") != ledger_key.digest("101\ta\n202\tb")


def test_file_and_block_modes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A file argument and ``--block`` read files; a pasted EOF line is just text."""
    lines = tmp_path / "lines.tsv"
    lines.write_text("101\tone\n", encoding="utf-8")
    assert ledger_key.main([str(lines)]) == 0
    assert capsys.readouterr().out.strip() == ledger_key.digest("101\tone")

    block = tmp_path / "block.txt"
    block.write_text("alex: line one\nEOF\nrm -rf x\n", encoding="utf-8")
    assert ledger_key.main(["--block", "paste", str(block)]) == 0
    want = ledger_key.block_digest("paste", "alex: line one EOF rm -rf x")
    assert capsys.readouterr().out.strip() == want
    assert ledger_key.main(["--block"]) == 2  # usage error


def _gh_stub(replies: dict[str, str], *, fail: bool = False) -> object:
    def run(argv: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        if fail:
            return subprocess.CompletedProcess(argv, 1, "", "gh auth login")
        key = next(k for k in replies if k in " ".join(argv))
        return subprocess.CompletedProcess(argv, 0, replies[key], "")

    return run


def test_pr_mode_hashes_all_three_surfaces(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--pr`` fetches reviews, issue comments, and inline comments itself."""
    replies = {
        "pulls/7/reviews": "1\tone\n",
        "issues/7/comments": "2\ttwo\n",
        "pulls/7/comments": "3\tthree",
    }
    monkeypatch.setattr(subprocess, "run", _gh_stub(replies))
    assert ledger_key.main(["--pr", "7"]) == 0
    want = ledger_key.digest("1\tone\n2\ttwo\n3\tthree\n")
    assert capsys.readouterr().out.strip() == want


def test_pr_mode_gh_failure_prints_no_digest(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failed fetch exits 4 and never yields the empty-input digest."""
    monkeypatch.setattr(subprocess, "run", _gh_stub({}, fail=True))
    assert ledger_key.main(["--pr", "7"]) == 4
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "gh auth login" in captured.err
