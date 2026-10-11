#!/usr/bin/env python3
r"""Convert a markdown ticket body to the HTML subset an Asana rich-text field takes.

Usage: asana_html.py FILE

Prints `<body>...</body>`. Asana accepts only a fixed tag set, allows
attributes on `<a>` alone, and rejects anything that is not valid XML. The
script maps paragraphs, headings (`#` to h1, deeper to h2, since Asana has
no h3), bold, italic, strikethrough, inline code, fenced code, flat lists,
block quotes, rules, and links. It exits 1, printing the reason and no
HTML, for what it cannot map: images, raw HTML, tables, nested lists, and a
`<details>` block. It exits 2 when FILE cannot be read.

>>> print(convert("## Plan\n\nRun `x` & **stop**.\n\n- [a](https://x.io?q=1&r=2)"))
<body><h2>Plan</h2>
<p>Run <code>x</code> &amp; <strong>stop</strong>.</p>
<ul><li><a href="https://x.io?q=1&amp;r=2">a</a></li></ul></body>
>>> unmappable("| a | b |")
'table'
"""

from __future__ import annotations

import html
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
ITEM_RE = re.compile(r"^([-*+]|\d+\.)\s+(.*)$")
NESTED_RE = re.compile(r"^\s{2,}(?:[-*+]|\d+\.)\s")
RULE_RE = re.compile(r"^(-{3,}|\*{3,}|_{3,})\s*$")
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
RAW_HTML_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>")
CODE_SPAN_RE = re.compile(r"`[^`]*`")
TABLE_RE = re.compile(r"^\s*\|.*\|\s*$")
INLINE = (
    (re.compile(r"\*\*(.+?)\*\*"), "strong"),
    (re.compile(r"~~(.+?)~~"), "s"),
    (re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])"), "em"),
)


def unmappable(text: str) -> str | None:
    """Return what Asana's tag set cannot carry, outside fenced code."""
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
        elif in_fence:
            continue
        elif IMAGE_RE.search(line):
            return "image"
        elif TABLE_RE.match(line):
            return "table"
        elif NESTED_RE.match(line):
            return "nested list"
        elif RAW_HTML_RE.search(CODE_SPAN_RE.sub("", line)):
            return "raw HTML"
    return None


def inline(text: str) -> str:
    """Convert inline markup, escaping everything else."""
    parts = re.split(r"(`[^`]+`)", text)
    out: list[str] = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(f"<code>{html.escape(part[1:-1], quote=False)}</code>")
            continue
        links: list[str] = []

        def stash(m: re.Match[str], links: list[str] = links) -> str:
            links.append(
                f'<a href="{html.escape(m.group(2))}">{html.escape(m.group(1), quote=False)}</a>'
            )
            return f"\x00{len(links) - 1}\x00"

        escaped = html.escape(LINK_RE.sub(stash, part), quote=False)
        for rx, tag in INLINE:
            escaped = rx.sub(rf"<{tag}>\1</{tag}>", escaped)
        out.append(re.sub(r"\x00(\d+)\x00", lambda m, ls=links: ls[int(m.group(1))], escaped))
    return "".join(out)


def convert(text: str) -> str:
    """Convert markdown to an Asana `<body>` fragment."""
    blocks: list[str] = []
    para: list[str] = []
    items: list[str] = []
    list_tag = ""
    quote: list[str] = []
    code: list[str] | None = None

    def flush() -> None:
        nonlocal para, items, quote
        if para:
            blocks.append(f"<p>{inline(' '.join(para))}</p>")
        if items:
            blocks.append(f"<{list_tag}>{''.join(items)}</{list_tag}>")
        if quote:
            blocks.append(f"<blockquote>{inline(' '.join(quote))}</blockquote>")
        para, items, quote = [], [], []

    for line in text.splitlines():
        if FENCE_RE.match(line):
            if code is None:
                flush()
                code = []
            else:
                blocks.append(f"<pre>{html.escape(chr(10).join(code), quote=False)}</pre>")
                code = None
        elif code is not None:
            code.append(line)
        elif not line.strip():
            flush()
        elif RULE_RE.match(line):
            flush()
            blocks.append("<hr/>")
        elif heading := HEADING_RE.match(line):
            flush()
            tag = "h1" if len(heading.group(1)) == 1 else "h2"
            blocks.append(f"<{tag}>{inline(heading.group(2))}</{tag}>")
        elif item := ITEM_RE.match(line):
            if para or quote:
                flush()
            tag = "ol" if item.group(1)[0].isdigit() else "ul"
            if items and tag != list_tag:
                flush()
            list_tag = tag
            items.append(f"<li>{inline(item.group(2))}</li>")
        elif line.startswith(">"):
            flush()
            quote.append(line.lstrip("> ").strip())
        else:
            if items or quote:
                flush()
            para.append(line.strip())
    flush()
    return "<body>" + "\n".join(blocks) + "</body>"


def main(argv: list[str] | None = None) -> int:
    """Convert FILE to stdout."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        _ = sys.stderr.write("usage: asana_html.py FILE\n")
        return 2
    try:
        text = Path(args[0]).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        _ = sys.stderr.write(f"cannot read: {exc}\n")
        return 2
    reason = unmappable(text)
    if reason:
        print(f"Asana rich text cannot carry a {reason}; print the body instead")
        return 1
    out = convert(text)
    try:
        _ = ET.fromstring(out)  # noqa: S314
    except ET.ParseError as exc:
        print(f"result is not valid XML ({exc}); print the body instead")
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
