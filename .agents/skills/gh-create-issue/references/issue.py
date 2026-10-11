#!/usr/bin/env python3
r"""Deterministic helpers for the create-issue skill.

``repo [--host HOST] [ARG...]`` reduces each ARG (a remote URL, a
``OWNER/REPO`` slug, or any github URL) to ``OWNER/REPO``. With no ARG it
reads ``git remote -v`` and prints ``<remote>\t<OWNER/REPO or ->`` per
remote. Exit status 1 when nothing reduced.

``template NAME [PATH]`` reads the issue template file NAME (its extension
picks form or markdown) from PATH or stdin and prints one JSON object:
``kind`` (``form`` or ``markdown``), ``name``, ``title``, ``labels``,
``assignees``, ``fields`` (label, type, required, options) and ``body``,
a skeleton to fill (``<ANSWER>`` and ``<CHOOSE>`` mark unanswered fields).
It parses only the YAML subset issue forms and front matter use, and
exits 2 with ``unsupported: ...`` on anything else.

``pick KIND`` reads template file names on stdin and prints the one named
for KIND (``defect``, ``proposal``, ``task``); exit 1 and the candidates
on stderr when none or several are.

``goencode MODULE`` prints a Go module path in the proxy's case-encoded form.

``labels NAME...`` reads ``gh label list --json name`` on stdin and prints
the NAMEs the repository has, in its spelling.

``lint [--file] [--tables] PATH`` prints ``<line>\t<category>`` for markdown
that renders badly on GitHub: ``details-blank`` (no blank line after
``</summary>``), ``hard-wrap``, ``heading-start`` (a body starts below
``###``; skipped with ``--file``), ``heading-jump``, ``summary-markdown``
(markdown inside ``<summary>`` renders literally), ``fence-open`` (a fence
never closed, or closed by a shorter one), ``table`` (only with
``--tables``), ``mention`` and ``xref`` (an unescaped ``@name`` or ``#N``
outside code notifies or links). Exit 1 on a hit; every row is a lead.

``body-check KIND PATH`` (KIND is ``defect``, ``proposal`` or ``task``)
prints ``<line>\t<category>`` for ``###`` headings that break the body
order: ``unknown``, ``not-for-kind``, ``duplicate``, ``out-of-order``, and
``0\tmissing-summary``. Exit 1 on a hit.

``fetch URL`` prints the body behind an issue, pull-request, or comment URL
via ``gh``; a ``gh`` failure is passed through verbatim.

``readback TITLE`` reads ``gh issue view --json title`` on stdin; exit 1
unless the title equals TITLE.

``scan [--title TITLE] PATH`` prints ``<line>\t<category>`` per line that may hold local
or personal data (the rendered-markdown skill shares ``scan`` and
``lint``), and ``0\tlength`` for a body over the API's reported
limit; ``placeholders PATH`` does the same for unresolved
placeholders outside code fences and code spans (``<ANSWER>`` and ``<CHOOSE>`` block even
inside a fence), so unfenced ``<Foo>``-shaped text blocks
by design: backtick code to pass. Both exit 1 on a hit and never print the
matched text.
"""

# ruff: noqa: S603, S607, D103, PLR2004, PLR0911
# pyright: reportAny=false, reportExplicitAny=false, reportUnknownVariableType=false
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
from __future__ import annotations

import ipaddress
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Callable

Json = Any

_SLUG = re.compile(r"^[\w.-]+/[\w.-]+$")
_SCP = re.compile(r"^(?:[\w.-]+@)?([\w.-]+):(?!//)(.+)$")


def reduce_remote(url: str, host: str = "github.com") -> str | None:
    r"""Reduce a remote URL or slug to ``OWNER/REPO`` on ``host``, else None.

    >>> reduce_remote("git@github.com:o/r.git")
    'o/r'
    >>> reduce_remote("https://user:tok@github.com/o/r.git/")
    'o/r'
    >>> reduce_remote("ssh://git@github.com:22/o/r")
    'o/r'
    >>> reduce_remote("https://github.com/o/r/issues/3")
    'o/r'
    >>> reduce_remote("o/r")
    'o/r'
    >>> reduce_remote("git@work-alias:o/r.git") is None
    True
    >>> reduce_remote("https://gitlab.com/o/r") is None
    True
    """
    url = url.strip()
    if _SLUG.match(url) and not url.endswith(".git/"):
        return _trim(url)
    if "://" in url:
        parts = urlsplit(url)
        found_host, path = (parts.hostname or "").lower(), parts.path
    else:
        scp = _SCP.match(url)
        if not scp:
            return None
        found_host, path = scp.group(1).lower(), scp.group(2)
    if found_host not in (host.lower(), "www." + host.lower()):
        return None
    segments = [s for s in path.split("/") if s]
    if len(segments) < 2:
        return None
    return _trim(f"{segments[0]}/{segments[1]}")


def _trim(slug: str) -> str:
    return slug.removesuffix(".git")


def _remotes() -> list[tuple[str, str]]:
    done = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True, check=False)
    seen: dict[str, str] = {}
    for line in done.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 2:
            _ = seen.setdefault(fields[0], fields[1])
    return list(seen.items())


def cmd_repo(args: list[str]) -> int:
    host = os.environ.get("GH_HOST", "github.com")
    if args[:1] == ["--host"] and len(args) >= 2:
        host, args = args[1], args[2:]
    rows = [(a, a) for a in args] if args else _remotes()
    hit = False
    for name, url in rows:
        slug = reduce_remote(url, host)
        hit = hit or slug is not None
        print(f"{name}\t{slug or '-'}" if not args else slug or "-")
    return 0 if hit else 1


class UnsupportedError(Exception):
    """The input uses YAML this parser does not read."""


def _refuse(message: str) -> NoReturn:
    raise UnsupportedError(message)


_KEY = re.compile(r"""^("[^"]*"|'[^']*'|[\w][\w .-]*?)\s*:(?:\s+(.*)|)$""")


class _Yaml:
    """Block mappings, block sequences, scalars, and flow lists of scalars."""

    def __init__(self, text: str) -> None:
        self.lines: list[tuple[int, str]] = []
        for no, raw in enumerate(text.splitlines(), 1):
            if raw.startswith("\t") or re.match(r" *\t", raw):
                _refuse(f"line {no}: tab indentation")
            self.lines.append((no, raw.rstrip()))
        self.pos: int = 0

    def _peek(self) -> tuple[int, int, str] | None:
        while self.pos < len(self.lines):
            no, raw = self.lines[self.pos]
            body = raw.lstrip()
            if body and not body.startswith("#"):
                if body.startswith(("---", "...")) and no > 1:
                    _refuse(f"line {no}: document marker")
                return no, len(raw) - len(body), body
            self.pos += 1
        return None

    def document(self) -> Json:
        if self.lines and self.lines[0][1].strip() == "---":
            self.pos = 1
        nxt = self._peek()
        if nxt is None:
            return None
        value = self._block(nxt[1])
        extra = self._peek()
        if extra is not None:
            _refuse(f"line {extra[0]}: unexpected indentation")
        return value

    def _block(self, indent: int) -> Json:
        nxt = self._peek()
        if nxt is None:
            _refuse("empty block")
        if nxt[2] == "-" or nxt[2].startswith("- "):
            return self._seq(indent)
        return self._map(indent)

    def _map(self, indent: int) -> Json:
        out: dict[str, Json] = {}
        while (nxt := self._peek()) is not None and nxt[1] == indent:
            no, _, body = nxt
            if body == "-" or body.startswith("- "):
                break
            m = _KEY.match(body)
            if not m:
                _refuse(f"line {no}: not a mapping entry")
            key = m.group(1).strip("\"'")
            if key in out:
                _refuse(f"line {no}: duplicate key {key}")
            self.pos += 1
            out[key] = self._value(indent, m.group(2) or "", no)
        return out

    def _value(self, indent: int, rest: str, no: int) -> Json:
        rest = _strip_comment(rest)
        if rest[:1] in ("|", ">"):
            return self._block_scalar(indent, rest, no)
        if rest:
            parts = [rest]
            while (nxt := self._peek()) is not None and nxt[1] > indent:
                if rest.startswith(('"', "'", "[", "{")):
                    _refuse(f"line {nxt[0]}: multi-line {rest[0]} value")
                parts.append(_strip_comment(nxt[2]))
                self.pos += 1
            return _scalar(" ".join(parts), no)
        nxt = self._peek()
        if nxt is None or nxt[1] < indent:
            return None
        if nxt[1] == indent:
            return self._seq(indent) if nxt[2][:2] in ("- ", "-") else None
        return self._block(nxt[1])

    def _seq(self, indent: int) -> Json:
        out: list[Json] = []
        while (nxt := self._peek()) is not None and nxt[1] == indent:
            no, _, body = nxt
            if not (body == "-" or body.startswith("- ")):
                break
            rest = body[1:].lstrip()
            offset = len(body) - len(rest)
            if not rest:
                self.pos += 1
                inner = self._peek()
                out.append(None if inner is None or inner[1] <= indent else self._block(inner[1]))
            elif _KEY.match(rest) and not rest.startswith(('"', "'", "[", "{")):
                self.lines[self.pos] = (no, " " * (indent + offset) + rest)
                out.append(self._map(indent + offset))
            else:
                self.pos += 1
                out.append(_scalar(_strip_comment(rest), no))
        return out

    def _block_scalar(self, indent: int, head: str, no: int) -> str:
        if not re.fullmatch(r"[|>]-?", head):
            _refuse(f"line {no}: block scalar header {head}")
        chunk: list[str] = []
        base = -1
        while self.pos < len(self.lines):
            _, raw = self.lines[self.pos]
            if raw.strip():
                depth = len(raw) - len(raw.lstrip())
                if depth <= indent:
                    break
                base = depth if base < 0 else base
                chunk.append(raw[base:] if depth >= base else raw.lstrip())
            else:
                chunk.append("")
            self.pos += 1
        while chunk and not chunk[-1]:
            _ = chunk.pop()
        if head[0] == "|":
            text = "\n".join(chunk)
        else:
            text = re.sub(r"(?<=\S)\n(?=\S)", " ", "\n".join(chunk))
        return text if head.endswith("-") or not text else text + "\n"


def _strip_comment(text: str) -> str:
    if text.startswith(('"', "'")):
        quote = text[0]
        end = text.find(quote, 1)
        while quote == '"' and end > 0 and text[end - 1] == "\\":
            end = text.find(quote, end + 1)
        while quote == "'" and end > 0 and text[end + 1 : end + 2] == "'":
            end = text.find(quote, end + 2)
        return text[: end + 1] if end > 0 else text
    return re.split(r"\s#", text, maxsplit=1)[0].rstrip()


def _scalar(text: str, no: int) -> Json:
    if text.startswith(("&", "*", "!", "%", "@", "`", "{")):
        _refuse(f"line {no}: anchor, alias, tag, or flow mapping")
    if text[:1] == '"':
        try:
            value = json.loads(text)
        except ValueError:
            _refuse(f"line {no}: double-quoted string")
        return value
    if text[:1] == "'":
        if not text.endswith("'") or len(text) < 2:
            _refuse(f"line {no}: single-quoted string")
        return text[1:-1].replace("''", "'")
    if text[:1] == "[":
        if not text.endswith("]"):
            _refuse(f"line {no}: flow list")
        inner = text[1:-1].strip()
        items = re.findall(r"""\s*("[^"]*"|'[^']*'|[^,]+?)\s*(?:,|$)""", inner)
        return [_scalar(i, no) for i in items if i]
    if text in ("true", "false"):
        return text == "true"
    if text in ("null", "~", ""):
        return None
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def parse_yaml(text: str) -> Json:
    r"""Parse the YAML subset issue templates use.

    >>> parse_yaml("a: 1\nb:\n- x: y\n  z: [p, 'q']\nc: |\n  hi\n  there\n")
    {'a': 1, 'b': [{'x': 'y', 'z': ['p', 'q']}], 'c': 'hi\nthere\n'}
    >>> parse_yaml("a: &x 1")
    Traceback (most recent call last):
    ...
    issue.UnsupportedError: line 1: anchor, alias, tag, or flow mapping
    """
    return _Yaml(text).document()


FORM_TYPES = ("markdown", "input", "textarea", "dropdown", "checkboxes")


def _names(value: Json) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, list) else str(value).split(",")
    return [str(i).strip() for i in items if str(i).strip()]


def _text(value: Json, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _refuse(f"{what} must be a non-empty string")
    return value


def form_from_yaml(data: Json) -> dict[str, Json]:
    r"""Validate an issue form and build the skeleton body.

    >>> form = form_from_yaml(parse_yaml(
    ...     "name: n\ndescription: d\nbody:\n"
    ...     "- type: textarea\n  attributes:\n    label: Steps\n"
    ...     "  validations:\n    required: true\n"))
    >>> form["body"], form["fields"][0]["required"]
    ('### Steps\n\n<ANSWER>\n', True)
    """
    if not isinstance(data, dict):
        _refuse("a form is a mapping")
    for key in ("name", "description", "body"):
        if key not in data:
            _refuse(f"missing top-level {key}")
    if not isinstance(data["body"], list):
        _refuse("body must be a list")
    fields: list[dict[str, Json]] = []
    chunks: list[str] = []
    for idx, item in enumerate(data["body"], 1):
        if not isinstance(item, dict) or item.get("type") not in FORM_TYPES:
            _refuse(f"body element {idx}: type is not one of {FORM_TYPES}")
        kind = item["type"]
        attrs = item.get("attributes")
        if not isinstance(attrs, dict):
            _refuse(f"body element {idx}: attributes must be a mapping")
        if kind == "markdown":
            continue
        label = _text(attrs.get("label"), f"body element {idx} label")
        valid = item.get("validations")
        required = isinstance(valid, dict) and valid.get("required") is True
        options = _options(kind, attrs, idx)
        fields.append({"label": label, "type": kind, "required": required, "options": options})
        chunks.append(_skeleton(kind, label, attrs, options))
    return {
        "kind": "form",
        "name": str(data["name"]),
        "title": data.get("title") or "",
        "labels": _names(data.get("labels")),
        "assignees": _names(data.get("assignees")),
        "fields": fields,
        "body": "\n".join(chunks),
    }


def _options(kind: str, attrs: dict[str, Json], idx: int) -> list[Json]:
    if kind not in ("dropdown", "checkboxes"):
        return []
    opts = attrs.get("options")
    if not isinstance(opts, list) or not opts:
        _refuse(f"body element {idx}: options must be a non-empty list")
    if kind == "dropdown":
        return [str(o) for o in opts]
    out: list[Json] = []
    for opt in opts:
        if not isinstance(opt, dict):
            _refuse(f"body element {idx}: checkbox option must be a mapping")
        out.append(
            {
                "label": _text(opt.get("label"), "checkbox label"),
                "required": opt.get("required") is True,
            }
        )
    return out


def _skeleton(kind: str, label: str, attrs: dict[str, Json], options: list[Json]) -> str:
    head = f"### {label}\n\n"
    if kind == "checkboxes":
        return head + "".join(f"- [ ] {o['label']}\n" for o in options)
    if kind == "dropdown":
        return head + "<CHOOSE>\n"
    answer = "<ANSWER>"
    render = attrs.get("render")
    if kind == "textarea" and isinstance(render, str) and render:
        answer = f"```{render}\n<ANSWER>\n```"
    return head + answer + "\n"


def template_from_markdown(text: str) -> dict[str, Json]:
    r"""Split front matter from a markdown template.

    >>> t = template_from_markdown("---\nname: Bug\nlabels: a, b\n---\n### Hi\n")
    >>> t["labels"], t["body"]
    (['a', 'b'], '### Hi\n')
    """
    meta: Json = {}
    body = text
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for end in range(1, len(lines)):
            if lines[end].strip() == "---":
                meta = parse_yaml("".join(lines[1:end])) or {}
                body = "".join(lines[end + 1 :]).lstrip("\n")
                break
        else:
            _refuse("front matter is not closed")
    if not isinstance(meta, dict):
        _refuse("front matter must be a mapping")
    return {
        "kind": "markdown",
        "name": str(meta.get("name") or ""),
        "title": meta.get("title") or "",
        "labels": _names(meta.get("labels")),
        "assignees": _names(meta.get("assignees")),
        "fields": [],
        "body": body,
    }


def cmd_template(name: str, path: str | None) -> int:
    if path is None:
        text = sys.stdin.read()
    else:
        text = Path(path).read_text(encoding="utf-8")
    try:
        if name.endswith((".yml", ".yaml")):
            out = form_from_yaml(parse_yaml(text))
        else:
            out = template_from_markdown(text)
    except UnsupportedError as exc:
        print(f"unsupported: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2))
    return 0


_BARE_KEYWORD_RUN = r"(?i:(?:secret|token|password|passwd|(?:api|access|private)[_-]?key)\w*\s+[A-Za-z0-9+/_-]{32,})"  # noqa: E501
# Each category is a lead, not a verdict: the reader confirms or fixes it.
SCAN_PATTERNS = (
    (
        "local-path",
        "|".join(  # noqa: FLY002
            (
                r"/home/[^/\s]+",
                r"/Users/[^/\s]+",
                r"/root/",
                r"\b[A-Za-z]:\\[\w.-]+\\",
                r"(?<![\w\\])\\\\[\w.-]+\\[\w$.-]+",
                r"(?:^|[\s\"'=(])~/[\w.-]",
            )
        ),
    ),
    ("url-userinfo", r"\b[A-Za-z][A-Za-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"),
    ("cookie", r"(?i)^\s*(?:set-)?cookie:"),
    (
        "signed-url",
        r"(?i)[?&;](?:x-amz-signature|x-amz-credential|x-goog-signature|sig|signature)=",
    ),
    ("email", r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    (
        "token",
        "|".join(  # noqa: FLY002
            (
                r"gh[pousr]_",
                r"github_pat_",
                r"glpat-",
                r"A[KS]IA[0-9A-Z]{12}",
                r"xox[a-z]-",
                r"x(?:app|wfp)-",
                r"sk-ant-",
                r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}",
                r"AIza[0-9A-Za-z_-]{35}",
                r"npm_[A-Za-z0-9]{36}",
                r"[sr]k_live_[A-Za-z0-9]{10,}",
                r"pypi-[A-Za-z0-9_-]{20,}",
                r"-----BEGIN ",
                r"eyJ[A-Za-z0-9_-]{10,}",
            )
        ),
    ),
    ("bearer", r"[Bb]earer\s+[A-Za-z0-9._~+/-]{8,}"),
    (
        "credential",
        "|".join(  # noqa: FLY002
            (
                r"(?i)(?:pass(?:word|wd)?|secret|token|api[_-]?key)\w*\s*[=:]\s*\S",
                _BARE_KEYWORD_RUN,
            )
        ),
    ),
    ("internal-host", r"(?i)\b[\w-]+(?:\.[\w-]+)*\.(?:internal|local|lan|corp|intranet)\b"),
)
_SKELETON = re.compile(r"<(?:ANSWER|CHOOSE)>")
_PLACEHOLDER = re.compile(r"<[A-Z][A-Z0-9_ -]*>|\bCONTACT\b")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


_IPV4 = re.compile(r"(?<![\w.-])((?:\d{1,3}\.){3}\d{1,3})(?![\w-]|\.\d)")
_VERSION_CONTEXT = re.compile(r"(?:\bv|version|\bver\.?|==|~=|>=|<=|@|=)\s*$", re.IGNORECASE)
_NON_PERSONAL = ("0.", "127.", "192.0.2.", "198.51.100.", "203.0.113.", "255.255.255.255")
MAX_BODY_CHARS = 65536  # observed in the API's error text; GitHub's docs do not state it


_IPV6 = re.compile(r"(?<![\w:.])[0-9A-Fa-f:]{4,}[0-9A-Fa-f](?![\w:])")


def _ipv6(line: str) -> bool:
    for m in _IPV6.finditer(line):
        try:
            addr = ipaddress.IPv6Address(m.group(0))
        except ValueError:
            continue
        if not (addr.is_loopback or addr.is_unspecified):
            return True
    return False


def _addresses(line: str) -> bool:
    for m in _IPV4.finditer(line):
        octets = m.group(1).split(".")
        if any(int(o) > 255 for o in octets) or m.group(1).startswith(_NON_PERSONAL):
            continue
        if not _VERSION_CONTEXT.search(line[: m.start()]):
            return True
    return False


_CODE_SPAN = re.compile(r"`[^`]*`")
_MENTION = re.compile(r"(?<![\w@/`.-])@[A-Za-z0-9][\w-]*(?:/[\w-]+)?")
_XREF = re.compile(r"(?<![\w&/#`.-])(?:[\w.-]+/[\w.-]+)?#\d+\b")
_SUMMARY_MD = re.compile(r"<summary>[^<]*(?:\*\*|`|\[[^\]]*\]\(|(?<!\w)_\w)")
_HEADING = re.compile(r"^(#{1,6})\s")
_LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")


def _prose(text: str) -> list[tuple[int, str, bool]]:
    """Return ``(line, text, in_fence)`` with inline code spans blanked."""
    out: list[tuple[int, str, bool]] = []
    fence = ""
    for no, line in enumerate(text.splitlines(), 1):
        m = _FENCE.match(line)
        if m:
            mark = m.group(1)
            if not fence:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence):
                fence = ""
            out.append((no, "", True))
            continue
        out.append((no, line if fence else _CODE_SPAN.sub("", line), bool(fence)))
    return out


def _notifies(text: str) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for no, line, fenced in _prose(text):
        if fenced:
            continue
        if _MENTION.search(line):
            hits.append((no, "mention"))
        if _XREF.search(line):
            hits.append((no, "xref"))
    return hits


def scan_text(text: str) -> list[tuple[int, str]]:
    r"""Return ``(line, category)`` leads.

    >>> scan_text("ok\nsee /home/ann/x and bob@example.com\n")
    [(2, 'local-path'), (2, 'email')]
    >>> scan_text("v1.2.3.4 and 999.1.1.1 and 127.0.0.1\nhost 10.1.2.3\n")
    [(2, 'ip-address')]
    """
    hits: list[tuple[int, str]] = []
    if len(text) > MAX_BODY_CHARS:
        hits.append((0, "length"))
    for no, line in enumerate(text.splitlines(), 1):
        hits.extend((no, name) for name, pat in SCAN_PATTERNS if re.search(pat, line))
        if _addresses(line) or _ipv6(line):
            hits.append((no, "ip-address"))
    return sorted(hits + _notifies(text), key=lambda h: h[0])


def lint_text(text: str, *, file: bool = False, tables: bool = False) -> list[tuple[int, str]]:
    r"""Return ``(line, category)`` rendering leads.

    >>> lint_text("<summary>x</summary>\nbody\n")
    [(1, 'details-blank')]
    """
    hits: list[tuple[int, str]] = []
    rows = _prose(text)
    raw = text.splitlines()
    level = 0
    para: list[tuple[int, str]] = []

    def flush() -> None:
        if len(para) >= 2 and all(40 <= len(t) <= 100 for _, t in para[:-1]):
            hits.append((para[0][0], "hard-wrap"))
        para.clear()

    for idx, (no, line, fenced) in enumerate(rows):
        plain = (
            line.strip()
            and not fenced
            and not line.startswith((" ", "\t", ">", "|", "<"))
            and not _HEADING.match(line)
            and not _LIST.match(line)
        )
        if plain:
            para.append((no, line))
            continue
        flush()
        if fenced or not line.strip():
            continue
        if "<summary>" in raw[idx] and _SUMMARY_MD.search(raw[idx]):
            hits.append((no, "summary-markdown"))
        if "</summary>" in line and idx + 1 < len(raw) and raw[idx + 1].strip():
            hits.append((no, "details-blank"))
        if (
            tables
            and line.startswith("|")
            and idx + 1 < len(rows)
            and re.match(r"^\|?[\s:|-]+-", rows[idx + 1][1])
        ):
            hits.append((no, "table"))
        head = _HEADING.match(line)
        if head:
            new = len(head.group(1))
            if level == 0 and new < 3 and not file:
                hits.append((no, "heading-start"))
            elif level and new > level + 1:
                hits.append((no, "heading-jump"))
            level = new
    flush()
    hits.extend(_open_fences(raw))
    return sorted(hits + _notifies(text), key=lambda h: h[0])


def _open_fences(raw: list[str]) -> list[tuple[int, str]]:
    """Return ``fence-open`` leads: a fence never closed, or closed oddly.

    >>> _open_fences(["```", "x"])
    [(1, 'fence-open')]
    >>> _open_fences(["````", "```", "x", "````"])
    [(1, 'fence-open')]
    >>> _open_fences(["````", "```sh", "x", "```", "````"])
    []
    """
    hits: list[tuple[int, str]] = []
    start = 0
    mark = ""
    shorter = 0
    for no, line in enumerate(raw, 1):
        m = _FENCE.match(line)
        if not m:
            continue
        found = m.group(1)
        same = found[0] == mark[:1]
        if not mark:
            start, mark, shorter = no, found, 0
        elif same and len(found) >= len(mark) and not line.strip().strip(found[0]):
            if shorter % 2:
                hits.append((start, "fence-open"))
            mark = ""
        elif same:
            shorter += 1
    if mark:
        hits.append((start, "fence-open"))
    return hits


def placeholder_text(text: str) -> list[tuple[int, str]]:
    r"""Return ``(line, blocking|fenced)`` placeholder hits; code spans are skipped.

    >>> placeholder_text("a <SHA> `Vec<T>`\n```\n<DEBUG>\n```\n")
    [(1, 'blocking'), (3, 'fenced')]
    >>> placeholder_text("```sh\n<ANSWER>\n```\n")
    [(2, 'blocking')]
    >>> placeholder_text("`HashMap<K, V>` and `<SHA>`")
    []
    """
    return [
        (no, "fenced" if fenced and not _SKELETON.search(line) else "blocking")
        for no, line, fenced in _prose(text)
        if _PLACEHOLDER.search(line)
    ]


def cmd_lines(
    path: str, hits_for: Callable[[str], list[tuple[int, str]]], blocking: str | None
) -> int:
    hits = hits_for(Path(path).read_text(encoding="utf-8"))
    for no, label in hits:
        print(f"{no}\t{label}")
    return 1 if any(blocking in (None, label) for _, label in hits) else 0


def cmd_scan(path: str, title: str | None) -> int:
    hits = [("title", cat) for _, cat in scan_text(title)] if title else []
    body = scan_text(Path(path).read_text(encoding="utf-8"))
    for where, label in [*hits, *body]:
        print(f"{where}\t{label}")
    return 1 if hits or body else 0


KIND_WORDS = {
    "defect": {"bug", "defect"},
    "proposal": {"feature", "enhancement", "proposal"},
    "task": {"task", "chore"},
}


def pick_template(kind: str, names: list[str]) -> str | None:
    """Return the single template file named for ``kind``, else None.

    >>> pick_template("defect", ["config.yml", "bug_report.yml", "feature.yml"])
    'bug_report.yml'
    >>> pick_template("defect", ["crash.yml", "performance.yml"]) is None
    True
    """
    words = KIND_WORDS.get(kind, set())
    hits = [
        n
        for n in names
        if n.endswith((".yml", ".yaml", ".md"))
        and n.split(".")[0] != "config"
        and words & set(re.split(r"[-_. 0-9]+", n.lower()))
    ]
    return hits[0] if len(hits) == 1 else None


def cmd_pick(kind: str) -> int:
    names = [n.strip() for n in sys.stdin.read().splitlines() if n.strip()]
    found = pick_template(kind, names)
    if found is None:
        print("\n".join(names), file=sys.stderr)
        return 1
    print(found)
    return 0


def cmd_labels(wanted: list[str]) -> int:
    have = {str(i["name"]).lower(): str(i["name"]) for i in json.load(sys.stdin)}
    for name in wanted:
        if name.lower() in have:
            print(have[name.lower()])
    return 0


def cmd_readback(title: str) -> int:
    try:
        got = json.load(sys.stdin).get("title")
    except ValueError:
        print("unreadable")
        return 1
    print("ok" if got == title else "mismatch")
    return 0 if got == title else 1


SECTIONS = (
    ("Summary", None),
    ("Motivation", {"proposal", "task"}),
    ("Reproduction", {"defect"}),
    ("Expected", {"defect"}),
    ("Actual", {"defect"}),
    ("Environment", {"defect"}),
    ("Evidence", None),
    ("Proposal", None),
    ("Alternatives", None),
    ("References", None),
)


def body_check(text: str, kind: str) -> list[tuple[int, str]]:
    r"""Return ``(line, category)`` leads against the body section order.

    >>> body_check("### Summary\n\n### Evidence\n\n### Reproduction\n", "defect")
    [(5, 'out-of-order')]
    >>> body_check("### Notes\n", "task")
    [(1, 'unknown'), (0, 'missing-summary')]
    """
    names = [n for n, _ in SECTIONS]
    hits: list[tuple[int, str]] = []
    seen: list[str] = []
    last = -1
    for no, line, fenced in _prose(text):
        m = re.match(r"^###\s+(.*?)\s*$", line)
        if fenced or not m:
            continue
        name = m.group(1)
        if name not in names:
            hits.append((no, "unknown"))
            continue
        kinds = SECTIONS[names.index(name)][1]
        if kinds is not None and kind not in kinds:
            hits.append((no, "not-for-kind"))
        if name in seen:
            hits.append((no, "duplicate"))
        elif names.index(name) < last:
            hits.append((no, "out-of-order"))
        seen.append(name)
        last = max(last, names.index(name))
    if "Summary" not in seen:
        hits.append((0, "missing-summary"))
    return hits


_URL = re.compile(
    "".join(  # noqa: FLY002
        (
            r"^https?://(?P<host>[^/]+)/(?P<repo>[^/]+/[^/]+)/(?P<kind>issues|pull)/(?P<num>\d+)",
            r"(?:#(?P<frag>issuecomment-\d+|discussion_r\d+))?/?$",
        )
    )
)


def fetch_args(url: str) -> tuple[str, list[str]] | None:
    """Return ``(host, gh args)`` that print the body behind ``url``.

    >>> fetch_args("https://github.com/o/r/issues/3")[1][:3]
    ['issue', 'view', '3']
    >>> fetch_args("https://github.com/o/r/pull/4#issuecomment-99")[1][0]
    'api'
    >>> fetch_args("https://example.com/nope") is None
    True
    """
    m = _URL.match(url.strip())
    if not m:
        return None
    repo, num, frag = m.group("repo"), m.group("num"), m.group("frag")
    if frag:
        route = "pulls" if frag.startswith("discussion_r") else "issues"
        cid = re.sub(r"\D", "", frag)
        return m.group("host"), ["api", f"repos/{repo}/{route}/comments/{cid}", "--jq", ".body"]
    verb = "issue" if m.group("kind") == "issues" else "pr"
    return m.group("host"), [verb, "view", num, "--repo", repo, "--json", "body", "--jq", ".body"]


def cmd_fetch(url: str) -> int:
    found = fetch_args(url)
    if found is None:
        print("unsupported: not an issue, pull-request, or comment URL", file=sys.stderr)
        return 2
    host, args = found
    env = {**os.environ, "GH_HOST": host}
    done = subprocess.run(["gh", *args], capture_output=True, text=True, check=False, env=env)
    _ = sys.stdout.write(done.stdout)
    _ = sys.stderr.write(done.stderr)
    return done.returncode


def go_encode(path: str) -> str:
    """Case-encode a Go module path for the module proxy.

    >>> go_encode("github.com/Azure/azure-sdk")
    'github.com/!azure/azure-sdk'
    """
    return re.sub(r"[A-Z]", lambda m: "!" + m.group(0).lower(), path)


def _usage() -> NoReturn:
    print(__doc__, file=sys.stderr)
    raise SystemExit(64)


def main(argv: list[str]) -> int:
    cmd, args = (argv[0], argv[1:]) if argv else ("", [])
    if cmd == "repo":
        return cmd_repo(args)
    if cmd == "template" and len(args) in (1, 2):
        return cmd_template(args[0], args[1] if len(args) == 2 else None)
    if cmd == "fetch" and len(args) == 1:
        return cmd_fetch(args[0])
    if cmd == "body-check" and len(args) == 2:
        return cmd_lines(args[1], lambda t: body_check(t, args[0]), None)
    if cmd == "goencode" and len(args) == 1:
        print(go_encode(args[0]))
        return 0
    if cmd == "pick" and len(args) == 1:
        return cmd_pick(args[0])
    if cmd == "labels":
        return cmd_labels(args)
    if cmd == "readback" and len(args) == 1:
        return cmd_readback(args[0])
    if cmd == "lint":
        flags = {a for a in args if a.startswith("--")}
        files = [a for a in args if not a.startswith("--")]
        if len(files) == 1 and flags <= {"--file", "--tables"}:
            return cmd_lines(
                files[0],
                lambda t: lint_text(t, file="--file" in flags, tables="--tables" in flags),
                None,
            )
    if cmd == "scan" and args[:1] == ["--title"] and len(args) == 3:
        return cmd_scan(args[2], args[1])
    if cmd in ("scan", "placeholders") and len(args) == 1:
        if cmd == "scan":
            return cmd_scan(args[0], None)
        return cmd_lines(args[0], placeholder_text, "blocking")
    _usage()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
