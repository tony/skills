"""Tests for collect_feedback.py with ``gh`` replaced by canned output."""

# ruff: noqa: S101, INP001, PLR2004
# pyright: reportAny=false
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import collect_feedback  # pyright: ignore[reportImplicitRelativeImport]
import ghcli  # pyright: ignore[reportImplicitRelativeImport]
from ghcli import GhError  # pyright: ignore[reportImplicitRelativeImport]

if TYPE_CHECKING:
    import pytest


def _thread(path: str, *, resolved: bool = False, more: bool = False) -> str:
    node = {
        "isResolved": resolved,
        "isOutdated": False,
        "path": path,
        "comments": {
            "pageInfo": {"hasNextPage": more},
            "nodes": [
                {
                    "databaseId": 9,
                    "author": {"login": "review-app", "__typename": "Bot"},
                    "body": "nit",
                    "createdAt": "t",
                }
            ],
        },
    }
    return json.dumps(node)


def _gh(*args: str, **_kw: bool) -> str:
    joined = " ".join(args)
    if joined.startswith("repo view"):
        return "acme widgets\n"
    if "graphql" in joined:
        return _thread("a.py") + "\n" + _thread("b.py", resolved=True) + "\n"
    if "pulls/7/reviews" in joined:
        return json.dumps(
            {
                "id": 1,
                "state": "COMMENTED",
                "body": "x",
                "commit": "abc",
                "login": "ann",
                "type": "User",
            }
        )
    if "issues/7/comments" in joined:
        return (
            json.dumps({"id": 2, "body": "y", "at": "t", "login": "app[bot]", "type": "Bot"}) + "\n"
        )
    if joined.startswith("pr checks"):
        return json.dumps(
            [
                {"name": "ci", "bucket": "fail", "link": "https://h/o/r/actions/runs/55/job/1"},
                {"name": "lint", "bucket": "pass", "link": ""},
            ]
        )
    return ""


def test_collect_normalizes_every_surface(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Bots are flagged by type, resolved threads dropped, failing checks carry a run id."""
    monkeypatch.setattr(collect_feedback, "gh", _gh)
    monkeypatch.setattr(ghcli, "gh", _gh)
    assert collect_feedback.main(["--pr", "7"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert [r["login"] for r in out["reviews"]] == ["ann"]
    assert out["reviews"][0]["bot"] is False
    assert out["comments"][0]["bot"] is True
    assert [t["path"] for t in out["threads"]] == ["a.py"]
    assert out["threads"][0]["comments"][0]["bot"] is True
    assert [(c["name"], c["run"]) for c in out["failing_checks"]] == [("ci", "55")]


def test_include_resolved_and_truncation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--include-resolved`` keeps settled threads; a cut-off thread says so."""

    def gh(*args: str, **kw: bool) -> str:
        if "graphql" in " ".join(args):
            return _thread("a.py", resolved=True, more=True) + "\n"
        return _gh(*args, **kw)

    monkeypatch.setattr(collect_feedback, "gh", gh)
    monkeypatch.setattr(ghcli, "gh", gh)
    assert collect_feedback.main(["--pr", "7", "--include-resolved"]) == 0
    thread = json.loads(capsys.readouterr().out)["threads"][0]
    assert (thread["resolved"], thread["truncated"]) == (True, True)


def test_gh_failure_exits_four_and_prints_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failed read is an error, never empty feedback."""

    def failing(*_a: str, **_k: bool) -> str:
        msg = "gh auth login"
        raise GhError(msg)

    monkeypatch.setattr(collect_feedback, "gh", failing)
    monkeypatch.setattr(ghcli, "gh", failing)
    assert collect_feedback.main(["--pr", "7"]) == 4
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "gh auth login" in captured.err
