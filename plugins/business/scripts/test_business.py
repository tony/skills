"""Tests for the completeness gate, scan allow flags, and permission-safe roots."""

# ruff: noqa: S101, INP001, PLR2004, D103, ARG001, SLF001
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false
# pyright: reportImplicitStringConcatenation=false, reportUnusedParameter=false

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
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
    (run / "README.md").write_text("Window: 2026-04-01..2026-06-30.\nNames: none\nPeople: none\n")
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
    assert [p.split(" (")[0] for p in business.check_run(run)] == [
        "README.md has no Names: line",
        "README.md has no People: line",
    ]
    (run / "README.md").write_text("Window: 2026-04-01..2026-06-30.\nNames: none\nPeople: none\n")
    assert business.check_run(run) == []


def test_gate_recomputes_figure_from_raw(tmp_path: Path) -> None:
    problems = business.check_run(make_run(tmp_path, claimed="15"))
    assert problems == ["measurements/timing.md: median of m-a in raw/t.csv is 18, claimed 15"]


def test_gate_rejects_nonfinite_data_and_duplicate_assumptions(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    (run / "raw" / "t.csv").write_text("task,m,a\n1,nan,12\n2,nan,14\n3,nan,18\n")
    (run / "assumptions.yaml").write_text(REGISTER + REGISTER.replace("value: 40", "value: nan"))
    problems = business.check_run(run)
    assert any("duplicate id" in problem for problem in problems)
    assert any("not a number" in problem for problem in problems)
    assert any("no numeric column" in problem for problem in problems)


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
    text = "PROJ-4, ABC-8, https://arxiv.org/abs/1 and https://corp.example/x"
    hits = business.scan_text(text, allow=["ABC-8"], allow_url=["https://arxiv.org/"])
    assert [h[3] for h in hits] == ["PROJ-4", "https://corp.example/x"]


def test_scan_rules_limits_kinds() -> None:
    text = "ROI of $5 at https://corp.example/x"
    hits = business.scan_text(text, rules=["currency", "money-term"])
    assert [h[2] for h in hits] == ["money-term", "currency"]


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
        ("manual-minutes", 30, 25, 40),
        ("savings-rate", 0.4, 0.3, 0.6),
        ("adoption-rate", 0.5, 0.3, 0.7),
        ("realization-rate", 0.6, 0.4, 0.8),
    ]
)


@pytest.mark.parametrize("value", ["-1", "inf", "nan"])
def test_projection_refuses_invalid_populations(value: str) -> None:
    register = PROJECT_REGISTER.replace(
        "value: 40\n  low: 30\n  high: 50", f"value: {value}\n  low: {value}\n  high: {value}"
    )
    figures, problems = business.project(register)
    assert figures == {}
    assert any("addressable-population:" in problem for problem in problems)


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


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("nan", "finite numbers"),
        ("inf", "finite numbers"),
        ("1e308", "numeric range"),
        ("not-a-number", "could not convert"),
    ],
)
def test_stats_refuses_invalid_observations(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], value: str, message: str
) -> None:
    sample = tmp_path / "timing.txt"
    sample.write_text(f"{value}\n{value}\n{value}\n")
    assert business.main(["stats", str(sample)]) == 2
    result = capsys.readouterr()
    assert result.out == ""
    assert message in result.err


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


@pytest.mark.parametrize("value", ["-1", "inf"])
def test_breakeven_refuses_invalid_rework_probability(value: str) -> None:
    register = BREAKEVEN_REGISTER.replace(
        "value: 0.2\n  low: 0.1\n  high: 0.3", f"value: {value}\n  low: {value}\n  high: {value}"
    )
    figures, missing, problems = business.breakeven(register)
    assert figures == {}
    assert missing == []
    assert any("rework-probability:" in problem for problem in problems)


def test_breakeven_cli_prints_every_scenario(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "assumptions.yaml").write_text(BREAKEVEN_REGISTER)
    assert business.main(["breakeven", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "conservative S_net (engineer-hours over horizon): -37.67\n" in out
    assert "base N_breakeven (instances): 140\n" in out
    assert "missing:" not in out


def test_calculators_refuse_overflowing_products() -> None:
    population = PROJECT_REGISTER.replace(
        "value: 40\n  low: 30\n  high: 50", "value: 1e308\n  low: 1e308\n  high: 1e308"
    )
    assert business.project(population) == ({}, ["projection exceeds the supported numeric range"])
    volume = BREAKEVEN_REGISTER.replace(
        "value: 600\n  low: 500\n  high: 700", "value: 1e308\n  low: 1e308\n  high: 1e308"
    )
    assert business.breakeven(volume) == (
        {},
        [],
        ["break-even exceeds the supported numeric range"],
    )


def test_breakeven_uses_high_volume_for_conservative_losses() -> None:
    register = BREAKEVEN_REGISTER.replace(
        "value: 30\n  low: 28\n  high: 40", "value: 10\n  low: 10\n  high: 10"
    )
    figures, missing, problems = business.breakeven(register)
    assert not missing
    assert not problems
    assert [figures[f"{s}_s_net"] for s in business.SCENARIOS] == [-244.33, -108, -35.67]
    assert all(figures[f"{s}_n_breakeven"] is None for s in business.SCENARIOS)


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


LEAKS: dict[str, tuple[str, list[str]]] = {
    "denied-name": ("Team lead priya shipped it.", ["Priya Raman"]),
    "denied-name-compound": ("Ran LeanTighten and lean tighten.", ["lean-tighten"]),
    "host": ("See wiki.acme-internal.example/tighten", []),
    "host-internal": ("Runs on build01.corp.local", []),
    "ip": ("Served from 10.2.3.4 today", []),
    "handle": ("Ask @ann-dev about it", []),
    "path-opt": ("Config in /opt/acme/app", []),
    "path-unc": (r"Share at \\fileserver\share", []),
    "path-drive": ("Saved to C:/Users/ann/x", []),
    "secret-github": ("Token ghp_abcdefghijklmnopqrstuvwxyz0123456789", []),
    "secret-aws": ("Key AKIAABCDEFGHIJKLMNOP", []),
    "secret-slack": ("Hook xoxb-1234567890-abcdefghij", []),
    "secret-pem": ("-----BEGIN RSA PRIVATE KEY-----", []),
    "repo-slug": ("Cloned from acme/widgets", []),
    "money-saving": ("It is a cost-saving move.", []),
    "money-salary": ("Fits the salary band.", []),
    "money-euros": ("Worth 5 euros or 150 bucks.", []),
    "currency-fullwidth": ("Costs \uff045 each", []),
}


@pytest.mark.parametrize("case", sorted(LEAKS))
def test_scan_flags_every_leak_class(case: str) -> None:
    text, deny = LEAKS[case]
    assert business.scan_text(text, deny=deny)


def test_scan_denies_each_name_word_but_not_longer_words() -> None:
    assert [h[3] for h in business.scan_text("priya met Raman.", deny=["Priya Raman"])] == [
        "priya",
        "Raman",
    ]
    assert business.scan_text("The Atlassian suite.", deny=["Atlas"]) == []


def test_scan_leaves_public_citations_and_prose_clean() -> None:
    text = (
        "METR (2025) found developers 19% slower (n=16, 246 tasks); Bain reports 10-15% gains.\n"
        "DORA 2024 measured -1.5% delivery throughput; see arXiv:2507.09089 and Cui et al.\n"
        "Windows for Q2-2026 follow ISO-8601; SHA-256 and GPT-4 and COVID-19 are not tickets.\n"
        "Read/write and client/server paths, and/or input/output, ran 24/7 in Node.js.\n"
        "Median fell from 26 h to 9 h (MEASURED, n=41).\n"
    )
    assert business.scan_text(text) == []


def test_scan_allow_url_also_allows_the_bare_host() -> None:
    hits = business.scan_text(
        "See arxiv.org and docs.corp.example", allow_url=["https://arxiv.org/"]
    )
    assert [h[3] for h in hits] == ["docs.corp.example"]


def test_scan_reads_names_from_the_run_readme(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = make_run(tmp_path)
    (run / "README.md").write_text("Window: 2026-04-01..2026-06-30.\nNames: Priya Raman, Atlas\n")
    draft = tmp_path / "draft.md"
    draft.write_text("Priya on the Atlas team.\n")
    assert business.main(["scan", "--run", str(run), str(draft)]) == 1
    assert capsys.readouterr().out == "1:1: denied-name: Priya\n1:14: denied-name: Atlas\n"
    (run / "README.md").write_text("Names: none\n")
    assert business.main(["scan", "--run", str(run), str(draft)]) == 0
    (run / "README.md").write_text("Window: 2026-04-01..2026-06-30.\n")
    assert business.main(["scan", "--run", str(run), str(draft)]) == 2
    assert "README.md has no Names: line" in capsys.readouterr().err


def test_scan_tier_three_denies_people_absent_from_names(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = make_run(tmp_path)
    (run / "README.md").write_text("Names: none\nPeople: Priya Raman\n")
    draft = tmp_path / "draft.md"
    draft.write_text("Thanks to Priya.\n")
    assert business.main(["scan", "--run", str(run), str(draft)]) == 1
    assert capsys.readouterr().out == "1:11: denied-name: Priya\n"


def test_scan_reads_names_from_a_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    names = tmp_path / "names.txt"
    names.write_text("Priya Raman\nlean-tighten, Atlas\n")
    draft = tmp_path / "draft.md"
    draft.write_text("lean tighten by Raman\n")
    assert business.main(["scan", "--names-file", str(names), str(draft)]) == 1
    assert [x.split(": ")[2] for x in capsys.readouterr().out.splitlines()] == [
        "lean tighten",
        "Raman",
    ]
    assert business.main(["scan", "--names-file", str(tmp_path / "gone"), str(draft)]) == 2


def test_trace_flags_figures_missing_from_the_case_study(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    study = tmp_path / "case-study-public.md"
    study.write_text("Median 18 min per task (MEASURED, n=41 PRs), a 12.5% drop, 1,200 tasks.\n")
    release = tmp_path / "pr-release.md"
    release.write_text("1. Median 18 min (MEASURED, n=41 PRs), 12.50% drop, 1200 tasks.\n")
    assert business.main(["trace", str(release), "--against", str(study)]) == 0
    release.write_text("Median 18 min, saving 30 min over 41 PRs\n")
    assert business.main(["trace", str(release), "--against", str(study)]) == 1
    assert capsys.readouterr().out.splitlines()[-1] == "1:23: figure not in the source text: 30"
    assert business.main(["trace", str(release), "--against", str(tmp_path / "gone")]) == 2


def test_gate_rejects_an_invented_timestamp(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    sources = run / "sources.md"
    sources.write_text(sources.read_text().replace("2026-06-30T10:00:00Z", "2026-invented"))
    assert business.check_run(run) == [
        "sources.md entry task-timings: executed '2026-invented' is not an ISO timestamp"
    ]
    sources.write_text(sources.read_text().replace("2026-invented", "2026-06-30"))
    assert len(business.check_run(run)) == 1


@pytest.mark.parametrize(
    "clause", ["Adoption: unknown, no data.", "Adoption: unknown; nothing to export."]
)
def test_unknown_with_a_negated_data_clause_does_not_resolve(tmp_path: Path, clause: str) -> None:
    run = make_run(tmp_path)
    (run / "findings.md").write_text(f"## Unknowns\n\n- {clause}\n")
    problems = business.check_run(run)
    assert len(problems) == 1
    assert "unknown without the data" in problems[0]


def test_init_creates_a_run_and_refuses_one_with_snapshots(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ["init", "lean-tighten", "--root", str(tmp_path), "--date", "2026-06-30"]
    assert business.main(args) == 0
    run = tmp_path / "2026-06-30" / "business" / "lean-tighten"
    assert capsys.readouterr().out.strip() == str(run)
    assert (
        (run / "index.md").read_text().startswith("---\nnamespace: business\ntopic: lean-tighten")
    )
    assert [p.name for p in sorted(run.iterdir())] == [
        "README.md",
        "index.md",
        "measurements",
        "raw",
        "reports",
    ]
    (run / "README.md").write_text("kept\n")
    assert business.main(args) == 0
    assert (run / "README.md").read_text() == "kept\n"
    (run / "raw" / "t.csv").write_text("a\n")
    assert business.main(args) == 2
    assert "raw/ of 2026-06-30/business/lean-tighten already holds 1 snapshot(s)" in (
        capsys.readouterr().err
    )
    assert (run / "raw" / "t.csv").read_text() == "a\n"


@pytest.mark.parametrize("bad", ["Lean Tighten", "../x", ""])
def test_init_refuses_a_non_slug_workflow(tmp_path: Path, bad: str) -> None:
    assert business.main(["init", bad, "--root", str(tmp_path)]) == 2
    assert list(tmp_path.iterdir()) == []


def test_collect_prs_blanks_absent_fields_and_counts_them(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pr: dict[str, object] = {
        "number": 9,
        "createdAt": "2026-04-02T00:00:00Z",
        "mergedAt": "2026-04-02T12:00:00Z",
        "additions": 4,
    }
    page = {"data": {"repository": {"pullRequests": {"nodes": [pr, {**pr, "number": 10}]}}}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(page)))
    args = ["collect-prs", "--start", "2026-04-01", "--end", "2026-04-30"]
    assert business.main(args) == 0
    out = capsys.readouterr()
    assert out.out.splitlines()[1:] == [
        "9,2026-04-02T00:00:00Z,2026-04-02T12:00:00Z,12.00,,,4,",
        "10,2026-04-02T00:00:00Z,2026-04-02T12:00:00Z,12.00,,,4,",
    ]
    assert out.err.splitlines() == [
        "warning: 2 of 2 rows lack reopened; left blank, not zero",
        "warning: 2 of 2 rows lack deletions; left blank, not zero",
    ]


def test_collect_prs_refuses_empty_input_and_never_overwrites_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "pr-metrics.csv"
    args = ["collect-prs", "--start", "2026-04-01", "--end", "2026-04-30", "--output", str(target)]
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert business.main(args) == 2
    assert not target.exists()
    monkeypatch.setattr("sys.stdin", io.StringIO(_review_page(has_next=False)))
    assert business.main(args) == 0
    first = target.read_text()
    monkeypatch.setattr("sys.stdin", io.StringIO(_review_page(has_next=False)))
    assert business.main(args) == 2
    assert target.read_text() == first
    assert f"refusing to overwrite the snapshot {target}" in capsys.readouterr().err


FIXTURE = Path(__file__).parent / "fixtures" / "graphql-pull-requests.json"


def test_collect_prs_reads_recorded_graphql_pages(capsys: pytest.CaptureFixture[str]) -> None:
    """The fixture holds nodes recorded from the live GitHub GraphQL API with this query.

    The query asks `reopened: timelineItems(itemTypes: [REOPENED_EVENT]) { filteredCount }`;
    the recording also asked for `totalCount`, which counts every timeline item whatever
    `itemTypes` says, and `reviews(first: 50)` returned oldest first.
    """
    text = FIXTURE.read_text(encoding="utf-8")
    notes: list[str] = []
    rows = business.collect_prs(text, "2019-10-01", "2021-06-30", notes)
    assert notes == []
    assert [r["number"] for r in rows] == ["1", "3", "5", "3773"]
    assert [r["reopened"] for r in rows] == ["0", "0", "0", "1"]
    assert [r["first_review_hours"] for r in rows] == ["", "15.57", "32.78", "3.53"]
    assert rows[3]["cycle_hours"] == "644.53"
    assert "totalCount" in text
    assert all("login" not in value for row in rows for value in row.values())
    args = ["collect-prs", "--start", "2019-10-01", "--end", "2021-06-30", str(FIXTURE)]
    assert business.main(args) == 0
    assert capsys.readouterr().out.splitlines()[0] == ",".join(business.PR_COLUMNS)


def test_project_accepts_a_measured_loss_and_reports_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "assumptions.yaml").write_text(
        PROJECT_REGISTER.replace(
            "value: 0.4\n  low: 0.3\n  high: 0.6", "value: -0.2\n  low: -0.3\n  high: -0.1"
        )
    )
    assert business.main(["project", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "conservative: -560\n" in out
    assert "base: -120\n" in out
    assert "net loss: the base case loses 120 engineer-hours per year\n" in out
    assert "  s:" in out


def test_project_flags_a_range_that_crosses_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "assumptions.yaml").write_text(
        PROJECT_REGISTER.replace(
            "value: 0.4\n  low: 0.3\n  high: 0.6", "value: 0.1\n  low: -0.1\n  high: 0.3"
        )
    )
    assert business.main(["project", str(tmp_path)]) == 0
    assert "net loss possible: the conservative case loses" in capsys.readouterr().out


def test_register_defines_the_manual_baseline_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    both = PROJECT_REGISTER + "\n- id: baseline-minutes\n  value: 30\n"
    assert business.project(both)[0] == {}
    assert (
        "baseline-minutes: same quantity as manual-minutes; register only manual-minutes"
        in (business.project(both)[1])
    )
    register = tmp_path / "assumptions.yaml"
    register.write_text(both)
    assert business.main(["assumptions", str(register)]) == 1
    assert "baseline-minutes: same quantity as manual-minutes" in capsys.readouterr().out
    alone = PROJECT_REGISTER.replace("manual-minutes", "baseline-minutes")
    assert "manual-minutes: missing from the assumptions register" in business.project(alone)[1]


def test_register_savings_rate_must_match_its_parts() -> None:
    def problems(extra: str) -> list[str]:
        entries = business._parse_register(BREAKEVEN_REGISTER + "\n" + extra)
        return business._check_quantities({e["id"]: e for e in entries})

    assert problems("- id: savings-rate\n  value: 0.4\n") == []
    wrong = problems("- id: savings-rate\n  value: 0.9\n")
    assert len(wrong) == 1
    assert "savings-rate: 0.9 disagrees with the 0.4 its parts imply" in wrong[0]


def test_gate_requires_each_sentence_figure_to_sit_in_a_tagged_sentence(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    tagged = "Saved 18 min (MEASURED: sources.md `task-timings`, n=3 tasks)."
    (run / "findings.md").write_text(f"{tagged} Another 300 PRs merged.\n")
    problems = business.check_run(run)
    assert problems == ["findings.md: figure without a provenance tag: Another 300 PRs merged."]
    (run / "findings.md").write_text(
        "Saved 18 min over 300 PRs (MEASURED: sources.md `task-timings`, n=3 tasks).\n"
    )
    assert business.check_run(run) == []


def test_gate_requires_a_check_line_over_a_measured_csv(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    timing = run / "measurements" / "timing.md"
    timing.write_text(timing.read_text().split("check:")[0])
    problems = business.check_run(run)
    assert len(problems) == 1
    assert "has no check: line over the CSV of task-timings" in problems[0]
    (run / "findings.md").write_text(
        "Saved 18 min (MEASURED: sources.md `task-timings`, n=3 tasks).\n"
    )
    assert len(business.check_run(run)) == 2


def test_gate_flags_money_framings(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    (run / "findings.md").write_text("No ROI claim; cost savings are not made.\n")
    problems = business.check_run(run)
    assert problems == [
        "findings.md:1: money framing 'ROI'; value is hours, never money",
        "findings.md:1: money framing 'cost savings'; value is hours, never money",
    ]


def test_stamp_and_fresh_detect_a_changed_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = make_run(tmp_path)
    reports = run / "reports"
    reports.mkdir()
    (reports / "case-study-public.md").write_text("study\n")
    (reports / "pr-release.md").write_text("release\n")
    (reports / ".reply-check.md").write_text("scratch\n")
    assert business.main(["fresh", str(run)]) == 1
    assert "case-study-public.md: no recorded inputs" in capsys.readouterr().out
    for name in ("case-study-public.md", "pr-release.md"):
        assert business.main(["stamp", str(run), name]) == 0
    assert business.main(["fresh", str(run)]) == 0
    (run / "raw" / "t.csv").write_text("task,m,a\n1,31,12\n")
    assert business.main(["fresh", str(run)]) == 1
    out = capsys.readouterr().out
    assert "case-study-public.md: stale; changed since it was written: raw/t.csv" in out
    assert "pr-release.md" not in out
    (reports / "case-study-public.md").write_text("regenerated\n")
    assert "pr-release.md: stale; changed since it was written: reports/case-study-public.md" in (
        "\n".join(business.stale_reports(run))
    )
    assert business.main(["stamp", str(run), "nope.md"]) == 2


def test_assumptions_reject_quoted_commented_and_nested_fields(tmp_path: Path) -> None:
    register = tmp_path / "a.yaml"
    register.write_text(REGISTER.replace("unit: engineers", 'unit: "engineers" # c'))
    problems = business.check_assumptions(register.read_text())
    assert problems == ["entry addressable-population: line 4: unit is quoted; write it bare"]
    register.write_text(REGISTER.replace("unit: engineers", "unit: engineers # c"))
    assert business.check_assumptions(register.read_text()) == [
        "entry addressable-population: line 4: unit has a trailing # comment"
    ]
    register.write_text(REGISTER + "  notes:\n    - a\n")
    assert any("nested structure" in p for p in business.check_assumptions(register.read_text()))
    assert business.check_assumptions("# a note\n" + REGISTER) == []


def test_runs_workflow_lists_only_that_slug_newest_first(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in ("2026-01-15/business/a", "2026-01-20/business/a", "2026-02-01/business/b"):
        (tmp_path / name).mkdir(parents=True)
    assert business.main(["runs", "--root", str(tmp_path), "--workflow", "a"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [Path(x).parent.parent.name for x in lines] == ["2026-01-20", "2026-01-15"]
    assert business.main(["runs", "--root", str(tmp_path), "--workflow", "none-such"]) == 0
    assert capsys.readouterr().out == ""


def _report_run(root: Path) -> Path:
    run = make_run(root)
    (run / "assumptions.yaml").write_text(BREAKEVEN_REGISTER + "\n" + PROJECT_REGISTER + "\n")
    return run


def test_trace_run_checks_report_figures_against_script_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = _report_run(tmp_path)
    report = tmp_path / "leadership.md"
    report.write_text("Base net 92 engineer-hours, conservative 45 hours, break-even 140.\n")
    assert business.main(["trace", str(report), "--run", str(run)]) == 0
    report.write_text("Base net 93 engineer-hours.\n")
    assert business.main(["trace", str(report), "--run", str(run)]) == 1
    assert "figure not in the source text: 93" in capsys.readouterr().out
    assert business.main(["trace", str(report)]) == 2


def test_trace_run_accepts_a_percent_of_a_registered_ratio(tmp_path: Path) -> None:
    run = _report_run(tmp_path)
    assert business.untraced_figures("40% saved", business.run_figure_source(run)) == []


def _readme(run: Path, extra: str) -> None:
    (run / "README.md").write_text(f"Window: 2026-04-01..2026-06-30.\nNames: Atlas\n{extra}")


def test_scan_tier_one_and_two_deny_people_but_allow_teams(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = make_run(tmp_path)
    draft = tmp_path / "report.md"
    draft.write_text("The Atlas team, led by Priya, ran https://corp.example/x for PROJ-1.\n")
    _readme(run, "People: Priya Raman\n")
    for tier in ("1", "2"):
        assert business.main(["scan", "--run", str(run), "--tier", tier, str(draft)]) == 1
        assert capsys.readouterr().out == "1:24: denied-name: Priya\n"
    assert business.main(["scan", "--run", str(run), str(draft)]) == 1
    assert "denied-name: Atlas" in capsys.readouterr().out
    _readme(run, "People: none\n")
    assert business.main(["scan", "--run", str(run), "--tier", "1", str(draft)]) == 0
    _readme(run, "")
    assert business.main(["scan", "--run", str(run), "--tier", "2", str(draft)]) == 2
    assert "README.md has no People: line" in capsys.readouterr().err


def test_collect_prs_records_output_hash_and_gate_verifies_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = make_run(tmp_path)
    target = run / "raw" / "pr-metrics.csv"
    monkeypatch.setattr("sys.stdin", io.StringIO(_review_page(has_next=False)))
    args = ["collect-prs", "--start", "2026-04-01", "--end", "2026-04-30", "--output", str(target)]
    assert business.main([*args, "--sources", str(run / "sources.md"), "--entry", "prs"]) == 0
    entry = (run / "sources.md").read_text().split("## prs\n")[1].splitlines()
    assert [x.split(":")[0] for x in entry] == ["- output", "- executed", "- sha256"]
    assert entry[0] == "- output: raw/pr-metrics.csv"
    assert entry[2] == f"- sha256: {business.file_sha256(target)} raw/pr-metrics.csv"
    problems = business.check_run(run)
    assert [p.split(": missing ")[-1] for p in problems] == ["query", "tool version"]
    sources = run / "sources.md"
    sources.write_text(sources.read_text() + "- query: gh\n- tool version: gh 2\n")
    assert business.check_run(run) == []
    target.write_text(target.read_text() + "tampered\n")
    assert business.check_run(run) == [
        "sources.md entry prs: raw/pr-metrics.csv does not match its sha256"
    ]


def test_collect_prs_sources_flags_go_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(_review_page(has_next=False)))
    args = ["collect-prs", "--start", "2026-04-01", "--end", "2026-04-30"]
    assert business.main([*args, "--sources", str(tmp_path / "sources.md")]) == 2
    assert "--sources and --entry go together and need --output" in capsys.readouterr().err


def test_stats_csv_prints_rows_dropped_blanks_and_input_hash(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sample = tmp_path / "t.csv"
    sample.write_text("a,b\n10,4\n9,\n8,2\n7,\n")
    assert business.main(["stats", "--csv", str(sample), "--column", "b"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert "n: 2" in out
    assert "rows: 4" in out
    assert "dropped_blank: 2" in out
    assert f"input_sha256: {business.file_sha256(sample)}" in out


def test_stats_csv_bad_column_names_the_column(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sample = tmp_path / "t.csv"
    sample.write_text("a,b\n1,2\n")
    assert business.main(["stats", "--csv", str(sample), "--column", "zzz"]) == 2
    assert f"column 'zzz' not found or not numeric in {sample}" in capsys.readouterr().err


def test_gate_requires_a_pinned_link_on_a_benchmarked_figure(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    (run / "findings.md").write_text("METR measured 19% slower (BENCHMARKED, early-2025 tools).\n")
    assert len(business.check_run(run)) == 1
    assert "BENCHMARKED figure has no pinned link" in business.check_run(run)[0]
    (run / "findings.md").write_text(
        "METR measured 19% slower (BENCHMARKED: https://arxiv.org/abs/2507.09089, 2026-10-10).\n"
    )
    assert business.check_run(run) == []


def test_scan_flags_short_commit_shas_but_not_hex_looking_words() -> None:
    assert [h[3] for h in business.scan_text("Fixed in 9a29b1a and 9a29b1a2c3d4e5f6.")] == [
        "9a29b1a",
        "9a29b1a2c3d4e5f6",
    ]
    prose = "A defaced facade, the accede decade, 1234567 and 2026-06-30 and cafe."
    assert business.scan_text(prose) == []
    assert business.scan_text("See https://git.example/c/9a29b1a") == [
        (1, 5, "url", "https://git.example/c/9a29b1a")
    ]


def test_source_writes_the_entry_from_the_clock_and_the_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = make_run(tmp_path)
    snap = run / "raw" / "export.json"
    snap.write_text("{}")
    args = ["source", str(run), "usage-export", str(snap)]
    assert business.main([*args, "--query", "cat export", "--tool-version", "cat 9"]) == 0
    entry = (run / "sources.md").read_text().split("## usage-export\n")[1].splitlines()
    assert [x.split(":")[0] for x in entry] == [
        "- output",
        "- executed",
        "- query",
        "- tool version",
        "- sha256",
    ]
    assert business._is_timestamp(entry[1].split(": ", 1)[1])
    assert entry[4] == f"- sha256: {business.file_sha256(snap)} raw/export.json"
    assert business.check_run(run) == []
    assert business.main(["source", str(run), "x", str(tmp_path / "gone")]) == 2
    outside = tmp_path / "outside.csv"
    outside.write_text("a")
    assert business.main(["source", str(run), "x", str(outside)]) == 2
    assert "is not inside the run" in capsys.readouterr().err


def _gh(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=False)  # noqa: S603, S607


def _gh_ready() -> bool:
    return shutil.which("gh") is not None and _gh("auth", "status").returncode == 0


@pytest.mark.integration
@pytest.mark.skipif(not _gh_ready(), reason="gh is missing or not authenticated")
def test_plugin_query_runs_against_the_live_github_api() -> None:
    """Run the query printed in instruments.md, unmodified, against a public repository."""
    text = (Path(__file__).parents[1] / "references" / "instruments.md").read_text(encoding="utf-8")
    found = re.search(r"-f query='(.*?)'\s*\\", text, re.DOTALL)
    assert found
    result = _gh(
        "api",
        "graphql",
        "-f",
        "owner=octocat",
        "-f",
        "name=Hello-World",
        "-f",
        f"query={found.group(1)}",
    )
    if "HTTP 5" in result.stderr:
        pytest.skip("GitHub API unavailable")
    assert result.returncode == 0, result.stderr
    page = json.loads(result.stdout)["data"]["repository"]["pullRequests"]
    assert page["nodes"]
    assert all(
        "filteredCount" in n["reopened"] and "pageInfo" in n["reviews"] for n in page["nodes"]
    )
    rows = business.collect_prs(result.stdout, "2000-01-01", "2100-01-01")
    assert all(r["reopened"].isdigit() for r in rows)

    def counts(query: str) -> dict[int, tuple[int, int]]:
        reply = _gh(
            "api",
            "graphql",
            "-f",
            "owner=octocat",
            "-f",
            "name=Hello-World",
            "-f",
            f"query={query}",
        )
        if "HTTP 5" in reply.stderr:
            pytest.skip("GitHub API unavailable")
        nodes = json.loads(reply.stdout)["data"]["repository"]["pullRequests"]["nodes"]
        return {
            n["number"]: (n["reopened"]["filteredCount"], n["reopened"]["totalCount"])
            for n in nodes
        }

    filtered = "reopened: timelineItems(itemTypes: [REOPENED_EVENT]) { filteredCount }"
    assert filtered in found.group(1)
    small = found.group(1).replace("pullRequests(first: 100", "pullRequests(first: 5")
    assert small != found.group(1)
    with_filter = counts(small.replace("{ filteredCount }", "{ filteredCount totalCount }"))
    without = counts(
        small.replace(filtered[len("reopened: ") :], "timelineItems { filteredCount totalCount }")
    )
    assert {k: v[1] for k, v in with_filter.items()} == {k: v[1] for k, v in without.items()}
    assert any(filt < total for filt, total in with_filter.values())
