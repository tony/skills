#!/usr/bin/env python3
"""Print the listed model that differs from MODEL only in its version.

Usage: <model list command> | closest_model.py MODEL

Reads a model list on stdin (`agent --list-models`, `agy models`); each
line's fields, split on a tab or " - ", are candidates. Prefers the nearest
newer version, else the nearest older one. Exits 1 with no output when no
candidate matches.

>>> pick("gpt-5.4-high", ["gpt-5.5-high - GPT-5.5", "gpt-5.6-sol-high"])
'gpt-5.5-high'
>>> pick("gpt-5.4-mini-medium", ["gpt-5.5-high"]) is None
True
"""

from __future__ import annotations

import re
import sys

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


def main(argv: list[str] | None = None) -> int:
    """Read the list from stdin and print the pick."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        _ = sys.stderr.write("usage: closest_model.py MODEL < model-list\n")
        return 2
    choice = pick(args[0], sys.stdin.read().splitlines())
    if choice is None:
        return 1
    print(choice)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
