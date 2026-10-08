"""Tests for ledger_key.py."""

# ruff: noqa: S101, INP001, PLR2004
# pyright: reportUnusedCallResult=false
from __future__ import annotations

import hashlib
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
