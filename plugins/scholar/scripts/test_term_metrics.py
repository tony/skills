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
