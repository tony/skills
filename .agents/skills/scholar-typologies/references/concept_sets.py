#!/usr/bin/env python3
r"""Check, diff, and tabulate a concept-set study for scholar.

A study directory holds ``sets.jsonl`` (one row per concept set),
``sources.jsonl`` (the format ``gather`` writes), and optionally
``catalog.jsonl`` (the reader's existing entries). Standard library only.

``check`` prints one finding per line and exits 1 when there are any.
``diff`` prints, as JSON, what the catalog has not codified.
``table`` prints the sets as a Markdown table, one row per set.
A missing or unreadable file prints one line to stderr and exits 2.

Examples
--------
Names compare after case, apostrophes, punctuation, and a leading article
are folded away:

>>> normalize("The  Maslow\u2019s Hierarchy-of-Needs")
'maslow hierarchy of needs'
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import cast

KINDS = frozenset(
    {
        "typology",
        "stage",
        "process",
        "level",
        "componential",
        "skills",
        "cross-classification",
        "axiom",
    }
)
ORDERS = frozenset({"developmental", "procedural", "rank", "presentation"})
STANDINGS = frozenset({"canonical", "contested", "superseded", "popularized"})
PROVENANCES = frozenset({"original", "later-synthesis", "editorial"})
ROLES = frozenset({"primary", "secondary"})

_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_REQUIRED_TEXT = ("name", "framework", "author", "year", "purpose", "member_noun")
_LINK_FIELDS = ("parent", "variant_of")
_MIN_MEMBERS = 2

type Row = dict[str, object]


def normalize(text: str) -> str:
    """Fold *text* to a comparison key: casefold, drop possessives and punctuation.

    >>> normalize("Erikson's eight stages")
    'erikson eight stages'
    >>> normalize("  ")
    ''
    """
    folded = text.casefold().replace("\u2019", "'").replace("\u2018", "'")
    folded = re.sub(r"'s\b", "", folded)
    words = re.sub(r"[^\w]+", " ", folded).split()
    if words[:1] == ["the"]:
        words = words[1:]
    return " ".join(words)


def load_rows(path: Path) -> tuple[list[Row], list[str]]:
    """Read a JSON-lines file of objects, skipping blank lines.

    Returns the object rows and one ``<file> line <n>: <problem>`` per bad line.
    """
    rows: list[Row] = []
    problems: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = cast("object", json.loads(line))
        except json.JSONDecodeError as exc:
            problems.append(f"{path.name} line {number}: invalid JSON ({exc.msg})")
            continue
        if isinstance(row, dict):
            rows.append(cast("Row", row))
        else:
            problems.append(f"{path.name} line {number}: row must be a JSON object")
    return rows, problems


def _text(row: Row, key: str) -> str:
    value = row.get(key)
    return value if isinstance(value, str) else ""


def _objects(row: Row, key: str) -> list[Row]:
    value = row.get(key)
    if not isinstance(value, list):
        return []
    return [cast("Row", item) for item in cast("list[object]", value) if isinstance(item, dict)]


def _strings(row: Row, key: str) -> list[str]:
    value = row.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in cast("list[object]", value) if isinstance(item, str)]


def _count(row: Row, key: str) -> int | None:
    value = row.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _shape_findings(rid: str, row: Row) -> list[str]:
    """Fields, types, and closed sets that one row must satisfy on its own."""
    findings: list[str] = []
    if row.get("schema") != 1:
        findings.append(f"{rid}: schema must be 1")
    findings.extend(
        f"{rid}: {key} must be a non-empty string"
        for key in _REQUIRED_TEXT
        if not _text(row, key).strip()
    )
    findings.extend(
        f"{rid}: {key} must be a string, empty when there is none"
        for key in _LINK_FIELDS
        if not isinstance(row.get(key), str)
    )
    for key, allowed in (
        ("kind", KINDS),
        ("order", ORDERS),
        ("standing", STANDINGS),
        ("provenance", PROVENANCES),
    ):
        if row.get(key) not in allowed:
            findings.append(f"{rid}: {key} must be one of {', '.join(sorted(allowed))}")
    for key in ("aliases", "open"):
        value = row.get(key)
        if not isinstance(value, list) or len(_strings(row, key)) != len(
            cast("list[object]", value)
        ):
            findings.append(f"{rid}: {key} must be a list of strings")
    if _text(row, "year").strip().casefold() == "unknown" and not _strings(row, "open"):
        findings.append(f"{rid}: year unknown; name the unread source in open")
    stated = row.get("stated_count")
    if stated is not None and (_count(row, "stated_count") is None or cast("int", stated) < 1):
        findings.append(f"{rid}: stated_count must be a positive integer or null")
    return findings


def _member_findings(rid: str, row: Row) -> list[str]:
    """Members: enough of them, labelled once each, with substance for axioms."""
    findings: list[str] = []
    members = _objects(row, "members")
    if len(members) < _MIN_MEMBERS:
        findings.append(f"{rid}: a concept set needs at least {_MIN_MEMBERS} members")
    keys = [normalize(_text(member, "label")) for member in members]
    if any(not key for key in keys):
        findings.append(f"{rid}: every member needs a label")
    repeated = sorted({key for key in keys if key and keys.count(key) > 1})
    findings.extend(f"{rid}: member {key!r} repeats" for key in repeated)
    if row.get("kind") == "axiom":
        findings.extend(
            f"{rid}: axiom member {_text(member, 'label')!r} needs its substance"
            for member in members
            if not _text(member, "substance").strip()
        )
    stated = _count(row, "stated_count")
    has_open = bool(_strings(row, "open"))
    if stated is not None and stated > len(members) and not has_open:
        findings.append(
            f"{rid}: stated count {stated}, {len(members)} members recovered; name the gap in open"
        )
    if stated is not None and stated < len(members):
        findings.append(
            f"{rid}: {len(members)} members exceed the stated count {stated}; "
            "record the other enumeration as a variant"
        )
    if row.get("kind") == "cross-classification" and len(_strings(row, "axes")) < _MIN_MEMBERS:
        findings.append(f"{rid}: a cross-classification names at least two axes")
    return findings


def _cite_findings(rid: str, row: Row, known: set[str]) -> list[str]:
    """Cites: each names a recorded source, a locator, a quote, and a role."""
    findings: list[str] = []
    cites = _objects(row, "cites")
    if not cites:
        findings.append(f"{rid}: needs at least one cite")
    for number, cite in enumerate(cites, start=1):
        label = f"{rid} cite {number}"
        if _text(cite, "source") not in known:
            findings.append(f"{label}: source is not a row of sources.jsonl")
        findings.extend(
            f"{label}: {key} is empty"
            for key in ("locator", "quote")
            if not _text(cite, key).strip()
        )
        if cite.get("role") not in ROLES:
            findings.append(f"{label}: role must be primary or secondary")
    primary = any(cite.get("role") == "primary" for cite in cites)
    if cites and not primary and not _strings(row, "open"):
        findings.append(f"{rid}: no primary cite; name the gap in open")
    return findings


def _follows(start: str, by_id: dict[str, Row], key: str) -> bool:
    """Whether following *key* links from *start* returns to *start*."""
    seen = {start}
    current = _text(by_id[start], key)
    while current in by_id:
        if current in seen:
            return current == start
        seen.add(current)
        current = _text(by_id[current], key)
    return False


def _link_findings(by_id: dict[str, Row]) -> list[str]:
    """Parent, variant, and axis links resolve, and parents and variants never loop."""
    findings: list[str] = []
    for rid, row in by_id.items():
        for key in _LINK_FIELDS:
            target = _text(row, key)
            if target and (target == rid or target not in by_id):
                findings.append(f"{rid}: {key} {target!r} is not another set's id")
            elif target and _follows(rid, by_id, key):
                findings.append(f"{rid}: {key} links loop back to it")
        findings.extend(
            f"{rid}: axis {axis!r} is not another set's id"
            for axis in _strings(row, "axes")
            if axis == rid or axis not in by_id
        )
    return findings


def check_sets(sets: list[Row], sources: list[Row]) -> list[str]:
    """List every finding that keeps ``sets.jsonl`` from passing its gate.

    >>> src = [{"source": "book-1"}]
    >>> row = {"schema": 1, "id": "needs", "name": "Hierarchy of needs",
    ...        "aliases": [], "parent": "", "variant_of": "", "framework": "Maslow",
    ...        "author": "A. Maslow", "year": "1943", "purpose": "rank motives",
    ...        "member_noun": "needs", "stated_count": 3, "kind": "level",
    ...        "order": "rank", "standing": "contested", "provenance": "original",
    ...        "members": [{"label": "a"}, {"label": "b"}], "open": [],
    ...        "cites": [{"source": "book-1", "locator": "p. 372", "quote": "q",
    ...                   "role": "primary"}]}
    >>> check_sets([row], src)
    ['needs: stated count 3, 2 members recovered; name the gap in open']
    """
    known = {_text(row, "source") for row in sources}
    by_id: dict[str, Row] = {}
    findings: list[str] = []
    for number, row in enumerate(sets, start=1):
        rid = row.get("id")
        if not isinstance(rid, str) or not _ID.match(rid):
            findings.append(f"row {number}: id must be a lowercase hyphenated slug")
            continue
        if rid in by_id:
            findings.append(f"{rid}: id repeats")
            continue
        by_id[rid] = row
        findings.extend(_shape_findings(rid, row))
        findings.extend(_member_findings(rid, row))
        findings.extend(_cite_findings(rid, row, known))
    findings.extend(_link_findings(by_id))
    return findings


def _member_keys(row: Row) -> set[str]:
    keys: set[str] = set()
    for member in _objects(row, "members"):
        keys.add(normalize(_text(member, "label")))
        keys.update(normalize(alias) for alias in _strings(member, "aliases"))
    keys.discard("")
    return keys


def _catalog_members(entry: Row) -> list[str]:
    """List a catalog entry's members, given as strings or ``{"label": ...}`` objects."""
    labels = _strings(entry, "members")
    labels.extend(_text(member, "label") for member in _objects(entry, "members"))
    return [label for label in labels if label.strip()]


def _lineage(rid: str, by_id: dict[str, Row]) -> str:
    """Return the first set reached by following ``variant_of`` links from *rid*."""
    seen = {rid}
    current = rid
    while (target := _text(by_id[current], "variant_of")) in by_id and target not in seen:
        seen.add(target)
        current = target
    return current


def _matches(entry: Row, by_id: dict[str, Row]) -> tuple[list[str], list[str]]:
    """Set ids an entry codifies, and ids it names that no set has.

    An explicit ``matches`` list is taken as written. Without one, an entry
    matches the sets whose name or alias normalizes to the entry's text.
    """
    if isinstance(entry.get("matches"), list):
        named = _strings(entry, "matches")
        return [rid for rid in named if rid in by_id], [rid for rid in named if rid not in by_id]
    key = normalize(_text(entry, "entry"))
    found = [
        rid
        for rid, row in by_id.items()
        if key and key in {normalize(_text(row, "name")), *map(normalize, _strings(row, "aliases"))}
    ]
    return found, []


def diff_catalog(sets: list[Row], catalog: list[Row]) -> dict[str, list[Row]]:
    """Compare a catalog with the sets a study found.

    Categories: ``uncodified`` sourced sets no entry codifies;
    ``loose_members`` entries that are members of an uncodified set;
    ``partial`` entries whose stated count exceeds what they show, that lack
    members their set names, or that show members it does not name;
    ``unsourced_groupings`` entries that group members with no source behind
    the grouping; ``merged_versions`` entries that fold versions of one set
    together; ``unknown_matches`` entries naming a set id the study lacks.

    >>> sets = [{"id": "e", "name": "Basic emotions", "provenance": "original",
    ...          "members": [{"label": "Anger"}, {"label": "Fear"}]}]
    >>> diff_catalog(sets, [{"entry": "Anger"}])["loose_members"]
    [{'set': 'e', 'name': 'Basic emotions', 'entries': ['Anger']}]
    """
    by_id = {_text(row, "id"): row for row in sets if _text(row, "id")}
    report: dict[str, list[Row]] = {
        "uncodified": [],
        "loose_members": [],
        "partial": [],
        "unsourced_groupings": [],
        "merged_versions": [],
        "unknown_matches": [],
    }
    matched: dict[int, list[str]] = {}
    for number, entry in enumerate(catalog):
        found, unknown = _matches(entry, by_id)
        matched[number] = found
        if unknown:
            report["unknown_matches"].append({"entry": _text(entry, "entry"), "ids": unknown})
    codified = {rid for ids in matched.values() for rid in ids}
    uncodified = [
        rid
        for rid, row in by_id.items()
        if rid not in codified and row.get("provenance") != "editorial"
    ]
    report["uncodified"] = [
        {
            "set": rid,
            "name": _text(by_id[rid], "name"),
            "framework": _text(by_id[rid], "framework"),
            "members": len(_objects(by_id[rid], "members")),
        }
        for rid in uncodified
    ]
    loose: dict[str, list[str]] = {}
    for number, entry in enumerate(catalog):
        if matched[number] or _catalog_members(entry):
            continue
        key = normalize(_text(entry, "entry"))
        for rid in uncodified:
            if key and key in _member_keys(by_id[rid]):
                loose.setdefault(rid, []).append(_text(entry, "entry"))
    report["loose_members"] = [
        {"set": rid, "name": _text(by_id[rid], "name"), "entries": entries}
        for rid, entries in loose.items()
    ]
    for number, entry in enumerate(catalog):
        name, shown, ids = _text(entry, "entry"), _catalog_members(entry), matched[number]
        stated = _count(entry, "stated_count")
        shown_keys = {normalize(label) for label in shown}
        missing = {
            rid: [
                _text(member, "label")
                for member in _objects(by_id[rid], "members")
                if normalize(_text(member, "label")) not in shown_keys
                and not shown_keys & {normalize(alias) for alias in _strings(member, "aliases")}
            ]
            for rid in ids
        }
        missing = {rid: labels for rid, labels in missing.items() if labels and shown}
        named = set().union(*(_member_keys(by_id[rid]) for rid in ids))
        extra = [label for label in shown if ids and normalize(label) not in named]
        if (stated is not None and stated > len(shown)) or missing or extra:
            report["partial"].append(
                {
                    "entry": name,
                    "stated": stated,
                    "shown": len(shown),
                    "missing": missing,
                    "extra": extra,
                }
            )
        editorial_only = all(by_id[rid].get("provenance") == "editorial" for rid in ids)
        if len(shown) >= _MIN_MEMBERS and editorial_only and not _text(entry, "source").strip():
            report["unsourced_groupings"].append({"entry": name, "members": shown, "sets": ids})
        lineages: dict[str, list[str]] = {}
        for rid in ids:
            lineages.setdefault(_lineage(rid, by_id), []).append(rid)
        report["merged_versions"].extend(
            {"entry": name, "sets": group} for group in lineages.values() if len(group) > 1
        )
    return report


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_table(sets: list[Row]) -> str:
    r"""Render one Markdown row per set, members in the source's order.

    >>> print(render_table([{"id": "a", "name": "A | B", "members": [{"label": "x"}]}]))
    | Set | Framework | Origin | Kind | Order | Members | Standing | Provenance | Primary cite |
    |---|---|---|---|---|---|---|---|---|
    | A \| B |  |  |  |  | 1: x |  |  | none |
    """
    by_id = {_text(row, "id"): row for row in sets}
    header = ("Set", "Framework", "Origin", "Kind", "Order", "Members", "Standing")
    header += ("Provenance", "Primary cite")
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for row in sets:
        name = _text(row, "name")
        parent = _text(row, "parent")
        if parent in by_id:
            name = f"{name} (in {_text(by_id[parent], 'name')})"
        variant = _text(row, "variant_of")
        if variant in by_id:
            name = f"{name} (version of {_text(by_id[variant], 'name')})"
        members = [_text(member, "label") for member in _objects(row, "members")]
        stated = _count(row, "stated_count")
        count = f"{len(members)} {_text(row, 'member_noun')}".strip()
        if stated is not None and stated != len(members):
            count = f"{count} of {stated} stated"
        primary = next(
            (cite for cite in _objects(row, "cites") if cite.get("role") == "primary"), None
        )
        cite = f"{_text(primary, 'source')}, {_text(primary, 'locator')}" if primary else "none"
        cells = [
            name,
            _text(row, "framework"),
            f"{_text(row, 'author')} {_text(row, 'year')}".strip(),
            _text(row, "kind"),
            _text(row, "order"),
            f"{count}: {'; '.join(members)}",
            _text(row, "standing"),
            _text(row, "provenance"),
            cite,
        ]
        lines.append("| " + " | ".join(_cell(value) for value in cells) + " |")
    return "\n".join(lines)


def _read(study: Path, name: str) -> list[Row] | None:
    """Load ``<study>/<name>``, or print why not and return ``None``."""
    path = study / name
    if not path.is_file():
        print(f"no {name} in {study}", file=sys.stderr)
        return None
    rows, problems = load_rows(path)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return None
    return rows


def main(argv: list[str]) -> int:
    """Run ``check``, ``diff``, or ``table`` against the study named in *argv*."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    commands = parser.add_subparsers(dest="command", required=True)
    for command, text in (
        ("check", "gate sets.jsonl against sources.jsonl"),
        ("diff", "what catalog.jsonl has not codified, as JSON"),
        ("table", "the sets as a Markdown table"),
    ):
        commands.add_parser(command, help=text).add_argument("study", type=Path)
    opts = parser.parse_args(argv)
    study = cast("Path", opts.study)
    sets = _read(study, "sets.jsonl")
    if sets is None:
        return 2
    if opts.command == "table":
        print(render_table(sets))
        return 0
    other = _read(study, "sources.jsonl" if opts.command == "check" else "catalog.jsonl")
    if other is None:
        return 2
    if opts.command == "diff":
        print(json.dumps(diff_catalog(sets, other), indent=2, ensure_ascii=False))
        return 0
    findings = check_sets(sets, other)
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
