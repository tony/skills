"""Tests for tally.py."""

# ruff: noqa: S101, INP001
from __future__ import annotations

import pytest
import tally  # pyright: ignore[reportImplicitRelativeImport]


def test_counts_each_verdict() -> None:
    """The hero counts sum to the bullet count."""
    text = "## Verdicts\n\n- Kept x\n- Rewrote y\n- Deleted z\n- Deleted w\n"
    assert tally.tally(text) == "4 comments: 1 kept, 1 rewritten, 2 deleted"


@pytest.mark.parametrize(
    ("text", "reason"), [("", "no verdict bullets"), ("- Fixed x\n", "unknown verdict")]
)
def test_refuses_unusable_input(text: str, reason: str) -> None:
    """Empty input or an unknown verdict word raises with the reason."""
    with pytest.raises(ValueError, match=reason):
        _ = tally.tally(text)


def test_singular_for_one_comment() -> None:
    """One bullet reads "1 comment"."""
    assert tally.tally("- Kept x\n") == "1 comment: 1 kept, 0 rewritten, 0 deleted"
