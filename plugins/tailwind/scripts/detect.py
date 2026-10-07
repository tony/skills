#!/usr/bin/env python3
"""Find candidate Tailwind spacing anti-patterns in template files.

Usage: detect.py PATTERN PATH [PATH ...]

PATTERN is one of ``margin``, ``gap``, ``width``, ``interactive``,
``wrapper``, ``space-gap``, ``space``. Each hit prints ``path:line:text``.
The patterns are candidate finders: every hit needs a read in context.

Exit codes: 0 hits found, 1 no hits, 2 usage error.
"""

# pyright: reportUnusedCallResult=false

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

EXTENSIONS = (
    ".tsx",
    ".jsx",
    ".vue",
    ".svelte",
    ".astro",
    ".html",
    ".erb",
    ".blade.php",
)
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".nuxt"}
MIN_ARGS = 3

QUOTES = "\"'`"
LEAD = r"(?:^|[\sQQ:])"
GAP = r"gap(?:-[xy])?-[0-9\[]"
SPACE = r"space-[xy]-[0-9\[]"
BEFORE = r"[QQ](?:[^QQ]*\s)?"

TAG_OPEN = r"<(?:a|button|Button|Link|NavLink|[A-Z]\w*(?:Button|Link))\s"
TAG_ATTR = r"(?:[^>]|=>)*?(?:class|className)=(?:\"[^\"]*\"|'[^']*'|\{[^}]*\})"
DIV_OPEN = r"<div\s(?:[^>]|=>)*?(?:class|className)=\{?(?:\w+\()?[QQ]"
FLEX_CENTER = r"(?:flex\s(?:[^QQ]*\s)?items-center|items-center\s(?:[^QQ]*\s)?flex)"
DIV_CLASS = r"(?:[^QQ]*\s)?" + FLEX_CENTER + r"(?:\s[^QQ]*)?[QQ]"


def _rx(template: str) -> re.Pattern[str]:
    """Compile ``template`` with ``QQ`` replaced by the three quote characters."""
    return re.compile(template.replace("QQ", QUOTES))


PATTERNS: dict[str, re.Pattern[str]] = {
    "margin": _rx(LEAD + r"-?m[xesrl]-[0-9\[]"),
    "gap": _rx(LEAD + GAP),
    "width": _rx(LEAD + r"w-[0-9\[]"),
    "interactive": _rx(TAG_OPEN + TAG_ATTR),
    "wrapper": _rx(DIV_OPEN + DIV_CLASS),
    "space-gap": _rx(BEFORE + GAP + r"[^QQ]*\s" + SPACE + "|" + BEFORE + SPACE + r"[^QQ]*\s" + GAP),
    "space": _rx(LEAD + SPACE),
}
LEADING_LEAD = {"margin", "gap", "width", "space"}


def find(pattern: str, text: str) -> list[tuple[int, str]]:
    """Return ``(line, first line of match)`` for each hit of ``pattern``.

    >>> find("margin", '<a className="px-2 me-4">')
    [(1, 'me-4')]
    """
    hits: list[tuple[int, str]] = []
    for m in PATTERNS[pattern].finditer(text):
        start = m.start()
        if pattern in LEADING_LEAD and m.group(0)[0] in "\n\t " + QUOTES + ":":
            start += 1
        line = text.count("\n", 0, start) + 1
        hits.append((line, text[start : m.end()].splitlines()[0]))
    return hits


def iter_files(paths: list[str]) -> Iterator[Path]:
    """Yield template files under each path; a file path is taken as given."""
    for raw in paths:
        p = Path(raw)
        if p.is_file():
            yield p
            continue
        for f in sorted(p.rglob("*")):
            if f.is_file() and f.name.endswith(EXTENSIONS) and not SKIP_DIRS.intersection(f.parts):
                yield f


def main(argv: list[str]) -> int:
    """Print hits for ``argv[1]`` in the paths ``argv[2:]``."""
    if len(argv) < MIN_ARGS or argv[1] not in PATTERNS:
        sys.stderr.write(__doc__ or "")
        return 2
    found = False
    for f in iter_files(argv[2:]):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line, snippet in find(argv[1], text):
            found = True
            sys.stdout.write(f"{f}:{line}:{snippet}\n")
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
