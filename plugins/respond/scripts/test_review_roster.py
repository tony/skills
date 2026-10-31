"""Tests for review_roster.py with ``gh`` replaced by canned output."""

# pyright: reportAny=false
# ruff: noqa: S101, INP001, PLR2004
import json
from typing import TYPE_CHECKING

import review_roster  # pyright: ignore[reportImplicitRelativeImport]
from ghcli import GhError  # pyright: ignore[reportImplicitRelativeImport]

if TYPE_CHECKING:
    import pytest


def _gh(*args: str, **_kw: bool) -> str:
    joined = " ".join(args)
    if joined.startswith("pr list"):
        return "1\n2\n"
    if "pulls/1/reviews" in joined:
        return "ann\tUser\nreview-app[bot]\tBot\n"
    if "issues/2/comments" in joined:
        return "ann\tUser\nplain-app\tBot\n"
    return ""


def test_roster_marks_accounts_by_type_not_by_name(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ``Bot``-typed login without ``[bot]`` is still a bot; a person is not."""
    monkeypatch.setattr(review_roster, "gh", _gh)
    assert review_roster.main([]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert [(r["login"], r["bot"]) for r in rows] == [
        ("plain-app", True),
        ("review-app[bot]", True),
        ("ann", False),
    ]
    assert rows[2]["prs"] == 2
    assert rows[2]["surfaces"] == ["comments", "reviews"]


def test_roster_gh_failure_exits_four(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failed read is an error, never an empty roster."""

    def failing(*_a: str, **_k: bool) -> str:
        msg = "gh auth login"
        raise GhError(msg)

    monkeypatch.setattr(review_roster, "gh", failing)
    assert review_roster.main([]) == 4
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "gh auth login" in captured.err
