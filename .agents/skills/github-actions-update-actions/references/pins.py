#!/usr/bin/env python3
"""Deterministic pin checks for GitHub Actions workflows.

``inventory REPO...`` prints one JSON object per repository (a clone path or an
``owner/name`` slug) listing every ``uses`` pin on its default branch. Workflow
and composite-action YAML is parsed, not line-matched; local composite actions
named by a ``uses: ./path`` are followed wherever they live. ``dependabot``
lists the Dependabot configuration files present. ``complete`` is false when a
file could not be parsed (``unparsed``), a local action could not be found
(``unresolved``), or a pin names an action or ref outside plain
``owner/name`` and tag characters (``unsafe``, left out of ``pins``); such an
inventory is not a list of every pin.
``majors ACTION PIN TARGET`` prints the first tag of each major above PIN's
major and at or below TARGET's, and exits 4 after printing when a major has no
listed tag. PIN and TARGET are versions with or without a leading ``v``
(``4``, ``v4.2.1``); anything else exits 1 with ``not a version``.
``latest ACTION`` prints the highest stable ``vN[.N[.N]]`` tag in the full tag
list. ``compare A B`` prints ``lt``, ``eq`` or ``gt`` over the components both
versions name, so a ``v6`` float equals ``6.0.1``. ``tag ACTION TAG`` exits 0
when the tag exists, 1 when it does not, and 3 when the lookup could not decide
(auth, rate limit, network, or a repository this login cannot read);
``sha ACTION TAG`` prints the tag's commit SHA with the same exit codes.
``proposal SLUG NUMBER`` prints the pin changes a pull request makes and how
many changed lines are anything else. ``pulls SLUG`` prints the open
Dependabot pull requests and exits 5 when a title carries shell syntax.
``pr-state SLUG NUMBER STATE`` exits 0 when the pull request is in STATE
(``open``, ``closed`` or ``merged``) and 1 otherwise. A bad argument exits 2.

Clone commands name their path; GitHub CLI queries name their repository and
github.com host independently of the working directory and host environment.
"""

# ruff: noqa: S603, S607, PLR2004, PLR0911, TRY003, EM102
# pyright: reportUnusedCallResult=false, reportAny=false, reportExplicitAny=false
from __future__ import annotations

import json
import os
import posixpath
import re
import shlex
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast, final
from urllib.parse import quote, urlsplit

USES = re.compile(r"^\s*-?\s*uses:\s*(?P<ref>[^\s#]+)\s*(?:#\s*(?P<note>.*))?$")
SLUG = re.compile(r"^[\w.-]+/[\w.-]+$")
SCP_REMOTE = re.compile(r"(?:[\w.-]+@)?github\.com:(?P<path>.+)", re.IGNORECASE | re.ASCII)
WORKFLOW = re.compile(
    r"\.github/workflows/.+\.ya?ml|\.github/actions/(?:.+/)?action\.ya?ml", re.DOTALL
)
MAJOR = re.compile(r"^(v)?(\d+)(?:\.(\d+))?(?:\.(\d+))?$")
VERSION = re.compile(r"^(?:tag\s*[=:]\s*)?v?(\d+(?:\.\d+){0,2}(?:-[0-9A-Za-z.-]+)?)(?![\w.-])")
REF_VERSION = re.compile(r"^(?:v\d+(?:\.\d+){0,2}|\d+\.\d+(?:\.\d+)?)(?:-[0-9A-Za-z.-]+)?$")
ANY_VERSION = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-(?P<pre>[0-9A-Za-z.-]+))?$")
SAFE_ACTION = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+", re.ASCII)
SAFE_REF = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.+/-]*", re.ASCII)
SHELL_SYNTAX = re.compile(r"[$`;|&<>\\'\"\x00-\x1f\x7f]")
STATES = {"open": "OPEN", "closed": "CLOSED", "merged": "MERGED"}
EXIT_INCOMPLETE = 4
EXIT_UNSAFE = 5
ANCHOR = re.compile(r"&([^\s,\[\]{}]+)\s*(.*)", re.DOTALL)
ALIAS = re.compile(r"\*([^\s,\[\]{}]+)\s*(?:#.*)?")


@final
class UnsupportedError(Exception):
    """A construct the workflow reader cannot interpret; the file stays unread."""

    def __init__(self, line: int, reason: str) -> None:
        super().__init__(f"line {line}: {reason}")
        self.line = line
        self.reason = reason


@final
class Scalar(str):  # noqa: SLOT000
    """A YAML scalar with its source line, trailing comment and block flag."""

    line: int = 0
    comment: str = ""
    block: bool = False

    def __new__(cls, text: str, line: int, comment: str = "", block: bool = False) -> Scalar:
        """Build a scalar holding ``text``."""
        obj = super().__new__(cls, text)
        obj.line = line
        obj.comment = comment
        obj.block = block
        return obj


Node = Any
Row = tuple[int, str, int]


def _quoted_end(text: str, start: int) -> int:
    """Return the index of the quote closing the scalar opened at ``start``, or -1."""
    opener, i = text[start], start + 1
    while i < len(text):
        ch = text[i]
        if opener == '"' and ch == "\\":
            i += 2
            continue
        if ch == opener:
            if opener == "'" and text[i + 1 : i + 2] == "'":
                i += 2
                continue
            return i
        i += 1
    return -1


def _unquote(text: str) -> str:
    if text[0] == "'":
        return text[1:-1].replace("''", "'")
    return text[1:-1].replace('\\"', '"').replace("\\\\", "\\")


def _comment_at(text: str) -> int:
    """Return the index of the first comment marker outside quotes, or -1."""
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in "\"'" and (i == 0 or text[i - 1] in " \t[{,:"):
            end = _quoted_end(text, i)
            if end < 0:
                return -1
            i = end + 1
            continue
        if ch == "#" and (i == 0 or text[i - 1] in " \t"):
            return i
        i += 1
    return -1


def _flow_depth(text: str, line: int) -> int:
    depth, i = 0, 0
    while i < len(text):
        ch = text[i]
        if ch in "\"'":
            end = _quoted_end(text, i)
            if end < 0:
                return 1
            i = end
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth < 0:
                raise UnsupportedError(line, "unbalanced flow collection")
        i += 1
    return depth


def _merge_sources(value: Node, line: int) -> dict[str, Node]:
    """Combine the mappings a ``<<`` key names; earlier sources win."""
    sources = cast("list[Node]", value) if isinstance(value, list) else [value]
    merged: dict[str, Node] = {}
    for source in sources:
        if not isinstance(source, dict):
            raise UnsupportedError(line, "merge key value is not a mapping")
        for name, item in cast("dict[str, Node]", source).items():
            merged.setdefault(name, item)
    return merged


@final
class _Flow:
    """Parses one complete flow collection held in a single string."""

    def __init__(self, text: str, line: int, anchors: dict[str, Node]) -> None:
        self.text = text
        self.line = line
        self.anchors = anchors

    def skip(self, i: int) -> int:
        while i < len(self.text) and self.text[i] in " \t":
            i += 1
        return i

    def node(self, i: int) -> tuple[Node, int]:
        i = self.skip(i)
        if i >= len(self.text):
            return None, i
        ch = self.text[i]
        if ch == "{":
            return self.mapping(i + 1)
        if ch == "[":
            return self.sequence(i + 1)
        if ch == "*":
            m = ALIAS.match(self.text, i)
            if not m or m.group(1) not in self.anchors:
                raise UnsupportedError(self.line, "unknown or malformed alias")
            return self.anchors[m.group(1)], m.end(1)
        if ch == "&":
            m = ANCHOR.match(self.text[i:])
            if not m:
                raise UnsupportedError(self.line, "malformed anchor")
            value, end = self.node(i + 1 + len(m.group(1)))
            self.anchors[m.group(1)] = value
            return value, end
        if ch in "!|>%@`":
            raise UnsupportedError(self.line, "tag or reserved indicator")
        if ch in "\"'":
            end = _quoted_end(self.text, i)
            if end < 0:
                raise UnsupportedError(self.line, "unterminated quoted scalar")
            return Scalar(_unquote(self.text[i : end + 1]), self.line), end + 1
        start = i
        while i < len(self.text):
            colon = self.text[i] == ":" and (i + 1 == len(self.text) or self.text[i + 1] in " \t")
            if self.text[i] in ",]}" or colon:
                break
            i += 1
        return Scalar(self.text[start:i].strip(), self.line), i

    def mapping(self, i: int) -> tuple[Node, int]:
        result: dict[str, Node] = {}
        while True:
            i = self.skip(i)
            if i >= len(self.text):
                raise UnsupportedError(self.line, "unterminated flow mapping")
            if self.text[i] == "}":
                return result, i + 1
            name, i = self.node(i)
            if not isinstance(name, Scalar):
                raise UnsupportedError(self.line, "unsupported flow mapping key")
            i = self.skip(i)
            value: Node = None
            if i < len(self.text) and self.text[i] == ":":
                value, i = self.node(i + 1)
                i = self.skip(i)
            if name == "<<":
                result = {**_merge_sources(value, self.line), **result}
            else:
                result[str(name)] = value
            if i < len(self.text) and self.text[i] == ",":
                i += 1

    def sequence(self, i: int) -> tuple[Node, int]:
        result: list[Node] = []
        while True:
            i = self.skip(i)
            if i >= len(self.text):
                raise UnsupportedError(self.line, "unterminated flow sequence")
            if self.text[i] == "]":
                return result, i + 1
            item, i = self.node(i)
            i = self.skip(i)
            if i < len(self.text) and self.text[i] == ":" and isinstance(item, Scalar):
                value, i = self.node(i + 1)
                item = {str(item): value}
                i = self.skip(i)
            result.append(item)
            if i < len(self.text) and self.text[i] == ",":
                i += 1


@final
class _Reader:
    """Reads the block and flow YAML a workflow uses and refuses the rest."""

    def __init__(self, rows: list[Row]) -> None:
        self.rows = rows
        self.anchors: dict[str, Node] = {}

    def next(self, i: int) -> int:
        while i < len(self.rows) and (not self.rows[i][1] or self.rows[i][1].startswith("#")):
            i += 1
        return i

    def document(self) -> Node:
        i = self.next(0)
        if i >= len(self.rows):
            return None
        node, i = self.node(i, -1)
        i = self.next(i)
        if i < len(self.rows):
            raise UnsupportedError(self.rows[i][2], "unexpected content")
        return node

    def node(self, i: int, parent: int) -> tuple[Node, int]:
        indent, text, no = self.rows[i]
        if text == "-" or text.startswith("- "):
            return self.sequence(i, indent)
        if self.key(text, no) is not None:
            return self.mapping(i, indent)
        return self.inline(i, text, parent)

    def sequence(self, i: int, indent: int) -> tuple[Node, int]:
        items: list[Node] = []
        while i < len(self.rows) and self.rows[i][0] == indent:
            _, text, no = self.rows[i]
            if not (text == "-" or text.startswith("- ")):
                break
            rest = text[1:].lstrip(" ")
            if not rest or rest.startswith("#"):
                j = self.next(i + 1)
                if j < len(self.rows) and self.rows[j][0] > indent:
                    item, i = self.node(j, indent)
                else:
                    item, i = None, j
            else:
                self.rows[i] = (indent + len(text) - len(rest), rest, no)
                item, i = self.node(i, indent)
            items.append(item)
            i = self.next(i)
        return items, i

    def mapping(self, i: int, indent: int) -> tuple[Node, int]:
        explicit: dict[str, Node] = {}
        merged: dict[str, Node] = {}
        while i < len(self.rows) and self.rows[i][0] == indent:
            _, text, no = self.rows[i]
            pair = self.key(text, no)
            if pair is None:
                raise UnsupportedError(no, "expected a mapping key")
            name, rest = pair
            if not rest or rest.startswith("#"):
                value, i = self.below(i, indent, same=True)
            else:
                value, i = self.inline(i, rest, indent)
            if name == "<<":
                for key_, item in _merge_sources(value, no).items():
                    merged.setdefault(key_, item)
            else:
                explicit[name] = value
            i = self.next(i)
        return {**merged, **explicit}, i

    def below(self, i: int, indent: int, *, same: bool) -> tuple[Node, int]:
        """Read the value on the lines after row ``i``; None when there is none."""
        j = self.next(i + 1)
        if j < len(self.rows) and self.rows[j][0] > indent:
            return self.node(j, indent)
        if (
            same
            and j < len(self.rows)
            and self.rows[j][0] == indent
            and (self.rows[j][1] == "-" or self.rows[j][1].startswith("- "))
        ):
            return self.sequence(j, indent)
        return None, j

    def key(self, text: str, no: int) -> tuple[str, str] | None:
        """Split ``key: rest``; None when the line is not a mapping entry."""
        if text[0] == "\t":
            raise UnsupportedError(no, "tab indentation")
        if text == "?" or text.startswith("? "):
            raise UnsupportedError(no, "complex mapping key")
        if text[0] in "\"'":
            end = _quoted_end(text, 0)
            if end < 0:
                return None
            tail = text[end + 1 :].lstrip(" ")
            if tail.startswith(":") and (len(tail) == 1 or tail[1] in " \t"):
                return _unquote(text[: end + 1]), tail[1:].strip()
            return None
        if text[0] in "{[&*!|>%@`":
            return None
        for i, ch in enumerate(text):
            if ch == ":" and (i + 1 == len(text) or text[i + 1] in " \t"):
                return text[:i].rstrip(), text[i + 1 :].strip()
            if ch == "#" and i and text[i - 1] in " \t":
                return None
        return None

    def inline(self, i: int, text: str, parent: int) -> tuple[Node, int]:
        no = self.rows[i][2]
        first = text[0]
        if first in "|>":
            return self.block(i, text, parent)
        if first == "&":
            return self.anchored(i, text, parent)
        if first == "*":
            m = ALIAS.fullmatch(text)
            if not m or m.group(1) not in self.anchors:
                raise UnsupportedError(no, "unknown or malformed alias")
            return self.anchors[m.group(1)], i + 1
        if first in "!%@`":
            raise UnsupportedError(no, "tag or reserved indicator")
        if first in "{[":
            return self.flow(i, text)
        if first in "\"'":
            return self.quoted(i, text)
        cut = _comment_at(text)
        body = text if cut < 0 else text[:cut]
        comment = "" if cut < 0 else text[cut + 1 :].strip()
        j = i + 1
        while j < len(self.rows):
            indent, more, _ = self.rows[j]
            if not more:
                j += 1
            elif more.startswith("#") or indent <= parent:
                break
            else:
                body += " " + more
                j += 1
        return Scalar(body.strip(), no, comment), j

    def anchored(self, i: int, text: str, parent: int) -> tuple[Node, int]:
        no = self.rows[i][2]
        m = ANCHOR.fullmatch(text)
        if not m:
            raise UnsupportedError(no, "malformed anchor")
        name, rest = m.group(1), m.group(2).strip()
        if not rest or rest.startswith("#"):
            value, j = self.below(i, parent, same=self.rows[i][0] == parent)
        elif self.key(rest, no) is not None:
            raise UnsupportedError(no, "anchor on a mapping key")
        else:
            value, j = self.inline(i, rest, parent)
        self.anchors[name] = value
        return value, j

    def block(self, i: int, text: str, parent: int) -> tuple[Node, int]:
        lines: list[str] = []
        j = i + 1
        while j < len(self.rows) and (not self.rows[j][1] or self.rows[j][0] > parent):
            lines.append(self.rows[j][1])
            j += 1
        cut = _comment_at(text)
        comment = "" if cut < 0 else text[cut + 1 :].strip()
        return Scalar("\n".join(lines), self.rows[i][2], comment, block=True), j

    def quoted(self, i: int, text: str) -> tuple[Node, int]:
        no, j = self.rows[i][2], i + 1
        while _quoted_end(text, 0) < 0:
            if j >= len(self.rows):
                raise UnsupportedError(no, "unterminated quoted scalar")
            text += " " + self.rows[j][1]
            j += 1
        end = _quoted_end(text, 0)
        tail = text[end + 1 :].strip()
        if tail and not tail.startswith("#"):
            raise UnsupportedError(no, "text after quoted scalar")
        return Scalar(_unquote(text[: end + 1]), no, tail[1:].strip()), j

    def flow(self, i: int, text: str) -> tuple[Node, int]:
        no, j = self.rows[i][2], i + 1
        parts: list[str] = []
        while True:
            cut = _comment_at(text)
            parts.append(text if cut < 0 else text[:cut])
            if _flow_depth(" ".join(parts), no) == 0:
                break
            if j >= len(self.rows):
                raise UnsupportedError(no, "unterminated flow collection")
            text = self.rows[j][1]
            j += 1
        joined = " ".join(parts)
        node, end = _Flow(joined, no, self.anchors).node(0)
        if joined[end:].strip():
            raise UnsupportedError(no, "text after flow collection")
        return node, j


def _documents(text: str) -> list[list[Row]]:
    """Split text into per-document ``(indent, content, line)`` rows."""
    documents: list[list[Row]] = [[]]
    for no, raw in enumerate(re.split(r"\r\n|\r|\n", text.removeprefix("﻿")), 1):
        if raw == "---" or raw.startswith(("--- ", "---\t")):
            tail = raw[3:].strip()
            if tail and not tail.startswith("#"):
                raise UnsupportedError(no, "content after document marker")
            documents.append([])
        elif raw == "..." or raw.startswith("%"):
            continue
        else:
            content = raw.lstrip(" ")
            documents[-1].append((len(raw) - len(content), content.rstrip(" \t"), no))
    return documents


def load_documents(text: str) -> list[Node]:
    """Parse every YAML document in ``text``; raise UnsupportedError when unclear."""
    return [_Reader(rows).document() for rows in _documents(text)]


def _mapping(node: Node) -> dict[str, Node]:
    return cast("dict[str, Node]", node) if isinstance(node, dict) else {}


def _items(node: Node) -> list[Node]:
    return cast("list[Node]", node) if isinstance(node, list) else []


def step_uses(documents: list[Node]) -> list[Scalar]:
    """Return ``uses`` values of jobs and steps in workflows and composite actions."""
    found: list[Scalar] = []

    def take(holder: Node) -> None:
        mapping = _mapping(holder)
        if "uses" in mapping:
            value = mapping["uses"]
            if not isinstance(value, Scalar):
                raise UnsupportedError(getattr(value, "line", 0), "uses is not a string")
            if value.block:
                lines = [row.strip() for row in value.splitlines() if row.strip()]
                if len(lines) != 1:
                    raise UnsupportedError(value.line, "uses block scalar is not one line")
                value = Scalar(lines[0], value.line, value.comment)
            found.append(value)

    def steps(holder: Node) -> None:
        for step in _items(_mapping(holder).get("steps")):
            take(step)

    for doc in documents:
        top = _mapping(doc)
        for job in _mapping(top.get("jobs")).values():
            take(job)
            steps(job)
        steps(top.get("runs"))
    return found


def pin_version(ref: str, note: str) -> str:
    """Return the version a pin names: its ref when a version, else its comment's.

    >>> pin_version("v4", ""), pin_version("a1b2c3", "v4.2.1"), pin_version("main", "")
    ('4', '4.2.1', '')
    >>> pin_version("v4.0.0-rc.1", ""), pin_version("1.75.0", ""), pin_version("a1", "tag=v3.1.0")
    ('4.0.0-rc.1', '1.75.0', '3.1.0')
    """
    if REF_VERSION.match(ref):
        return ref.removeprefix("v")
    m = VERSION.match(note.strip())
    return m.group(1) if m else ""


def _pin(raw: str, note: str, line: int) -> dict[str, str]:
    raw = raw.strip()
    base = {"line": str(line), "uses": raw, "note": note}
    if raw.startswith("./"):
        return {**base, "kind": "local", "action": raw, "ref": "", "version": ""}
    if raw.startswith("docker://"):
        return {**base, "kind": "docker", "action": raw, "ref": "", "version": ""}
    action, _, ref = raw.partition("@")
    version = pin_version(ref, note)
    return {**base, "kind": "action", "action": action, "ref": ref, "version": version}


def parse_uses(line: str) -> dict[str, str] | None:
    """Parse one diff or text line holding ``uses:``; None when it is not one.

    >>> parse_uses("  - uses: actions/checkout@v3")["ref"]
    'v3'
    >>> parse_uses("uses: a/b/sub@abc123 # v1.2.3")["version"]
    '1.2.3'
    >>> parse_uses("uses: ./local")["kind"]
    'local'
    >>> parse_uses("run: echo uses: x") is None
    True
    """
    m = USES.match(line)
    if not m:
        return None
    return _pin(m.group("ref").strip("'\""), (m.group("note") or "").strip(), 0)


def action_repo(action: str) -> str:
    """Return ``owner/repo`` for ``owner/repo/subpath``.

    >>> action_repo("github/codeql-action/init")
    'github/codeql-action'
    """
    return "/".join(action.split("/")[:2])


def unsafe_reason(action: str, ref: str) -> str:
    """Return why an action or ref cannot be written into a command, else ``""``.

    >>> unsafe_reason("actions/checkout", "v4"), unsafe_reason("a/b", "")
    ('', '')
    >>> unsafe_reason("evil/x;touch${IFS}PWNED", "v1")
    'action is not owner/name'
    >>> unsafe_reason("a/b", "v1$(id)")
    'ref is not a plain tag, branch or SHA'
    """
    if not SAFE_ACTION.fullmatch(action) or any(p in {".", ".."} for p in action.split("/")):
        return "action is not owner/name"
    if ref and (not SAFE_REF.fullmatch(ref) or ".." in ref or "//" in ref or ref.endswith("/")):
        return "ref is not a plain tag, branch or SHA"
    return ""


def compare_versions(left: str, right: str) -> str:
    """Compare over the components both versions name: ``lt``, ``eq`` or ``gt``.

    A prerelease sorts below the release it precedes, as in semver.

    >>> compare_versions("4.2.1", "v4.10"), compare_versions("v6", "6.0.1")
    ('lt', 'eq')
    >>> compare_versions("7", "6.9"), compare_versions("v4.0.0-rc.1", "v4")
    ('gt', 'lt')
    >>> compare_versions("4.0.0-rc.2", "4.0.0-rc.10")
    'lt'
    """
    a, apre = _parts(left)
    b, bpre = _parts(right)
    n = min(len(a), len(b))
    if a[:n] != b[:n]:
        return "lt" if a[:n] < b[:n] else "gt"
    if bool(apre) != bool(bpre):
        return "lt" if apre else "gt"
    ka, kb = _pre_key(apre), _pre_key(bpre)
    return "lt" if ka < kb else "gt" if ka > kb else "eq"


def _pre_key(pre: str) -> list[tuple[int, int, str]]:
    return [(0, int(x), "") if x.isdigit() else (1, 0, x) for x in pre.split(".") if x]


def _parts(version: str) -> tuple[list[int], str]:
    m = ANY_VERSION.match(version)
    if not m:
        raise SystemExit(f"not a version: {version}")
    return [int(g) for g in m.groups()[:3] if g is not None], m.group("pre") or ""


def tag_parts(tag: str) -> list[int] | None:
    """Return ``[major, minor, patch]`` parts of a stable tag, with or without ``v``.

    A bare tag needs a dot, so a year-like ``2024`` is not a version.

    >>> tag_parts("v4"), tag_parts("1.75.0"), tag_parts("2024"), tag_parts("v1.2.3-rc.1")
    ([4], [1, 75, 0], None, None)
    """
    m = MAJOR.match(tag)
    if not m or (not m.group(1) and m.group(3) is None):
        return None
    return [int(g) for g in m.groups()[1:] if g is not None]


def first_of_majors(tags: list[str], above: int, upto: int) -> list[str]:
    """Pick the earliest listed tag of each major in (above, upto].

    Prefers the lowest ``vN.x.y``, then ``vN.x``, then the floating ``vN``.

    >>> first_of_majors(["v4.2.2", "v4.0.0", "v5.0.0", "v6.0.0", "v6.1.0"], 3, 5)
    ['v4.0.0', 'v5.0.0']
    >>> first_of_majors(["v4", "v5", "v5.1.0", "v5.0.3"], 3, 5)
    ['v4', 'v5.0.3']
    >>> first_of_majors(["v4.1.0", "v5.0.1"], 3, 5)
    ['v4.1.0', 'v5.0.1']
    """
    found: dict[int, list[tuple[int, int, int, str]]] = {}
    for tag in tags:
        nums = tag_parts(tag)
        if nums is None or not above < nums[0] <= upto:
            continue
        rest = nums[1:]
        found.setdefault(nums[0], []).append(
            (3 - len(nums), rest[0] if rest else 0, rest[1] if len(rest) > 1 else 0, tag)
        )
    return [min(found[n])[3] for n in sorted(found)]


def _major_of(ref: str) -> int:
    return _parts(ref)[0][0]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def _out(*args: str) -> str:
    done = _run(*args)
    if done.returncode:
        sys.stderr.write(done.stderr or f"{args[0]} failed\n")
        raise SystemExit(1)
    return done.stdout


def _remote(path: str) -> str:
    names = _out("git", "-C", path, "remote").split()
    if "origin" in names:
        return "origin"
    if len(names) == 1:
        return names[0]
    raise SystemExit(f"{path}: no origin and {len(names)} remotes; name one")


def _github_slug(url: str) -> str | None:
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url) or any(
        c in url for c in "\\?#"
    ):
        return None
    if "://" in url:
        try:
            parsed = urlsplit(url)
            # urlsplit defers port validation until this property is read.
            _ = parsed.port
        except ValueError:
            return None
        if (
            parsed.scheme not in {"https", "ssh"}
            or parsed.hostname != "github.com"
            or parsed.netloc.count("@") > 1
        ):
            return None
        path = parsed.path.removeprefix("/")
    else:
        match = SCP_REMOTE.fullmatch(url)
        if not match:
            return None
        path = match.group("path")
    slug = path.removesuffix("/").removesuffix(".git")
    if not SLUG.fullmatch(slug) or any(part in {".", ".."} for part in slug.split("/")):
        return None
    return slug


def _slug_from_remote(path: str, remote: str) -> str:
    url = _out("git", "-C", path, "config", "--get-all", f"remote.{remote}.url")
    slug = _github_slug(url.removesuffix("\n"))
    if slug is None:
        raise SystemExit(f"{path}: remote {remote} is not a github.com URL")
    return slug


def _default_branch(slug: str) -> str:
    return _out(
        "gh", "repo", "view", f"https://github.com/{slug}", "--json", "defaultBranchRef",
        "--jq", ".defaultBranchRef.name",
    ).strip()  # fmt: skip


Fetch = Callable[[str], "str | None"]


def _local_files(raw: str) -> list[str] | None:
    """Return candidate files for ``uses: ./path``; None when it leaves the repository."""
    path = posixpath.normpath(raw)
    if path == ".." or path.startswith(("../", "/")):
        return None
    if path.endswith((".yml", ".yaml")):
        return [path]
    return [posixpath.normpath(posixpath.join(path, f"action.{ext}")) for ext in ("yml", "yaml")]


def _scan(files: dict[str, str], fetch: Fetch) -> dict[str, Any]:
    """Parse files, following local composite actions through ``fetch``."""
    texts = dict(files)
    results: dict[str, list[Scalar]] = {}
    unparsed: list[dict[str, object]] = []
    unresolved: list[dict[str, str]] = []
    absent: set[str] = set()
    queue = sorted(texts)
    while queue:
        name = queue.pop(0)
        try:
            results[name] = step_uses(load_documents(texts[name]))
        except UnsupportedError as err:
            unparsed.append({"file": name, "line": err.line, "reason": err.reason})
            continue
        for value in results[name]:
            if not value.startswith("./"):
                continue
            candidates = _local_files(value.strip())
            if candidates is None:
                unresolved.append({"file": name, "uses": value, "reason": "outside repository"})
                continue
            for cand in candidates:
                if cand not in texts and cand not in absent:
                    text = fetch(cand)
                    if text is None:
                        absent.add(cand)
                    else:
                        texts[cand] = text
                        queue.append(cand)
            if not any(c in texts for c in candidates):
                unresolved.append({"file": name, "uses": value, "reason": "no action file found"})
    pins: list[dict[str, str]] = []
    unsafe: list[dict[str, str]] = []
    for name in sorted(results):
        for value in results[name]:
            pin = {"file": name, **_pin(str(value), value.comment, value.line)}
            why = unsafe_reason(pin["action"], pin["ref"]) if pin["kind"] == "action" else ""
            if why:
                unsafe.append(
                    {"file": name, "line": pin["line"], "uses": pin["uses"], "reason": why}
                )
            else:
                pins.append(pin)
    return {
        "files": sorted(texts),
        "quoted_files": {name: shlex.quote(name) for name in sorted(texts)},
        "pins": pins,
        "unparsed": sorted(unparsed, key=lambda u: str(u["file"])),
        "unresolved": unresolved,
        "unsafe": unsafe,
        "complete": not unparsed and not unresolved and not unsafe,
    }


def _clone_fetch(path: str, ref: str) -> Fetch:
    def fetch(name: str) -> str | None:
        done = subprocess.run(
            ["git", "-C", path, "ls-tree", "-z", ref, "--", name],
            capture_output=True,
            check=False,
        )
        if done.returncode:
            sys.stderr.write(done.stderr.decode(errors="replace") or "git ls-tree failed\n")
            raise SystemExit(1)
        for entry in done.stdout.split(b"\0"):
            meta, _, found = entry.partition(b"\t")
            if os.fsdecode(found) == name and meta.split()[1:2] == [b"blob"]:
                return _out("git", "-C", path, "show", f"{ref}:{name}")
        return None

    return fetch


def _read_clone(path: str, ref: str) -> dict[str, str]:
    # Text-mode newline conversion would change CR and CRLF inside filenames.
    done = subprocess.run(
        ["git", "-C", path, "ls-tree", "-r", "-z", "--name-only", ref, ".github"],
        capture_output=True,
        check=False,
    )
    if done.returncode:
        sys.stderr.write(done.stderr.decode(errors="replace") or "git ls-tree failed\n")
        raise SystemExit(1)
    names = (os.fsdecode(name) for name in done.stdout.split(b"\0"))
    return {
        n: _out("git", "-C", path, "show", f"{ref}:{n}") for n in names if WORKFLOW.fullmatch(n)
    }


def _tree_paths(slug: str, tree_sha: str) -> list[str]:
    tree = json.loads(_out(
        "gh", "api", "--hostname", "github.com",
        f"repos/{slug}/git/trees/{tree_sha}?recursive=1",
    ))  # fmt: skip
    if not tree["truncated"]:
        return [
            entry["path"]
            for entry in tree["tree"]
            if entry["type"] == "blob" and WORKFLOW.fullmatch(entry["path"])
        ]

    names: list[str] = []
    pending = [("", tree_sha)]
    while pending:
        prefix, sha = pending.pop()
        subtree = json.loads(_out(
            "gh", "api", "--hostname", "github.com", f"repos/{slug}/git/trees/{sha}",
        ))  # fmt: skip
        if subtree["truncated"]:
            raise SystemExit(f"{slug}: incomplete non-recursive tree {sha}")
        for entry in subtree["tree"]:
            name = prefix + entry["path"]
            if entry["type"] == "blob" and WORKFLOW.fullmatch(name):
                names.append(name)
            elif entry["type"] == "tree" and (
                name in {".github", ".github/workflows", ".github/actions"}
                or name.startswith((".github/workflows/", ".github/actions/"))
            ):
                pending.append((name + "/", entry["sha"]))
    return names


def _slug_fetch(slug: str, commit: str) -> Fetch:
    def fetch(name: str) -> str | None:
        done = _run(
            "gh", "api", "--hostname", "github.com",
            "-H", "Accept: application/vnd.github.raw+json",
            f"repos/{slug}/contents/{quote(name, safe='/')}?ref={commit}",
        )  # fmt: skip
        if done.returncode == 0:
            return done.stdout
        if "HTTP 404" in done.stderr:
            return None
        sys.stderr.write(done.stderr or "gh failed\n")
        raise SystemExit(1)

    return fetch


def _read_slug(slug: str, default: str) -> tuple[dict[str, str], str, str]:
    ref = quote(f"heads/{default}", safe="")
    snapshot = json.loads(_out(
        "gh", "api", "--hostname", "github.com", f"repos/{slug}/commits/{ref}",
    ))  # fmt: skip
    commit, tree = snapshot["sha"], snapshot["commit"]["tree"]["sha"]
    fetch = _slug_fetch(slug, commit)
    files: dict[str, str] = {}
    for name in _tree_paths(slug, tree):
        text = fetch(name)
        if text is None:
            raise SystemExit(f"{slug}: {name} listed in tree {tree} but unreadable")
        files[name] = text
    return files, commit, tree


def inventory(repo: str) -> dict[str, Any]:
    """Inventory one repository by clone path or slug."""
    if Path(repo).is_dir():
        remote = _remote(repo)
        slug = _slug_from_remote(repo, remote)
        _out("git", "-C", repo, "fetch", remote)
        default = _default_branch(slug)
        commit = _out(
            "git", "-C", repo, "rev-parse", "--verify", f"{remote}/{default}^{{commit}}"
        ).strip()
        files = _read_clone(repo, commit)
        fetch = _clone_fetch(repo, commit)
        where: dict[str, object] = {"path": repo, "remote": remote, "commit": commit}
    elif SLUG.fullmatch(repo):
        slug = repo
        default = _default_branch(slug)
        files, commit, tree = _read_slug(slug, default)
        fetch = _slug_fetch(slug, commit)
        where = {"path": None, "commit": commit, "tree": tree}
    else:
        raise SystemExit(f"not a directory or owner/name slug: {repo}")
    configs = [
        n for n in (".github/dependabot.yml", ".github/dependabot.yaml") if fetch(n) is not None
    ]
    return {"slug": slug, "default": default, **where, **_scan(files, fetch), "dependabot": configs}


def _tag_ref(action: str, tag: str) -> tuple[str, str, str]:
    """Return ``exists``, ``missing`` or ``unchecked``, gh's error, and the ref JSON.

    A 404 also answers a repository this login cannot read, so ``missing``
    needs the repository itself to be readable.
    """
    repo = action_repo(action)
    done = _run(
        "gh", "api", "--hostname", "github.com",
        f"repos/{repo}/git/ref/tags/{quote(tag, safe='/')}",
    )  # fmt: skip
    if done.returncode == 0:
        return "exists", "", done.stdout
    err = done.stderr.strip()
    if "HTTP 404" not in err:
        return "unchecked", err, ""
    if _run("gh", "api", "--hostname", "github.com", f"repos/{repo}").returncode == 0:
        return "missing", err, ""
    return "unchecked", f"{err} (repository {repo} is not readable with this login)", ""


def tag_status(action: str, tag: str) -> tuple[str, str]:
    """Return ``exists``, ``missing`` or ``unchecked``, plus gh's error."""
    status, err, _ = _tag_ref(action, tag)
    return status, err


def tag_commit(action: str, tag: str) -> tuple[str, str, str]:
    """Return the tag's status, gh's error, and its commit SHA when it exists.

    An annotated tag points at a tag object; the loop peels it to the commit.
    """
    status, err, body = _tag_ref(action, tag)
    if status != "exists":
        return status, err, ""
    repo = action_repo(action)
    try:
        obj = json.loads(body)["object"]
        for _ in range(5):
            if obj["type"] == "commit":
                return "exists", "", str(obj["sha"])
            if obj["type"] != "tag":
                break
            done = _run(
                "gh", "api", "--hostname", "github.com", f"repos/{repo}/git/tags/{obj['sha']}"
            )
            if done.returncode:
                return "unchecked", done.stderr.strip() or "gh failed", ""
            obj = json.loads(done.stdout)["object"]
    except KeyError, TypeError, ValueError:
        pass
    return "unchecked", "unexpected ref response", ""


def highest_tag(tags: list[str]) -> str:
    """Return the highest stable ``vN[.N[.N]]`` tag, preferring the fuller spelling.

    >>> highest_tag(["v4", "v4.2.2", "v5", "v5.0.0", "v5.0.0-rc.1", "latest", "v3.9.9"])
    'v5.0.0'
    >>> highest_tag(["nightly"])
    ''
    """
    best: tuple[list[int], int, str] | None = None
    for tag in tags:
        parts = tag_parts(tag)
        if parts is None:
            continue
        key = (parts + [0] * (3 - len(parts)), len(parts), tag)
        if best is None or key[:2] > best[:2]:
            best = key
    return best[2] if best else ""


def latest_tag(action: str) -> str:
    """Return the highest stable tag in the repository's full tag list."""
    tags = _out(
        "gh", "api", "--hostname", "github.com", f"repos/{action_repo(action)}/tags",
        "--paginate", "--jq", ".[].name",
    ).split()  # fmt: skip
    return highest_tag(tags)


def majors(action: str, pin: str, target: str) -> tuple[list[str], list[int]]:
    """Return the first tag of each major between pin and target, and majors with none."""
    repo = action_repo(action)
    above, upto = _major_of(pin), _major_of(target)
    tags = _out(
        "gh", "api", "--hostname", "github.com", f"repos/{repo}/tags",
        "--paginate", "--jq", ".[].name",
    ).split()  # fmt: skip
    picked = first_of_majors(tags, above, upto)
    listed = {_major_of(tag) for tag in picked}
    return picked, [n for n in range(above + 1, upto + 1) if n not in listed]


def proposal(slug: str, number: str) -> dict[str, Any]:
    """Return the pin changes a pull request makes and the changed lines that are not pins."""
    diff = _out(
        "gh", "api", "--hostname", "github.com", "-H", "Accept: application/vnd.github.diff",
        f"repos/{slug}/pulls/{number}",
    )  # fmt: skip
    changes: list[dict[str, str]] = []
    files: list[str] = []
    other = 0
    current = ""
    removed: list[str] = []
    added: list[str] = []

    def flush() -> None:
        nonlocal other
        for old, new in zip(removed, added, strict=False):
            was, now = parse_uses(old), parse_uses(new)
            if (
                was
                and now
                and was["action"] == now["action"]
                and was["kind"] == "action"
                and not unsafe_reason(was["action"], was["ref"])
                and not unsafe_reason(now["action"], now["ref"])
            ):
                changes.append(
                    {
                        "file": current,
                        "action": was["action"],
                        "from": was["uses"].partition("@")[2],
                        "to": now["uses"].partition("@")[2],
                        "from_version": was["version"],
                        "to_version": now["version"],
                    }
                )
            else:
                other += 2
        other += abs(len(removed) - len(added))
        removed.clear()
        added.clear()

    in_hunk = False
    for line in diff.split("\n"):
        if line.startswith("diff --git "):
            flush()
            in_hunk = False
        elif not in_hunk and line.startswith("+++ "):
            current = line[4:].removeprefix("b/")
            files.append(current)
        elif line.startswith("@@"):
            flush()
            in_hunk = True
        elif in_hunk and line.startswith("-"):
            removed.append(line[1:])
        elif in_hunk and line.startswith("+"):
            added.append(line[1:])
        elif in_hunk and line.startswith("\\"):
            continue
        else:
            flush()
            if not in_hunk and line.startswith(
                ("rename ", "new file", "deleted file", "old mode", "new mode", "Binary files")
            ):
                other += 1
    flush()
    return {"slug": slug, "number": number, "files": files, "changes": changes, "other": other}


def pulls(slug: str) -> dict[str, Any]:
    """List open Dependabot pull requests; ``blocked`` holds numbers whose title is unsafe."""
    limit = 100
    while True:
        rows = json.loads(_out(
            "gh", "pr", "list", "--repo", slug, "--app", "dependabot", "--state", "open",
            "--limit", str(limit), "--json", "number,title",
        ))  # fmt: skip
        if len(rows) < limit:
            break
        limit *= 2
    prs = [
        {
            "number": row["number"],
            "title": row["title"],
            "safe": not SHELL_SYNTAX.search(row["title"]),
        }
        for row in rows
    ]
    return {"slug": slug, "prs": prs, "blocked": [p["number"] for p in prs if not p["safe"]]}


def pr_state(slug: str, number: str) -> dict[str, str]:
    """Read a pull request's state and URL back from GitHub."""
    data = json.loads(_out(
        "gh", "pr", "view", number, "--repo", slug, "--json", "state,url",
    ))  # fmt: skip
    return {"state": str(data["state"]), "url": str(data["url"])}


def _usage(reason: str) -> int:
    sys.stderr.write(f"{reason}\n{__doc__ or ''}")
    return 2


def main(argv: list[str]) -> int:
    """Run the CLI."""
    cmd, args = (argv[0], argv[1:]) if argv else ("", [])
    if cmd == "inventory" and args:
        for repo in args:
            print(json.dumps(inventory(repo)))
        return 0
    if cmd in {"majors", "tag", "sha", "latest", "proposal", "pulls", "pr-state", "compare"}:
        return _query(cmd, args)
    return _usage("unknown command" if cmd else "no command")


def _query(cmd: str, args: list[str]) -> int:
    count = {"majors": 3, "tag": 2, "sha": 2, "latest": 1, "proposal": 2, "pulls": 1}
    if len(args) != count.get(cmd, 3 if cmd == "pr-state" else 2):
        return _usage(f"{cmd}: wrong number of arguments")
    if cmd in {"majors", "tag", "sha", "latest"} and unsafe_reason(args[0], ""):
        return _usage(f"{cmd}: {args[0]!r} is not owner/name")
    if cmd in {"tag", "sha"} and unsafe_reason(args[0], args[1]):
        return _usage(f"{cmd}: {args[1]!r} is not a plain tag")
    if cmd in {"proposal", "pulls", "pr-state"} and not SLUG.fullmatch(args[0]):
        return _usage(f"{cmd}: {args[0]!r} is not an owner/name slug")
    if cmd in {"proposal", "pr-state"} and not args[1].isdigit():
        return _usage(f"{cmd}: {args[1]!r} is not a number")
    if cmd == "pr-state" and args[2] not in STATES:
        return _usage("pr-state: state is open, closed or merged")
    if cmd == "compare":
        print(compare_versions(args[0], args[1]))
        return 0
    if cmd == "majors":
        picked, missing = majors(args[0], args[1], args[2])
        print("\n".join(picked))
        if missing:
            listed = ", ".join(str(n) for n in missing)
            sys.stderr.write(f"no tag listed for major {listed}; coverage is incomplete\n")
            return EXIT_INCOMPLETE
        return 0
    if cmd == "latest":
        found = latest_tag(args[0])
        if not found:
            sys.stderr.write(f"{args[0]}: no stable vN tag is listed\n")
            return 1
        print(found)
        return 0
    if cmd in {"tag", "sha"}:
        if cmd == "sha":
            status, err, commit = tag_commit(args[0], args[1])
        else:
            (status, err), commit = tag_status(args[0], args[1]), ""
        if status == "unchecked":
            sys.stderr.write(f"could not be checked: {err or 'gh failed'}\n")
            return 3
        print(commit if cmd == "sha" and commit else status)
        return 0 if status == "exists" else 1
    if cmd == "proposal":
        print(json.dumps(proposal(args[0], args[1])))
        return 0
    if cmd == "pulls":
        found_prs = pulls(args[0])
        print(json.dumps(found_prs))
        if found_prs["blocked"]:
            first = found_prs["blocked"][0]
            sys.stderr.write(f"PR #{first} title carries shell syntax; run nothing for it\n")
            return EXIT_UNSAFE
        return 0
    state = pr_state(args[0], args[1])
    print(json.dumps(state))
    if state["state"] != STATES[args[2]]:
        sys.stderr.write(f"PR #{args[1]} is {state['state'].lower()}, not {args[2]}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
