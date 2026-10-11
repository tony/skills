#!/usr/bin/env python3
# Vendored from shared/closest_model.py; edit that file, then run 'scripts/marketplace.py portable'.
"""Pick a model from a model list on stdin (`agent --list-models`, `agy models`).

Usage: <model list command> | closest_model.py MODEL
       <model list command> | closest_model.py --newest TEMPLATE
           [--exclude WORD ...] [--emit id|label]
       <model list command> | closest_model.py --match "WORDS" [--emit id|label]

Each line's fields, split on a tab or " - ", are candidates; the first is the
ID and the second the label.

MODEL form: print the listed ID that differs from MODEL only in its version,
preferring the nearest newer version, else the nearest older one.

--newest form: TEMPLATE is an ID with `{v}` for the version and `*` for any
run of word characters, dots and dashes (`gpt-{v}-*high`). Print the match
with the highest version, the first listed on a tie, skipping IDs with an
--exclude word as a dash-separated part. --emit label prints the label
instead of the ID.

--match form: print each listed entry whose line contains every word of WORDS,
case-insensitively, one per line; the caller chooses among several.

Exit status: 0 on a result; 1 when nothing matches; 3 for --newest with no
match, with "not live-listed" on stderr, meaning the tier should run on the
CLI's default model.

>>> pick("gpt-5.4-high", ["gpt-5.5-high - GPT-5.5", "gpt-5.6-sol-high"])
'gpt-5.5-high'
>>> pick("gpt-5.4-mini-medium", ["gpt-5.5-high"]) is None
True
>>> newest("gpt-{v}-*high", ["gpt-5.3-codex-high - A", "gpt-5.6-sol-high - B"])
'gpt-5.6-sol-high'
>>> newest("gemini-{v}-pro-high", ["gemini-3.1-pro-high - Gemini 3.1 Pro (High)"], label=True)
'Gemini 3.1 Pro (High)'
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import cast

VERSION_RE = re.compile(r"\d+(?:[.-]\d+)*")


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.split(r"[.-]", text))


def pick(want: str, lines: list[str]) -> str | None:
    """Return the closest same-family candidate, or None."""
    match = VERSION_RE.search(want)
    if match is None:
        return None
    family = re.compile(
        re.escape(want[: match.start()])
        + f"({VERSION_RE.pattern})"
        + re.escape(want[match.end() :])
    )
    current = _version(match.group())
    found: dict[tuple[int, ...], str] = {}
    for line in lines:
        for field in re.split(r"\t| - ", line):
            hit = family.fullmatch(field.strip())
            if hit and _version(hit.group(1)) != current:
                _ = found.setdefault(_version(hit.group(1)), field.strip())
    newer = [v for v in found if v > current]
    older = [v for v in found if v < current]
    if newer:
        return found[min(newer)]
    if older:
        return found[max(older)]
    return None


def _template_regex(template: str) -> re.Pattern[str]:
    if template.count("{v}") != 1:
        msg = "template needs exactly one {v}"
        raise ValueError(msg)
    parts = re.split(r"(\{v\}|\*)", template)
    sources = {"{v}": f"({VERSION_RE.pattern})", "*": r"[\w.-]*"}
    return re.compile("".join(sources.get(p) or re.escape(p) for p in parts))


def newest(
    template: str,
    lines: list[str],
    exclude: tuple[str, ...] = (),
    *,
    label: bool = False,
) -> str | None:
    """Return the highest-version ID matching TEMPLATE (or its label), or None."""
    regex = _template_regex(template)
    best: tuple[tuple[int, ...], str] | None = None
    for line in lines:
        fields = [f.strip() for f in re.split(r"\t| - ", line, maxsplit=1)]
        hit = regex.fullmatch(fields[0])
        if hit is None or set(fields[0].split("-")) & set(exclude):
            continue
        version = _version(hit.group(1))
        if best is None or version > best[0]:
            best = (version, fields[1] if label and len(fields) > 1 else fields[0])
    return None if best is None else best[1]


def match(words: str, lines: list[str], *, label: bool = False) -> list[str]:
    """Return the entries whose line holds every word, case-insensitively.

    >>> match("3.8 flash", ["g-3.8-flash-high - Gemini 3.8 Flash (High)", "g-3.1-pro - P"])
    ['g-3.8-flash-high']
    """
    needles = words.lower().split()
    found: list[str] = []
    for line in lines:
        fields = [f.strip() for f in re.split(r"\t| - ", line, maxsplit=1)]
        if len(fields) > 1 and needles and all(n in line.lower() for n in needles):
            found.append(fields[1] if label else fields[0])
    return found


def main(argv: list[str] | None = None) -> int:
    """Read the list from stdin and print the pick."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("model", nargs="?")
    _ = parser.add_argument("--newest")
    _ = parser.add_argument("--exclude", action="append", default=[])
    _ = parser.add_argument("--match")
    _ = parser.add_argument("--emit", choices=("id", "label"), default="id")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    model = cast("str | None", args.model)
    template = cast("str | None", args.newest)
    words = cast("str | None", args.match)
    if sum(x is not None for x in (model, template, words)) != 1:
        parser.error("give one of MODEL, --newest TEMPLATE, --match WORDS")
    lines = sys.stdin.read().splitlines()
    label = cast("str", args.emit) == "label"
    if words is not None:
        hits = match(words, lines, label=label)
        _ = sys.stdout.write("".join(f"{hit}\n" for hit in hits))
        return 0 if hits else 1
    if template is not None:
        try:
            choice = newest(template, lines, tuple(cast("list[str]", args.exclude)), label=label)
        except ValueError as exc:
            parser.error(str(exc))
        if choice is None:
            _ = sys.stderr.write("no listed match: not live-listed, use the default model\n")
            return 3
    else:
        choice = pick(cast("str", model), lines)
    if choice is None:
        return 1
    print(choice)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
