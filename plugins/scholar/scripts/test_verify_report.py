"""Tests for verify_report.py: ref comparison, measurement diff, report assembly."""

# ruff: noqa: S101, INP001, PLR2004
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
import verify_report  # pyright: ignore[reportImplicitRelativeImport]

if TYPE_CHECKING:
    from pathlib import Path

_METRICS = """# Metrics

```console
$ python3 term_metrics.py notes/ontology/s/
```

```text
analyzer-sha256: aaaa
synonymy: a / b at 0.600
```

```console
$ touch canary
```

```text
(no output)
```
"""


def test_moved_compares_once_per_source() -> None:
    """A repeated source row yields one finding; missing data is Uncheckable, not Moved."""
    rows: list[dict[str, object]] = [
        {"source": "o/r", "ref": "v1", "commit": "a" * 40},
        {"source": "o/r", "ref": "v1", "commit": "a" * 40},
        {"source": "o/p", "ref": "v2", "commit": ""},
        {"source": "o/q", "ref": "v3", "commit": "c" * 40},
    ]
    out = verify_report.moved(rows, {"o/r": "b" * 40})
    assert out == {
        "moved": ["o/r: v1 now bbbbbbb"],
        "uncheckable": ["o/p: no commit recorded", "o/q: host unreachable"],
    }


def test_changed_ignores_analyzer_identity_and_unrun_commands() -> None:
    """A new digest alone is not Changed; a new number is; an unrun command is not run."""
    command = "python3 term_metrics.py notes/ontology/s/"
    same = {command: "analyzer-sha256: bbbb\nsynonymy: a / b at 0.600\n"}
    assert verify_report.changed(_METRICS, same) == {
        "changed": [],
        "uncheckable": ["Metrics command `touch canary`: not run, no confirmation"],
    }
    moved_number = {command: "analyzer-sha256: bbbb\nsynonymy: a / b at 0.550\n"}
    out = verify_report.changed(_METRICS, moved_number)
    assert out["changed"] == [
        f"`{command}`: recorded synonymy: a / b at 0.600, now synonymy: a / b at 0.550"
    ]


@pytest.mark.parametrize(
    ("results", "hero"),
    [
        ({"checked": 0, "uncheckable": ["x", "y"]}, "⚠ Nothing checked: 2 uncheckable"),
        ({"checked": 4}, "✓ 4 citations checked, none stale"),
        ({"checked": 4, "moved": ["m"], "misquoted": ["a", "b"]}, "⚠ 2 misquoted, 1 moved"),
        ({"checked": 4, "analyzer": ["Vanished: t (f)"]}, "⚠ 1 vanished"),
    ],
)
def test_report_hero(results: dict[str, object], hero: str) -> None:
    """The hero follows the stated rule for every mix of categories."""
    assert verify_report.report(results).splitlines()[0] == hero


def test_report_has_five_sections_in_order_with_none() -> None:
    """Empty sections read ``None.`` and analyzer lines land in their section."""
    text = verify_report.report({"checked": 2, "analyzer": ["Misquoted: t (f:1): quote not found"]})
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings == ["## Moved", "## Vanished", "## Misquoted", "## Changed", "## Uncheckable"]
    assert "## Misquoted\n\n- t (f:1): quote not found\n" in text
    assert "## Moved\n\nNone.\n" in text


def test_cli_round_trip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The subcommands read the files the skill writes and print JSON or the report."""
    (tmp_path / "sources.jsonl").write_text(
        json.dumps({"source": "o/r", "ref": "v1", "commit": "a" * 40}) + "\n", encoding="utf-8"
    )
    (tmp_path / "current.json").write_text(json.dumps({"o/r": "b" * 40}), encoding="utf-8")
    code = verify_report.main(
        ["moved", str(tmp_path / "sources.jsonl"), str(tmp_path / "current.json")]
    )
    assert code == 0
    results = json.loads(capsys.readouterr().out)
    results["checked"] = 1
    (tmp_path / "results.json").write_text(json.dumps(results), encoding="utf-8")
    assert verify_report.main(["report", str(tmp_path / "results.json")]) == 0
    assert capsys.readouterr().out.startswith("⚠ 1 moved\n")


def test_cli_refuses_a_missing_file(capsys: pytest.CaptureFixture[str]) -> None:
    """A missing input is a one-line refusal, not a traceback."""
    assert verify_report.main(["report", "/nonexistent/results.json"]) == 2
    assert capsys.readouterr().err.startswith("verify_report.py: ")
