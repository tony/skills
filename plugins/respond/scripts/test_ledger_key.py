"""Tests for ledger_key.py."""

# ruff: noqa: S101, INP001
from __future__ import annotations

import hashlib

import ledger_key  # pyright: ignore[reportImplicitRelativeImport]


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
