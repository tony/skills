"""Tests for the completeness gate, scan allow flags, and permission-safe roots."""

# ruff: noqa: S101, INP001, PLR2004, D103, ARG001, TC002
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false
# pyright: reportImplicitStringConcatenation=false, reportUnusedParameter=false

from __future__ import annotations

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
    (run / "README.md").write_text("Window: 2026-04-01..2026-06-30.\n")
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
