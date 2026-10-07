#!/usr/bin/env python3
"""Find candidate Tailwind spacing anti-patterns in template files.

Usage: detect.py PATTERN PATH [PATH ...]

PATTERN is one of ``margin``, ``vmargin``, ``margin-in-gap``, ``gap``,
``width``, ``interactive``, ``wrapper``, ``space-gap``, ``space``. Each hit
prints ``path:line:text``. The patterns are candidate finders: every hit
needs a read in context.

``margin`` lists horizontal margins. ``vmargin`` lists ``mt-``, ``mb-``, and
``my-`` margins in files that use ``flex-col`` or ``grid``. ``margin-in-gap``
lists both kinds of margin in files that also set ``gap-*``, and stops after
50 hits.

Exit codes: 0 hits found, 1 no hits, 2 usage error or a path that does not exist.
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
LEAD = r"(?<![^\sQQ:!])"
STEP = r"(?:[0-9\[]|px\b)"
GAP = r"gap(?:-[xy])?-" + STEP
SPACE = r"space-[xy]-" + STEP
MAX_SNIPPET = 200
MAX_HITS = 50
CAPPED = {"margin-in-gap"}


def _rx(template: str) -> re.Pattern[str]:
    """Compile ``template`` with ``QQ`` replaced by the three quote characters."""
    return re.compile(template.replace("QQ", QUOTES))


SIMPLE: dict[str, re.Pattern[str]] = {
    "margin": _rx(LEAD + r"-?m[xesrl]-" + STEP),
    "gap": _rx(LEAD + GAP),
    "width": _rx(LEAD + r"w-[0-9\[]"),
    "space": _rx(LEAD + SPACE),
}
VMARGIN = _rx(LEAD + r"-?m[ytb]-" + STEP)
COLUMN = _rx(LEAD + r"(?:flex-col(?:-reverse)?|inline-grid|grid)(?![\w-])")
PATTERNS = (*SIMPLE, "vmargin", "margin-in-gap", "interactive", "wrapper", "space-gap")

BUTTON_OPEN = re.compile(r"<(?:a|button|Button|Link|NavLink|[A-Z]\w*(?:Button|Link))\s")
DIV_OPEN = re.compile(r"<div\s")
ATTR_VALUE = re.compile(r"(?:class|className)=(?:\"[^\"]*\"|'[^']*'|\{[^}]{0,2000}\})")
CLASS_START = _rx(r"(?:class|className)=\{?(?:\w+\()?[QQ]")
STRING_END = _rx(r"[^QQ]*[QQ]")
SEGMENT = _rx(r"[QQ][^QQ]*")
GAP_TOKEN = re.compile(GAP)
SPACE_TOKEN = re.compile(SPACE)


def _tag_end(text: str, pos: int) -> int:
    """Return the index of the ``>`` closing the tag body at ``pos``; ``=>`` does not close."""
    while True:
        j = text.find(">", pos)
        if j < 0:
            return len(text)
        if text[j - 1] == "=":
            pos = j + 1
            continue
        return j


def _tags(text: str, opener: re.Pattern[str]) -> Iterator[tuple[int, int, int]]:
    """Yield ``(start, body_start, body_end)`` per tag, skipping openers inside a prior tag."""
    end = -1
    for m in opener.finditer(text):
        if m.start() < end:
            continue
        end = _tag_end(text, m.end())
        yield m.start(), m.end(), end


def _scan(pattern: str, text: str) -> Iterator[tuple[int, int]]:
    """Yield ``(start, end)`` of each hit; every step is linear in ``text``."""
    if pattern in SIMPLE:
        for m in SIMPLE[pattern].finditer(text):
            yield m.start(), m.end()
    elif pattern == "vmargin":
        if COLUMN.search(text):
            for m in VMARGIN.finditer(text):
                yield m.start(), m.end()
    elif pattern == "margin-in-gap":
        if SIMPLE["gap"].search(text):
            hits = [m.span() for m in SIMPLE["margin"].finditer(text)]
            if COLUMN.search(text):
                hits += [m.span() for m in VMARGIN.finditer(text)]
            yield from sorted(hits)
    elif pattern == "interactive":
        for start, body, end in _tags(text, BUTTON_OPEN):
            attr = ATTR_VALUE.search(text, body, end)
            if attr:
                yield start, attr.end()
    elif pattern == "wrapper":
        for start, body, end in _tags(text, DIV_OPEN):
            for attr in CLASS_START.finditer(text, body, end):
                close = STRING_END.match(text, attr.end())
                if close and {"flex", "items-center"} <= set(
                    text[attr.end() : close.end() - 1].split()
                ):
                    yield start, close.end()
                    break
    else:
        for m in SEGMENT.finditer(text):
            tokens = m.group()[1:].split()
            if any(GAP_TOKEN.match(t) for t in tokens) and any(
                SPACE_TOKEN.match(t) for t in tokens
            ):
                yield m.start(), m.end()


def find(pattern: str, text: str) -> list[tuple[int, str]]:
    """Return ``(line, first line of match)`` for each hit of ``pattern``.

    >>> find("margin", '<a className="px-2 me-4">')
    [(1, 'me-4')]
    """
    return [
        (text.count("\n", 0, start) + 1, text[start:end].splitlines()[0][:MAX_SNIPPET])
        for start, end in _scan(pattern, text)
    ]


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
    missing = [p for p in argv[2:] if not Path(p).exists()]
    if missing:
        sys.stderr.write(f"detect.py: no such path: {', '.join(missing)}\n")
        return 2
    found = False
    count = 0
    for f in iter_files(argv[2:]):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line, snippet in find(argv[1], text):
            if argv[1] in CAPPED and count == MAX_HITS:
                sys.stderr.write(f"detect.py: stopped at {MAX_HITS} hits; narrow the path\n")
                return 0
            found = True
            count += 1
            sys.stdout.write(f"{f}:{line}:{snippet}\n")
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
