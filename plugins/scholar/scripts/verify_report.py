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

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import cast

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


def moved(sources: list[dict[str, object]], current: dict[str, str]) -> dict[str, list[str]]:
    """Compare each source's recorded commit with *current*, once per source."""
    out: dict[str, list[str]] = {"moved": [], "uncheckable": []}
    seen: set[str] = set()
    for row in sources:
        source = str(row.get("source", ""))
        if source in seen:
            continue
        seen.add(source)
        recorded = str(row.get("commit", "")).strip()
        if not recorded:
            out["uncheckable"].append(f"{source}: no commit recorded")
        elif source not in current:
            out["uncheckable"].append(f"{source}: host unreachable")
        elif current[source] != recorded:
            out["moved"].append(f"{source}: {row.get('ref', '')} now {current[source][:7]}")
    return out


def recorded_measurements(text: str) -> list[tuple[str, str]]:
    r"""Return ``(command, recorded output)`` for each console block with a text block after it.

    >>> md = "```console\n$ cmd a\n```\n\n```text\n1 2\n```\n"
    >>> recorded_measurements(md)
    [('cmd a', '1 2')]
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
            first = next((x for x in body if x.startswith("$ ")), None)
            command = first[2:].strip() if first else None
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
            pair = next((p for p in zip(before, after) if p[0] != p[1]), None)
            detail = f"recorded {pair[0]}, now {pair[1]}" if pair else "line count differs"
            out["changed"].append(f"`{command}`: {detail}")
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
    checked = int(cast("int", results.get("checked", 0)))
    stale = [f"{len(lists[k])} {k}" for k in _HERO_ORDER if lists[k]]
    if not checked:
        hero = f"⚠ Nothing checked: {len(lists['uncheckable'])} uncheckable"
    elif stale:
        hero = "⚠ " + ", ".join(stale)
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


def main(argv: list[str]) -> int:
    """Run one subcommand."""
    parser = argparse.ArgumentParser(prog="verify_report.py", allow_abbrev=False)
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("moved", help="compare recorded commits with current ones")
    _ = one.add_argument("sources")
    _ = one.add_argument("current")
    two = sub.add_parser("changed", help="diff recorded measurements against fresh output")
    _ = two.add_argument("metrics")
    _ = two.add_argument("fresh")
    three = sub.add_parser("report", help="print the verify report from results JSON")
    _ = three.add_argument("results")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    command = cast("str", args.command)
    try:
        if command == "moved":
            data = moved(
                _sources(cast("str", args.sources)),
                cast("dict[str, str]", _json(cast("str", args.current))),
            )
            print(json.dumps(data))
        elif command == "changed":
            text = Path(cast("str", args.metrics)).read_text(encoding="utf-8")
            print(json.dumps(changed(text, cast("dict[str, str]", _json(cast("str", args.fresh))))))
        else:
            print(report(cast("dict[str, object]", _json(cast("str", args.results)))))
    except (OSError, ValueError) as exc:
        print(f"verify_report.py: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
