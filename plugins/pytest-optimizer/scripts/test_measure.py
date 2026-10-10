"""Critical measurement and resume gates for optimizer execution."""

# ruff: noqa: S101, INP001
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false, reportImplicitStringConcatenation=false
from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING

import measure  # pyright: ignore[reportImplicitRelativeImport]
import pytest

if TYPE_CHECKING:
    import pathlib


def test_run_preserves_unavailable_count_evidence() -> None:
    """Successful quiet output is not evidence of a zero-test run."""
    result = measure.run_once([sys.executable, "-c", "print('.... [100%]')"])

    assert result["exit"] == 0
    assert result["passed"] is None
    assert result["total"] is None
    assert result["reason"] == "test outcome summary unavailable"
    assert measure.parse_summary("no tests ran in 0.01s") == {"total": 0}


def test_run_survives_undecodable_output_and_bounds_it() -> None:
    """Binary noise before the summary cannot break parsing or exhaust memory."""
    code = (
        "import sys;"
        "sys.stdout.buffer.write(b'\\xff\\xfe' * 3_000_000);"
        "sys.stdout.buffer.write(b'\\n2 passed in 0.01s\\n')"
    )
    result = measure.run_once([sys.executable, "-c", code])

    assert (result["exit"], result["passed"], result["total"]) == (0, 2, 2)


def test_timed_out_run_is_killed_and_invalid() -> None:
    """A hung command is stopped and cannot form a baseline."""
    slow = measure.run_once([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.2)

    assert slow["exit"] == measure.TIMED_OUT
    assert measure.band([slow] * 3) == {"valid": False, "reason": "a run timed out"}


def test_baseline_needs_the_minimum_repeats() -> None:
    """Two samples cannot estimate a spread; a single verify run is allowed explicitly."""
    run = {"seconds": 1.0, "exit": 0, "passed": 5, "total": 5}

    assert measure.band([run] * 2)["valid"] is False
    baseline = measure.band([run] * 3)
    assert measure.compare(baseline, [run])["valid"] is False
    assert measure.compare(baseline, [run], min_runs=1)["valid"] is True


def test_malformed_input_is_a_reported_failure(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Undecodable or non-JSON run files stay inside the JSON error contract."""
    bad = tmp_path / "runs.jsonl"
    bad.write_bytes(b"\xff\xfe not json\n")

    assert measure.main(["band", str(bad)]) == 1
    assert json.loads(capsys.readouterr().out)["valid"] is False


def test_identity_allows_only_approved_removals() -> None:
    """Equal counts with swapped tests fail; a planned removal passes."""
    base = "a::t1\na::t2\na::t3\n"
    plan = [{"order": 1, "removed_ids": ["a::t2"]}, {"order": 2}]

    assert measure.identity(base, "a::t1\na::t2\na::t4\n")["same"] is False
    removed = measure._removed_ids(plan, [1], None)  # noqa: SLF001
    assert measure.identity(base, "a::t3\na::t1\n", removed)["same"] is True
    assert measure._removed_ids(plan, [], 2) == set()  # noqa: SLF001


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


def test_token_cli_binds_inputs_and_command(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The command option cannot shadow the subcommand name."""
    listing = tmp_path / "collection.txt"
    listing.write_text("a::t1\n")
    base = ["token", "--head", "abc", "--collection", str(listing)]
    tokens: list[str] = []
    for extra in ([], ["--command", "pytest -x"], ["--inputs-digest", "d"]):
        assert measure.main([*base, *extra]) == 0
        tokens.append(json.loads(capsys.readouterr().out)["token"])
    assert len(set(tokens)) == len(tokens)
