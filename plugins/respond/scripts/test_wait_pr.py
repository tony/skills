"""Tests for wait_pr.py with ``gh`` replaced by canned output."""

# ruff: noqa: S101, INP001, PLR2004
import json
import subprocess
from typing import TYPE_CHECKING

import wait_pr

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest


def _fake(reply: str, only: str = "", head: str = "abc") -> Callable[..., str]:
    def gh(*args: str, **_kw: bool) -> str:
        if "headRefOid" in args:
            return head + "\n"
        return reply if only in " ".join(args) else ""

    return gh


def test_ci_failure_exits_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failed bucket stops the wait even with checks still pending."""
    out = json.dumps([{"bucket": "fail"}, {"bucket": "pending"}])
    monkeypatch.setattr(wait_pr, "_gh", _fake(out))
    assert wait_pr.main(["ci", "7", "--sha", "abc", "--interval", "0"]) == 1
    assert json.loads(capsys.readouterr().out) == {"status": "failed"}


def test_ci_no_checks_after_grace_exits_three(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An empty check list is not green; it is reported as none."""
    monkeypatch.setattr(wait_pr, "_gh", _fake("[]"))
    assert wait_pr.main(["ci", "7", "--sha", "abc", "--grace", "0", "--interval", "0"]) == 3
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
    review = json.dumps({"login": "reviewer-app[bot]", "commit": "abc"})
    monkeypatch.setattr(wait_pr, "_gh", _fake(review, "reviews"))
    argv = ["agents", "7", "--sha", "abc", "--since", "2026-01-01T00:00:00Z"]
    argv += ["--agents", "reviewer-app", "other[bot]", "--timeout", "0", "--interval", "0"]
    assert wait_pr.main(argv) == 2
    assert json.loads(capsys.readouterr().out) == {"missing": ["other[bot]"]}


def test_ci_green_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Passing and skipped checks end the wait green."""
    out = json.dumps([{"bucket": "pass"}, {"bucket": "skipping"}])
    monkeypatch.setattr(wait_pr, "_gh", _fake(out))
    assert wait_pr.main(["ci", "7", "--sha", "abc", "--interval", "0"]) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "green"}


def test_ci_pending_past_cap_exits_two(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A check still pending at the cap is a timeout."""
    monkeypatch.setattr(wait_pr, "_gh", _fake(json.dumps([{"bucket": "pending"}])))
    assert wait_pr.main(["ci", "7", "--sha", "abc", "--timeout", "0", "--interval", "0"]) == 2
    assert json.loads(capsys.readouterr().out) == {"status": "timeout"}


def test_agents_all_present_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A review on the head and a later comment cover the whole roster."""
    review = json.dumps({"login": "a", "commit": "abc"})
    comment = json.dumps({"login": "b", "at": "2026-01-02T00:00:00Z"})

    def gh(*args: str, **_kw: bool) -> str:
        return review if "reviews" in " ".join(args) else comment

    monkeypatch.setattr(wait_pr, "_gh", gh)
    argv = ["agents", "7", "--sha", "abc", "--since", "2026-01-01T00:00:00Z"]
    argv += ["--agents", "a", "b", "--timeout", "0", "--interval", "0"]
    assert wait_pr.main(argv) == 0
    assert json.loads(capsys.readouterr().out) == {"missing": []}


def test_agents_skip_null_logins(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A deleted account (null login) is skipped, not a crash."""
    review = json.dumps({"login": None, "commit": "abc"})
    monkeypatch.setattr(wait_pr, "_gh", _fake(review, "reviews"))
    argv = ["agents", "7", "--sha", "abc", "--since", "2026-01-01T00:00:00Z"]
    argv += ["--agents", "a", "--timeout", "0", "--interval", "0"]
    assert wait_pr.main(argv) == 2
    assert json.loads(capsys.readouterr().out) == {"missing": ["a"]}


def test_ci_head_mismatch_exits_five(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Green checks on another head are not the pushed head's checks."""
    out = json.dumps([{"bucket": "pass"}])
    monkeypatch.setattr(wait_pr, "_gh", _fake(out, head="old"))
    argv = ["ci", "7", "--sha", "abc", "--timeout", "0", "--interval", "0"]
    assert wait_pr.main(argv) == 5
    assert json.loads(capsys.readouterr().out) == {"status": "head-mismatch", "head": "old"}


def _run_result(code: int, out: str, err: str, *, head_ok: bool = True) -> Callable[..., object]:
    def run(*a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        if head_ok and "headRefOid" in str(a):
            return subprocess.CompletedProcess([], 0, "abc\n", "")
        return subprocess.CompletedProcess([], code, out, err)

    return run


def test_gh_failure_exits_four_with_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unauthenticated ``gh`` is an error, not "no checks" or "waiting"."""
    monkeypatch.setattr(subprocess, "run", _run_result(1, "", "gh auth login", head_ok=False))
    assert wait_pr.main(["ci", "7", "--sha", "abc", "--interval", "0"]) == 4
    captured = capsys.readouterr()
    assert "gh auth login" in captured.err
    assert captured.out == ""
    argv = ["agents", "7", "--sha", "abc", "--since", "", "--agents", "a"]
    assert wait_pr.main(argv) == 4


def test_gh_checks_nonzero_exit_with_output_is_read(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``gh pr checks`` exits nonzero on failing checks yet prints them."""
    out = json.dumps([{"bucket": "fail"}])
    monkeypatch.setattr(subprocess, "run", _run_result(1, out, ""))
    assert wait_pr.main(["ci", "7", "--sha", "abc", "--interval", "0"]) == 1
    assert json.loads(capsys.readouterr().out) == {"status": "failed"}


def _checks_fail(rollup: str) -> Callable[..., object]:
    def run(*a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        text = str(a)
        if "headRefOid" in text:
            return subprocess.CompletedProcess([], 0, "abc\n", "")
        if "statusCheckRollup" in text:
            return subprocess.CompletedProcess([], 0, rollup, "")
        return subprocess.CompletedProcess([], 1, "", "some other wording")

    return run


def test_empty_rollup_means_no_checks_whatever_gh_prints(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A head with an empty ``statusCheckRollup`` has no checks, by field, not by message."""
    monkeypatch.setattr(subprocess, "run", _checks_fail("0\n"))
    assert wait_pr.main(["ci", "7", "--sha", "abc", "--grace", "0", "--interval", "0"]) == 3
    assert json.loads(capsys.readouterr().out) == {"status": "none"}


def test_agents_inline_review_comments_count(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An agent that posts only inline review comments has weighed in."""
    inline = json.dumps({"login": "a[bot]", "commit": "abc", "at": "2026-01-02T00:00:00Z"})

    def gh(*args: str, **_kw: bool) -> str:
        return inline if "pulls/7/comments" in " ".join(args) else ""

    monkeypatch.setattr(wait_pr, "_gh", gh)
    argv = ["agents", "7", "--sha", "abc", "--since", "2026-01-01T00:00:00Z"]
    argv += ["--agents", "a", "--timeout", "0", "--interval", "0"]
    assert wait_pr.main(argv) == 0
    assert json.loads(capsys.readouterr().out) == {"missing": []}
