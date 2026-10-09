"""Critical rollback and resume gates for optimizer execution."""

# ruff: noqa: S101, INP001
from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import measure  # pyright: ignore[reportImplicitRelativeImport]
import pytest

if TYPE_CHECKING:
    import pathlib


@pytest.mark.parametrize("reset_exit", [0, 128])
def test_restore_requires_successful_reset_before_clean(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    reset_exit: int,
) -> None:
    """A failed tracked-tree reset cannot trigger untracked-file deletion."""
    calls: list[tuple[str, ...]] = []

    def git_result(root: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
        assert root == tmp_path
        calls.append(args)
        if args == ("rev-parse", "--show-toplevel"):
            return subprocess.CompletedProcess(args, 0, str(tmp_path), "")
        if args == ("reset", "--hard", "HEAD"):
            return subprocess.CompletedProcess(args, reset_exit, "", "reset refused\n")
        assert args == ("clean", "-fd")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(measure, "_git", git_result)
    result = measure.restore(tmp_path.parent / "memory", tmp_path, tmp_path.parent / "home")

    assert result == {
        "restored": reset_exit == 0,
        "reason": "reset refused" if reset_exit else None,
    }
    expected = [("rev-parse", "--show-toplevel"), ("reset", "--hard", "HEAD")]
    if reset_exit == 0:
        expected.append(("clean", "-fd"))
    assert calls == expected


def test_run_preserves_unavailable_count_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful quiet output is not evidence of a zero-test run."""

    def run_command(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, ".... [100%]\n", "")

    monkeypatch.setattr(subprocess, "run", run_command)
    result = measure.run_once(["pytest"])

    assert result["exit"] == 0
    assert result["passed"] is None
    assert result["total"] is None
    assert result["reason"] == "test outcome summary unavailable"
    assert measure.parse_summary("no tests ran in 0.01s") == {"total": 0}


@pytest.mark.parametrize(
    "counts",
    [
        {"passed": None, "total": None},
        {"passed": 0, "total": 0},
        {"passed": True, "total": 1},
        {"passed": -1, "total": 1},
        {"passed": 1.0, "total": 1},
        {"passed": 2, "total": 1},
        {},
    ],
)
def test_invalid_counts_cannot_form_or_compare_a_baseline(counts: dict[str, object]) -> None:
    """Malformed or absent evidence fails on both sides of a comparison."""
    good = [{"seconds": 1.0, "exit": 0, "passed": 5, "total": 5}] * 3
    baseline = measure.band(good)
    invalid = [{"seconds": 0.1, "exit": 0, **counts}] * 3

    assert measure.band(invalid)["valid"] is False
    assert measure.compare(baseline, invalid)["valid"] is False
    assert measure.compare({**baseline, "tests": counts}, good)["valid"] is False


@pytest.mark.parametrize(
    ("base_passed", "passed", "total", "target", "valid"),
    [
        (5, 4, 4, 4, True),
        (5, 0, 4, 4, False),
        (4, 3, 4, 4, True),
        (4, 4, 4, 4, False),
        (4, 2, 4, 4, False),
        (5, 5, 5, None, True),
        (5, 4, 5, None, False),
        (5, 0, 0, 0, False),
        (5, 1, 1, True, False),
    ],
)
def test_expected_total_conserves_non_passing_outcomes(
    base_passed: int,
    passed: int,
    total: int,
    target: int | None,
    *,
    valid: bool,
) -> None:
    """Approved deselection cannot authorize a different non-passing count."""
    base_run = {"seconds": 10.0, "exit": 0, "passed": base_passed, "total": 5}
    baseline = measure.band([base_run] * 3)
    runs = [{"seconds": 1.0, "exit": 0, "passed": passed, "total": total}] * 3

    result = measure.compare(baseline, runs, expect_total=target)

    assert result["valid"] is valid
    assert result["clears_noise"] is valid


@pytest.mark.parametrize(
    ("ancestor_exit", "stderr", "reason"),
    [
        (0, "", None),
        (1, "", "base is not an ancestor of HEAD"),
        (128, "fatal: unknown revision\n", "fatal: unknown revision"),
        (128, "", "could not verify base ancestry"),
    ],
)
def test_chain_requires_verified_ancestry(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    ancestor_exit: int,
    stderr: str,
    reason: str | None,
) -> None:
    """A successful revision range cannot substitute for an ancestry check."""
    calls: list[tuple[str, ...]] = []

    def git_result(root: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
        assert root == tmp_path
        calls.append(args)
        if args == ("merge-base", "--is-ancestor", "--", "base", "HEAD"):
            return subprocess.CompletedProcess(args, ancestor_exit, "", stderr)
        assert args == ("rev-list", "--reverse", "base..HEAD")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(measure, "_git", git_result)

    assert measure.chain(tmp_path, "base", []) == {
        "ok": ancestor_exit == 0,
        "reason": reason,
    }
    expected: list[tuple[str, ...]] = [("merge-base", "--is-ancestor", "--", "base", "HEAD")]
    if ancestor_exit == 0:
        expected.append(("rev-list", "--reverse", "base..HEAD"))
    assert calls == expected
