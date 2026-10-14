"""Tests for term_metrics.py malformed-row and URL handling."""

# ruff: noqa: S101, INP001, PLR2004
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import term_metrics  # pyright: ignore[reportImplicitRelativeImport]

if TYPE_CHECKING:
    from collections.abc import Mapping


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


@pytest.mark.parametrize(
    ("brief", "valid"),
    [
        ("See [the source](paper.md).", False),
        ("Similarity is [0.575](evidence/../../outside.md).", False),
        ("Similarity is [0.575](evidence/metrics.md).", True),
    ],
)
def test_brief_links_stay_in_evidence(brief: str, *, valid: bool) -> None:
    """Only contained evidence links exempt their labels from the brief gate."""
    findings = term_metrics.check_brief(brief)
    assert (not findings) is valid
    if not valid:
        assert "link target must stay in evidence/" in findings[0]


def test_type_row_needs_no_citation_but_a_member_does(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The term gate exempts ``kind: type`` rows from citing, never a member row."""
    rows = [
        '{"schema": 1, "term": "role", "definition": "names", "kind": "type", "parent": "root"}',
        '{"schema": 1, "term": "adapter", "definition": "wraps", "kind": "role", "parent": "role"}',
    ]
    (tmp_path / "terms.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (tmp_path / "sources.jsonl").write_text("", encoding="utf-8")
    assert term_metrics.main([str(tmp_path), "--check-terms"]) == 1
    assert capsys.readouterr().out.splitlines() == ["adapter: no citation"]


def test_type_row_without_parent_or_cite_fails_the_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A harvested ``kind: type`` row has no parent yet, so it must cite."""
    row = '{"schema": 1, "term": "Config", "definition": "a class", "kind": "type"}'
    (tmp_path / "terms.jsonl").write_text(row + "\n", encoding="utf-8")
    (tmp_path / "sources.jsonl").write_text("", encoding="utf-8")
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
    row = '{"schema": 1, "term": "a", "definition": "x", "cites": [{' + source + ' "quote": "q"}]}'
    (tmp_path / "terms.jsonl").write_text(row + "\n", encoding="utf-8")
    (tmp_path / "sources.jsonl").write_text("", encoding="utf-8")
    assert term_metrics.main([str(tmp_path), "--check-terms"]) == 1
    assert capsys.readouterr().out.splitlines() == ["a: citation without a source"]


def _clone_with_file(root: Path, body: str, name: str = "clone") -> tuple[Path, str]:
    """Create a one-commit git repo holding ``src/a.py``; return it and the commit."""
    repo = root / name
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
@pytest.mark.integration
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


@pytest.mark.integration
def test_check_quotes_reports_a_commit_missing_from_the_clone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A recorded commit the clone lacks is Uncheckable, not Vanished."""
    clone, _ = _clone_with_file(tmp_path, "alpha\n")
    study = _study(tmp_path, "a" * 40, "src/a.py:1-1", "alpha")
    assert term_metrics.main([str(study), "--check-quotes", str(clone)]) == 1
    assert capsys.readouterr().out.startswith("Uncheckable: t (src/a.py:1-1): commit not in")


def test_report_discloses_measurement_identity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The report identifies the analyzer bytes and scoring thresholds used."""
    row = '{"term": "a", "definition": "x"}'
    (tmp_path / "terms.jsonl").write_text(row + "\n", encoding="utf-8")
    assert term_metrics.main([str(tmp_path)]) == 0
    output = capsys.readouterr().out
    expected = hashlib.sha256(Path(term_metrics.__file__).read_bytes()).hexdigest()
    assert f"analyzer-sha256: {expected}" in output
    assert "thresholds: synonymy >= 0.5, polysemy < 0.3" in output


def _write(path: Path, *rows: Mapping[str, object]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


_SRC = {
    "source": "https://github.com/o/r",
    "ref": "v1",
    "commit": "a" * 40,
    "scope": "src/",
    "locator_kind": "line-range",
    "read": True,
    "why": "",
}


def test_hierarchy_gate_exits_nonzero_on_orphan_and_cycle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The report exits 0 by design; ``--check-hierarchy`` is the gate."""
    _write(
        tmp_path / "terms.jsonl",
        {"term": "a", "parent": "b"},
        {"term": "b", "parent": "a"},
        {"term": "c", "parent": "missing"},
    )
    assert term_metrics.main([str(tmp_path), "--check-hierarchy"]) == 1
    assert capsys.readouterr().out.splitlines() == ["Orphan: c", "Cycle: a -> b -> a"]
    _write(tmp_path / "terms.jsonl", {"term": "a", "parent": "root"})
    assert term_metrics.main([str(tmp_path), "--check-hierarchy"]) == 0


def test_a_deep_parent_chain_is_not_a_traceback() -> None:
    """Walking a 3000-deep chain neither recurses nor reports a cycle."""
    rows: list[term_metrics._Row] = [{"term": f"t{i}", "parent": f"t{i + 1}"} for i in range(3000)]
    rows.append({"term": "t3000", "parent": "root"})
    assert term_metrics.cycles(rows) == []


@pytest.mark.parametrize(
    ("rows", "finding"),
    [
        ([{**_SRC, "commit": "abc"}], "row 1: commit must be 40 hex digits"),
        ([{**_SRC, "commit": ""}], "row 1: a GitHub source needs its commit"),
        ([{**_SRC, "locator_kind": "paragraph"}], "row 1: locator_kind must be one of"),
        ([{**_SRC, "read": False}], "row 1: not read, so why is required"),
        ([{**_SRC, "read": "yes"}], "row 1: read must be true or false"),
        ([{**_SRC, "why": None}], "row 1: why must be a string"),
        (
            [_SRC, {**_SRC, "locator_kind": "page"}],
            "row 2: locator_kind differs from the first row",
        ),
        ([_SRC, {**_SRC, "scope": "test/", "read": False, "why": "tests"}], ""),
    ],
)
def test_check_sources_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], rows: list[dict[str, object]], finding: str
) -> None:
    """Each break in the gather gate is a finding; the happy path prints nothing."""
    _write(tmp_path / "sources.jsonl", *rows)
    code = term_metrics.main([str(tmp_path), "--check-sources"])
    out = capsys.readouterr().out
    assert code == (1 if finding else 0)
    assert finding in out


def test_malformed_sources_line_is_reported_not_skipped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A bad ``sources.jsonl`` line must not turn every cite into a silent Uncheckable."""
    (tmp_path / "terms.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "sources.jsonl").write_text("{oops\n", encoding="utf-8")
    for flag in ("--check-sources", "--check-terms"):
        assert term_metrics.main([str(tmp_path), flag]) == 1
        assert "sources.jsonl line 1: invalid JSON" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("patch", "finding"),
    [
        ({"kind": "banana"}, "a: unknown kind 'banana'"),
        ({"schema": 2}, "a: schema must be 1"),
        ({"cites": [{"quote": "q", "source": "nowhere"}]}, "a: source 'nowhere' is not in"),
    ],
)
def test_check_terms_enforces_kind_schema_and_source(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], patch: dict[str, object], finding: str
) -> None:
    """The documented closed kind set, schema version and source ids are enforced."""
    row = {
        "schema": 1,
        "term": "a",
        "definition": "x",
        "kind": "class",
        "cites": [{"quote": "q", "source": _SRC["source"]}],
    }
    _write(tmp_path / "terms.jsonl", {**row, **patch})
    _write(tmp_path / "sources.jsonl", _SRC)
    assert term_metrics.main([str(tmp_path), "--check-terms"]) == 1
    assert finding in capsys.readouterr().out


def test_check_terms_without_sources_file_is_a_refusal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A cite's source cannot be resolved with no ``sources.jsonl``, so the gate refuses."""
    _write(tmp_path / "terms.jsonl", {"term": "a"})
    assert term_metrics.main([str(tmp_path), "--check-terms"]) == 2
    assert capsys.readouterr().err == f"no sources.jsonl in {tmp_path}\n"


def _prose_study(root: Path, quote: str) -> Path:
    study = root / "study"
    (study / "corpus").mkdir(parents=True)
    (study / "corpus" / "excerpt-1.txt").write_text("The boundary is where it stops.\n", "utf-8")
    cite = {"source": "corpus/excerpt-1.txt", "locator": "p.1", "quote": quote}
    _write(study / "terms.jsonl", {"term": "t", "definition": "d", "cites": [cite]})
    prose = {
        **_SRC,
        "source": "corpus/excerpt-1.txt",
        "commit": "",
        "locator_kind": "search-string",
    }
    _write(study / "sources.jsonl", prose)
    return study


@pytest.mark.parametrize(
    ("quote", "expected"),
    [
        ("is where it stops", 0),
        ("The boundary ... it stops", 0),
        ("INVENTED TEXT NOT IN SOURCE", 1),
    ],
)
def test_prose_cites_into_a_stored_excerpt_are_searched(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], quote: str, expected: int
) -> None:
    """An invented prose quote is Misquoted, not waved through as Uncheckable."""
    study = _prose_study(tmp_path, quote)
    assert term_metrics.main([str(study), "--check-quotes", str(tmp_path)]) == expected
    assert ("Misquoted" in capsys.readouterr().out) is bool(expected)


def test_quotations_are_checked_against_the_excerpt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``annotate``'s verbatim promise is checkable for a stored excerpt."""
    study = _prose_study(tmp_path, "is where it stops")
    good = {"source": "corpus/excerpt-1.txt", "quote": "where it stops"}
    bad = {"source": "corpus/excerpt-1.txt", "quote": "where it never stops"}
    other = {"source": "a book", "quote": "x"}
    _write(study / "quotations.jsonl", good, bad, other)
    assert term_metrics.main([str(study), "--check-quotations"]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "Misquoted: quotation 2 (corpus/excerpt-1.txt): quote not found in the source",
        "Uncheckable: quotation 3 (a book): source is not in sources.jsonl",
    ]


@pytest.mark.parametrize(
    ("term", "quote", "hit"),
    [
        ("class", "all classes derive from Base", True),
        ("process", "the processes share memory", True),
        ("processes", "one process only", True),
        ("naive", "a na\u00efve reading", False),
        ("na\u00efve", "A NA\u00cfVE reading", True),
        ("\u7c7b", "\u6240\u6709\u7c7b\u7ee7\u627f", True),
        ("C++", "ported to C++ in 2019", True),
        ("C++", "the C compiler", False),
    ],
)
def test_circular_matches_plurals_unicode_and_punctuated_terms(
    term: str, quote: str, hit: bool
) -> None:
    """Plural stems, non-ASCII letters, CJK, and ``C++`` are judged like plain words."""
    row: term_metrics._Row = {"term": term, "cites": [{"quote": quote}]}
    assert (term_metrics.circular([row]) == [term]) is hit


def test_ellipsis_marks_omissions_in_order() -> None:
    """The ``annotate`` rule (an ellipsis for every omission) verifies; reversed pieces do not."""
    text = "alpha\nbeta\ngamma"
    assert term_metrics.check_quote("f", "search-string", "alpha ... gamma", text) == "ok"
    assert term_metrics.check_quote("f", "search-string", "gamma ... alpha", text) == "misquoted"


@pytest.mark.integration
def test_each_source_is_checked_in_its_own_clone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A wrong quote cited into the second source is flagged when both clones are named."""
    clone_a, commit_a = _clone_with_file(tmp_path, "alpha\nbeta\n", "a")
    clone_b, commit_b = _clone_with_file(tmp_path, "gamma\ndelta\n", "b")
    study = tmp_path / "study"
    study.mkdir()
    cites = [
        {"source": "A", "locator": "src/a.py:1-1", "quote": "alpha"},
        {"source": "B", "locator": "src/a.py:1-1", "quote": "WRONG"},
    ]
    _write(study / "terms.jsonl", {"term": "t", "definition": "d", "cites": cites})
    rows = [
        {**_SRC, "source": "A", "commit": commit_a},
        {**_SRC, "source": "B", "commit": commit_b},
    ]
    _write(study / "sources.jsonl", *rows)
    one = term_metrics.main([str(study), "--check-quotes", str(clone_a)])
    assert one == 1
    assert "Uncheckable: t (src/a.py:1-1): commit not in the clone" in capsys.readouterr().out
    both = ["--check-quotes", f"A={clone_a}", "--check-quotes", f"B={clone_b}"]
    assert term_metrics.main([str(study), *both]) == 1
    assert capsys.readouterr().out.startswith("Misquoted: t (src/a.py:1-1): quote not found")


def test_rows_that_disagree_make_their_cites_uncheckable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The first row no longer wins silently when two rows disagree on locator_kind."""
    cite = {"source": _SRC["source"], "locator": "f.py:1-1", "quote": "x"}
    _write(tmp_path / "terms.jsonl", {"term": "t", "definition": "d", "cites": [cite]})
    _write(tmp_path / "sources.jsonl", _SRC, {**_SRC, "locator_kind": "search-string"})
    assert term_metrics.main([str(tmp_path), "--check-quotes", "unused"]) == 1
    assert "Uncheckable: t (f.py:1-1): rows for the source disagree" in capsys.readouterr().out


def test_verdict_gate_counts_findings_and_open_claims(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every analyzer finding needs a judged entry naming its terms; an open claim fails."""
    rows = [
        {"term": "bump", "parent": "root", "definition": "raise one pin"},
        {"term": "update", "parent": "root", "definition": "raise one pin"},
    ]
    _write(tmp_path / "terms.jsonl", *rows)
    assert term_metrics.main([str(tmp_path), "--check-verdicts"]) == 1
    assert capsys.readouterr().out.splitlines() == ["Unjudged: synonymy bump / update"]
    (tmp_path / "evidence").mkdir()
    ledger = tmp_path / "evidence" / "contested.md"
    ledger.write_text("- Claim: bump and update\n- Verdict: open\n", encoding="utf-8")
    assert term_metrics.main([str(tmp_path), "--check-verdicts"]) == 1
    assert "Open: bump and update" in capsys.readouterr().out
    ledger.write_text("- Claim: bump and update\n- Verdict: killed.\n", encoding="utf-8")
    assert term_metrics.main([str(tmp_path), "--check-verdicts"]) == 0


def test_brief_gate_fails_on_a_dangling_evidence_link(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A link into ``evidence/`` must resolve to a file in the study."""
    (tmp_path / "brief.md").write_text(
        "Names split in [vocabulary](evidence/vocabulary.md).\n", "utf-8"
    )
    assert term_metrics.main([str(tmp_path), "--check-brief"]) == 1
    assert capsys.readouterr().out == "line 1: evidence/vocabulary.md does not exist\n"
    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / "vocabulary.md").write_text("x\n", encoding="utf-8")
    assert term_metrics.main([str(tmp_path), "--check-brief"]) == 0
