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
>>> orphans([{"term": "probe", "parent": "root", "kind": "verb", "definition": "one path"}])
['probe']

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

A quote is checked against the cited lines of a local git clone at the
commit recorded for its source; a moved line is a misquote:

>>> check_quote("src/a.py:2-3", "line-range", "beta gamma", "alpha\nbeta\ngamma\ndelta\n")
'ok'
>>> check_quote("src/a.py:1-1", "line-range", "beta gamma", "alpha\nbeta\ngamma\ndelta\n")
'misquoted'
>>> check_quote("src/a.py", "search-string", "gamma", "alpha\nbeta\ngamma\n")
'ok'
>>> parse_locator("src/a.py@9a29b1a:12-18")
('src/a.py', 12, 18)
>>> parse_locator("ch.3 section 2") is None
True

Every term row needs ``schema: 1``, a definition and a citation with a quote
and a ``source`` that ``sources.jsonl`` lists; a ``type`` row with a ``parent``
needs no citation of its own, since its is-a claims are cited in
``evidence/hierarchy.md``:

>>> v = {"schema": 1}
>>> src = [{"source": "s"}]
>>> cite = {"quote": "q", "source": "s"}
>>> check_terms([{**v, "term": "a", "definition": "x", "cites": [cite]}], src)
[]
>>> check_terms([{**v, "term": "t", "definition": "d", "kind": "type", "parent": "root"}])
[]
>>> check_terms([{**v, "term": "t", "definition": "d", "kind": "type"}])
['t: no citation']
>>> check_terms([{**v, "term": "t", "definition": " ", "kind": "type", "parent": "root"}])
['t: empty definition']
>>> check_terms([{**v, "term": "t", "definition": "x", "kind": "type", "cites": [{}]}])
['t: citation without a quote']
>>> check_terms([{**v, "term": "a", "definition": " "}, {**v, "term": "b", "definition": "y"}])
['a: empty definition', 'a: no citation', 'b: no citation']
>>> check_terms([{**v, "term": "a", "definition": "x", "cites": [{"locator": "f:1"}]}])
['a: citation without a quote']
>>> check_terms([{**v, "term": "a", "definition": "x", "cites": [{"quote": "q"}]}])
['a: citation without a source']
>>> check_terms([{"term": "a", "definition": "x", "kind": "banana", "parent": "root"}])
['a: schema must be 1', "a: unknown kind 'banana'", 'a: no citation']
>>> cite = {"quote": "q", "source": "z"}
>>> check_terms([{**v, "term": "a", "definition": "x", "cites": [cite]}], src)
["a: source 'z' is not in sources.jsonl"]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import TypedDict, cast


class _Cite(TypedDict, total=False):
    quote: str
    source: str
    locator: str
    url: str


class _RowBase(TypedDict):
    term: str


class _Row(_RowBase, total=False):
    schema: int
    parent: str
    definition: str
    kind: str
    cites: list[_Cite]


Vector = dict[str, float]

SYNONYMY_THRESHOLD = 0.5
"""Sibling definitions at or above this are candidates for one term, not two."""

POLYSEMY_THRESHOLD = 0.3
"""Two rows sharing a term whose definitions fall below this mean two concepts."""

_CJK = "\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af"
_WORD = re.compile(rf"[{_CJK}]|[^\W_{_CJK}]+")
_URL = re.compile(r"https?://|\bwww\.", re.IGNORECASE)
_MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]*)\)")
_EVIDENCE_TARGET = re.compile(r"evidence/[\w./-]+(?:#[\w.-]+)?")
_CODE_SPAN = re.compile(r"`[^`]*`")
_LIST_MARKER = re.compile(r"^\s*(?:\d+[.)]|[-*+])\s+")
_DIGIT = re.compile(r"\d")
_LEMMA_MIN = 5


def tokenize(text: object) -> list[str]:
    """Casefold, split on non-alphanumerics, drop one-letter Latin tokens.

    Letters of any script count; each CJK character is its own token.

    >>> tokenize("Update-Action, v2!")
    ['update', 'action', 'v2']
    >>> tokenize("na\u00efve \u7c7b")
    ['na\u00efve', '\u7c7b']
    """
    tokens = cast("list[str]", _WORD.findall(str(text).casefold()))
    return [tok for tok in tokens if len(tok) > 1 or re.match(f"[{_CJK}]", tok)]


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
    """Terms whose parent is unassigned, or neither another term nor ``root``.

    A typed row other than ``type`` parented to ``root`` is also reported:
    only types sit directly under ``root``.
    """
    known = {row["term"] for row in terms} | {"root"}
    return [
        row["term"]
        for row in terms
        if row.get("parent", "") not in known
        or (row.get("parent") == "root" and row.get("kind", "type") != "type")
    ]


def cycles(terms: list[_Row]) -> list[str]:
    """Parent chains that loop back on themselves, self-parents included.

    >>> cycles([{"term": "a", "parent": "a"}])
    ['a -> a']
    >>> cycles([{"term": "a", "parent": "b"}, {"term": "b", "parent": "a"}])
    ['a -> b -> a']
    >>> cycles([{"term": "a", "parent": "root"}])
    []
    """
    parents: dict[str, list[str]] = {}
    for row in terms:
        parent = row.get("parent", "")
        if parent:
            parents.setdefault(row["term"], []).append(parent)
    found: set[tuple[str, ...]] = set()
    done: set[str] = set()
    for start, first in parents.items():
        if start in done:
            continue
        path = [start]
        on_path = {start}
        stack = [iter(first)]
        while stack:
            parent = next(stack[-1], None)
            if parent is None:
                _ = stack.pop()
                node = path.pop()
                on_path.discard(node)
                done.add(node)
                continue
            if parent in on_path:
                loop = path[path.index(parent) :]
                pivot = loop.index(min(loop))
                found.add(tuple(loop[pivot:] + loop[:pivot]))
            elif parent in parents and parent not in done:
                path.append(parent)
                on_path.add(parent)
                stack.append(iter(parents[parent]))
    return [" -> ".join((*loop, loop[0])) for loop in sorted(found)]


def check_hierarchy(terms: list[_Row]) -> list[str]:
    """One line per orphan or parent cycle, for the ``distill`` and ``contest`` gates.

    >>> check_hierarchy([{"term": "a", "parent": "a"}, {"term": "b", "parent": "x"}])
    ['Orphan: b', 'Cycle: a -> a']
    >>> check_hierarchy([{"term": "a", "parent": "root", "kind": "type"}])
    []
    """
    return [f"Orphan: {term}" for term in orphans(terms)] + [
        f"Cycle: {loop}" for loop in cycles(terms)
    ]


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


def _stems(token: str) -> frozenset[str]:
    """Return the token and each plausible singular or base form of it.

    Two words match when their stem sets intersect, so ``classes`` meets
    ``class`` and ``caches`` meets ``cache`` without a single rule having to
    guess which suffix was dropped.

    >>> sorted(_stems("classes") & _stems("class"))
    ['class']
    >>> bool(_stems("process") & _stems("processes"))
    True
    >>> bool(_stems("status") & _stems("statu"))
    False
    """
    forms = {token}
    if len(token) >= _LEMMA_MIN:
        if token.endswith("ies"):
            forms.add(token[:-3] + "y")
        if token.endswith("es"):
            forms.update((token[:-2], token[:-1]))
        elif token.endswith("s") and not token.endswith(("ss", "us", "is")):
            forms.add(token[:-1])
        if token.endswith("ing"):
            forms.add(token[:-3])
        if token.endswith("ed"):
            forms.update((token[:-2], token[:-1]))
    return frozenset(forms)


def _lemmas(text: object) -> list[frozenset[str]]:
    """Stem sets of the tokens in *text*."""
    return [_stems(tok) for tok in tokenize(text)]


def _contains(haystack: list[frozenset[str]], needle: list[frozenset[str]]) -> bool:
    """Return whether *needle* occurs in *haystack* as a contiguous run of matching words."""
    width = len(needle)
    return bool(needle) and any(
        all(a & b for a, b in zip(haystack[i : i + width], needle))
        for i in range(len(haystack) - width + 1)
    )


def _names(term: str, quote: str) -> bool:
    """Return whether *quote* contains *term*, ignoring case and plural or verb endings.

    A term with no word tokens (``C++``) is matched as a literal run that
    does not start or end inside a longer word.
    """
    own = _lemmas(term)
    if own:
        return _contains(_lemmas(quote), own)
    literal = term.strip().casefold()
    if not literal:
        return False
    pattern = rf"(?<!\w){re.escape(literal)}(?!\w)"
    return re.search(pattern, quote.casefold()) is not None


def circular(terms: list[_Row]) -> list[str]:
    """Terms whose whole name, lemmatized, appears in a citation supporting them.

    >>> circular([{"term": "class", "cites": [{"quote": "all classes derive from Base"}]}])
    ['class']
    >>> circular([{"term": "C++", "cites": [{"quote": "ported to C++ in 2019"}]}])
    ['C++']
    """
    return [
        row["term"]
        for row in terms
        if any(_names(row["term"], str(cite.get("quote", ""))) for cite in row.get("cites", []))
    ]


def _strip_evidence_link(match: re.Match[str]) -> str:
    """Exempt only lexical descendants of ``evidence/``."""
    target = match.group(1)
    if _EVIDENCE_TARGET.fullmatch(target) and ".." not in target.split("#", 1)[0].split("/"):
        return ""
    return match.group(0)


def check_brief(text: str, study: Path | None = None) -> list[str]:
    """Find URLs, bare numbers, and inline links outside ``evidence/``.

    With *study*, a link into ``evidence/`` must also name a file that exists.

    >>> check_brief("See [it](evidence/nowhere.md).", Path("/nonexistent-study"))
    ['line 1: evidence/nowhere.md does not exist']
    """
    findings: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if study is not None:
            for link in _MARKDOWN_LINK.finditer(line):
                target = link.group(1).split("#", 1)[0]
                if _strip_evidence_link(link) == "" and not (study / target).is_file():
                    findings.append(f"line {number}: {target} does not exist")
        bare = _MARKDOWN_LINK.sub(_strip_evidence_link, line)
        if _MARKDOWN_LINK.search(bare):
            findings.append(f"line {number}: link target must stay in evidence/")
        if _URL.search(bare):
            findings.append(f"line {number}: URL belongs in evidence/, not the brief")
        bare = _LIST_MARKER.sub("", _CODE_SPAN.sub("", bare))
        if _DIGIT.search(bare):
            findings.append(f"line {number}: bare number belongs in evidence/, not the brief")
    return findings


KINDS = frozenset({"class", "module", "verb", "role", "message", "concept", "type"})
LOCATOR_KINDS = frozenset({"line-range", "section", "page", "search-string"})
SCHEMA = 1


def check_terms(
    terms: list[_Row],
    sources: list[dict[str, object]] | None = None,
) -> list[str]:
    """List rows that break the term-table contract.

    A row needs a known ``kind`` when it has one, a non-empty definition, and
    at least one citation with a quote and a source; when *sources* is given,
    each cite's source must name a row there. A ``type`` row with a
    ``parent`` may omit citations, since ``distill`` assigns the parent and
    cites the is-a claim in ``evidence/hierarchy.md``; any citation it carries
    still needs a quote.
    """
    known = {str(row.get("source", "")) for row in sources} if sources is not None else None
    findings: list[str] = []
    for row in terms:
        name = row["term"]
        if row.get("schema") != SCHEMA:
            findings.append(f"{name}: schema must be {SCHEMA}")
        if "kind" in row and row["kind"] not in KINDS:
            findings.append(f"{name}: unknown kind '{row['kind']}'")
        if not row.get("definition", "").strip():
            findings.append(f"{name}: empty definition")
        cites = row.get("cites")
        if not cites:
            if row.get("kind") == "type" and row.get("parent", ""):
                continue
            findings.append(f"{name}: no citation")
        elif any(not str(cite.get("quote", "")).strip() for cite in cites):
            findings.append(f"{name}: citation without a quote")
        elif any(not str(cite.get("source", "")).strip() for cite in cites):
            findings.append(f"{name}: citation without a source")
        elif known is not None:
            findings.extend(
                f"{name}: source '{cite.get('source', '')}' is not in sources.jsonl"
                for cite in cites
                if cite.get("source", "") not in known
            )
    return findings


_FULL_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_STRING_FIELDS = ("source", "ref", "commit", "scope", "why")


def check_sources(sources: list[dict[str, object]]) -> list[str]:
    """List ``sources.jsonl`` rows that break the gather gate.

    Every row has its string fields, a known ``locator_kind`` and a boolean
    ``read``; a recorded ``commit`` is 40 hex digits; a GitHub source has one;
    a source not read says why; rows sharing a ``source`` agree on ``commit``
    and ``locator_kind``.

    >>> row = {"source": "https://github.com/o/r", "ref": "v1", "commit": "a" * 40,
    ...        "scope": "src/", "locator_kind": "line-range", "read": True, "why": ""}
    >>> check_sources([row])
    []
    >>> check_sources([{**row, "commit": "abc", "read": False}])
    ['row 1: commit must be 40 hex digits', 'row 1: not read, so why is required']
    """
    findings: list[str] = []
    seen: dict[str, dict[str, object]] = {}
    for number, row in enumerate(sources, start=1):
        label = f"row {number}"
        bad = [key for key in _STRING_FIELDS if not isinstance(row.get(key), str)]
        if bad:
            findings.append(f"{label}: {', '.join(bad)} must be a string")
            continue
        source, commit = str(row["source"]), str(row["commit"])
        if not source.strip():
            findings.append(f"{label}: source is empty")
        if row.get("locator_kind") not in LOCATOR_KINDS:
            findings.append(
                f"{label}: locator_kind must be one of {', '.join(sorted(LOCATOR_KINDS))}"
            )
        if not isinstance(row.get("read"), bool):
            findings.append(f"{label}: read must be true or false")
        if commit and not _FULL_COMMIT.match(commit):
            findings.append(f"{label}: commit must be 40 hex digits")
        elif not commit and source.startswith("https://github.com/"):
            findings.append(f"{label}: a GitHub source needs its commit")
        if row.get("read") is False and not str(row["why"]).strip():
            findings.append(f"{label}: not read, so why is required")
        first = seen.setdefault(source, row)
        if first is not row:
            findings.extend(
                f"{label}: {key} differs from the first row for {source}"
                for key in ("commit", "locator_kind")
                if first.get(key) != row.get(key)
            )
    return findings


_LOCATOR = re.compile(r"^([A-Za-z0-9_./-]+?)(?:@[0-9a-fA-F]{7,40})?(?::(\d+)(?:-(\d+))?)?$")
_HEX_COMMIT = re.compile(r"^[0-9a-fA-F]{7,40}$")
_SNIPPET = 200


def parse_locator(locator: str) -> tuple[str, int, int] | None:
    """Split ``path[@commit][:first[-last]]`` into path and 1-based lines.

    A locator without lines yields ``(path, 0, 0)``; anything that is not a
    plain relative path gives ``None``.
    """
    match = _LOCATOR.match(locator.strip())
    if not match or match.group(1).startswith(("/", "-")) or ".." in match.group(1).split("/"):
        return None
    first = int(match.group(2) or 0)
    last = int(match.group(3) or first)
    if match.group(2) is not None and not 1 <= first <= last:
        return None
    return match.group(1), first, last


def _squash(text: str) -> str:
    return " ".join(text.split())


_ELLIPSIS = re.compile(r"\.\.\.|\u2026")


def _quote_in(quote: str, text: str) -> bool | None:
    r"""Return whether *quote* is in *text*, or ``None`` for an empty quote.

    Whitespace differences do not count; case does. An ellipsis marks an
    omission, so the pieces around it must appear in order.

    >>> _quote_in("alpha ... gamma", "alpha\nbeta\ngamma")
    True
    >>> _quote_in("gamma ... alpha", "alpha beta gamma")
    False
    >>> _quote_in("...", "alpha") is None
    True
    """
    pieces = [_squash(piece) for piece in _ELLIPSIS.split(quote)]
    pieces = [piece for piece in pieces if piece]
    if not pieces:
        return None
    haystack, at = _squash(text), 0
    for piece in pieces:
        found = haystack.find(piece, at)
        if found < 0:
            return False
        at = found + len(piece)
    return True


def check_quote(locator: str, kind: str, quote: str, text: str) -> str:
    """Return ``ok``, ``misquoted``, or ``uncheckable`` for one cite against file *text*.

    A ``line-range`` locator must identify existing lines. Other recognized
    kinds search the whole file. Whitespace differences do not count.
    """
    parsed = parse_locator(locator)
    if parsed is None or kind not in LOCATOR_KINDS or _quote_in(quote, "") is None:
        return "uncheckable"
    _, first, last = parsed
    if kind == "line-range":
        lines = text.splitlines()
        if not 1 <= first <= last <= len(lines):
            return "uncheckable"
        text = "\n".join(lines[first - 1 : last])
    return "ok" if _quote_in(quote, text) else "misquoted"


def _git_show(clone: str, commit: str, path: str) -> str | None:
    """Return the file at *commit*, or ``None`` when git cannot produce it."""
    try:
        done = subprocess.run(  # noqa: S603
            ["git", "-C", clone, "show", f"{commit}:{path}"],  # noqa: S607
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    return done.stdout.decode("utf-8", "replace") if done.returncode == 0 else None


def _has_commit(clone: str, commit: str) -> bool:
    try:
        done = subprocess.run(  # noqa: S603
            ["git", "-C", clone, "cat-file", "-e", f"{commit}^{{commit}}"],  # noqa: S607
            capture_output=True,
            check=False,
        )
    except OSError:
        return False
    return done.returncode == 0


def _excerpt(study: Path | None, source: str) -> str | None:
    """Return the text of a pasted excerpt stored in the study as *source*, else ``None``."""
    if study is None or source.startswith(("/", "-")) or ".." in source.split("/"):
        return None
    path = study / source
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _source_rows(sources: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    """Map each source to its first row; disagreeing rows are ``check_sources``'s finding."""
    rows: dict[str, dict[str, object]] = {}
    for row in sources:
        if isinstance(row.get("source"), str):
            _ = rows.setdefault(str(row["source"]), row)
    return rows


def _conflicted(sources: list[dict[str, object]]) -> set[str]:
    """Return the sources whose rows disagree on ``commit`` or ``locator_kind``."""
    first: dict[str, dict[str, object]] = {}
    bad: set[str] = set()
    for row in sources:
        name = row.get("source")
        if not isinstance(name, str):
            continue
        base = first.setdefault(name, row)
        if any(base.get(key) != row.get(key) for key in ("commit", "locator_kind")):
            bad.add(name)
    return bad


def _check_excerpt_cite(label: str, cite: _Cite, study: Path | None) -> str | None:
    """Search a pasted excerpt stored in the study for the cite's quote."""
    source = str(cite.get("source", ""))
    text = _excerpt(study, source)
    if text is None:
        return f"Uncheckable: {label}: no pinned commit or excerpt file"
    found = _quote_in(str(cite.get("quote", "")), text)
    if found is None:
        return f"Uncheckable: {label}: empty quote"
    return None if found else f"Misquoted: {label}: quote not found in {source}"


def _check_git_cite(
    label: str, cite: _Cite, pin: dict[str, object], clone: str | None
) -> str | None:
    """Read the cite's file at the pinned commit in *clone* and test its quote."""
    commit = str(pin.get("commit", "")).strip()
    parsed = parse_locator(str(cite.get("locator", "")))
    if not _HEX_COMMIT.match(commit) or parsed is None:
        return f"Uncheckable: {label}: no pinned commit or file path"
    if clone is None:
        return f"Uncheckable: {label}: no clone given for {cite.get('source', '')}"
    if not _has_commit(clone, commit):
        return f"Uncheckable: {label}: commit not in the clone"
    text = _git_show(clone, commit, parsed[0])
    if text is None:
        return f"Vanished: {label}: {parsed[0]} is not in the commit"
    return _judge(label, cite, str(pin.get("locator_kind", "")), parsed, text)


def _judge(
    label: str, cite: _Cite, kind: str, parsed: tuple[str, int, int], text: str
) -> str | None:
    """Test the cite's quote against the file *text* it names."""
    verdict = check_quote(str(cite.get("locator", "")), kind, str(cite.get("quote", "")), text)
    if verdict == "misquoted":
        first, last = parsed[1], parsed[2]
        there = _squash("\n".join(text.splitlines()[first - 1 : last]))
        where = there[:_SNIPPET] if kind == "line-range" and first else "whole file"
        return f"Misquoted: {label}: quote not found; text there: {where}"
    if verdict == "uncheckable":
        return f"Uncheckable: {label}: empty quote or unusable locator"
    return None


def _check_cite(
    label: str,
    cite: _Cite,
    pin: dict[str, object] | None,
    clone: str | None,
    study: Path | None,
) -> str | None:
    """Return one finding line for *cite*, or ``None`` when its quote is present."""
    if pin is None:
        return f"Uncheckable: {label}: source is not in sources.jsonl"
    if not str(pin.get("commit", "")).strip():
        return _check_excerpt_cite(label, cite, study)
    return _check_git_cite(label, cite, pin, clone)


def check_quotes(
    terms: list[_Row],
    sources: list[dict[str, object]],
    clones: dict[str, str],
    default_clone: str | None = None,
    study: Path | None = None,
) -> list[str]:
    """List cites whose quote is missing from the source they name.

    A cite into a git source is read at the recorded commit in the clone for
    its source (*clones*), else *default_clone*. A cite into a pasted excerpt
    stored under *study* is searched for in that file. Each finding starts
    with ``Misquoted``, ``Vanished`` or ``Uncheckable``, the report sections
    ``verify`` uses.
    """
    rows, bad = _source_rows(sources), _conflicted(sources)
    findings: list[str] = []
    for row in terms:
        for cite in row.get("cites", []):
            source = str(cite.get("source", ""))
            label = f"{row['term']} ({cite.get('locator', '')})"
            if source in bad:
                findings.append(f"Uncheckable: {label}: rows for the source disagree")
                continue
            found = _check_cite(
                label, cite, rows.get(source), clones.get(source, default_clone), study
            )
            if found:
                findings.append(found)
    return findings


def check_quotations(
    quotations: list[dict[str, object]],
    sources: list[dict[str, object]],
    study: Path,
) -> list[str]:
    """List ``quotations.jsonl`` rows whose quote is not verbatim in a stored excerpt."""
    rows = _source_rows(sources)
    findings: list[str] = []
    for number, row in enumerate(quotations, start=1):
        source = str(row.get("source", ""))
        quote = str(row.get("quote", ""))
        label = f"quotation {number} ({source})"
        text = _excerpt(study, source)
        found = None if text is None else _quote_in(quote, text)
        if source not in rows:
            findings.append(f"Uncheckable: {label}: source is not in sources.jsonl")
        elif text is None:
            findings.append(f"Uncheckable: {label}: source is not stored in the study")
        elif found is None:
            findings.append(f"Uncheckable: {label}: empty quote")
        elif not found:
            findings.append(f"Misquoted: {label}: quote not found in the source")
    return findings


_CLAIM = re.compile(r"^\s*(?:[-*]\s*)?Claim:\s*(.*)$", re.IGNORECASE)
_VERDICT = re.compile(r"^\s*(?:[-*]\s*)?Verdict:\s*([A-Za-z]+)", re.IGNORECASE)
_VERDICTS = frozenset({"upheld", "revised", "killed"})


def contest_entries(text: str) -> list[tuple[str, str, str]]:
    r"""Split ``contested.md`` into ``(claim, body, verdict)`` entries.

    An entry starts at a ``Claim:`` line and runs to the next one; its verdict
    is the first word after ``Verdict:``, lowercased, or ``""`` when absent.

    >>> contest_entries("- Claim: a / b are one\n- Verdict: Killed. They differ.\n")
    [('a / b are one', '- Claim: a / b are one\n- Verdict: Killed. They differ.', 'killed')]
    """
    entries: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        claim = _CLAIM.match(line)
        if claim:
            entries.append((claim.group(1).strip(), [line]))
        elif entries:
            entries[-1][1].append(line)
    out: list[tuple[str, str, str]] = []
    for claim, lines in entries:
        verdicts = [m.group(1).lower() for m in map(_VERDICT.match, lines) if m]
        out.append((claim, "\n".join(lines).strip(), verdicts[0] if verdicts else ""))
    return out


def _mentions(body: str, term: str) -> bool:
    pattern = rf"(?<!\w){re.escape(term.casefold())}(?!\w)"
    return re.search(pattern, body.casefold()) is not None


def check_verdicts(terms: list[_Row], entries: list[tuple[str, str, str]]) -> list[str]:
    r"""List findings the analyzer raised with no judged entry, and claims still open.

    A finding is judged when one entry with a verdict of ``upheld``,
    ``revised`` or ``killed`` names every term in it.

    >>> rows = [{"term": "a", "parent": "r", "definition": "bump one pin"},
    ...         {"term": "b", "parent": "r", "definition": "bump one pin"}]
    >>> check_verdicts(rows, [])
    ['Unjudged: synonymy a / b', 'Unjudged: orphan a', 'Unjudged: orphan b']
    >>> check_verdicts(rows, [("a b", "Claim: a and b\nVerdict: open", "open")])
    ['Unjudged: synonymy a / b', 'Unjudged: orphan a', 'Unjudged: orphan b', 'Open: a b']
    """
    findings: list[tuple[str, list[str]]] = [
        (f"synonymy {a} / {b}", [a, b]) for a, b, _ in synonymy(terms)
    ]
    findings += [(f"polysemy {term}", [term]) for term, _ in polysemy(terms)]
    findings += [(f"orphan {term}", [term]) for term in orphans(terms)]
    findings += [(f"cycle {loop}", loop.split(" -> ")) for loop in cycles(terms)]
    findings += [(f"circular evidence {term}", [term]) for term in circular(terms)]
    judged = [body for _, body, verdict in entries if verdict in _VERDICTS]
    lines = [
        f"Unjudged: {label}"
        for label, names in findings
        if not any(all(_mentions(body, name) for name in names) for body in judged)
    ]
    lines += [f"Open: {claim}" for claim, _, verdict in entries if verdict not in _VERDICTS]
    return lines


def _cite_problem(cite: object) -> str | None:
    """Describe why *cite* is not a well-typed citation, or return ``None``."""
    if not isinstance(cite, dict):
        return "each entry in 'cites' must be an object"
    fields = cast("dict[str, object]", cite)
    for key in ("quote", "source", "locator", "url"):
        if not isinstance(fields.get(key, ""), str):
            return f"'{key}' must be a string"
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


def _load_objects(path: Path) -> tuple[list[dict[str, object]], list[str]]:
    """Read a JSON-lines file of objects, reporting each blank-skipped bad line."""
    rows: list[dict[str, object]] = []
    problems: list[str] = []
    if not path.is_file():
        return rows, problems
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = cast("object", json.loads(line))
        except json.JSONDecodeError as exc:
            problems.append(f"{path.name} line {number}: invalid JSON ({exc.msg})")
            continue
        if isinstance(row, dict):
            rows.append(cast("dict[str, object]", row))
        else:
            problems.append(f"{path.name} line {number}: row must be a JSON object")
    return rows, problems


class _Opts(argparse.Namespace):
    study: str = ""
    check_quotes: list[str] | None = None
    check_brief: bool = False
    check_terms: bool = False
    check_sources: bool = False
    check_hierarchy: bool = False
    check_quotations: bool = False
    check_verdicts: bool = False


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="term_metrics.py", allow_abbrev=False)
    _ = parser.add_argument("study", help="study directory")
    gate = parser.add_mutually_exclusive_group()
    _ = gate.add_argument("--check-brief", action="store_true", help="gate brief.md")
    _ = gate.add_argument("--check-terms", action="store_true", help="gate terms.jsonl")
    _ = gate.add_argument("--check-sources", action="store_true", help="gate sources.jsonl")
    _ = gate.add_argument(
        "--check-hierarchy",
        action="store_true",
        help="exit 1 on an orphan or a parent cycle",
    )
    _ = gate.add_argument(
        "--check-verdicts",
        action="store_true",
        help="exit 1 on a finding with no verdict in evidence/contested.md, or an open claim",
    )
    _ = gate.add_argument(
        "--check-quotations",
        action="store_true",
        help="check quotations.jsonl against the excerpts stored in the study",
    )
    _ = gate.add_argument(
        "--check-quotes",
        action="append",
        metavar="[SOURCE=]CLONE",
        help="check each quote at the recorded commit in a git clone; repeat per source",
    )
    return parser


def _brief_gate(study: str) -> int:
    """Print the brief's findings; exit 2 when brief.md is missing."""
    brief = Path(f"{study}/brief.md")
    if not brief.is_file():
        print(f"no brief.md in {study}", file=sys.stderr)
        return 2
    findings = check_brief(brief.read_text(encoding="utf-8"), Path(study))
    for finding in findings:
        print(finding)
    return 1 if findings else 0


def _report(findings: list[str]) -> int:
    """Print *findings*; exit 1 when there are any."""
    for finding in findings:
        print(finding)
    return 1 if findings else 0


def _sources_file(study: str) -> tuple[list[dict[str, object]], list[str]] | None:
    """Load ``sources.jsonl``, or print the refusal and return ``None``."""
    path = Path(f"{study}/sources.jsonl")
    if not path.is_file():
        print(f"no sources.jsonl in {study}", file=sys.stderr)
        return None
    return _load_objects(path)


def _clone_args(values: list[str]) -> tuple[dict[str, str], str | None]:
    """Split ``--check-quotes`` values into per-source clones and a default clone."""
    clones: dict[str, str] = {}
    default: str | None = None
    for value in values:
        source, sep, clone = value.partition("=")
        if sep and source and not Path(value).is_dir():
            clones[source] = clone
        else:
            default = value
    return clones, default


def _source_gates(opts: _Opts, study: str) -> int:
    """Run the gates that read ``sources.jsonl`` without a term table."""
    loaded = _sources_file(study)
    if loaded is None:
        return 2
    sources, problems = loaded
    if problems:
        return _report(problems)
    if opts.check_sources:
        return _report(check_sources(sources))
    path = Path(f"{study}/quotations.jsonl")
    if not path.is_file():
        print(f"no quotations.jsonl in {study}", file=sys.stderr)
        return 2
    quotations, problems = _load_objects(path)
    return _report(problems or check_quotations(quotations, sources, Path(study)))


def _sourced_gates(opts: _Opts, study: str, terms: list[_Row]) -> int:
    """Run the term and quote gates, which also read ``sources.jsonl``."""
    loaded = _sources_file(study)
    if loaded is None:
        return 2
    sources, problems = loaded
    if problems:
        return _report(problems)
    if opts.check_quotes:
        clones, default = _clone_args(opts.check_quotes)
        return _report(check_quotes(terms, sources, clones, default, Path(study)))
    return _report(check_terms(terms, sources))


def _term_gates(opts: _Opts, study: str, terms: list[_Row]) -> int | None:
    """Run the gates that read the term table; ``None`` when none was asked for."""
    if opts.check_hierarchy:
        return _report(check_hierarchy(terms))
    if opts.check_verdicts:
        ledger = Path(f"{study}/evidence/contested.md")
        text = ledger.read_text(encoding="utf-8") if ledger.is_file() else ""
        return _report(check_verdicts(terms, contest_entries(text)))
    if opts.check_terms or opts.check_quotes:
        return _sourced_gates(opts, study, terms)
    return None


def _report_all(terms: list[_Row]) -> int:
    """Print the full analyzer report."""
    sections: list[tuple[str, list[str]]] = [
        ("synonymy", [f"{a} / {b} at {score:.3f}" for a, b, score in synonymy(terms)]),
        ("polysemy", [f"{term}: {len(defs)} definitions" for term, defs in polysemy(terms)]),
        ("orphans", orphans(terms)),
        ("hierarchy cycles", cycles(terms)),
        ("circular evidence", circular(terms)),
        ("fan-out", [f"{p}: {n}" for p, n in sorted(fan_out(terms).items())]),
    ]
    print(f"analyzer-sha256: {hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}")
    print(f"thresholds: synonymy >= {SYNONYMY_THRESHOLD}, polysemy < {POLYSEMY_THRESHOLD}")
    for title, rows in sections:
        print(f"== {title} ==")
        for row in rows or ["(none)"]:
            print(f"  {row}")
    return 0


def _study_gates(opts: _Opts, study: str) -> int:
    """Run the gate or report that *opts* names, for a study with a term table."""
    table = Path(f"{study}/terms.jsonl")
    if not table.is_file():
        print(f"no terms.jsonl in {study}", file=sys.stderr)
        return 2
    terms, problems = _load(table)
    if problems:
        return _report(problems)
    gated = _term_gates(opts, study, terms)
    return _report_all(terms) if gated is None else gated


def main(argv: list[str]) -> int:
    """Report every finding for the study directory named in *argv*."""
    try:
        opts = _parser().parse_args(argv, namespace=_Opts())
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    study = opts.study.rstrip("/")
    if opts.check_brief:
        return _brief_gate(study)
    if opts.check_sources or opts.check_quotations:
        return _source_gates(opts, study)
    return _study_gates(opts, study)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
