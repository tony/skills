"""Tests for term_metrics.py malformed-row and URL handling."""

# ruff: noqa: S101, INP001
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false
from __future__ import annotations

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
    ],
)
@pytest.mark.parametrize("flags", [[], ["--check-terms"]])
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
