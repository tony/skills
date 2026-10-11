#!/usr/bin/env python3
"""Check that a written body reads back from the tracker, word for word.

Usage: compare_body.py WRITTEN FETCHED

WRITTEN is the body file the write command received. FETCHED is the read
command's saved output. In JSON output, each string field and each Jira ADF
document is a candidate, and one must hold exactly the written words, so an
added or dropped line is a mismatch. Plain-text output can only be checked
for the written words appearing unbroken, and the report says so. Markup,
HTML tags and entities are ignored; link targets count as words, since
providers render `[text](url)` as `text (url)`. Exits 0 on a match, 1 with
the first divergence otherwise, and 2 when a file cannot be read.

>>> words('### Hi **there** <a href="https://x.io">link</a>')
['hi', 'there', 'link', 'https', 'x', 'io']
"""

from __future__ import annotations

import difflib
import html
import json
import re
import sys
from pathlib import Path
from typing import cast

ANCHOR_RE = re.compile(r"<a\s[^>]*?href=\"([^\"]*)\"[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>")


def words(text: str) -> list[str]:
    """Lowercased word tokens with markup removed."""
    text = ANCHOR_RE.sub(r"\2 (\1)", html.unescape(text))
    return re.findall(r"\w+", TAG_RE.sub(" ", text).lower())


def _adf_text(node: object) -> str:
    if not isinstance(node, dict):
        return ""
    item = cast("dict[str, object]", node)
    own = item.get("text")
    children = item.get("content")
    parts = [own] if isinstance(own, str) else []
    if isinstance(children, list):
        parts += [_adf_text(child) for child in cast("list[object]", children)]
    return " ".join(parts)


def candidates(fetched: str) -> list[str] | None:
    """Return each JSON string field and ADF document, or None for plain text."""
    try:
        data = cast("object", json.loads(fetched))
    except ValueError:
        return None
    found: list[str] = []
    stack: list[object] = [data]
    while stack:
        node = stack.pop()
        if isinstance(node, str):
            found.append(node)
        elif isinstance(node, dict):
            item = cast("dict[str, object]", node)
            if item.get("type") == "doc":
                found.append(_adf_text(item))
            else:
                stack.extend(item.values())
        elif isinstance(node, list):
            stack.extend(cast("list[object]", node))
    return found


def main(argv: list[str] | None = None) -> int:
    """Compare the two files and report."""
    args = sys.argv[1:] if argv is None else argv
    try:
        written_path, fetched_path = args
    except ValueError:
        _ = sys.stderr.write("usage: compare_body.py WRITTEN FETCHED\n")
        return 2
    try:
        written = Path(written_path).read_text(encoding="utf-8")
        fetched = Path(fetched_path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        _ = sys.stderr.write(f"cannot read: {exc}\n")
        return 2
    want = words(written)
    found = candidates(fetched)
    if found is None:
        pool = [words(fetched)]
        if f" {' '.join(want)} " in f" {' '.join(pool[0])} ":
            print(f"match: {len(want)} words; plain text, so containment only")
            return 0
    else:
        pool = [words(c) for c in found] or [[]]
        if want in pool:
            print(f"match: {len(want)} words")
            return 0
    best = max(pool, key=lambda c: difflib.SequenceMatcher(None, want, c).ratio())
    ops = difflib.SequenceMatcher(None, want, best).get_opcodes()
    _, i1, _, j1, _ = next(op for op in ops if op[0] != "equal")
    print(f"mismatch at word {i1 + 1}")
    print(f"written: {' '.join(want[i1 : i1 + 8])}")
    print(f"fetched: {' '.join(best[j1 : j1 + 8])}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
