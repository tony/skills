#!/usr/bin/env python3
"""Scan a ticket body for text that should not ship, or count its media.

Usage: scan_body.py [--keep-evidence] FILE [FILE...]
       scan_body.py --mask FILE
       scan_body.py --media [--field KEY] FILE [FETCHED]
       scan_body.py --text --field KEY FILE

Without a mode, print one `kind<TAB>line<TAB>excerpt` row per finding and
exit 1 when there is any, 0 when clean, 2 when FILE cannot be read. Kinds:
secret (credential-shaped string), path (local home path), host (internal
hostname or private IP), email, mention (@name), ref (a reference that
notifies a third party: owner/repo#N, !N, or a tracker key; a bare #N is the
in-repo house form and is not flagged), rot (insertion or line
counts, line anchors, branch-pinned links). A finding is a lead, not a
verdict: a version number or a quoted log line can be evidence. Secret
excerpts are masked.

With --keep-evidence, rot rows (insertion counts, line anchors) in any fenced
block or quoted line are dropped; every other kind, mentions and references
included, is kept.

With --cut-candidates, print only the mechanical Cut candidates, `cut<TAB>line<TAB>
excerpt` (insertion and line counts, file sizes, line anchors, branch-pinned
links), and exit 0; whether each is evidence stays a judgment.

Credential shapes and their sources. Official: `AKIA` and `ASIA` access key
prefixes (AWS IAM identifiers, docs.aws.amazon.com/IAM/latest/UserGuide/
reference_identifiers.html); `npm_` (github.blog/changelog/2021-09-23-npm-has-a-new-
access-token-format); `glpat-` (GitLab's token-prefix table,
docs.gitlab.com/security/tokens);
`ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_` (github.blog/2021-04-05-behind-githubs-new-
authentication-token-formats). No official source found, kept as leads:
`lin_api_`, `ATATT` (Atlassian documents its tokens as opaque), `xox*`,
`sk_live_`, `AIza`, `sk-`. A secret with no prefix is detected only beside a key
word (a 40-character AWS secret after `aws_secret_access_key`, any value after
`token=`); other context-free secrets are left to the reread.

With several files, each row ends with the file's name, so a title and a
body scan together. With --mask, print the text with every credential
replaced by `<redacted>`, so a quote cannot repeat one.

With --media, print `media<TAB>N` and one row per inline image, video or
embedded media node, then exit 0. FILE may be a tracker's JSON output;
strings and Atlassian Document Format `media` nodes are read from it. With
a second file, exit 1 when it holds fewer media than FILE. --field KEY
limits JSON input to the value at the `/`-separated key path KEY from the
root, such as `fields/description` (case-insensitive; a nested comment is
never matched, so its image cannot mask a lost body image); it applies to FETCHED when
there is one.

With --text, print the body field KEY of a tracker's JSON output as text:
an Atlassian Document Format value becomes one line per block, and a string
is printed as is.

>>> scan_text('token = "ghp_' + 'a' * 36 + '"')
[('secret', 1, 'ghp_...')]
>>> scan_text('see /home/alex/work/app.log')
[('path', 1, '/home/alex/work/app.log')]
>>> media_refs('![shot](https://x.io/a.png) and <img src="b.gif">')
['![shot](https://x.io/a.png)', '<img src="b.gif">']
"""

import json
import re
import sys
from pathlib import Path
from typing import cast

FENCE_RE = re.compile(r"^\s*(```|~~~)")
SECRET_RES = [
    re.compile(p)
    for p in (
        r"(?:AKIA|ASIA)[0-9A-Z]{16}",
        r"(?i)aws[_-]?secret[_-]?(?:access[_-]?)?key[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{40}",
        r"glpat-[A-Za-z0-9_-]{20,}",
        r"lin_api_[A-Za-z0-9]{20,}",
        r"ATATT[A-Za-z0-9_=-]{20,}",
        r"npm_[A-Za-z0-9]{30,}",
        r"gh[pousr]_[A-Za-z0-9]{30,}",
        r"github_pat_[A-Za-z0-9_]{30,}",
        r"xox[abprs]-[A-Za-z0-9-]{10,}",
        r"hooks\.slack\.com/services/[A-Za-z0-9/]{10,}",
        r"[sr]k_(?:live|test)_[A-Za-z0-9]{10,}",
        r"sk-[A-Za-z0-9_-]{20,}",
        r"AIza[0-9A-Za-z_-]{35}",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+",
        r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}",
        r"://[^/\s:@]+:[^/\s@]+@",
        r"(?i)(?<![A-Za-z])(?:api[_-]?key|secret|token)\b[\"']?\s*[:=]\s*[\"']?[^\s\"'<>]{8,}",
        r"(?i)(?<![A-Za-z])passw(?:or)?d\b[\"']?\s*[:=]\s*[\"']?[^\s\"'<>]{4,}",
    )
]
OTHER_RES = [
    (kind, re.compile(pattern))
    for kind, pattern in (
        (
            "path",
            r"(?:/home/|/Users/|/root/|/tmp/|(?<![\w.])~/)[^\s'\"`)]+|[A-Za-z]:\\Users\\[^\s'\"`)]+",
        ),
        ("ref", r"\b[\w.-]+/[\w.-]+#\d+\b"),
        ("ref", r"(?<![\w&/#])!\d+\b"),
        (
            "ref",
            r"\b(?!(?:UTF|SHA|ISO|RFC|MD|TLS|SSL|CVE|HTTP|IPV|AES|RSA|TCP)-)[A-Z][A-Z0-9]+-\d+\b",
        ),
        ("host", r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"),
        ("host", r"\b[\w-]+(?:\.[\w-]+)*\.(?:internal|corp|lan|local|intranet)\b"),
        ("email", r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),
        ("mention", r"(?<![\w.@/])@[A-Za-z][\w-]*"),
        ("rot", r"[+-]\d+/[+-]\d+"),
        ("rot", r"\b\d+ (?:lines?|files?|tests?|insertions?)\b"),
        ("rot", r"\b\d+(?:\.\d+)?\s?(?:KB|MB|GB|kB)\b"),
        ("rot", r"#L\d+|blob/(?:main|master)/"),
    )
]
MEDIA_RES = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"!\[[^\]]*\]\([^)\s]+[^)]*\)",
        r"<(?:img|video|source)\b[^>]*>",
        r"![^!\s|]+\.(?:png|jpe?g|gif|svg|webp|mp4|mov|webm)[^!\s]*!",
        r"\[media\]",
    )
]


EVIDENCE_KINDS = ("rot",)


def scan_text(text: str, *, keep_evidence: bool = False) -> list[tuple[str, int, str]]:
    """Return (kind, line number, excerpt) for each finding.

    With keep_evidence, rot rows inside any fenced block or quoted line
    are dropped: they are the pasted evidence. Everything else, including
    mentions and references that still notify, is kept.
    """
    found: list[tuple[str, int, str]] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
        evidence = keep_evidence and (in_fence or line.lstrip().startswith(">"))
        for rx in SECRET_RES:
            hit = rx.search(line)
            if hit:
                found.append(("secret", number, hit.group(0)[:4] + "..."))
                break
        for kind, rx in OTHER_RES:
            if evidence and kind in EVIDENCE_KINDS:
                continue
            found.extend((kind, number, hit.group(0)) for hit in rx.finditer(line))
    return found


def media_refs(text: str) -> list[str]:
    """Return inline image, video, and embed references in markup."""
    return [m.group(0) for rx in MEDIA_RES for m in rx.finditer(text)]


def _walk(node: object, strings: list[str], media_nodes: list[str]) -> None:
    if isinstance(node, str):
        strings.append(node)
    elif isinstance(node, dict):
        item = cast("dict[str, object]", node)
        if item.get("type") in ("media", "mediaInline"):
            media_nodes.append("adf media node")
        for value in item.values():
            _walk(value, strings, media_nodes)
    elif isinstance(node, list):
        for value in cast("list[object]", node):
            _walk(value, strings, media_nodes)


def load(text: str) -> tuple[list[str], list[str]]:
    """Return the text fields and any structural media nodes of a file."""
    try:
        data = cast("object", json.loads(text))
    except ValueError:
        return [text], []
    strings: list[str] = []
    nodes: list[str] = []
    _walk(data, strings, nodes)
    return strings, nodes


BLOCKS = {"paragraph", "heading", "listItem", "codeBlock", "blockquote", "tableRow"}


def _leaf(item: dict[str, object], kind: object) -> str | None:
    """Return the text of an ADF leaf node, or None for a container."""
    raw = item.get("attrs")
    attrs = cast("dict[str, object]", raw) if isinstance(raw, dict) else {}
    if kind == "text":
        text = item.get("text")
        text = text if isinstance(text, str) else ""
        for mark in cast("list[dict[str, object]]", item.get("marks") or []):
            mark_attrs = mark.get("attrs")
            href = (
                cast("dict[str, object]", mark_attrs).get("href")
                if isinstance(mark_attrs, dict)
                else None
            )
            if mark.get("type") == "link" and isinstance(href, str):
                return f"{text} ({href})"
        return text
    leaves = {"hardBreak": "\n", "media": "[media]", "mediaInline": "[media]"}
    if isinstance(kind, str) and kind in leaves:
        return leaves[kind]
    if kind in ("inlineCard", "blockCard", "embedCard"):
        url = attrs.get("url")
        return url if isinstance(url, str) else ""
    if kind == "mention":
        name = attrs.get("text")
        return name if isinstance(name, str) else "@mention"
    return None


def adf_lines(node: object) -> str:
    """Flatten an Atlassian Document Format node: one line per block.

    >>> adf_lines({"type": "text", "text": "log", "marks": [{"type": "link", "attrs": {"href": "https://x.io"}}]})
    'log (https://x.io)'
    >>> adf_lines({"type": "mention", "attrs": {"id": "1", "text": "@sam"}})
    '@sam'
    """
    if not isinstance(node, dict):
        return ""
    item = cast("dict[str, object]", node)
    kind = item.get("type")
    leaf = _leaf(item, kind)
    if leaf is not None:
        return leaf
    children = item.get("content")
    inner = (
        "".join(adf_lines(c) for c in cast("list[object]", children))
        if isinstance(children, list)
        else ""
    )
    if kind == "listItem":
        return f"- {inner.strip()}\n"
    return f"{inner.strip()}\n" if kind in BLOCKS else inner


def fields(data: object, path: str) -> list[object]:
    """Return the value at a `/`-separated key path from the root, ignoring case.

    >>> fields({"fields": {"A.B": "x"}, "comments": [{"body": "c"}]}, "fields/a.b")
    ['x']
    >>> fields({"comments": [{"body": "c"}]}, "body")
    []
    """
    node = data
    for part in path.split("/"):
        if not isinstance(node, dict):
            return []
        match = [v for k, v in cast("dict[str, object]", node).items() if k.lower() == part.lower()]
        if not match:
            return []
        node = match[0]
    return [node]


KEY_BLOCK_RE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.DOTALL
)


def mask(text: str) -> str:
    r"""Return the text with every credential-shaped string replaced.

    >>> mask("a\n-----BEGIN PRIVATE KEY-----\nMIIB\n-----END PRIVATE KEY-----\nb")
    'a\n<redacted>\nb'
    """
    text = KEY_BLOCK_RE.sub("<redacted>", text)
    for rx in SECRET_RES:
        text = rx.sub("<redacted>", text)
    return text


def media_of(path: str, field: str | None = None) -> list[str]:
    """Return the media references of a file, structural nodes included."""
    text = Path(path).read_text(encoding="utf-8")
    if field is None:
        strings, nodes = load(text)
    else:
        strings: list[str] = []
        nodes: list[str] = []
        for value in fields(cast("object", json.loads(text)), field):
            _walk(value, strings, nodes)
    return [ref for s in strings for ref in media_refs(s)] + nodes


def body_text(path: str, field: str) -> str:
    """Return the text of the body field of a JSON file."""
    values = fields(cast("object", json.loads(Path(path).read_text(encoding="utf-8"))), field)
    if not values:
        message = f"no field {field!r}"
        raise ValueError(message)
    value = values[0]
    return value if isinstance(value, str) else adf_lines(value).rstrip("\n")


USAGE = (
    "usage: scan_body.py [--keep-evidence | --cut-candidates] FILE... | --mask FILE"
    " | --media [--field KEY] FILE [FETCHED] | --text --field KEY FILE\n"
)


def media_report(paths: list[str], field: str | None) -> int:
    """Print media counts, and fail when the fetched file holds fewer."""
    refs = media_of(paths[0])
    print(f"media\t{len(refs)}")
    for ref in refs:
        print(f"media\t{ref}")
    if len(paths) > 1:
        after = len(media_of(paths[1], field))
        print(f"fetched\t{after}")
        if after < len(refs):
            print("media lost in the write")
            return 1
    return 0


def _option(args: list[str], name: str) -> tuple[list[str], str | None]:
    """Remove `name VALUE` from args and return the value."""
    if name not in args:
        return args, None
    at = args.index(name)
    value = args[at + 1] if at + 1 < len(args) else None
    return args[:at] + args[at + 2 :], value


def main(argv: list[str] | None = None) -> int:
    """Scan FILE and report."""
    args = sys.argv[1:] if argv is None else argv
    args, field = _option(args, "--field")
    media = "--media" in args
    text_mode = "--text" in args
    mask_mode = "--mask" in args
    keep = "--keep-evidence" in args
    cut = "--cut-candidates" in args
    paths = [
        a
        for a in args
        if a not in ("--media", "--text", "--mask", "--keep-evidence", "--cut-candidates")
    ]
    limit = 2 if media else 1 if text_mode or mask_mode else len(paths)
    if not paths or len(paths) > limit or (text_mode and field is None):
        _ = sys.stderr.write(USAGE)
        return 2
    try:
        if text_mode and field:
            print(body_text(paths[0], field))
            return 0
        if mask_mode:
            print(mask(Path(paths[0]).read_text(encoding="utf-8")), end="")
            return 0
        if media:
            return media_report(paths, field)
        rows: list[tuple[str, int, str, str]] = []
        for path in paths:
            strings, _nodes = load(Path(path).read_text(encoding="utf-8"))
            rows += [
                (*f, Path(path).name) for s in strings for f in scan_text(s, keep_evidence=keep)
            ]
    except (OSError, UnicodeError, ValueError) as exc:
        _ = sys.stderr.write(f"cannot read: {exc}\n")
        return 2
    return report_rows(rows, multi=len(paths) > 1, cut=cut)


def report_rows(rows: list[tuple[str, int, str, str]], *, multi: bool, cut: bool) -> int:
    """Print scan rows, or the cut candidates, and return the exit code."""
    if cut:
        for kind, number, excerpt, _name in rows:
            if kind == "rot":
                print(f"cut\t{number}\t{excerpt}")
        return 0
    for kind, number, excerpt, name in rows:
        tail = f"\t{name}" if multi else ""
        print(f"{kind}\t{number}\t{excerpt}{tail}")
    if not rows:
        print("clean")
    return 1 if rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
