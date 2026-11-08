#!/usr/bin/env python3
"""Check that a written body reads back as the same words, ignoring case and punctuation.

Usage: compare_body.py WRITTEN FETCHED [--title TITLE]
       compare_body.py --same BEFORE AFTER [--field KEY]
       compare_body.py --exact WRITTEN FETCHED --field KEY [--title TITLE]

WRITTEN is the body file the write command received. FETCHED is the read
command's saved output. In JSON output, each string field and each Jira ADF
document is a candidate, and one must hold exactly the written words, so an
added or dropped line is a mismatch. Plain-text output can only be checked
for the written words appearing unbroken, and the report says so. Markup,
HTML tags and entities are ignored; link targets count as words, since
providers render `[text](url)` as `text (url)`. Exits 0 on a match, 1 with
the first divergence otherwise, and 2 when a file cannot be read. With
--title, the title must also read back: in JSON output one string field
holds exactly its words, and in plain text they appear unbroken.

With --same, two fetches of one item must hold identical content, so an
edit by someone else shows even when it changes only a link or punctuation:
the values at the `/`-separated key path KEY of two JSON files compare exactly, and without
JSON or KEY the whole files compare with whitespace collapsed.

With --exact, the written text must equal the string at KEY in FETCHED,
whitespace collapsed but case and punctuation kept. Use it where the
provider stores and returns markdown; the default mode compares words,
case-insensitively, for providers that convert on write.

>>> words('### Hi **there** <a href="https://x.io">link</a>')
['hi', 'there', 'link', 'https', 'x', 'io']
"""

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
    return [str(word) for word in re.findall(r"\w+", TAG_RE.sub(" ", text).lower())]


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


def title_matches(title: str, pool: list[list[str]], *, plain: bool) -> bool:
    """Whether the title's words read back as a whole field or, for plain text, unbroken."""
    want = words(title)
    if plain:
        return f" {' '.join(want)} " in f" {' '.join(pool[0])} "
    return want in pool


def report(want: list[str], title: str | None, pool: list[list[str]], *, plain: bool) -> int:
    """Print the match line, or the title mismatch."""
    if title is not None and not title_matches(title, pool, plain=plain):
        print(f"title mismatch: written {title!r}")
        return 1
    suffix = "; plain text, so containment only" if plain else ""
    print(f"match: {len(want)} words{suffix}")
    return 0


def _values(data: object, path: str) -> list[object]:
    """Return the value at a `/`-separated key path from the root, ignoring case."""
    node = data
    for part in path.split("/"):
        if not isinstance(node, dict):
            return []
        match = [v for k, v in cast("dict[str, object]", node).items() if k.lower() == part.lower()]
        if not match:
            return []
        node = match[0]
    return [node]


def _canon(text: str, key: str | None) -> str:
    """Return a comparable form: the exact field value, or collapsed text."""
    if key is not None:
        try:
            values = _values(cast("object", json.loads(text)), key)
        except ValueError:
            values = []
        if values:
            return json.dumps(values, sort_keys=True)
    return " ".join(text.split())


def same(before: str, after: str, key: str | None) -> int:
    """Report whether two fetches hold identical content."""
    if _canon(before, key) == _canon(after, key):
        print("same")
        return 0
    print("changed")
    return 1


def exact_main(args: list[str]) -> int:
    """Run --exact with its arguments."""
    opts: dict[str, str] = {}
    files: list[str] = []
    skip = False
    for i, a in enumerate(args):
        if skip:
            skip = False
        elif a in ("--field", "--title") and i + 1 < len(args):
            opts[a] = args[i + 1]
            skip = True
        else:
            files.append(a)
    key = opts.get("--field")
    try:
        if len(files) != 2 or key is None:  # noqa: PLR2004
            raise ValueError("usage: compare_body.py --exact WRITTEN FETCHED --field KEY")  # noqa: EM101, TRY003, TRY301
        written, fetched = (Path(f).read_text(encoding="utf-8") for f in files)
        data = cast("object", json.loads(fetched))
    except (OSError, UnicodeError, ValueError) as exc:
        _ = sys.stderr.write(f"{exc}\n")
        return 2
    found = [v for v in _values(data, key) if isinstance(v, str)]
    want = written.split()
    if not any(c.split() == want for c in found):
        best = (found or [""])[0].split()
        ops = difflib.SequenceMatcher(None, want, best).get_opcodes()
        _, i1, _, j1, _ = next((op for op in ops if op[0] != "equal"), ("equal", 0, 0, 0, 0))
        print(f"differs at token {i1 + 1}")
        print(f"written: {' '.join(want[i1 : i1 + 8])}")
        print(f"fetched: {' '.join(best[j1 : j1 + 8])}")
        return 1
    title = opts.get("--title")
    if title is not None and not title_matches(
        title, [words(c) for c in (candidates(fetched) or [])], plain=False
    ):
        print(f"title mismatch: written {title!r}")
        return 1
    print(f"exact match: {len(want)} tokens")
    return 0


def same_main(args: list[str]) -> int:
    """Run --same with its arguments."""
    key = args[args.index("--field") + 1] if "--field" in args[:-1] else None
    files = [a for a in args if a not in ("--field", key)]
    try:
        if len(files) != 2:  # noqa: PLR2004
            raise ValueError("usage: compare_body.py --same BEFORE AFTER [--field KEY]")  # noqa: EM101, TRY003, TRY301
        texts = [Path(f).read_text(encoding="utf-8") for f in files]
    except (OSError, UnicodeError, ValueError) as exc:
        _ = sys.stderr.write(f"{exc}\n")
        return 2
    return same(texts[0], texts[1], key)


def main(argv: list[str] | None = None) -> int:
    """Compare the two files and report."""
    args = sys.argv[1:] if argv is None else argv
    modes = {"--same": same_main, "--exact": exact_main}
    if args[:1] and args[0] in modes:
        return modes[args[0]](args[1:])
    title: str | None = None
    if "--title" in args[:-1]:
        at = args.index("--title")
        title = args[at + 1]
        args = args[:at]
    try:
        written_path, fetched_path = args
    except ValueError:
        _ = sys.stderr.write("usage: compare_body.py WRITTEN FETCHED [--title TITLE]\n")
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
            return report(want, title, pool, plain=True)
    else:
        pool = [words(c) for c in found] or [[]]
        if want in pool:
            return report(want, title, pool, plain=False)
    best = max(pool, key=lambda c: difflib.SequenceMatcher(None, want, c).ratio())
    ops = difflib.SequenceMatcher(None, want, best).get_opcodes()
    _, i1, _, j1, _ = next(op for op in ops if op[0] != "equal")
    print(f"mismatch at word {i1 + 1}")
    print(f"written: {' '.join(want[i1 : i1 + 8])}")
    print(f"fetched: {' '.join(best[j1 : j1 + 8])}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
