"""Tests for verify_report.py: ref comparison, measurement diff, report assembly."""

# ruff: noqa: S101, S603, S607, INP001, PLR2004
# pyright: reportAny=false, reportUnusedCallResult=false
import json
import subprocess
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
        "uncheckable": ["o/p: no commit recorded", "o/q: no current SHA supplied"],
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


def test_changed_keys_a_multi_line_command_by_its_whole_text() -> None:
    """The command contest records spans lines; fresh output is keyed by that exact text."""
    command = "printf 'path: ' \\\n    && read -r p \\\n    && python3 \"$p\" study/"
    md = f"```console\n$ {command}\n```\n\n```text\nsynonymy: a / b at 0.600\n```\n"
    assert verify_report.recorded_measurements(md) == [(command, "synonymy: a / b at 0.600")]
    out = verify_report.changed(md, {command: "synonymy: a / b at 0.500"})
    assert len(out["changed"]) == 1
    assert verify_report.changed(md, {})["uncheckable"] == [
        f"Metrics command `{command}`: not run, no confirmation"
    ]


def test_report_with_nothing_checked_still_lists_moved() -> None:
    """A moved ref found offline is not hidden behind the nothing-checked hero."""
    text = verify_report.report({"checked": 0, "moved": ["o/r: v1 now bbbbbbb"]})
    assert text.splitlines()[0] == "⚠ 1 moved"
    assert "- o/r: v1 now bbbbbbb" in text


def test_moved_refuses_a_non_string_sha(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A malformed current-SHA file is one line, not a traceback."""
    (tmp_path / "s.jsonl").write_text('{"source": "o/r", "commit": "a"}\n', encoding="utf-8")
    (tmp_path / "c.json").write_text('{"o/r": 5}', encoding="utf-8")
    assert verify_report.main(["moved", str(tmp_path / "s.jsonl"), str(tmp_path / "c.json")]) == 2
    assert capsys.readouterr().err == "verify_report.py: current SHAs must be strings or null\n"


@pytest.mark.integration
def test_local_checks_moved_and_vanished_offline(tmp_path: Path) -> None:
    """Rev-parse against the recorded commit finds a moved tag; cat-file finds a gone file."""
    repo = tmp_path / "clone"
    repo.mkdir()
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
    (repo / "a.py").write_text("x\n", encoding="utf-8")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "--quiet", "-m", "one"], check=True)
    first = subprocess.run(
        [*git, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    subprocess.run([*git, "tag", "v1"], check=True)
    study = tmp_path / "study"
    study.mkdir()
    source = {"source": "s", "ref": "v1", "commit": first}
    cites = [
        {"source": "s", "locator": "a.py:1-1", "quote": "x"},
        {"source": "s", "locator": "gone.py:1-1", "quote": "x"},
    ]
    (study / "sources.jsonl").write_text(json.dumps(source) + "\n", encoding="utf-8")
    (study / "terms.jsonl").write_text(
        json.dumps({"term": "t", "definition": "d", "cites": cites}) + "\n", encoding="utf-8"
    )
    clones = {"s": str(repo)}
    rows = [json.loads(x) for x in (study / "sources.jsonl").read_text("utf-8").splitlines()]
    terms = [json.loads(x) for x in (study / "terms.jsonl").read_text("utf-8").splitlines()]
    out = verify_report.local(rows, terms, clones)
    assert out == {
        "moved": [],
        "vanished": ["t (gone.py:1-1): gone.py is not in the commit"],
        "uncheckable": [],
    }
    (repo / "b.py").write_text("y\n", encoding="utf-8")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "--quiet", "-m", "two"], check=True)
    subprocess.run([*git, "tag", "-f", "v1"], check=True)
    again = verify_report.local(rows, terms, clones)
    assert len(again["moved"]) == 1
    assert again["moved"][0].startswith("s: v1 now ")
    subprocess.run([*git, "tag", "-d", "v1"], check=True)
    assert verify_report.local(rows, terms, clones)["vanished"][0] == "s: ref v1 is gone"


def test_moved_tells_a_failed_lookup_from_one_never_made() -> None:
    """An omitted source was not looked up; a null one failed."""
    rows: list[dict[str, object]] = [
        {"source": "o/p", "ref": "v1", "commit": "c" * 40},
        {"source": "o/q", "ref": "v3", "commit": "c" * 40},
    ]
    out = verify_report.moved(rows, {"o/q": None})
    assert out["uncheckable"] == ["o/p: no current SHA supplied", "o/q: host unreachable"]


def test_moved_cli_accepts_null_for_a_failed_lookup(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The JSON file carries null for a failed lookup."""
    (tmp_path / "s.jsonl").write_text('{"source": "o/q", "commit": "c"}\n', encoding="utf-8")
    (tmp_path / "c.json").write_text('{"o/q": null}', encoding="utf-8")
    argv = ["moved", str(tmp_path / "s.jsonl"), str(tmp_path / "c.json")]
    assert verify_report.main(argv) == 0
    assert json.loads(capsys.readouterr().out)["uncheckable"] == ["o/q: host unreachable"]


def test_report_keeps_one_cause_per_source() -> None:
    """Most specific wins: no clone on disk, then host unreachable, then no SHA supplied."""
    results: dict[str, object] = {
        "checked": 1,
        "uncheckable": [
            "g: no current SHA supplied",
            "g: no clone on disk",
            "h: no current SHA supplied",
            "h: host unreachable",
            "k: no current SHA supplied",
            "Metrics command `x`: not run, no confirmation",
        ],
    }
    text = verify_report.report(results)
    tail = text.split("## Uncheckable\n\n")[1].splitlines()
    assert tail == [
        "- g: no clone on disk",
        "- h: host unreachable",
        "- k: no current SHA supplied",
        "- Metrics command `x`: not run, no confirmation",
    ]


def test_local_source_without_a_clone_is_uncheckable() -> None:
    """A source with no remote and no --clone is reported, not silently skipped."""
    rows: list[dict[str, object]] = [
        {"source": "tiny-lib", "ref": "main", "commit": "a" * 40},
        {"source": "https://github.com/o/r", "ref": "v1", "commit": "b" * 40},
        {"source": "https://gitlab.com/o/r", "ref": "v1", "commit": "d" * 40},
        {"source": "corpus/excerpt-1.txt", "ref": "ed", "commit": ""},
    ]
    out = verify_report.local(rows, [], {})
    assert sorted(out["uncheckable"]) == [
        "https://gitlab.com/o/r: no clone on disk",
        "tiny-lib: no clone on disk",
    ]
