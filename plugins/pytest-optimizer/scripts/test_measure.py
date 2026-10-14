"""Critical measurement and resume gates for optimizer execution."""

# ruff: noqa: S101, INP001
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false, reportImplicitStringConcatenation=false
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import typing as t

import measure  # pyright: ignore[reportImplicitRelativeImport]
import pytest


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


IMPACT_QUARTILE = 0.75


def _run_cli(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, dict[str, object]]:
    code = measure.main(list(argv))
    return code, json.loads(capsys.readouterr().out)


def test_score_derives_impact_and_refuses_out_of_range_dimensions(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Impact comes from the measured saving, so a stale or negative impact cannot be passed."""
    rest = ["--effort", "1", "--confidence", "1", "--reversibility", "1", "--safety"]
    gate = ["--delta", "3", "--baseline", "10"]

    code, out = _run_cli(capsys, "score", *gate, *rest, "2")
    assert (code, str(out["reason"]).endswith("must be between 0 and 1")) == (1, True)
    _, out = _run_cli(capsys, "score", *gate, *rest, "1")
    assert (out["impact"], out["dropped"]) == (0.0, "impact is 0")
    _, out = _run_cli(capsys, "score", *gate, "--clears-noise", *rest, "1")
    assert (out["impact"], out["dropped"]) == (IMPACT_QUARTILE, None)
    assert _run_cli(capsys, "score", *rest, "1")[0] == 1


def test_memory_dir_resolves_an_explicit_relative_path(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Phases run from the worktree, so a relative path must not stay relative."""
    monkeypatch.chdir(tmp_path)
    code, out = _run_cli(capsys, "memory-dir", "--memory-dir", "rel", "--repo-root", str(tmp_path))

    assert code == 0
    assert out["path"] == str(tmp_path.resolve() / "rel")


def test_state_resume_and_complete_follow_the_phase_order(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Completing an earlier phase clears the later flags; resume names the first open one."""
    state = tmp_path / "m" / "state.json"
    assert _run_cli(capsys, "state", "resume", str(state))[1]["next"] == "scan"
    for phase in ("scan", "benchmark", "plan"):
        _run_cli(capsys, "state", "complete", str(state), "--phase", phase)
    assert _run_cli(capsys, "state", "resume", str(state))[1]["next"] == "execute"

    _, out = _run_cli(
        capsys, "state", "complete", str(state), "--phase", "scan", "--set", 'env_token="t"'
    )
    saved = json.loads(state.read_text())

    assert out["next"] == "benchmark"
    assert (saved["completed"]["plan"], saved["env_token"], saved["phase"]) == (False, "t", "scan")

    _run_cli(capsys, "state", "update", str(state), "--set", "last_applied_index=2")
    kept = json.loads(state.read_text())
    assert (kept["last_applied_index"], kept["completed"]["scan"], kept["phase"]) == (
        2,
        True,
        "scan",
    )


def test_baseline_cli_writes_the_file_and_keeps_later_fields(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Valid runs become baseline.json; invalid runs write nothing."""
    run = {"seconds": 1.0, "exit": 0, "passed": 5, "total": 5}
    runs = tmp_path / "runs.jsonl"
    runs.write_text("\n".join(json.dumps(run) for _ in range(3)))
    out_file = tmp_path / "baseline.json"
    out_file.write_text(json.dumps({"timings": [{"nodeid": "a"}]}))
    argv = ["--test-command", "pytest", "--pytest-version", "9.1.1", "--plugin", "x=1"]

    code, _ = _run_cli(capsys, "baseline", str(runs), "--out", str(out_file), *argv)
    saved = json.loads(out_file.read_text())

    assert code == 0
    assert (saved["tests"], saved["plugins"], saved["timings"]) == (
        {"passed": 5, "total": 5},
        {"x": "1"},
        [{"nodeid": "a"}],
    )
    assert measure.compare(saved, [run] * 3)["valid"] is True

    runs.write_text(json.dumps(run))
    out_file.unlink()
    code, out = _run_cli(capsys, "baseline", str(runs), "--out", str(out_file), *argv)
    assert (code, out["valid"], out_file.exists()) == (1, False, False)


def test_record_stamps_and_replaces_by_id(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Entries carry the scan's token and HEAD; a re-benchmark replaces its own entry."""
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"env_token": "tok", "base_head": "abc"}))
    bench = tmp_path / "benchmarks.json"
    entry = tmp_path / "entry.json"
    for delta in (1, 2):
        entry.write_text(json.dumps({"id": "H10", "median_delta": delta}))
        code, _ = _run_cli(
            capsys, "record", str(bench), "--state", str(state), "--entry", str(entry)
        )
        assert code == 0

    assert json.loads(bench.read_text()) == [
        {"id": "H10", "median_delta": 2, "env_token": "tok", "base_head": "abc"}
    ]
    state.write_text("{}")
    assert (
        _run_cli(capsys, "record", str(bench), "--state", str(state), "--entry", str(entry))[0] == 1
    )


def test_budget_totals_and_regress_cli(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The arithmetic the phases used to do in prose is one command each."""
    _, out = _run_cli(capsys, "budget", "--phase", "scan", "--seconds", "100", "--runs", "5")
    assert (out["estimate"], out["over"], out["timeout"]) == (700.0, False, 400.0)
    _, out = _run_cli(
        capsys, "budget", "--phase", "benchmark", "--seconds", "100", "--runs", "3",
        "--hypotheses", "5",
    )  # fmt: skip
    assert (out["estimate"], out["fits"]) == (2400.0, 3)

    base = tmp_path / "baseline.json"
    base.write_text(json.dumps({"tests": {"passed": 10, "total": 10}}))
    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps([{"order": 2}, {"order": 1, "removes_tests": 2}]))
    _, out = _run_cli(capsys, "totals", str(base), str(draft))
    assert out["totals"] == [{"order": 1, "expected_total": 8}, {"order": 2, "expected_total": 8}]

    control = tmp_path / "control.json"
    control.write_text(json.dumps({"noise": {"median": 10.0, "band": 0.5}}))
    assert _run_cli(capsys, "regress", str(control), "11")[1]["rerun"] is True
    code, out = _run_cli(capsys, "regress", str(control), "11", "12", "10")
    assert (code, out["regressed"]) == (1, True)


def test_expected_total_and_ids_cli_read_the_files(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The commands 03-execute runs behave end to end, not only through their helpers."""
    base = tmp_path / "baseline.json"
    base.write_text(json.dumps({"tests": {"passed": 3, "total": 3}}))
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps([{"order": 1, "expected_total": 2, "removed_ids": ["a::t2"]}]))
    log = tmp_path / "log.json"
    log.write_text(json.dumps([]))
    listing = tmp_path / "collection.txt"
    listing.write_text("a::t1\na::t2\na::t3\n")
    after = tmp_path / "after.txt"
    after.write_text("a::t1\na::t3\n")

    _, out = _run_cli(capsys, "expected-total", "--through", "1", str(base), str(plan), str(log))
    assert out == {"expected_total": 2}
    ids = ["ids", "--plan", str(plan), "--log", str(log), str(listing), str(after)]
    assert _run_cli(capsys, *ids, "--through", "1")[0] == 0
    assert _run_cli(capsys, *ids)[0] == 1


def test_runs_dir_and_exclude_cli(
    tmp_path: pathlib.Path,
    tmp_path_factory: pytest.TempPathFactory,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Run files land in the git directory; the exclude line is added once."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)  # noqa: S603, S607
    root = ["--repo-root", str(tmp_path)]

    _, out = _run_cli(capsys, "runs-dir", *root, "--memory-dir", str(tmp_path / "mem"))
    assert out["source"] == "git"
    assert (tmp_path / ".git" / "pytest-optimizer-runs").is_dir()
    assert _run_cli(capsys, "exclude", *root, ".pytest-optimizer/")[1]["added"] == [
        ".pytest-optimizer/"
    ]
    assert _run_cli(capsys, "exclude", *root, ".pytest-optimizer/")[1]["added"] == []
    assert (tmp_path / ".git" / "info" / "exclude").read_text().count(".pytest-optimizer/") == 1
    not_repo = tmp_path_factory.mktemp("plain")
    assert _run_cli(capsys, "exclude", "--repo-root", str(not_repo), "x")[0] == 1


def test_rubric_table_weights_match_the_scorer() -> None:
    """The reference table and WEIGHTS are two spellings of one rule."""
    text = (pathlib.Path(__file__).parent.parent / "references" / "scoring-rubric.md").read_text()
    rows = re.findall(r"^\| `(\w+)` \| ([\d.]+) \|", text, flags=re.MULTILINE)

    assert {name: float(weight) for name, weight in rows} == measure.WEIGHTS


def test_baseline_cli_stores_timings_plugins_and_capabilities(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A literal run records every field the schema names, timings included."""
    run = {"seconds": 1.0, "exit": 0, "passed": 5, "total": 5}
    runs = tmp_path / "runs.jsonl"
    runs.write_text("\n".join(json.dumps(run) for _ in range(3)))
    caps = tmp_path / "capabilities.json"
    caps.write_text('{"durations_min": true}')
    table = tmp_path / "durations.txt"
    table.write_text("4.80s setup    t.py::a\n0.61s call     t.py::a\n4.80s setup    t.py::a\n")
    out_file = tmp_path / "baseline.json"

    code, _ = _run_cli(
        capsys, "baseline", str(runs), "--out", str(out_file), "--test-command", "pytest",
        "--pytest-version", "9.1.1", "--plugin", "x=1",
        "--flag=-p", "--flag=no:cacheprovider", "--capabilities", str(caps),
        "--durations", str(table),
    )  # fmt: skip
    saved = json.loads(out_file.read_text())

    assert code == 0
    assert saved["measurement_flags"] == ["-p", "no:cacheprovider"]
    assert saved["capabilities"] == {"durations_min": True}
    assert [(r["nodeid"], r["phase"]) for r in saved["timings"]] == [
        ("t.py::a", "setup"),
        ("t.py::a", "call"),
    ]


def test_scan_idempotency_hypothesis_ids_and_pending(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The skip decision, the ids and the to-do list come from commands, not prose."""
    mem = tmp_path / "m"
    state = mem / "state.json"
    _run_cli(capsys, "state", "complete", str(state), "--phase", "scan",
             "--set", 'env_token="t"', "--set", 'base_head="h"',
             "--set", "hygiene=false")  # fmt: skip
    check = ["state", "unchanged", str(state), "--token", "t", "--hygiene", "false"]
    assert _run_cli(capsys, *check, "--require", "hypotheses.json")[1]["unchanged"] is False
    for hid in ("H10", "H33"):
        _, out = _run_cli(capsys, "hyp-id", "--heuristic", hid, "--file", "a.py", "--evidence", hid)
        _run_cli(capsys, "record", str(mem / "hypotheses.json"), "--id", str(out["id"]),
                 "--set", f'heuristic="{hid}"')  # fmt: skip
    assert _run_cli(capsys, *check, "--require", "hypotheses.json")[1]["unchanged"] is True
    assert _run_cli(capsys, *check[:-1], "true")[1]["unchanged"] is False

    first = t.cast("list[str]", _run_cli(capsys, "pending", "--memory-dir", str(mem))[1]["ids"])
    assert len(first) == len(("H10", "H33"))
    _run_cli(capsys, "record", str(mem / "benchmarks.json"), "--state", str(state),
             "--id", first[0])  # fmt: skip
    assert _run_cli(capsys, "pending", "--memory-dir", str(mem))[1]["ids"] == first[1:]
    forced = _run_cli(capsys, "pending", "--memory-dir", str(mem), "--force")
    assert forced[1]["ids"] == first


def test_plan_build_and_log_cli(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The plan takes impact and totals from the benchmarks; the log propagates skips."""
    mem = tmp_path
    (mem / "state.json").write_text(json.dumps({"env_token": "t", "base_head": "h"}))
    (mem / "baseline.json").write_text(
        json.dumps({"noise": {"median": 10.0}, "tests": {"passed": 10, "total": 10}})
    )
    entry = {"verdict": "validated", "env_token": "t", "median_delta": 3.0, "clears_noise": True,
             "files": ["f"], "patch": "p", "patch_sha256": "x"}  # fmt: skip
    (mem / "benchmarks.json").write_text(
        json.dumps([{"id": "a", **entry}, {"id": "b", **entry, "clears_noise": False}])
    )
    dims = {"safety": 0.9, "effort": 1, "confidence": 0.9, "reversibility": 0.9}
    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps([
        {"order": 1, "id": "a", "score": dims, "commit": {}},
        {"order": 2, "id": "b", "score": dims, "commit": {}},
    ]))  # fmt: skip
    code, out = _run_cli(capsys, "plan-build", "--memory-dir", str(mem), "--draft", str(draft),
                         "--out", str(mem / "plan.json"))  # fmt: skip

    assert code == 0
    assert out["dropped"] == [{"id": "b", "reason": "impact is 0"}]
    assert json.loads((mem / "plan.json").read_text())[0]["score"]["impact"] == IMPACT_QUARTILE

    plan = [{"order": 1, "id": "a"}, {"order": 2, "id": "b", "depends_on": ["a"]}]
    (mem / "plan.json").write_text(json.dumps(plan))
    base = ["log", "--memory-dir", str(mem)]
    _run_cli(capsys, *base, "begin", "--order", "1", "--set", 'pending_tree="T"')
    _run_cli(capsys, *base, "skip", "--order", "1", "--set", 'reason="red"')
    saved = json.loads((mem / "execution-log.json").read_text())

    assert [(e["order"], e["applied"], e["skip_reason"]) for e in saved] == [
        (1, False, "red"),
        (2, False, "depends on a skipped item"),
    ]
    assert json.loads((mem / "state.json").read_text())["last_applied_index"] == 1


def test_record_reads_capture_and_ids_outputs(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Hash, files and removed ids come from the tools' own JSON, not from copying."""
    mem = tmp_path / "mem"
    (mem / "patches").mkdir(parents=True)
    state = mem / "state.json"
    state.write_text(json.dumps({"env_token": "t", "base_head": "h"}))
    cap = tmp_path / "cap.json"
    cap.write_text(
        json.dumps(
            {
                "ok": True,
                "patch": str(mem / "patches" / "a.patch"),
                "sha256": "abc",
                "paths": ["f.py"],
            }
        )
    )
    ids = tmp_path / "ids.json"
    ids.write_text(json.dumps({"same": False, "missing": ["x::t2"], "unexpected": []}))

    code, _ = _run_cli(
        capsys, "record", str(mem / "benchmarks.json"), "--state", str(state), "--id", "a",
        "--capture-json", str(cap), "--ids-json", str(ids),
    )  # fmt: skip
    entry = json.loads((mem / "benchmarks.json").read_text())[0]

    assert code == 0
    assert (entry["patch"], entry["patch_sha256"], entry["files"]) == (
        "patches/a.patch", "abc", ["f.py"],
    )  # fmt: skip
    assert (entry["removed_ids"], entry["removes_tests"]) == (["x::t2"], 1)


def test_plan_build_names_an_unknown_or_rejected_item(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The refusal says which item and why, in one line."""
    (tmp_path / "state.json").write_text(json.dumps({"env_token": "t"}))
    (tmp_path / "baseline.json").write_text(
        json.dumps({"noise": {"median": 10.0}, "tests": {"passed": 1, "total": 1}})
    )
    (tmp_path / "benchmarks.json").write_text(
        json.dumps([{"id": "r", "verdict": "rejected", "reason": "count drop"}])
    )
    dims = {"safety": 1, "effort": 1, "confidence": 1, "reversibility": 1}
    reasons: list[object] = []
    for item in ("ghost", "r"):
        draft = tmp_path / "d.json"
        draft.write_text(json.dumps([{"order": 1, "id": item, "score": dims, "commit": {}}]))
        code, out = _run_cli(capsys, "plan-build", "--memory-dir", str(tmp_path),
                             "--draft", str(draft))  # fmt: skip
        assert code == 1
        reasons.append(out["reason"])

    assert reasons == [
        "ghost is not in benchmarks.json",
        "r is rejected, not validated: count drop",
    ]


def test_log_reads_gate_and_run_outputs(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Pending tree, parent and verify seconds come straight from gate and run."""
    (tmp_path / "plan.json").write_text(json.dumps([{"order": 1, "id": "a"}]))
    gate = tmp_path / "gate.json"
    gate.write_text(json.dumps({"ok": True, "tree": "T", "parent": "P"}))
    run = tmp_path / "verify.jsonl"
    run.write_text(json.dumps({"seconds": 7.9, "exit": 0}) + "\n")
    base = ["log", "--memory-dir", str(tmp_path), "--order", "1"]

    _run_cli(capsys, *base[:1], "begin", *base[1:], "--gate-json", str(gate))
    pending = json.loads((tmp_path / "execution-log.json").read_text())[0]
    assert (pending["pending_parent"], pending["pending_tree"]) == ("P", "T")

    _run_cli(capsys, *base[:1], "commit", *base[1:], "--run-json", str(run),
             "--set", 'commit_sha="abc"')  # fmt: skip
    done = json.loads((tmp_path / "execution-log.json").read_text())[0]
    assert (done["verify"]["seconds"], "pending_tree" in done) == (7.9, False)


def test_log_and_record_name_a_failed_input_instead_of_a_key_error(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A failed gate or capture is reported by its own reason, exit 1."""
    (tmp_path / "plan.json").write_text(json.dumps([{"order": 1, "id": "a"}]))
    gate = tmp_path / "gate.json"
    gate.write_text(
        json.dumps({"ok": False, "reason": "staged paths differ from the plan's files"})
    )
    argv = ["log", "begin", "--memory-dir", str(tmp_path), "--order", "1"]
    code, out = _run_cli(capsys, *argv, "--gate-json", str(gate))
    assert (code, out["reason"]) == (
        1, "gate did not pass: staged paths differ from the plan's files",
    )  # fmt: skip

    cap = tmp_path / "cap.json"
    cap.write_text(json.dumps({"ok": False, "reason": "the worktree has no change against HEAD"}))
    bench = tmp_path / "benchmarks.json"
    code, out = _run_cli(capsys, "record", str(bench), "--id", "a", "--capture-json", str(cap))
    assert (code, out["reason"]) == (
        1, "capture did not succeed: the worktree has no change against HEAD",
    )  # fmt: skip
    assert not bench.exists()
