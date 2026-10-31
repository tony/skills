#!/usr/bin/env python3
r"""Mechanical parts of scholar's verify: ref comparison, metrics diff, report.

Network fetches and the judgment of an Uncheckable cause stay with the skill;
this script only compares what they produced. Standard library only. A refusal
prints one line to stderr and exits 2.

Examples
--------
Moved refs compare the recorded commit with the current one, once per source:

>>> rows = [{"source": "o/r", "ref": "v1", "commit": "a" * 40},
...         {"source": "o/r", "ref": "v1", "commit": "a" * 40}]
>>> moved(rows, {"o/r": "b" * 40})["moved"]
['o/r: v1 now bbbbbbb']

A failing report starts with the counts of the stale categories:

>>> report({"checked": 3, "misquoted": ["t"], "moved": ["o/r"]}).splitlines()[0]
'⚠ 1 misquoted, 1 moved'
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import cast

from term_metrics import parse_locator

_FENCE = re.compile(r"^```(\w*)\s*$")
_IDENTITY = ("analyzer-sha256:", "analyzer-version:")
_BUCKETS = (
    ("Misquoted: ", "misquoted"),
    ("Vanished: ", "vanished"),
    ("Uncheckable: ", "uncheckable"),
)
_SECTIONS = (
    ("Moved", "moved"),
    ("Vanished", "vanished"),
    ("Misquoted", "misquoted"),
    ("Changed", "changed"),
    ("Uncheckable", "uncheckable"),
)
_HERO_ORDER = ("misquoted", "vanished", "moved", "changed")


def moved(sources: list[dict[str, object]], current: dict[str, str | None]) -> dict[str, list[str]]:
    """Compare each source's recorded commit with *current*, once per source.

    A source absent from *current* was never looked up ("no current SHA
    supplied"); one mapped to ``None`` was looked up and failed ("host
    unreachable").
    """
    out: dict[str, list[str]] = {"moved": [], "uncheckable": []}
    seen: set[str] = set()
    for row in sources:
        source = str(row.get("source", ""))
        if source in seen:
            continue
        seen.add(source)
        recorded = str(row.get("commit", "")).strip()
        sha = current.get(source)
        if not recorded:
            out["uncheckable"].append(f"{source}: no commit recorded")
        elif source not in current:
            out["uncheckable"].append(f"{source}: {_CAUSES[2]}")
        elif sha is None:
            out["uncheckable"].append(f"{source}: {_CAUSES[1]}")
        elif sha != recorded:
            out["moved"].append(f"{source}: {row.get('ref', '')} now {sha[:7]}")
    return out


_CAUSES = ("no clone on disk", "host unreachable", "no current SHA supplied")
_CAUSE_LINE = re.compile(r"^(.*): (" + "|".join(_CAUSES) + r")$")
_SAFE = re.compile(r"^[A-Za-z0-9._/-]+$")
_HEX = re.compile(r"^[0-9a-f]{7,40}$")


def _git(clone: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", "-C", clone, *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


def _safe(value: str) -> bool:
    parts = value.split("/")
    return (
        bool(_SAFE.match(value)) and not value.startswith("-") and not {"", ".", ".."} & set(parts)
    )


def _check_source(
    source: str,
    row: dict[str, object] | None,
    clone: str,
    terms: list[dict[str, object]],
    out: dict[str, list[str]],
) -> None:
    ref = str(row.get("ref", "")) if row else ""
    commit = str(row.get("commit", "")) if row else ""
    if not (_safe(ref) and _HEX.match(commit)):
        out["uncheckable"].append(f"{source}: no usable ref and commit")
        return
    done = _git(clone, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if done.returncode != 0:
        out["vanished"].append(f"{source}: ref {ref} is gone")
    elif not done.stdout.strip().startswith(commit):
        out["moved"].append(f"{source}: {ref} now {done.stdout.strip()[:7]}")
    if _git(clone, "cat-file", "-e", f"{commit}^{{commit}}").returncode != 0:
        out["uncheckable"].append(f"{source}: commit not in the clone")
        return
    for term in terms:
        for cite in cast("list[dict[str, object]]", term.get("cites", [])):
            parsed = parse_locator(str(cite.get("locator", "")))
            if cite.get("source") != source or parsed is None:
                continue
            if _git(clone, "cat-file", "-e", f"{commit}:{parsed[0]}").returncode != 0:
                label = f"{term.get('term', '')} ({cite.get('locator', '')})"
                out["vanished"].append(f"{label}: {parsed[0]} is not in the commit")


def local(
    sources: list[dict[str, object]],
    terms: list[dict[str, object]],
    clones: dict[str, str],
) -> dict[str, list[str]]:
    """Check sources that have a clone on disk, offline.

    Moved: the recorded ref now resolves to another commit. Vanished: the ref
    no longer resolves, or a cited file is not in the recorded commit.
    """
    out: dict[str, list[str]] = {"moved": [], "vanished": [], "uncheckable": []}
    rows = {str(r.get("source", "")): r for r in reversed(sources)}
    for source, clone in clones.items():
        _check_source(source, rows.get(source), clone, terms, out)
    for source, row in rows.items():
        github = source.startswith("https://github.com/")
        if not github and str(row.get("commit", "")).strip() and source not in clones:
            out["uncheckable"].append(f"{source}: {_CAUSES[0]}")
    return out


def recorded_measurements(text: str) -> list[tuple[str, str]]:
    r"""Return ``(command, recorded output)`` for each console block with a text block after it.

    >>> md = "```console\n$ cmd a\n```\n\n```text\n1 2\n```\n"
    >>> recorded_measurements(md)
    [('cmd a', '1 2')]

    A command that continues over several lines is keyed by its whole text:

    >>> md = "```console\n$ a \\\\\n    && b\n```\n```text\n1\n```\n"
    >>> recorded_measurements(md)[0][0]
    'a \\\\\n    && b'
    """
    out: list[tuple[str, str]] = []
    lines = text.splitlines()
    i, command = 0, None
    while i < len(lines):
        match = _FENCE.match(lines[i])
        if not match:
            i += 1
            continue
        end = next((j for j in range(i + 1, len(lines)) if lines[j].startswith("```")), len(lines))
        body = lines[i + 1 : end]
        if match.group(1) == "console":
            text = "\n".join(line.rstrip() for line in body).strip()
            command = text[2:].strip() if text.startswith("$ ") else None
        elif command is not None:
            out.append((command, "\n".join(body).strip()))
            command = None
        i = end + 1
    return out


def _significant(output: str) -> list[str]:
    return [
        " ".join(line.split())
        for line in output.splitlines()
        if line.strip() and not line.strip().startswith(_IDENTITY)
    ]


def changed(metrics: str, fresh: dict[str, str]) -> dict[str, list[str]]:
    """Classify each recorded measurement as unchanged, Changed, or not run."""
    out: dict[str, list[str]] = {"changed": [], "uncheckable": []}
    for command, recorded in recorded_measurements(metrics):
        if command not in fresh:
            out["uncheckable"].append(f"Metrics command `{command}`: not run, no confirmation")
            continue
        before, after = _significant(recorded), _significant(fresh[command])
        if before != after:
            pair = next((p for p in zip(before, after, strict=False) if p[0] != p[1]), None)
            detail = f"recorded {pair[0]}, now {pair[1]}" if pair else "line count differs"
            out["changed"].append(f"`{command}`: {detail}")
    return out


def _one_cause_per_source(items: list[str]) -> list[str]:
    """Keep the most specific cause for a source named by more than one entry.

    >>> _one_cause_per_source(["s: no current SHA supplied", "s: no clone on disk"])
    ['s: no clone on disk']
    """
    best: dict[str, int] = {}
    for item in items:
        match = _CAUSE_LINE.match(item)
        if match:
            rank = _CAUSES.index(match.group(2))
            best[match.group(1)] = min(rank, best.get(match.group(1), rank))
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        match = _CAUSE_LINE.match(item)
        if not match:
            out.append(item)
        elif match.group(1) not in seen:
            seen.add(match.group(1))
            out.append(f"{match.group(1)}: {_CAUSES[best[match.group(1)]]}")
    return out


def report(results: dict[str, object]) -> str:
    """Assemble the hero and the five verify sections from *results*."""
    lists: dict[str, list[str]] = {
        key: [str(x) for x in cast("list[object]", results.get(key, []))] for _, key in _SECTIONS
    }
    for line in cast("list[object]", results.get("analyzer", [])):
        for prefix, key in _BUCKETS:
            if str(line).startswith(prefix):
                lists[key].append(str(line)[len(prefix) :])
    lists["uncheckable"] = _one_cause_per_source(lists["uncheckable"])
    checked = int(cast("int", results.get("checked", 0)))
    stale = [f"{len(lists[k])} {k}" for k in _HERO_ORDER if lists[k]]
    if stale:
        hero = "⚠ " + ", ".join(stale)
    elif not checked:
        hero = f"⚠ Nothing checked: {len(lists['uncheckable'])} uncheckable"
    else:
        hero = f"✓ {checked} citations checked, none stale"
    parts = [hero]
    for title, key in _SECTIONS:
        items = [f"- {item}" for item in lists[key]] or ["None."]
        parts.extend(["", f"## {title}", "", *items])
    return "\n".join(parts)


def _json(path: str) -> object:
    return cast("object", json.loads(Path(path).read_text(encoding="utf-8")))


def _sources(path: str) -> list[dict[str, object]]:
    rows = [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
    return cast("list[dict[str, object]]", rows)


def _refuse(message: str) -> int:
    print(f"verify_report.py: {message}", file=sys.stderr)
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="verify_report.py", allow_abbrev=False)
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("moved", help="compare recorded commits with current ones")
    _ = one.add_argument("sources")
    _ = one.add_argument("current")
    two = sub.add_parser("changed", help="diff recorded measurements against fresh output")
    _ = two.add_argument("metrics")
    _ = two.add_argument("fresh")
    loc = sub.add_parser("local", help="check sources that have a clone on disk")
    _ = loc.add_argument("study")
    _ = loc.add_argument("--clone", action="append", default=[], metavar="SOURCE=CLONE")
    three = sub.add_parser("report", help="print the verify report from results JSON")
    _ = three.add_argument("results")
    return parser


def _run(args: argparse.Namespace) -> int:
    command = cast("str", args.command)
    if command == "moved":
        current = cast("dict[str, object]", _json(cast("str", args.current)))
        shas: dict[str, str | None] = {}
        for key, value in current.items():
            if value is not None and not isinstance(value, str):
                return _refuse("current SHAs must be strings or null")
            shas[key] = value
        data = moved(_sources(cast("str", args.sources)), shas)
        print(json.dumps(data))
    elif command == "local":
        study = cast("str", args.study)
        pairs = [c.partition("=") for c in cast("list[str]", args.clone)]
        clones = {a: b for a, sep, b in pairs if sep and a}
        sources = _sources(f"{study}/sources.jsonl")
        print(json.dumps(local(sources, _sources(f"{study}/terms.jsonl"), clones)))
    elif command == "changed":
        text = Path(cast("str", args.metrics)).read_text(encoding="utf-8")
        fresh = cast("dict[str, str]", _json(cast("str", args.fresh)))
        print(json.dumps(changed(text, fresh)))
    else:
        print(report(cast("dict[str, object]", _json(cast("str", args.results)))))
    return 0


def main(argv: list[str]) -> int:
    """Run one subcommand."""
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    try:
        return _run(args)
    except (OSError, ValueError) as exc:
        return _refuse(str(exc))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
