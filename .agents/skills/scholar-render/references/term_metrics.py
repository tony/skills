#!/usr/bin/env python3
r"""Measure a scholar term table.

Reads the study's own artifacts (``terms.jsonl``, ``brief.md``), never the
corpus. Standard library only, so it runs inside any corpus checkout.

It proposes; it never decides. Every finding is a candidate for judgment in
``contest``.

Examples
--------
Two sibling terms whose definitions say the same thing:

>>> terms = [
...     {"term": "update-action", "parent": "raise",
...      "definition": "update one named action to its current version"},
...     {"term": "update-actions", "parent": "raise",
...      "definition": "update every outdated action to its current version"},
...     {"term": "cut", "parent": "release",
...      "definition": "tag a release at an explicit version"},
... ]
>>> [(a, b) for a, b, _ in synonymy(terms, threshold=0.5)]
[('update-action', 'update-actions')]

One term standing for two unrelated things:

>>> rows = [
...     {"term": "bump", "parent": "raise", "definition": "raise a dependency pin"},
...     {"term": "bump", "parent": "release", "definition": "choose the next version number"},
... ]
>>> [term for term, _ in polysemy(rows)]
['bump']

A term whose parent is not in the table, or that has no parent at all:

>>> orphans([{"term": "probe", "parent": "spike", "definition": "one path"}])
['probe']
>>> orphans([{"term": "probe", "parent": "", "definition": "one path"}])
['probe']
>>> orphans([{"term": "probe", "definition": "one path"}])
['probe']
>>> orphans([{"term": "probe", "parent": "root", "definition": "one path"}])
[]

A citation that quotes the term it is meant to support:

>>> circular([{"term": "ratchet", "definition": "converges",
...            "cites": [{"quote": "the ratchet stops advancing"}]}])
['ratchet']

A quote that shares only one word of a multi-word term does not name it:

>>> circular([{"term": "update-action", "definition": "bump one pin",
...            "cites": [{"quote": "update the lockfile before release"}]}])
[]
>>> circular([{"term": "update-action", "definition": "bump one pin",
...            "cites": [{"quote": "each update actions step runs once"}]}])
['update-action']

The brief may not carry citations, permalinks, or bare numbers:

>>> check_brief("Names split three ways.")
[]
>>> check_brief("See https://example.com/x for detail.")
['line 1: URL belongs in evidence/, not the brief']
>>> check_brief("Twelve plugins, 0.575 similar.")
['line 1: bare number belongs in evidence/, not the brief']
>>> check_brief("Similarity is [0.575](evidence/metrics.md).")
[]
>>> check_brief("See www.example.com for detail.")
['line 1: URL belongs in evidence/, not the brief']

List markers and code spans are not numbers:

>>> check_brief("1. Names split.")
[]
>>> check_brief("2) Parents differ.")
[]
>>> check_brief("- Use `v2` here.")
[]
>>> check_brief("Anchor #L12 is a number.")
['line 1: bare number belongs in evidence/, not the brief']

A missing file is a usage error, not a traceback:

>>> import contextlib, sys
>>> with contextlib.redirect_stderr(sys.stdout):
...     main(["/nonexistent-study", "--check-brief"])
no brief.md in /nonexistent-study
2
>>> with contextlib.redirect_stderr(sys.stdout):
...     main(["/nonexistent-study"])
no terms.jsonl in /nonexistent-study
2

An unknown flag, or a prefix of a real one, is a usage error, never a full
report:

>>> with contextlib.redirect_stderr(sys.stdout):
...     main(["/nonexistent-study", "--check-term"])  # doctest: +ELLIPSIS
usage: term_metrics.py ...
term_metrics.py: error: unrecognized arguments: --check-term
2

A malformed row is reported with its line number and a nonzero exit, never a
traceback:

>>> import tempfile
>>> with tempfile.TemporaryDirectory() as tmp:
...     _ = Path(tmp, "terms.jsonl").write_text("{oops", encoding="utf-8")
...     with contextlib.redirect_stderr(sys.stdout):
...         main([tmp, "--check-terms"])
terms.jsonl line 1: invalid JSON (Expecting property name enclosed in double quotes)
1

A null definition or a citation that is not an object is a finding too:

>>> with tempfile.TemporaryDirectory() as tmp:
...     _ = Path(tmp, "terms.jsonl").write_text(
...         '{"term": "a", "definition": null}\n'
...         '{"term": "b", "definition": "x", "cites": ["q"]}\n',
...         encoding="utf-8",
...     )
...     with contextlib.redirect_stderr(sys.stdout):
...         main([tmp])
terms.jsonl line 1: 'definition' must be a string
terms.jsonl line 2: each entry in 'cites' must be an object
1

Every term row needs a definition and a quoted citation; a ``type`` row
needs no citation of its own, since its is-a claims are cited in
``evidence/hierarchy.md``:

>>> check_terms([{"term": "a", "definition": "x", "cites": [{"quote": "q"}]}])
[]
>>> check_terms([{"term": "t", "definition": "names a doer", "kind": "type"}])
[]
>>> check_terms([{"term": "t", "definition": " ", "kind": "type"}])
['t: empty definition']
>>> check_terms([{"term": "t", "definition": "x", "kind": "type", "cites": [{}]}])
['t: citation without a quote']
>>> check_terms([{"term": "a", "definition": " "}, {"term": "b", "definition": "y"}])
['a: empty definition', 'a: no citation', 'b: no citation']
>>> check_terms([{"term": "a", "definition": "x", "cites": [{"locator": "f:1"}]}])
['a: citation without a quote']
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import TypedDict, cast


class _Cite(TypedDict, total=False):
    quote: str


class _RowBase(TypedDict):
    term: str


class _Row(_RowBase, total=False):
    parent: str
    definition: str
    kind: str
    cites: list[_Cite]


Vector = dict[str, float]

SYNONYMY_THRESHOLD = 0.5
"""Sibling definitions at or above this are candidates for one term, not two."""

POLYSEMY_THRESHOLD = 0.3
"""Two rows sharing a term whose definitions fall below this mean two concepts."""

_WORD = re.compile(r"[a-z0-9]+")
_URL = re.compile(r"https?://|\bwww\.", re.IGNORECASE)
_EVIDENCE_LINK = re.compile(r"\[[^\]]*\]\(evidence/[^)]*\)")
_CODE_SPAN = re.compile(r"`[^`]*`")
_LIST_MARKER = re.compile(r"^\s*(?:\d+[.)]|[-*+])\s+")
_DIGIT = re.compile(r"\d")
_SUFFIX = re.compile(r"(?:ing|ed|es|s)$")
_LEMMA_MIN = 5


def tokenize(text: object) -> list[str]:
    """Lowercase, split on non-alphanumerics, drop one-character tokens.

    >>> tokenize("Update-Action, v2!")
    ['update', 'action', 'v2']
    """
    tokens = cast("list[str]", _WORD.findall(str(text).lower()))
    return [tok for tok in tokens if len(tok) > 1]


def idf(docs: list[list[str]]) -> dict[str, float]:
    """Smoothed inverse document frequency per token across *docs*.

    Computed as ``log((N + 1) / (1 + df)) + 1`` so a token in every row keeps
    a positive weight; the textbook ``log(N / df)`` zeroes the shared
    vocabulary that makes siblings look alike.

    >>> round(idf([["a", "b"], ["a"]])["a"], 3)
    1.0
    >>> round(idf([["a", "b"], ["a"]])["b"], 3)
    1.405
    """
    total = len(docs)
    df: dict[str, int] = {}
    for doc in docs:
        for token in set(doc):
            df[token] = df.get(token, 0) + 1
    return {tok: math.log((total + 1) / (1 + n)) + 1 for tok, n in df.items()}


def cosine(a: Vector, b: Vector) -> float:
    """Cosine similarity of two token-weight maps.

    >>> cosine({"a": 1.0}, {"a": 1.0})
    1.0
    >>> cosine({"a": 1.0}, {})
    0.0
    """
    shared = set(a) & set(b)
    dot = sum(a[tok] * b[tok] for tok in shared)
    norm_a = math.sqrt(sum(val * val for val in a.values()))
    norm_b = math.sqrt(sum(val * val for val in b.values()))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def _vectors(terms: list[_Row]) -> list[Vector]:
    """Map each row index to its tf-idf weighted definition vector."""
    docs = [tokenize(row.get("definition", "")) for row in terms]
    weights = idf(docs)
    out: list[Vector] = []
    for doc in docs:
        vec: Vector = {}
        for token in doc:
            vec[token] = vec.get(token, 0.0) + weights.get(token, 1.0)
        out.append(vec)
    return out


def synonymy(
    terms: list[_Row],
    threshold: float = SYNONYMY_THRESHOLD,
) -> list[tuple[str, str, float]]:
    """Sibling pairs whose definitions score at or above *threshold*.

    Only rows sharing a parent are compared. Two terms under different parents
    are expected to differ, so a high score there is not evidence of one
    concept wearing two names.
    """
    vecs = _vectors(terms)
    hits: list[tuple[str, str, float]] = []
    for i, left in enumerate(terms):
        for j in range(i + 1, len(terms)):
            right = terms[j]
            if left.get("parent") != right.get("parent"):
                continue
            score = cosine(vecs[i], vecs[j])
            if score >= threshold:
                hits.append((left["term"], right["term"], score))
    hits.sort(key=lambda hit: -hit[2])
    return hits


def polysemy(terms: list[_Row]) -> list[tuple[str, list[str]]]:
    """Terms appearing more than once with definitions that do not match.

    Two rows sharing a term whose definitions score alike are a duplicate
    entry, not polysemy. The finding is one term standing for two concepts.
    """
    vecs = _vectors(terms)
    by_term: dict[str, list[int]] = {}
    for index, row in enumerate(terms):
        by_term.setdefault(row["term"], []).append(index)
    hits: list[tuple[str, list[str]]] = []
    for term, indexes in by_term.items():
        if len(indexes) <= 1:
            continue
        distant = any(
            cosine(vecs[a], vecs[b]) < POLYSEMY_THRESHOLD
            for pos, a in enumerate(indexes)
            for b in indexes[pos + 1 :]
        )
        if distant:
            hits.append((term, [terms[i].get("definition", "") for i in indexes]))
    hits.sort()
    return hits


def orphans(terms: list[_Row]) -> list[str]:
    """Terms whose parent is unassigned, or neither another term nor ``root``."""
    known = {row["term"] for row in terms} | {"root"}
    return [row["term"] for row in terms if row.get("parent", "") not in known]


def fan_out(terms: list[_Row]) -> dict[str, int]:
    """Child count per parent.

    >>> fan_out([{"term": "a", "parent": "t"}, {"term": "b", "parent": "t"}])
    {'t': 2}
    """
    counts: dict[str, int] = {}
    for row in terms:
        parent = row.get("parent", "")
        if parent:
            counts[parent] = counts.get(parent, 0) + 1
    return counts


def _lemmas(text: object) -> list[str]:
    """Tokens with one plural or verb suffix removed from words over four letters."""
    return [_SUFFIX.sub("", tok) if len(tok) >= _LEMMA_MIN else tok for tok in tokenize(text)]


def _contains(haystack: list[str], needle: list[str]) -> bool:
    """Return whether *needle* occurs in *haystack* as a contiguous run."""
    width = len(needle)
    return bool(needle) and any(
        haystack[i : i + width] == needle for i in range(len(haystack) - width + 1)
    )


def circular(terms: list[_Row]) -> list[str]:
    """Terms whose whole name, lemmatized, appears in a citation supporting them."""
    hits: list[str] = []
    for row in terms:
        own = _lemmas(row["term"])
        if any(_contains(_lemmas(cite.get("quote", "")), own) for cite in row.get("cites", [])):
            hits.append(row["term"])
    return hits


def check_brief(text: str) -> list[str]:
    """List findings for a brief that carries a citation, a permalink, or a bare number."""
    findings: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        bare = _EVIDENCE_LINK.sub("", line)
        if _URL.search(bare):
            findings.append(f"line {number}: URL belongs in evidence/, not the brief")
        bare = _LIST_MARKER.sub("", _CODE_SPAN.sub("", bare))
        if _DIGIT.search(bare):
            findings.append(f"line {number}: bare number belongs in evidence/, not the brief")
    return findings


def check_terms(terms: list[_Row]) -> list[str]:
    """List rows with an empty definition, no citation, or a citation with no quote.

    A ``type`` row may omit citations; any it carries still need a quote.
    """
    findings: list[str] = []
    for row in terms:
        if not row.get("definition", "").strip():
            findings.append(f"{row['term']}: empty definition")
        cites = row.get("cites")
        if not cites:
            if row.get("kind") == "type":
                continue
            findings.append(f"{row['term']}: no citation")
        elif any(not str(cite.get("quote", "")).strip() for cite in cites):
            findings.append(f"{row['term']}: citation without a quote")
    return findings


def _cite_problem(cite: object) -> str | None:
    """Describe why *cite* is not an object with a string ``quote``, or ``None``."""
    if not isinstance(cite, dict):
        return "each entry in 'cites' must be an object"
    if not isinstance(cast("dict[str, object]", cite).get("quote", ""), str):
        return "'quote' must be a string"
    return None


def _row_problem(row: object) -> str | None:
    """Describe why *row* is not a well-typed term row, or return ``None``."""
    if not isinstance(row, dict):
        return "row must be a JSON object"
    fields = cast("dict[str, object]", row)
    if not isinstance(fields.get("term"), str):
        return "row needs a string 'term'"
    for key in ("definition", "parent", "kind"):
        if key in fields and not isinstance(fields[key], str):
            return f"'{key}' must be a string"
    cites = fields.get("cites", [])
    if not isinstance(cites, list):
        return "'cites' must be a list"
    return next(filter(None, map(_cite_problem, cast("list[object]", cites))), None)


def _load(path: Path) -> tuple[list[_Row], list[str]]:
    """Read a JSON-lines file, skipping blank lines.

    Returns the well-typed rows and one ``<file> line <n>: <problem>`` message
    per row that is invalid JSON or mistyped.
    """
    rows: list[_Row] = []
    problems: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = cast("object", json.loads(line))
            except json.JSONDecodeError as exc:
                problems.append(f"{path.name} line {number}: invalid JSON ({exc.msg})")
                continue
            problem = _row_problem(row)
            if problem:
                problems.append(f"{path.name} line {number}: {problem}")
            else:
                rows.append(cast("_Row", row))
    return rows, problems


class _Opts(argparse.Namespace):
    study: str = ""
    check_brief: bool = False
    check_terms: bool = False


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="term_metrics.py", allow_abbrev=False)
    _ = parser.add_argument("study", help="study directory")
    gate = parser.add_mutually_exclusive_group()
    _ = gate.add_argument("--check-brief", action="store_true", help="gate brief.md")
    _ = gate.add_argument("--check-terms", action="store_true", help="gate terms.jsonl")
    return parser


def _brief_gate(study: str) -> int:
    """Print the brief's findings; exit 2 when brief.md is missing."""
    brief = Path(f"{study}/brief.md")
    if not brief.is_file():
        print(f"no brief.md in {study}", file=sys.stderr)
        return 2
    findings = check_brief(brief.read_text(encoding="utf-8"))
    for finding in findings:
        print(finding)
    return 1 if findings else 0


def main(argv: list[str]) -> int:
    """Report every finding for the study directory named in *argv*."""
    try:
        opts = _parser().parse_args(argv, namespace=_Opts())
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    study = opts.study.rstrip("/")

    if opts.check_brief:
        return _brief_gate(study)

    table = Path(f"{study}/terms.jsonl")
    if not table.is_file():
        print(f"no terms.jsonl in {study}", file=sys.stderr)
        return 2
    terms, problems = _load(table)
    if problems:
        for problem in problems:
            print(problem)
        return 1
    if opts.check_terms:
        findings = check_terms(terms)
        for finding in findings:
            print(finding)
        return 1 if findings else 0

    sections: list[tuple[str, list[str]]] = [
        ("synonymy", [f"{a} / {b} at {score:.3f}" for a, b, score in synonymy(terms)]),
        ("polysemy", [f"{term}: {len(defs)} definitions" for term, defs in polysemy(terms)]),
        ("orphans", orphans(terms)),
        ("circular evidence", circular(terms)),
        ("fan-out", [f"{p}: {n}" for p, n in sorted(fan_out(terms).items())]),
    ]
    for title, rows in sections:
        print(f"== {title} ==")
        for row in rows or ["(none)"]:
            print(f"  {row}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
