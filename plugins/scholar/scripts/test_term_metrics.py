"""Tests for term_metrics.py malformed-row and URL handling."""

# ruff: noqa: S101, INP001
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false
from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING

import pytest
import term_metrics  # pyright: ignore[reportImplicitRelativeImport]

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("row", "finding"),
    [
        ('{"term": "a", "definition": null}', "line 1: 'definition' must be a string"),
        (
            '{"term": "a", "definition": "x", "cites": ["q"]}',
            "line 1: each entry in 'cites' must be an object",
        ),
        ('{"term": "a", "definition": "x", "cites": "q"}', "line 1: 'cites' must be a list"),
        ('["a"]', "line 1: row must be a JSON object"),
        (
            '{"term": "a", "cites": [{"quote": "q", "source": {}}]}',
            "line 1: 'source' must be a string",
        ),
        (
            '{"term": "a", "cites": [{"quote": "q", "source": "s", "locator": []}]}',
            "line 1: 'locator' must be a string",
        ),
    ],
)
@pytest.mark.parametrize("flags", [[], ["--check-terms"], ["--check-quotes", "unused-clone"]])
def test_malformed_row_is_a_finding(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    row: str,
    finding: str,
    flags: list[str],
) -> None:
    """A mistyped row exits 1 naming its line, in every mode, with no traceback."""
    (tmp_path / "terms.jsonl").write_text(row + "\n", encoding="utf-8")
    assert term_metrics.main([str(tmp_path), *flags]) == 1
    assert finding in capsys.readouterr().out


@pytest.mark.parametrize(
    ("locator", "kind", "verdict"),
    [
        ("src/a.py", "line-range", "uncheckable"),
        ("src/a.py:0", "line-range", "uncheckable"),
        ("src/a.py:2-1", "line-range", "uncheckable"),
        ("src/a.py:1-4", "line-range", "uncheckable"),
        ("src/a.py", "unknown", "uncheckable"),
        ("src/a.py", "search-string", "ok"),
        ("src/a.py:2", "line-range", "ok"),
    ],
)
def test_quote_verification_never_broadens_an_invalid_range(
    locator: str, kind: str, verdict: str
) -> None:
    """Only a valid recorded range or explicit search can verify the quote."""
    assert term_metrics.check_quote(locator, kind, "beta", "alpha\nbeta\n") == verdict


def test_bare_www_url_fails_the_brief_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A scheme-less ``www.`` host is still a URL in the brief."""
    (tmp_path / "brief.md").write_text("See www.example.com for detail.\n", encoding="utf-8")
    assert term_metrics.main([str(tmp_path), "--check-brief"]) == 1
    assert "URL belongs in evidence/" in capsys.readouterr().out


def test_type_row_needs_no_citation_but_a_member_does(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The term gate exempts ``kind: type`` rows from citing, never a member row."""
    rows = [
        '{"term": "role", "definition": "names a doer", "kind": "type", "parent": "root"}',
        '{"term": "adapter", "definition": "wraps a client", "kind": "role", "parent": "role"}',
    ]
    (tmp_path / "terms.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
    assert term_metrics.main([str(tmp_path), "--check-terms"]) == 1
    assert capsys.readouterr().out.splitlines() == ["adapter: no citation"]


def test_type_row_without_parent_or_cite_fails_the_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A harvested ``kind: type`` row has no parent yet, so it must cite."""
    row = '{"term": "Config", "definition": "a class", "kind": "type"}'
    (tmp_path / "terms.jsonl").write_text(row + "\n", encoding="utf-8")
    assert term_metrics.main([str(tmp_path), "--check-terms"]) == 1
    assert capsys.readouterr().out.splitlines() == ["Config: no citation"]


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ([("a", "a")], ["a -> a"]),
        ([("a", "b"), ("b", "a")], ["a -> b -> a"]),
        ([("a", "b"), ("b", "c"), ("c", "b")], ["b -> c -> b"]),
        ([("a", "root"), ("b", "a")], []),
    ],
)
def test_cycles_reports_self_loops_and_loops(
    rows: list[tuple[str, str]], expected: list[str]
) -> None:
    """Parent chains that never reach ``root`` are reported once each."""
    assert term_metrics.cycles([{"term": t, "parent": p} for t, p in rows]) == expected


def test_main_prints_cycles_section(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The analyzer report lists a self-parent under hierarchy cycles."""
    row = '{"term": "a", "definition": "x", "parent": "a"}'
    (tmp_path / "terms.jsonl").write_text(row + "\n", encoding="utf-8")
    assert term_metrics.main([str(tmp_path)]) == 0
    assert "== hierarchy cycles ==\n  a -> a" in capsys.readouterr().out


@pytest.mark.parametrize("source", ['"source": "",', ""])
def test_cite_without_source_fails_the_term_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], source: str
) -> None:
    """``verify`` marks a cite with no source Uncheckable, so the gate rejects it."""
    row = '{"term": "a", "definition": "x", "cites": [{' + source + ' "quote": "q"}]}'
    (tmp_path / "terms.jsonl").write_text(row + "\n", encoding="utf-8")
    assert term_metrics.main([str(tmp_path), "--check-terms"]) == 1
    assert capsys.readouterr().out.splitlines() == ["a: citation without a source"]


def _clone_with_file(root: Path, body: str) -> tuple[Path, str]:
    """Create a one-commit git repo holding ``src/a.py``; return it and the commit."""
    repo = root / "clone"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "a.py").write_text(body, encoding="utf-8")
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True)  # noqa: S603, S607
    subprocess.run([*git, "add", "."], check=True)  # noqa: S603
    subprocess.run([*git, "commit", "--quiet", "-m", "x"], check=True)  # noqa: S603
    head = subprocess.run(  # noqa: S603
        [*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    )
    return repo, head.stdout.strip()


def _study(root: Path, commit: str, locator: str, quote: str) -> Path:
    study = root / "study"
    study.mkdir()
    cite = {"source": "s", "locator": locator, "quote": quote}
    row = {"term": "t", "definition": "d", "cites": [cite]}
    (study / "terms.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    src = {"source": "s", "ref": "v1", "commit": commit, "locator_kind": "line-range"}
    (study / "sources.jsonl").write_text(json.dumps(src) + "\n", encoding="utf-8")
    return study


@pytest.mark.parametrize(
    ("locator", "quote", "expected"),
    [
        ("src/a.py:2-3", "beta   gamma", []),
        ("src/a.py:1-1", "beta gamma", ["Misquoted: t (src/a.py:1-1): quote not found"]),
        ("src/gone.py:1-1", "beta", ["Vanished: t (src/gone.py:1-1)"]),
        ("see chapter 2", "beta", ["Uncheckable: t (see chapter 2)"]),
        ("src/a.py", "beta", ["Uncheckable: t (src/a.py)"]),
    ],
)
def test_check_quotes_against_a_local_clone(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    locator: str,
    quote: str,
    expected: list[str],
) -> None:
    """A moved line is Misquoted, a missing file Vanished, a free-text locator Uncheckable."""
    clone, commit = _clone_with_file(tmp_path, "alpha\nbeta\ngamma\ndelta\n")
    study = _study(tmp_path, commit, locator, quote)
    code = term_metrics.main([str(study), "--check-quotes", str(clone)])
    out = capsys.readouterr().out.splitlines()
    assert code == (1 if expected else 0)
    assert [line[: len(exp)] for line, exp in zip(out, expected)] == expected
    assert len(out) == len(expected)


def test_check_quotes_reports_a_commit_missing_from_the_clone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A recorded commit the clone lacks is Uncheckable, not Vanished."""
    clone, _ = _clone_with_file(tmp_path, "alpha\n")
    study = _study(tmp_path, "a" * 40, "src/a.py:1-1", "alpha")
    assert term_metrics.main([str(study), "--check-quotes", str(clone)]) == 1
    assert capsys.readouterr().out.startswith("Uncheckable: t (src/a.py:1-1): commit not in")


def test_report_discloses_thresholds(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The analyzer output states the thresholds a finding was scored against."""
    row = '{"term": "a", "definition": "x"}'
    (tmp_path / "terms.jsonl").write_text(row + "\n", encoding="utf-8")
    assert term_metrics.main([str(tmp_path)]) == 0
    assert "thresholds: synonymy >= 0.5, polysemy < 0.3" in capsys.readouterr().out
