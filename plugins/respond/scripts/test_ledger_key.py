"""Tests for ledger_key.py."""

# ruff: noqa: S101, INP001
from __future__ import annotations

import hashlib

import ledger_key  # pyright: ignore[reportImplicitRelativeImport]


def test_digest_matches_documented_recipe() -> None:
    """Sorted, whitespace-collapsed, newline-terminated lines hash to 12 hex."""
    want = hashlib.sha256(b"alex\tone two\nlint-bot\tthree\n").hexdigest()[:12]
    assert ledger_key.digest("lint-bot\tthree\nalex\tone   two\n") == want


def test_digest_changes_when_a_claim_changes() -> None:
    """Edited feedback invalidates the key."""
    assert ledger_key.digest("alex\ta") != ledger_key.digest("alex\tb")
