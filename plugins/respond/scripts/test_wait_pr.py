"""Tests for wait_pr.py with ``gh`` replaced by canned output."""

# ruff: noqa: S101, INP001, PLR2004
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import wait_pr  # pyright: ignore[reportImplicitRelativeImport]

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest


def _fake(reply: str, only: str = "") -> Callable[..., str]:
    def gh(*args: str) -> str:
        return reply if only in " ".join(args) else ""

    return gh


def test_ci_failure_exits_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failed bucket stops the wait even with checks still pending."""
    out = json.dumps([{"bucket": "fail"}, {"bucket": "pending"}])
    monkeypatch.setattr(wait_pr, "_gh", _fake(out))
    assert wait_pr.main(["ci", "7", "--interval", "0"]) == 1
    assert json.loads(capsys.readouterr().out) == {"status": "failed"}


def test_ci_no_checks_after_grace_exits_three(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An empty check list is not green; it is reported as none."""
    monkeypatch.setattr(wait_pr, "_gh", _fake("[]"))
    assert wait_pr.main(["ci", "7", "--grace", "0", "--interval", "0"]) == 3
    assert json.loads(capsys.readouterr().out) == {"status": "none"}


def test_agents_reports_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A roster login with no review on the head is reported at the cap."""
    review = json.dumps({"login": "a", "commit": "abc"})
    monkeypatch.setattr(wait_pr, "_gh", _fake(review, "reviews"))
    argv = ["agents", "7", "--sha", "abc", "--since", "2026-01-01T00:00:00Z"]
    argv += ["--agents", "a", "b", "--timeout", "0", "--interval", "0"]
    assert wait_pr.main(argv) == 2
    assert json.loads(capsys.readouterr().out) == {"missing": ["b"]}


def test_agents_match_bot_logins_across_suffix(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A roster login without ``[bot]`` matches the REST login with it, and back."""
    review = json.dumps({"login": "coderabbitai[bot]", "commit": "abc"})
    monkeypatch.setattr(wait_pr, "_gh", _fake(review, "reviews"))
    argv = ["agents", "7", "--sha", "abc", "--since", "2026-01-01T00:00:00Z"]
    argv += ["--agents", "coderabbitai", "other[bot]", "--timeout", "0", "--interval", "0"]
    assert wait_pr.main(argv) == 2
    assert json.loads(capsys.readouterr().out) == {"missing": ["other[bot]"]}
