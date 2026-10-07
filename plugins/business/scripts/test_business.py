"""Tests for the completeness gate, scan allow flags, and permission-safe roots."""

# ruff: noqa: S101, INP001, PLR2004, D103, ARG001
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false
# pyright: reportImplicitStringConcatenation=false, reportUnusedParameter=false

from __future__ import annotations

import io
import json
import typing as t
from pathlib import Path

import business  # pyright: ignore[reportImplicitRelativeImport]
import pytest

REGISTER = """\
- id: addressable-population
  description: Engineers whose work includes tightening drafts
  value: 40
  unit: engineers
  source_type: ESTIMATED
  confidence: low
  rationale: Team roster count
  source_ref: none
  retrieved: 2026-06-30
  owner: team lead
  updated: 2026-06-30
"""


def make_run(root: Path, *, claimed: str = "18", cite: str = "task-timings") -> Path:
    run = root / "2026-06-30" / "business" / "lean-tighten"
    (run / "raw").mkdir(parents=True)
    (run / "measurements").mkdir()
    (run / "README.md").write_text("Window: 2026-04-01..2026-06-30.\nNames: none\n")
    (run / "sources.md").write_text(
        "## task-timings\n- query: cat raw/t.csv\n- executed: 2026-06-30T10:00:00Z\n"
        "- tool version: coreutils 9.4\n- output: raw/t.csv\n"
    )
    (run / "raw" / "t.csv").write_text("task,m,a\n1,30,12\n2,25,14\n3,40,18\n")
    (run / "assumptions.yaml").write_text(REGISTER)
    (run / "measurements" / "timing.md").write_text(
        f"Median saving {claimed} min (MEASURED: sources.md `{cite}`, n=3 tasks).\n\n"
        f"check: median raw/t.csv m-a = {claimed}\n"
    )
    (run / "findings.md").write_text(
        "## Unknowns\n\n- Adoption: unknown. A usage export would resolve it.\n"
    )
    return run


def test_gate_passes_complete_run(tmp_path: Path) -> None:
    assert business.check_run(make_run(tmp_path)) == []


def test_gate_requires_names_line(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    (run / "README.md").write_text("Window: 2026-04-01..2026-06-30.\n")
    assert [p.split(":")[0] for p in business.check_run(run)] == ["README.md has no Names"]


def test_gate_recomputes_figure_from_raw(tmp_path: Path) -> None:
    problems = business.check_run(make_run(tmp_path, claimed="15"))
    assert problems == ["measurements/timing.md: median of m-a in raw/t.csv is 18, claimed 15"]


def test_gate_rejects_unresolved_citation(tmp_path: Path) -> None:
    problems = business.check_run(make_run(tmp_path, cite="missing-entry"))
    assert problems == [
        "measurements/timing.md: cited sources.md entry missing-entry does not exist"
    ]


def test_gate_flags_untagged_figure_and_bare_unknown(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    (run / "findings.md").write_text("Review took 9 h.\n\n## Unknowns\n\n- Adoption: unknown.\n")
    problems = business.check_run(run)
    assert [p.split(":")[1].strip().split(" ")[0] for p in problems] == ["figure", "unknown"]


def test_gate_cli_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert business.main(["gate", str(make_run(tmp_path))]) == 0
    assert capsys.readouterr().out == "ok\n"
    assert business.main(["gate", str(tmp_path / "nope")]) == 2


def test_scan_allow_flags() -> None:
    text = "GPT-4, UTF-8, https://arxiv.org/abs/1 and https://corp.example/x"
    hits = business.scan_text(text, allow=["UTF-8"], allow_url=["https://arxiv.org/"])
    assert [h[3] for h in hits] == ["GPT-4", "https://corp.example/x"]


def test_default_roots_survive_unreadable_windows_mount(monkeypatch: pytest.MonkeyPatch) -> None:
    def deny(self: Path, pattern: str) -> t.NoReturn:
        raise PermissionError(13, "denied", str(self))

    monkeypatch.setattr(Path, "glob", deny)
    assert business.default_roots() == [Path.home() / "Documents"]
    assert business.list_runs([Path("/mnt/c/Users/x/Documents")]) == []


@pytest.mark.parametrize(
    "text",
    [
        "Saved 18 minutes per task.",
        "Took 3 weeks.",
        "A 3-week window.",
        "About 2 engineer-days.",
        "Latency 40 sec.",
        "Over 6 months.",
        "Down 12%.",
    ],
)
def test_figure_catches_every_time_unit(text: str) -> None:
    assert business.FIGURE.search(text)


def test_figure_ignores_dates_and_ids() -> None:
    assert not business.FIGURE.search("Window 2026-04-01..2026-06-30, entry task-timings.")


PROJECT_REGISTER = "\n".join(
    f"- id: {i}\n  value: {v}\n  low: {lo}\n  high: {hi}"
    for i, v, lo, hi in [
        ("addressable-population", 40, 30, 50),
        ("instances-per-person-year", 100, 100, 100),
        ("baseline-minutes", 30, 25, 40),
        ("savings-rate", 0.4, 0.3, 0.6),
        ("adoption-rate", 0.5, 0.3, 0.7),
        ("realization-rate", 0.6, 0.4, 0.8),
    ]
)


def test_project_cli_prints_scenarios_and_ranked_sensitivity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "assumptions.yaml").write_text(PROJECT_REGISTER)
    assert business.main(["project", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "conservative: 45\n" in out
    assert "base: 240\n" in out
    assert out.index("  a: 192") < out.index("  s: 180")


def test_project_requires_multipliers_strictly_below_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "assumptions.yaml").write_text(
        PROJECT_REGISTER.replace(
            "value: 0.5\n  low: 0.3\n  high: 0.7", "value: 1\n  low: 1\n  high: 1"
        )
    )
    assert business.main(["project", str(tmp_path)]) == 1
    assert "adoption-rate: value 1.0 must be strictly between 0 and 1" in capsys.readouterr().out
    (tmp_path / "assumptions.yaml").write_text("- id: addressable-population\n  value: 40\n")
    assert business.main(["project", str(tmp_path)]) == 1
    assert "adoption-rate: missing from the assumptions register" in capsys.readouterr().out


def test_stats_and_runs_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sample = tmp_path / "n.txt"
    sample.write_text("1\n2\n9\n")
    assert business.main(["stats", str(sample)]) == 0
    out = capsys.readouterr().out
    assert "label: DIRECTIONAL" in out
    assert "range_lo: 1.0" in out
    assert "range_hi: 9.0" in out
    assert "ci95" not in out
    sample.write_text("1\n2\n3\n4\n9\n")
    assert business.main(["stats", str(sample)]) == 0
    assert "ci95_lo" in capsys.readouterr().out
    make_run(tmp_path)
    assert business.main(["runs", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip().endswith("2026-06-30/business/lean-tighten")


def test_project_lists_every_missing_factor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "assumptions.yaml").write_text("- id: unrelated\n  value: 1\n")
    assert business.main(["project", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert all(f"{ident}: missing" in out for _, ident in business.FACTORS)


def test_gate_flags_open_unknowns_heading_and_currency(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    (run / "findings.md").write_text("## Open unknowns\n\n- Adoption: unknown.\n\nSaved $40.\n")
    problems = business.check_run(run)
    assert any("unknown without the data" in p for p in problems)
    assert any("currency '$'" in p for p in problems)


def test_stats_csv_column_difference_skips_blank_cells(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sample = tmp_path / "t.csv"
    sample.write_text("a,b\n10,4\n9,\n8,2\n")
    assert business.main(["stats", "--csv", str(sample), "--column", "a-b"]) == 0
    assert "n: 2\n" in capsys.readouterr().out
    assert business.main(["stats", "--csv", str(sample), "--column", "z"]) == 2


def test_collect_prs_reads_paginated_pages(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def page(number: int, merged: str) -> str:
        pr: dict[str, object] = {
            "number": number,
            "createdAt": "2026-04-02T00:00:00Z",
            "mergedAt": merged,
            "additions": 1,
            "deletions": 0,
            "author": {"login": "ann"},
            "reviews": {"nodes": []},
            "reopened": {"filteredCount": 1},
        }
        return json.dumps({"data": {"repository": {"pullRequests": {"nodes": [pr]}}}})

    pages = tmp_path / "pages.json"
    pages.write_text(page(2, "2026-04-02T12:00:00Z") + page(1, "2026-07-02T00:00:00Z") + "\n")
    args = ["collect-prs", "--start", "2026-04-01", "--end", "2026-06-30", str(pages)]
    assert business.main(args) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("number,created_at")
    assert lines[1:] == ["2,2026-04-02T00:00:00Z,2026-04-02T12:00:00Z,12.00,,1,1,0"]
    pages.write_text("[1]")
    assert business.main(args) == 2


BREAKEVEN_REGISTER = "\n".join(
    f"- id: {i}\n  value: {v}\n  low: {lo}\n  high: {hi}"
    for i, v, lo, hi in [
        ("manual-minutes", 30, 28, 40),
        ("ai-minutes", 10, 8, 12),
        ("verify-minutes", 4, 3, 6),
        ("rework-probability", 0.2, 0.1, 0.3),
        ("rework-minutes", 20, 10, 30),
        ("instances-in-period", 600, 500, 700),
        ("build-hours", 20, 15, 30),
        ("maintenance-hours-per-period", 2, 1, 4),
        ("periods", 4, 4, 4),
    ]
)


def test_breakeven_cli_prints_every_scenario(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "assumptions.yaml").write_text(BREAKEVEN_REGISTER)
    assert business.main(["breakeven", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "conservative S_net (engineer-hours per period): -37.67\n" in out
    assert "base N_breakeven (instances): 140\n" in out
    assert "missing:" not in out


def test_breakeven_reports_unknowns_and_computes_only_what_is_registered(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "assumptions.yaml").write_text(
        "- id: " + "\n- id: ".join(BREAKEVEN_REGISTER.split("- id: ")[1:6])
    )
    assert business.main(["breakeven", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "base S_inst (minutes per instance): 12\n" in out
    assert "S_net" not in out
    assert "missing: build-hours\n" in out
    (tmp_path / "assumptions.yaml").write_text("- id: periods\n  value: 4\n")
    assert business.main(["breakeven", str(tmp_path)]) == 1


def _review_page(*, has_next: bool) -> str:
    pr: dict[str, object] = {
        "number": 9,
        "createdAt": "2026-04-02T00:00:00Z",
        "mergedAt": "2026-04-02T12:00:00Z",
        "additions": 1,
        "deletions": 0,
        "author": {"login": "ann-author"},
        "reviews": {
            "pageInfo": {"hasNextPage": has_next},
            "nodes": [
                {
                    "submittedAt": "2026-04-02T03:00:00Z",
                    "author": {"login": "bo-reviewer", "__typename": "User"},
                }
            ],
        },
        "reopened": {"filteredCount": 0},
    }
    return json.dumps({"data": {"repository": {"pullRequests": {"nodes": [pr]}}}})


def test_collect_prs_stdin_output_holds_no_logins(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(_review_page(has_next=False)))
    args = ["collect-prs", "--start", "2026-04-01", "--end", "2026-04-30"]
    assert business.main(args) == 0
    out = capsys.readouterr()
    assert out.out.splitlines()[1].split(",")[4] == "3.00"
    assert "ann-author" not in out.out + out.err
    assert "bo-reviewer" not in out.out + out.err
    assert out.err == ""


def test_collect_prs_warns_when_reviews_are_truncated(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(_review_page(has_next=True)))
    args = ["collect-prs", "--start", "2026-04-01", "--end", "2026-04-30"]
    assert business.main(args) == 0
    assert "warning: PR #9: reviews truncated at 1" in capsys.readouterr().err


def test_unknown_bullet_accepts_any_data_clause(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    (run / "findings.md").write_text("## Unknowns\n\n- Adoption: unknown. Needs a usage export.\n")
    assert business.check_run(run) == []
    (run / "findings.md").write_text("## Unknowns\n\n- Adoption: unknown.\n")
    assert len(business.check_run(run)) == 1
