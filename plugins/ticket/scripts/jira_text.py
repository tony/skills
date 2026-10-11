#!/usr/bin/env python3
r"""Convert a markdown ticket body to the plain text a Jira description takes.

Usage: jira_text.py FILE

Prints the converted text. Exits 1, printing the reason and no text, when
the body holds an image, a table, or a nested list that plain text would
drop or flatten, and
2 when FILE cannot be read. Rules: a heading becomes its text, bold and
code markers are dropped, a fenced block becomes its lines indented four
spaces, `[text](url)` becomes `text (url)`, list markers stay, and a
`<details>` block becomes its summary line followed by its content.

>>> print(convert("### Steps\n\n1. Run `export`\n2. See [log](https://x.io)"))
Steps
<BLANKLINE>
1. Run export
2. See log (https://x.io)
>>> flattens("- a\n  - b")
'nested list'
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^#{1,6}\s+")
LINK_RE = re.compile(r"!?\[([^\]]*)\]\(([^)\s]+)[^)]*\)")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(")
TABLE_RE = re.compile(r"^\s*\|.*\|\s*$")
NESTED_RE = re.compile(r"^\s{2,}(?:[-*+]|\d+\.)\s")
SUMMARY_RE = re.compile(r"<summary>(.*?)</summary>", re.IGNORECASE)
DETAILS_RE = re.compile(r"</?details>", re.IGNORECASE)


def flattens(text: str) -> str | None:
    """Return what plain text would drop or flatten, outside fences."""
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            if IMAGE_RE.search(line):
                return "image"
            if TABLE_RE.match(line):
                return "table"
            if NESTED_RE.match(line):
                return "nested list"
    return None


def convert(text: str) -> str:
    """Convert markdown to Jira plain text."""
    out: list[str] = []
    in_fence = False
    for raw in text.splitlines():
        if FENCE_RE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            out.append("    " + raw if raw else "")
            continue
        line = DETAILS_RE.sub("", SUMMARY_RE.sub(r"\1", raw))
        if not line.strip() and out and out[-1] == "":
            continue
        line = HEADING_RE.sub("", line)
        line = LINK_RE.sub(r"\1 (\2)", line)
        out.append(line.replace("**", "").replace("`", "").rstrip())
    return "\n".join(out).strip("\n")


def main(argv: list[str] | None = None) -> int:
    """Convert FILE to stdout."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        _ = sys.stderr.write("usage: jira_text.py FILE\n")
        return 2
    try:
        text = Path(args[0]).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        _ = sys.stderr.write(f"cannot read: {exc}\n")
        return 2
    reason = flattens(text)
    if reason:
        print(f"plain text would drop or flatten a {reason}; print the body instead")
        return 1
    print(convert(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
