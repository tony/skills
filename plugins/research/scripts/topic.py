#!/usr/bin/env python3
"""Dated research topics with source provenance.

A topic lives in ``<root>/<YYYY-MM-DD>/<namespace>/<topic>/``, one directory per
run. The run's source manifest records what it rests on and is
append-only; cards and ``index.md`` frontmatter are views of it. Without
``--resume``, a run on an earlier date is never written again: a later run
carries its sources forward.

Run ``topic.py <command> --help`` for each command.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import csv
import difflib
import getpass
import hashlib
import html
import http.client
import io
import json
import os
import re
import shutil
import sys
import tempfile
import typing as t
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

if t.TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    Fetch = Callable[[str], tuple[int, str, bytes]]

Row = dict[str, object]

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
AUDIENCES = ("private", "internal", "public")
MODES = ("research", "assessment")
SYSTEM_PROFILES = frozenset({
    "public", "default", "default user", "all users", "defaultuser0", "wsiaccount",
    "wdagutilityaccount",
})  # fmt: skip
REFS = "references"
MANIFEST = REFS + "/sources.jsonl"
CHECKS = REFS + "/checks.jsonl"
RAW_DIR = REFS + "/raw"
STALE_DAYS = 180
SIMILAR_RATIO = 0.75
MIN_CONTAINED = 4
SUMMARY_WORDS = 150
MAX_EM_DASHES = 2
MIN_TITLE_WORDS = 4
USER_AGENT = "topic.py (+https://github.com/tony/skills)"
YAML_WORDS = frozenset({
    "true", "false", "null", "yes", "no", "on", "off", "y", "n", "~", "nan", "infinity",
})  # fmt: skip
RATINGS = {"strong": 3.0, "adequate": 2.0, "weak": 1.0, "unknown": 0.0}
CAPTURE_SUFFIXES = frozenset({
    ".md", ".txt", ".rst", ".json", ".html", ".htm", ".xml", ".csv", ".pdf", ".py", ".c",
    ".h", ".rs", ".go", ".js", ".ts", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".sh",
})  # fmt: skip
TEXT_SUFFIXES = (".md", ".txt", ".rst", ".json", ".html", ".htm")
SCANNED_SUFFIXES = frozenset({".md", ".txt", ".csv", ".svg"})
NOISE_HOSTS = frozenset({
    "w3.org", "img.shields.io", "shields.io", "badge.fury.io", "codecov.io", "coveralls.io",
    "discord.gg", "matrix.to", "twitter.com", "x.com", "gitter.im", "pepy.tech",
})  # fmt: skip
ASSET_SUFFIXES = (".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff2")

LEAKS = (
    ("home-path", re.compile(r"(?:(?<![\w.:/-])|(?<=://)|(?<=:///))/home/[\w.-]+")),
    ("home-path", re.compile(r"(?:(?<![\w.:/-])|(?<=://)|(?<=:///))/Users/[\w.-]+(?: [\w.-]+)?")),
    ("home-path", re.compile(r"/mnt/[a-z]/Users/[\w.-]+", re.IGNORECASE)),
    ("home-path", re.compile(r"\b[A-Za-z]:\\Users\\[^\\\s]+")),
    (
        "home-path",
        re.compile(r"\\\\wsl(?:\.localhost|\$)\\[^\\\s]+\\home\\[^\\\s]+", re.IGNORECASE),
    ),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}\b(?!:)")),
)
TICKET = re.compile(r"\b([A-Z][A-Z0-9]{1,9})-\d+\b")
NOT_TICKETS = frozenset({
    "AES", "ANSI", "ARM", "COVID", "CVE", "CWE", "DDR", "ECMA", "GHSA", "GPT", "HTTP", "IEC",
    "IEEE", "IPV", "ISBN", "ISO", "MD", "PDF", "PEP", "RAID", "RFC", "RSA", "SHA", "SSL", "TLS",
    "UCS", "USB", "UTF", "WCAG", "WPA", "X",
})  # fmt: skip
HTML_ELEMENTS = (
    "a", "abbr", "article", "aside", "audio", "b", "blockquote", "body", "br", "button",
    "caption", "center", "cite", "code", "dd", "del", "details", "div", "dl", "dt", "em",
    "figcaption", "figure", "font", "footer", "form", "h[1-6]", "head", "header", "hr",
    "html", "i", "iframe", "img", "input", "ins", "kbd", "label", "li", "link", "main",
    "mark", "meta", "nav", "noscript", "ol", "option", "p", "path", "picture", "pre", "q",
    "s", "samp", "section", "select", "small", "source", "span", "strong", "sub", "summary",
    "sup", "svg", "table", "tbody", "td", "textarea", "tfoot", "th", "thead", "time",
    "title", "tr", "u", "ul", "var", "video", "wbr",
)  # fmt: skip
# Known elements and custom ones only, so List<String> in a capture is text, not a tag.
HTML_TAG = re.compile(
    r"(?is)<!--.*?-->|<!doctype[^>]*>|</?(?:[a-z][a-z0-9]*-[a-z0-9-]*|"
    + "|".join(HTML_ELEMENTS)
    + r")\b[^<>]*>"
)
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")
CITE_RE = re.compile(r"\[(S\d+)\]")
SLOP_WORDS = (
    "delve", "leverage", "utilize", "facilitate", "empower", "streamline", "robust",
    "seamless", "comprehensive", "cutting-edge", "game changer", "paradigm shift",
    "tapestry", "realm", "beacon", "multifaceted", "meticulous", "paramount",
    "transformative", "elevate", "embark", "supercharge", "pivotal", "testament",
    "it's worth noting", "it is worth noting", "it's important to note",
    "in today's world", "at the end of the day", "let's dive in", "in conclusion",
    "best practices",
)  # fmt: skip
SLOP_PATTERNS = tuple(
    (name, re.compile(pattern, re.IGNORECASE))
    for name, pattern in (
        (
            "binary contrast",
            (
                r"\b(?:isn't|is not|not just)\b[^.]{1,60}\b(?:it's|it is|but)\b"
                r"|\bnot\b[^.,]{1,60},\s+(?:it's|it is)\b"
            ),
        ),
        ("faux insight", r"\b(?:what most people|here's what nobody|the part everyone)\b"),
        (
            "puffery",
            r"\b(?:stands as a testament|marks a pivotal|plays a (?:vital|crucial) role)\b",
        ),
        ("weasel attribution", r"\b(?:experts agree|studies show|many argue|widely regarded)\b"),
        ("recap ending", r"^(?:in conclusion|ultimately|overall)\b"),
    )
)
FAILURES = frozenset({"vanished", "moved", "changed", "misquoted", "unreachable"})
KINDS = ("vendor", "independent", "measured")
BRANCH_REFS = frozenset({"main", "master", "head", "trunk", "develop", "dev", "latest", "stable"})
MOVING_URL = re.compile(
    r"""
      /(?:blob|tree|raw)/(?:main|master|HEAD|trunk|develop)/
    | raw\.githubusercontent\.com/[^/]+/[^/]+/(?:main|master|HEAD)/
    | /(?:latest|stable|current|nightly|dev)/
    | /docs/\d+(?:\.x)?/
    """,
    re.VERBOSE,
)
ABSOLUTES = re.compile(
    r"\b(?:closed|solved|safe|guaranteed|always|never|eliminat\w*|proven|settled)\b", re.IGNORECASE
)
EMOJI = re.compile("[\U0001f300-\U0001faff\u2600-\u27bf]")
MISSING_EVIDENCE = re.compile(r"unsourced|no source|not sourced|untested", re.IGNORECASE)
STOPWORDS = frozenset({
    "that", "this", "with", "from", "have", "were", "they", "their", "there", "than", "then",
    "when", "what", "which", "will", "would", "could", "should", "does", "into", "only", "also",
    "each", "both", "more", "most", "some", "such", "been", "being", "over", "under", "about",
    "after", "before", "while", "because", "these", "those", "other", "every", "same", "very",
})  # fmt: skip
SECTION_ORDER = (
    "summary", "findings", "since", "open questions", "method", "exhibits", "sources",
)  # fmt: skip


class Args(argparse.Namespace):
    """Typed view of every CLI option; options a command lacks keep these defaults."""

    cmd: str = ""
    root: str | None = None
    namespace: str | None = None
    topic: str = ""
    date: str | None = None
    subject: str | None = None
    mode: str | None = None
    audience: str | None = None
    resume: bool = False
    new_topic: bool = False
    run: str = ""
    url: str = ""
    ref: str | None = None
    title: str | None = None
    author: str | None = None
    file: str | None = None
    fetch: bool = False
    quote: list[str] | None = None
    set_quotes: bool = False
    replaces: str | None = None
    source_kind: str | None = None
    pattern: str = ""
    offline: bool = False
    ids: list[str] | None = None
    report: str = ""
    csv: str = ""
    out: str = ""
    kind: str = "bar"
    label: str | None = None
    value: list[str] | None = None
    note: str | None = None
    redact: list[str] | None = None
    include_references: bool = False
    strict: bool = False
    reviewed: bool = False
    write: bool = False
    width: int = 80


# --- names, dates, roots -------------------------------------------------------


def slugify(text: str) -> str:
    """Return a lowercase ``[a-z0-9-]`` path component for ``text``.

    Accents fold to ASCII; text with no Latin letters or digits falls back to a
    hash so two such topics never share a directory.

    Examples
    --------
    >>> slugify("SQLite  WAL_mode!")
    'sqlite-wal-mode'
    >>> slugify("Épée & Co")
    'epee-co'
    >>> slugify("../etc")
    'etc'
    >>> slugify("日本語")
    't-77710a'
    """
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    out = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")[:80].strip("-")
    return out or "t-" + hashlib.sha256(text.encode()).hexdigest()[:6]


def is_date(text: str) -> bool:
    """Whether ``text`` is a real ``YYYY-MM-DD`` date.

    Examples
    --------
    >>> is_date("2026-01-08"), is_date("2026-13-01"), is_date("notes")
    (True, False, False)
    """
    if not DATE_RE.match(text):
        return False
    try:
        _ = date.fromisoformat(text)
    except ValueError:
        return False
    return True


def parse_date(text: str | None, today: date | None = None) -> str:
    """Validate a run date, defaulting to today.

    Examples
    --------
    >>> parse_date(None, date(2026, 2, 3))
    '2026-02-03'
    >>> parse_date("2026-13-01")
    Traceback (most recent call last):
    ...
    ValueError: bad date '2026-13-01', expected YYYY-MM-DD
    """
    if text is None:
        return (today or date.today()).isoformat()  # noqa: DTZ011 - the user's calendar day
    if not is_date(text):
        msg = f"bad date {text!r}, expected YYYY-MM-DD"
        raise ValueError(msg)
    return text


def pick_root(home: Path, wsl_documents: list[Path] | None, hints: Iterable[str] = ()) -> Path:
    """Pick the default root: ``~/Documents``, or the user's Windows Documents on WSL.

    ``wsl_documents`` is None off WSL, else the ``/mnt/c/Users/*/Documents`` matches.
    Service profiles are skipped; among several user profiles, the one named in
    ``hints`` (the Windows user from ``PATH``, the Linux user) wins.

    Examples
    --------
    >>> pick_root(Path("/h/u"), None).as_posix()
    '/h/u/Documents'
    >>> docs = [Path(f"/mnt/c/Users/{u}/Documents") for u in ("Public", "WsiAccount", "tony")]
    >>> pick_root(Path("/h/u"), docs).as_posix()
    '/mnt/c/Users/tony/Documents'
    >>> two = [Path("/mnt/c/Users/a/Documents"), Path("/mnt/c/Users/b/Documents")]
    >>> pick_root(Path("/h/u"), two, hints=["B"]).as_posix()
    '/mnt/c/Users/b/Documents'
    >>> pick_root(Path("/h/u"), two)
    Traceback (most recent call last):
    ...
    ValueError: 2 Windows Documents folders (a, b); pass --root or set RESEARCH_ROOT
    """
    if not wsl_documents:
        return home / "Documents"
    users = [p for p in wsl_documents if p.parent.name.lower() not in SYSTEM_PROFILES]
    wanted = {h.lower() for h in hints}
    named = [p for p in users if p.parent.name.lower() in wanted]
    for group in (users, named):
        if len(group) == 1:
            return group[0]
    names = ", ".join(p.parent.name for p in users)
    msg = f"{len(users)} Windows Documents folders ({names}); pass --root or set RESEARCH_ROOT"
    raise ValueError(msg)


def windows_users(path_env: str) -> list[str]:
    """Windows profile names that appear in a WSL ``PATH``.

    Examples
    --------
    >>> windows_users("/usr/bin:/mnt/c/Users/tony/AppData/Local/Microsoft/WindowsApps")
    ['tony']
    """
    found = re.findall(r"(?:^|:)/mnt/[a-z]/Users/([^/:]+)/", path_env)
    return sorted({str(name) for name in t.cast("list[object]", found)})


def resolve_root(arg: str | None) -> Path:
    """Return ``--root``, else ``RESEARCH_ROOT``, else the detected default (never the temp dir)."""
    explicit = arg or os.environ.get("RESEARCH_ROOT")
    if explicit:
        return Path(explicit).expanduser()
    try:
        wsl = "microsoft" in Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        wsl = False
    found = sorted(Path("/mnt/c/Users").glob("*/Documents")) if wsl else None
    hints = windows_users(os.environ.get("PATH", ""))
    if wsl:
        with contextlib.suppress(KeyError, OSError):  # < 3.13: no login name, no passwd entry
            hints.append(getpass.getuser())
    root = pick_root(Path.home(), found, hints)
    temp = Path(tempfile.gettempdir()).resolve()
    if root.resolve() == temp or temp in root.resolve().parents:
        msg = f"default root {root} is a temp directory; pass --root"
        raise ValueError(msg)
    return root


def now_utc() -> str:
    """Return the current UTC time as ``YYYY-MM-DDTHH:MM:SSZ``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: UP017 - 3.9


# --- files ---------------------------------------------------------------------


def atomic_write(path: Path, data: bytes) -> None:
    """Replace ``path`` so a crash leaves the old file or the new one, never half.

    Examples
    --------
    >>> with tempfile.TemporaryDirectory() as d:
    ...     p = Path(d) / "x"
    ...     atomic_write(p, b"a")
    ...     atomic_write(p, b"b")
    ...     (p.read_bytes(), sorted(q.name for q in Path(d).iterdir()))
    (b'b', ['x'])

    The file keeps its mode, or gets the umask default when new; ``mkstemp``
    alone would leave it owner-only.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as fh:
            _ = fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        Path(tmp).chmod(path.stat().st_mode & 0o7777 if path.exists() else default_mode())
        _ = Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def default_mode() -> int:
    """Mode a new file gets from the process umask."""
    mask = os.umask(0)
    _ = os.umask(mask)
    return 0o666 & ~mask


def dumps(row: Row) -> str:
    """One JSON line, keys sorted so reruns produce identical bytes."""
    return json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"


def append_jsonl(path: Path, rows: Iterable[Row]) -> None:
    """Append rows with one ``write`` each, so concurrent appenders interleave whole lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            _ = fh.write(dumps(row))


def read_jsonl(path: Path) -> list[Row]:
    r"""Read JSON-lines rows, skipping blank and unparsable lines.

    Examples
    --------
    >>> with tempfile.TemporaryDirectory() as d:
    ...     p = Path(d) / "s.jsonl"
    ...     _ = p.write_text('{"id": "S1"}\n\nnot json\n[1]\n', encoding="utf-8")
    ...     read_jsonl(p)
    [{'id': 'S1'}]

    Rows split on newlines only: ``dumps`` writes U+2028 and U+0085 raw, and
    ``str.splitlines`` would cut a row there.

    >>> with tempfile.TemporaryDirectory() as d:
    ...     p = Path(d) / "s.jsonl"
    ...     append_jsonl(p, [{"id": "S1", "title": "a\u2028b"}])
    ...     [r["id"] for r in read_jsonl(p)]
    ['S1']
    """
    if not path.is_file():
        return []
    rows: list[Row] = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        try:
            value = t.cast("object", json.loads(line))
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(t.cast("Row", value))
    return rows


def sha256(data: bytes) -> str:
    """Hex SHA-256 of ``data``."""
    return hashlib.sha256(data).hexdigest()


def link_or_copy(src: Path, dst: Path) -> None:
    """Hard-link ``src`` to ``dst`` where the filesystem allows, else copy it."""
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        _ = shutil.copy2(src, dst)


def _str(row: Row, key: str) -> str:
    value = row.get(key)
    return value if isinstance(value, str) else ""


def _strs(value: object) -> list[str]:
    if isinstance(value, list):
        return [x for x in t.cast("list[object]", value) if isinstance(x, str)]
    return []


# --- frontmatter ---------------------------------------------------------------


def dump_frontmatter(meta: Row) -> str:
    """Render flat frontmatter; anything but a plain word is JSON, which YAML also reads.

    Examples
    --------
    >>> print(dump_frontmatter({"topic": "wal", "title": "A: b", "prior": None, "n": 3}))
    ---
    topic: wal
    title: "A: b"
    prior: null
    n: 3
    ---
    <BLANKLINE>
    """
    lines = ["---"]
    for key, value in meta.items():
        shown = (
            value
            if isinstance(value, str) and is_plain(value)
            else json.dumps(value, ensure_ascii=False)
        )
        lines.append(f"{key}: {shown}")
    return "\n".join([*lines, "---", ""])


def is_plain(value: str) -> bool:
    """Whether ``value`` can be written unquoted and still read back as the same string.

    Examples
    --------
    >>> [is_plain(v) for v in ("2026-01-08", "3.46.0", "sqlite-wal", "SQLite WAL")]
    [True, True, True, True]
    >>> [is_plain(v) for v in ("12", "17.11", "null", "a: b", "@tanstack/query")]
    [False, False, False, False, False]
    >>> [is_plain(v) for v in ("0x1F", "+1", ".5", "a ", "-")]
    [False, False, False, False, False]

    A plain value starts with a letter, an underscore, or a slash, or is a date
    or a version with two dots; YAML reads anything else as another type or not
    at all.
    """
    if value.lower() in YAML_WORDS:
        return False
    word = re.fullmatch(r"[A-Za-z_/](?:[\w ./@+-]*[\w./@+-])?", value)
    return bool(word or re.fullmatch(r"\d{4}-\d{2}-\d{2}|\d+(?:\.\d+){2,}[\w.+-]*", value))


def split_frontmatter(text: str) -> tuple[Row, str]:
    r"""Split ``text`` into frontmatter and body; the inverse of `dump_frontmatter`.

    Examples
    --------
    >>> split_frontmatter('---\ntopic: wal\nredact: ["Jane"]\n---\n# Hi\n')
    ({'topic': 'wal', 'redact': ['Jane']}, '# Hi\n')
    >>> split_frontmatter("# no frontmatter\n")
    ({}, '# no frontmatter\n')
    """
    match = re.match(r"---\r?\n(.*?)\r?\n---\r?\n?", text, re.DOTALL)
    if not match:
        return {}, text
    meta: Row = {}
    for line in match.group(1).split("\n"):
        key, sep, raw = line.partition(":")
        key, raw = key.strip(), raw.strip()
        if not sep or not key or key.startswith("#"):
            continue
        try:
            meta[key] = t.cast("object", json.loads(raw))
        except json.JSONDecodeError:
            meta[key] = raw
    return meta, text[match.end() :]


def read_meta(run: Path) -> Row:
    """Frontmatter of ``run/index.md``; empty when absent."""
    try:
        return split_frontmatter((run / "index.md").read_text(encoding="utf-8"))[0]
    except OSError:
        return {}


# --- runs ----------------------------------------------------------------------


def list_runs(root: Path, namespace: str, topic: str) -> list[tuple[str, Path]]:
    r"""``(date, dir)`` for every run of a topic, newest first.

    Examples
    --------
    A directory without an ``index.md`` is not a run: ``open`` died before writing it.

    >>> with tempfile.TemporaryDirectory() as d:
    ...     for day in ("2026-01-08", "2026-01-15", "notes"):
    ...         run = Path(d) / day / "research" / "wal"
    ...         run.mkdir(parents=True)
    ...         _ = (run / "index.md").write_text("# T\n", encoding="utf-8")
    ...     (Path(d) / "2026-01-20" / "research" / "wal").mkdir(parents=True)
    ...     [day for day, _ in list_runs(Path(d), "research", "wal")]
    ['2026-01-15', '2026-01-08']
    """
    runs = [
        (p.parent.parent.name, p)
        for p in root.glob(f"*/{namespace}/{topic}")
        if (p / "index.md").is_file() and is_date(p.parent.parent.name)
    ]
    return sorted(runs, reverse=True)


def similar_topics(root: Path, namespace: str, topic: str, subject: str | None) -> list[str]:
    """Other topics in ``namespace`` that may be the one meant: a close slug or the same subject.

    Examples
    --------
    >>> with tempfile.TemporaryDirectory() as d:
    ...     for name in ("sqlite-wal", "sqlite-wal-mode", "rust-async"):
    ...         (Path(d) / "2026-01-08" / "research" / name).mkdir(parents=True)
    ...     similar_topics(Path(d), "research", "sqlite-wal-checkpoints", None)
    ['sqlite-wal', 'sqlite-wal-mode']
    """
    found: set[str] = set()
    for run in root.glob(f"*/{namespace}/*"):
        name = run.name
        if name == topic or not run.is_dir() or not is_date(run.parent.parent.name):
            continue
        close = difflib.SequenceMatcher(None, name, topic).ratio() >= SIMILAR_RATIO
        contains = len(name) >= MIN_CONTAINED and (name in topic or topic in name)
        shared = len(set(name.split("-")) & set(topic.split("-"))) >= 2  # noqa: PLR2004
        wanted = (subject or "").lower()
        same = bool(wanted) and _str(read_meta(run), "subject").lower() == wanted
        if close or contains or shared or same:
            found.add(name)
    return sorted(found)


FRAMING = ("Question", "Criteria", "Scope", "Open questions")


def sections(text: str) -> dict[str, str]:
    r"""Bodies of the ``## `` sections in a markdown document, by heading.

    Examples
    --------
    >>> sections("# T\n\n## Question\n\nWhy?\n\n## Log\n\n- x\n")
    {'Question': 'Why?', 'Log': '- x'}
    """
    parts = re.split(r"(?m)^## (.+?)\s*$", text)
    return {parts[k].strip(): parts[k + 1].strip() for k in range(1, len(parts) - 1, 2)}


def framing_from(prior_index: str) -> dict[str, str]:
    r"""Return the prior run's framing to carry: question, criteria, scope, open questions.

    Examples
    --------
    >>> framing_from("## Question\n\nWhy?\n\n## Open questions\n\n- [x] done\n- [ ] NFS?\n")
    {'Question': 'Why?', 'Open questions': '- [ ] NFS?'}
    """
    found = sections(prior_index)
    out = {k: found[k] for k in FRAMING if found.get(k)}
    if "Open questions" in out:
        still = [
            ln for ln in out["Open questions"].splitlines() if not re.match(r"\s*[-*] \[[xX]\]", ln)
        ]
        out["Open questions"] = "\n".join(still).strip()
    return {k: v for k, v in out.items() if v}


def render_index(meta: Row, carried: int, framing: dict[str, str] | None = None) -> str:
    """Render a new ``index.md``: frontmatter, carried framing, and sections to fill in."""
    prior = _str(meta, "prior")
    log = f"- {meta['date']}: opened"
    if prior:
        log += f"; carried {carried} sources from {prior}, re-verification pending"
    if meta.get("mode") == "assessment":
        question = "- Decision:\n- Options:\n- Who decides, by when:\n- What would make it obvious:"
        criteria = "| Criterion | Strong looks like | Weak looks like |\n|---|---|---|\n| | | |"
    else:
        question, criteria = "The question this topic answers.", ""
    body = {
        "Question": question,
        "Criteria": criteria,
        "Scope": "- In:\n- Out:",
        "Open questions": "- [ ] ",
    }
    body.update(framing or {})
    if prior:
        body["Since " + prior] = "What changed since the last run."
    body["Log"] = log
    order = [
        "Question",
        "Criteria",
        "Scope",
        *(["Since " + prior] if prior else []),
        "Open questions",
        "Log",
    ]
    text = "".join(f"\n## {k}\n\n{body[k]}\n" for k in order if body.get(k))
    return dump_frontmatter(meta) + f"\n# {_str(meta, 'subject') or _str(meta, 'topic')}\n{text}"


def carry(prior_run: Path, prior_date: str, run: Path) -> int:
    """Copy the prior run's manifest, captures, and card notes into ``run``.

    Rows keep their ids and ``retrieved``; ``carried_from`` names the run they came
    from. Captures are hard-linked where possible, so each run stays self-contained.
    Sources carry forward, conclusions do not: ``data/`` and the report stay behind.
    """
    rows = read_jsonl(prior_run / MANIFEST)
    if not rows:
        return 0
    out: list[Row] = []
    for row in rows:
        new = {k: v for k, v in row.items() if k != "quote"}
        new.update(carried_from=prior_date, quotes=quotes_of(row))
        out.append(new)
    refs, new_refs = prior_run / REFS, run / REFS
    for row in out:
        if _str(row, "file") and (refs / _str(row, "file")).is_file():
            link_or_copy(refs / _str(row, "file"), new_refs / _str(row, "file"))
    atomic_write(run / MANIFEST, "".join(dumps(r) for r in out).encode())
    latest = latest_by_id(out)
    retired_by = {_str(r, "replaces"): sid for sid, r in latest.items() if _str(r, "replaces")}
    for sid, row in latest.items():
        card = refs / _str(row, "card")
        notes = split_frontmatter(card.read_text(encoding="utf-8"))[1] if card.is_file() else ""
        write_card(run, {**row, "replaced_by": retired_by.get(sid)}, notes)
    return len(current(out))


def append_log(run: Path, line: str) -> None:
    r"""Add ``- line`` at the end of the ``## Log`` section of ``index.md`` unless present.

    Examples
    --------
    >>> with tempfile.TemporaryDirectory() as d:
    ...     _ = (Path(d) / "index.md").write_text("# T\n\n## Log\n\n- a\n\n## Notes\n\nx\n")
    ...     append_log(Path(d), "b")
    ...     print((Path(d) / "index.md").read_text())
    # T
    <BLANKLINE>
    ## Log
    <BLANKLINE>
    - a
    - b
    <BLANKLINE>
    ## Notes
    <BLANKLINE>
    x
    <BLANKLINE>
    """
    index = run / "index.md"
    lines = index.read_text(encoding="utf-8").split("\n") if index.is_file() else []
    entry = f"- {line}"
    if entry in lines:
        return
    head = next((i for i, x in enumerate(lines) if x.strip() == "## Log"), None)
    if head is None:
        body = "\n".join(lines).rstrip("\n")
        atomic_write(index, f"{body}\n\n## Log\n\n{entry}\n".encode())
        return
    end = next((i for i in range(head + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    last = max((i for i in range(head + 1, end) if lines[i].strip()), default=head)
    lines.insert(last + 1, entry)
    if last == head:
        lines.insert(last + 1, "")
    atomic_write(index, ("\n".join(lines).rstrip("\n") + "\n").encode())


def snapshot_report(run: Path) -> None:
    """Keep the report as it stood at the last visit, before a resumed run rewrites it."""
    report = run / "report.md"
    if not report.is_file():
        return
    visits = re.findall(
        r"(?m)^- (\d{4}-\d{2}-\d{2}):", (run / "index.md").read_text(encoding="utf-8")
    )
    last = visits[-1] if visits else run.parent.parent.name
    dest = run / "history" / f"report-{last}.md"
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        _ = shutil.copy2(report, dest)


def csv_rows(text: str) -> list[dict[str, str]]:
    r"""Rows of a CSV as header-to-text dicts; cells beyond the header are dropped.

    Examples
    --------
    >>> csv_rows("criterion,rating,note\nSpeed,strong,slow, but fine\n")
    [{'criterion': 'Speed', 'rating': 'strong', 'note': 'slow'}]

    A short row keeps every header as an empty cell, a leading byte-order mark is
    dropped, and a quoted cell keeps its line breaks.

    >>> csv_rows('\ufeffa,b,c\nx,1\ny,"p\nq",3\n')
    [{'a': 'x', 'b': '1', 'c': ''}, {'a': 'y', 'b': 'p\nq', 'c': '3'}]
    """
    reader = csv.DictReader(io.StringIO(text.removeprefix("\ufeff"), newline=""), restval="")
    rows = t.cast("list[dict[object, object]]", list(reader))
    return [{k: v for k, v in r.items() if isinstance(k, str) and isinstance(v, str)} for r in rows]


def criteria_gaps(run: Path) -> list[str]:
    r"""Criteria in ``data/criteria.csv`` rated unknown or citing no source.

    Examples
    --------
    >>> with tempfile.TemporaryDirectory() as d:
    ...     (Path(d) / "data").mkdir()
    ...     rows = "criterion,rating,sources\nSpeed,strong,S1\nCost,unknown,\nRisk,weak,\n"
    ...     _ = (Path(d) / "data" / "criteria.csv").write_text(rows, encoding="utf-8")
    ...     criteria_gaps(Path(d))
    ['Cost', 'Risk']
    """
    path = run / "data" / "criteria.csv"
    if not path.is_file():
        return []
    table = csv_rows(path.read_text(encoding="utf-8"))
    gaps: list[str] = []
    for r in table:
        cells = [v.strip().lower() for v in r.values() if v]
        if "unknown" in cells or not (r.get("sources") or "").strip():
            gaps.append(r.get("criterion") or "")
    return gaps


def open_result(run: Path, runs: list[tuple[str, Path]], **flags: object) -> Row:
    """Build what ``open`` prints: the run, its earlier runs, and what happened."""
    prior = [{"date": d, "run_dir": str(p)} for d, p in runs if p != run]
    return {"run_dir": str(run), **flags, "prior": prior, "meta": read_meta(run)}


def cmd_open(a: Args) -> int:
    """Open today's run of a topic; a same-day rerun returns the same run unchanged."""
    root = resolve_root(a.root)
    namespace, topic, day = slugify(a.namespace or "research"), slugify(a.topic), parse_date(a.date)
    runs = list_runs(root, namespace, topic)
    if a.resume and runs:
        run = runs[0][1]
        visited = f"- {day}: resumed" in (run / "index.md").read_text(encoding="utf-8")
        if runs[0][0] != day and not visited:
            snapshot_report(run)
            append_log(run, f"{day}: resumed")
        emit(open_result(run, runs, created=False, resumed=True, carried=0))
        return 0
    run = root / day / namespace / topic
    if (run / "index.md").is_file():
        emit(open_result(run, runs, created=False, resumed=False, carried=0))
        return 0
    if not runs and not a.new_topic:
        candidates = similar_topics(root, namespace, topic, a.subject)
        if candidates:
            hint = "rerun with --topic <candidate>, or --new-topic for a separate topic"
            emit({"needs_choice": True, "topic": topic, "candidates": candidates, "hint": hint})
            return 3
    earlier = [(d, p) for d, p in runs if d < day]
    prior_day, prior_run = earlier[0] if earlier else ("", None)
    prior_meta = read_meta(prior_run) if prior_run else {}
    meta: Row = {
        "namespace": namespace,
        "topic": topic,
        "subject": a.subject or _str(prior_meta, "subject") or a.topic,
        "mode": a.mode or _str(prior_meta, "mode") or "research",
        "audience": a.audience or _str(prior_meta, "audience") or "private",
        "date": day,
        "prior": prior_day or None,
    }
    if prior_meta.get("redact"):
        meta["redact"] = prior_meta["redact"]
    run.mkdir(parents=True, exist_ok=True)
    carried = carry(prior_run, prior_day, run) if prior_run else 0
    criteria = prior_run / "data" / "criteria.csv" if prior_run else None
    if criteria and criteria.is_file() and meta["mode"] == "assessment":
        (run / "data").mkdir(parents=True, exist_ok=True)
        _ = shutil.copyfile(criteria, run / "data" / "criteria.csv")
    framing = (
        framing_from((prior_run / "index.md").read_text(encoding="utf-8"))
        if prior_run and (prior_run / "index.md").is_file()
        else {}
    )
    atomic_write(run / "index.md", render_index(meta, carried, framing).encode())
    emit(open_result(run, runs, created=True, resumed=False, carried=carried))
    return 0


def cmd_prior(a: Args) -> int:
    """List a topic's runs, newest first."""
    runs = list_runs(resolve_root(a.root), slugify(a.namespace or "research"), slugify(a.topic))
    emit([{"date": d, "run_dir": str(p)} for d, p in runs])
    return 0


# --- sources -------------------------------------------------------------------


def capture_name(title: str, data: bytes, url: str, suffix: str) -> str:
    """Capture file name: a readable stem, then a hash so versions never clash.

    Examples
    --------
    >>> capture_name("Write-Ahead Logging", b"x", "https://sqlite.org/wal.html", ".html")
    'write-ahead-logging-2d711642.html'
    """
    return f"{_stem(title, url)}-{sha256(data)[:8]}{suffix}"


def _stem(title: str, url: str) -> str:
    return slugify(title or Path(url.split("?", 1)[0].rstrip("/")).name or "source")[:48].strip("-")


CARD_KEYS = (
    "id", "title", "author", "url", "ref", "retrieved", "sha256", "file", "quotes",
    "kind", "carried_from", "replaces", "replaced_by",
)  # fmt: skip
CARD_TEMPLATE = "What this source supports, and where."


def write_card(run: Path, row: Row, notes: str = "") -> None:
    """Write a source's card: frontmatter mirrored from its latest row, then the notes body."""
    meta: Row = {k: row[k] for k in CARD_KEYS if row.get(k) is not None}
    heading = _str(row, "title") or _str(row, "url")
    body = notes or f"\n# {heading}\n\n{CARD_TEMPLATE}\n"
    atomic_write(run / REFS / _str(row, "card"), (dump_frontmatter(meta) + body).encode())


def rewrite_card(run: Path, row: Row, **extra: object) -> None:
    """Refresh a card's frontmatter from ``row``, keeping the notes below it."""
    path = run / REFS / _str(row, "card")
    notes = split_frontmatter(path.read_text(encoding="utf-8"))[1] if path.is_file() else ""
    write_card(run, {**row, **extra}, notes)


def next_id(rows: list[Row]) -> str:
    """Next free ``S<n>`` id.

    Examples
    --------
    >>> next_id([{"id": "S1"}, {"id": "S7"}, {"id": "x"}])
    'S8'
    """
    nums = [int(_str(r, "id")[1:]) for r in rows if re.fullmatch(r"S\d+", _str(r, "id"))]
    return f"S{max(nums, default=0) + 1}"


def quotes_of(row: Row) -> list[str]:
    """Return the quotes a source row records.

    Examples
    --------
    >>> quotes_of({"quotes": ["a", "b"]}), quotes_of({"quote": "a"}), quotes_of({})
    (['a', 'b'], ['a'], [])
    """
    found = _strs(row.get("quotes"))
    return found or ([_str(row, "quote")] if _str(row, "quote") else [])


def merge_quotes(old: list[str], new: list[str]) -> list[str]:
    """``old`` then each new quote not already present, ignoring whitespace and case.

    Examples
    --------
    >>> merge_quotes(["Readers proceed"], ["readers  proceed", "writers append"])
    ['Readers proceed', 'writers append']
    """
    out = list(old)
    seen = {normalize(q) for q in old}
    for q in new:
        if q.strip() and normalize(q) not in seen:
            seen.add(normalize(q))
            out.append(q)
    return out


def latest_by_id(rows: list[Row]) -> dict[str, Row]:
    """Return the newest row of each source id, in order of first appearance.

    Examples
    --------
    >>> rows = [{"id": "S1", "quote": "a"}, {"id": "S2"}, {"id": "S1", "quote": "b"}]
    >>> {k: v.get("quote") for k, v in latest_by_id(rows).items()}
    {'S1': 'b', 'S2': None}
    """
    return {_str(row, "id"): row for row in rows}


def url_key(url: str) -> str:
    """``url`` without its fragment and trailing slash: what names the document.

    Examples
    --------
    >>> url_key("https://a.io/x/#top")
    'https://a.io/x'
    """
    return url.split("#", 1)[0].rstrip("/")


def same_url(a: str, b: str) -> bool:
    """Whether two URLs name the same document, ignoring a fragment and a trailing slash.

    Examples
    --------
    >>> same_url("https://a.io/x/#top", "https://a.io/x"), same_url("https://a.io/x", "https://a.io/y")
    (True, False)
    """
    return url_key(a) == url_key(b)


def current(rows: list[Row]) -> list[Row]:
    """Return the latest version of each source still in use.

    A source drops out when another names it in ``replaces``. Two racing adds of
    one new source mint two ids for the same URL; the first counts.

    Examples
    --------
    >>> rows = [{"id": "S1", "url": "a"}, {"id": "S2", "url": "b", "replaces": "S1"}]
    >>> [r["id"] for r in current(rows)]
    ['S2']
    >>> [r["id"] for r in current([{"id": "S1", "url": "u"}, {"id": "S2", "url": "u"}])]
    ['S1']
    """
    latest = latest_by_id(rows)
    replaced = {_str(r, "replaces") for r in latest.values()}
    seen: set[str] = set()
    out: list[Row] = []
    for sid, row in latest.items():
        key = url_key(_str(row, "url"))
        if sid not in replaced and key not in seen:
            seen.add(key)
            out.append(row)
    return out


def fetch_url(url: str) -> str:
    """URL to download for ``url``: a GitHub blob page maps to its raw file.

    Examples
    --------
    >>> fetch_url("https://github.com/o/r/blob/v1.0/src/x.py#L3-L9")
    'https://raw.githubusercontent.com/o/r/v1.0/src/x.py'
    >>> fetch_url("https://sqlite.org/wal.html")
    'https://sqlite.org/wal.html'
    """
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/blob/([^?#]+)", url)
    return f"https://raw.githubusercontent.com/{m[1]}/{m[2]}/{m[3]}" if m else url


def ascii_url(url: str) -> str:
    """``url`` as ASCII for urllib: an IDNA host, a percent-encoded path and query.

    Examples
    --------
    >>> ascii_url("https://en.wikipedia.org/wiki/Zürich")
    'https://en.wikipedia.org/wiki/Z%C3%BCrich'
    >>> ascii_url("https://a.io/x?q=1%202")
    'https://a.io/x?q=1%202'
    >>> ascii_url("http://[::1]:8080/x")
    'http://[::1]:8080/x'
    """
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname.encode("idna").decode() if parts.hostname else ""
    if ":" in host:
        host = f"[{host}]"
    netloc = host + (f":{parts.port}" if parts.port else "")
    path = urllib.parse.quote(parts.path, safe="/%:@!$&'()*+,;=-._~")
    query = urllib.parse.quote(parts.query, safe="=&%/:@!$'()*+,;?-._~")
    return urllib.parse.urlunsplit((parts.scheme, netloc, path, query, ""))


def http_fetch(url: str) -> tuple[int, str, bytes]:
    """GET ``url``; return ``(status, final_url, body)``, status 0 when unreachable."""
    if not url.startswith(("https://", "http://")):
        return 0, url, b""
    try:
        req = urllib.request.Request(  # noqa: S310
            ascii_url(fetch_url(url)), headers={"User-Agent": USER_AGENT}
        )
        with t.cast("http.client.HTTPResponse", urllib.request.urlopen(req, timeout=20)) as resp:  # noqa: S310
            return resp.status, resp.url or url, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, url, b""
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError):
        return 0, url, b""


def read_capture(a: Args, fetch: Fetch) -> tuple[bytes, str, str] | None:
    """Read the capture ``add`` was given: ``(bytes, suffix, how)``, or None for none."""
    if a.file:
        return Path(a.file).read_bytes(), Path(a.file).suffix or ".txt", "file"
    if not a.fetch:
        return None
    status, _, data = fetch(a.url)
    if status != 200:  # noqa: PLR2004
        msg = f"fetch {a.url} returned {status or 'no response'}"
        raise ValueError(msg)
    return data, url_suffix(fetch_url(a.url)), "fetch"


def url_suffix(url: str) -> str:
    """File extension for a capture from ``url``: a known one from its path, else ``.html``.

    Examples
    --------
    >>> [url_suffix(u) for u in ("https://a.io/x/README.md", "https://a.io/os.html#os.path",
    ...                          "https://a.io/guide/v1.2/", "https://a.io/api?x=1.5")]
    ['.md', '.html', '.html', '.html']
    """
    path = re.split(r"[?#]", url, maxsplit=1)[0].rstrip("/")
    suffix = Path(path.rsplit("/", 1)[-1]).suffix.lower()
    return suffix if suffix in CAPTURE_SUFFIXES else ".html"


VERSION_KEYS = ("ref", "sha256", "capture", "title", "author", "quotes", "replaces", "kind")


def run_dir(arg: str) -> Path:
    """``--run`` as a path, refusing anything that is not a topic run."""
    run = Path(arg)
    if not (run / "index.md").is_file():
        msg = f"{run} is not a run (no index.md); open it first or pass the run directory"
        raise ValueError(msg)
    return run


def cmd_add(a: Args, fetch: Fetch = http_fetch) -> int:
    """Record a source, or a new version of one; an unchanged re-add is a no-op.

    One id per URL. New bytes, a fetched capture of bytes you supplied, a new ref,
    or a corrected title, author, or quote append a version under the same id. A
    re-add without a capture keeps the old one, along with whether it was carried.
    """
    run = run_dir(a.run)
    if not a.url and a.source_kind == "measured" and a.file:
        a.url = f"measured:{measured_name(run, Path(a.file))}"
    if not re.match(r"https?://|measured:", a.url):
        msg = "--url must be http(s); a measured source with --kind measured and --file may omit it"
        raise ValueError(msg)
    rows = read_jsonl(run / MANIFEST)
    ref = a.ref or None
    latest = latest_by_id(rows)
    empty: Row = {}
    matches = (r for r in current(rows) if same_url(_str(r, "url"), a.url))
    prev = next(matches, empty)
    if a.replaces and a.replaces not in latest:
        msg = f"--replaces {a.replaces}: no such source"
        raise ValueError(msg)
    if a.replaces and a.replaces == _str(prev, "id"):
        msg = f"--replaces {a.replaces}: that is this URL's own id; re-add without --replaces"
        raise ValueError(msg)
    got = read_capture(a, fetch)
    row: Row = {
        "id": _str(prev, "id") or next_id(rows),
        "url": a.url,
        "ref": ref or prev.get("ref"),
        "title": a.title or prev.get("title"),
        "author": a.author or prev.get("author"),
        "retrieved": now_utc() if got else prev.get("retrieved", now_utc()),
        "sha256": sha256(got[0]) if got else prev.get("sha256"),
        "capture": got[2] if got else prev.get("capture"),
        "quotes": merge_quotes([] if a.set_quotes else quotes_of(prev), a.quote or []),
        "added": prev.get("added") if prev and not got else _str(read_meta(run), "date") or None,
        "carried_from": prev.get("carried_from") if prev and not got else None,
        "replaces": a.replaces or prev.get("replaces"),
        "kind": a.source_kind or prev.get("kind"),
    }
    data = got[0] if got else None
    if got:
        row["file"] = f"raw/{capture_name(_str(row, 'title'), got[0], a.url, got[1])}"
    elif prev.get("file"):
        row["file"] = prev["file"]
        data = (run / REFS / _str(prev, "file")).read_bytes()
    missing = missing_quotes(quotes_of(row), data) if data is not None else []
    if missing:
        hint = "copy quotes verbatim from the capture"
        if got and prev and not a.set_quotes:
            hint += "; after a new capture, --set-quotes replaces the old quotes"
        msg = f"quote not in the capture of {a.url}: {missing[0]!r}; {hint}"
        raise ValueError(msg)
    if prev and all(prev.get(k) == row.get(k) for k in VERSION_KEYS):
        emit({**prev, "duplicate": True})
        return 0
    row["card"] = _str(prev, "card") or f"{row['id']}-{_stem(_str(row, 'title'), a.url)}.md"
    if got:
        atomic_write(run / REFS / _str(row, "file"), got[0])
    append_jsonl(run / MANIFEST, [row])
    rewrite_card(run, row)
    if a.replaces:
        rewrite_card(run, latest[a.replaces], replaced_by=row["id"])
    version = sum(r.get("id") == row["id"] for r in rows) + 1
    warnings = pin_warnings(a.url, _str(row, "ref") or None)
    warnings += capture_warnings(row, got, prev, read_meta(run))
    emit({**row, "duplicate": False, "version": version, "warnings": warnings})
    return 0


def measured_name(run: Path, path: Path) -> str:
    """Name of a measured source: its path inside the run, else its file name.

    Examples
    --------
    >>> measured_name(Path("/r"), Path("/r/data/a/result.txt"))
    'data/a/result.txt'
    >>> measured_name(Path("/r"), Path("/elsewhere/result.txt"))
    'result.txt'
    """
    try:
        return path.resolve().relative_to(run.resolve()).as_posix()
    except ValueError:
        return path.name


def pin_warnings(url: str, ref: str | None) -> list[str]:
    """Warnings for a source pinned to something that moves.

    Examples
    --------
    >>> pin_warnings("https://github.com/o/r/blob/main/x.py", None)[0][:22]
    'the URL is a moving al'
    >>> pin_warnings("https://www.postgresql.org/docs/17/wal.html", "17.6")
    []
    >>> len(pin_warnings("https://www.postgresql.org/docs/17/wal.html", "17"))
    1
    >>> pin_warnings("https://a.io/x", "main")
    ['ref main is a branch name; pin a tag, commit, or version']
    """
    out: list[str] = []
    if ref and ref.lower() in BRANCH_REFS:
        out.append(f"ref {ref} is a branch name; pin a tag, commit, or version")
    exact = re.fullmatch(r"v?\d+(?:\.\d+)+\S*|[0-9a-f]{7,40}", ref or "") is not None
    if MOVING_URL.search(url) and not exact:
        out.append("the URL is a moving alias; record the exact version the page states as --ref")
    return out


def capture_warnings(
    row: Row, got: tuple[bytes, str, str] | None, prev: Row, meta: Row
) -> list[str]:
    """Warnings about how a source was captured and typed."""
    out: list[str] = []
    if got and got[2] == "file" and not prev and not _str(row, "url").startswith("measured:"):
        out.append("you supplied this capture; make sure it is what the URL serves, or use --fetch")
    if not got and not row.get("sha256"):
        out.append("no capture: verify can only check the URL, never the claim")
    if meta.get("mode") == "assessment" and not row.get("kind"):
        out.append("no --kind; an assessment caps confidence by the kind of evidence")
    return out


# --- status --------------------------------------------------------------------


def days_between(start: str, end: str) -> int | None:
    """Days from ``start`` to ``end`` (ISO dates), None when either is not a date."""
    try:
        return (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days
    except ValueError:
        return None


def source_states(run: Path, today: str) -> dict[str, str]:
    """State of each current source: fresh, verified, intact, unverified, stale, or a check status.

    Fresh sources were added in this run; carried ones stay unverified until a
    check in this run passes, and turn stale past ``STALE_DAYS``. A check counts
    only for the version it tested; verified needs a live check, an offline
    one leaves the source intact.
    """
    checks = {_str(c, "id"): c for c in read_jsonl(run / CHECKS)}
    states: dict[str, str] = {}
    for row in current(read_jsonl(run / MANIFEST)):
        sid, last = _str(row, "id"), checks.get(_str(row, "id"), {})
        check = _str(last, "status") if last.get("version") == version_key(row) else ""
        age = days_between(_str(row, "retrieved"), today)
        if check == "ok":
            states[sid] = "verified" if last.get("live") else "intact"
        elif check:
            states[sid] = check
        elif age is not None and age > STALE_DAYS:
            states[sid] = "stale"
        else:
            states[sid] = "unverified" if row.get("carried_from") else "fresh"
    return states


def unannotated(run: Path) -> int:
    """Count current sources whose card still holds the template instead of notes."""
    count = 0
    for row in current(read_jsonl(run / MANIFEST)):
        card = run / REFS / _str(row, "card")
        if (
            _str(row, "card")
            and card.is_file()
            and CARD_TEMPLATE in card.read_text(encoding="utf-8")
        ):
            count += 1
    return count


def open_questions(run: Path) -> list[str]:
    r"""Unchecked items under ``## Open questions`` in index.md.

    Examples
    --------
    >>> with tempfile.TemporaryDirectory() as d:
    ...     _ = (Path(d) / "index.md").write_text(
    ...         "## Open questions\n\n- [ ] Does WAL survive NFS?\n- [x] Done\n- [ ] \n\n## Log\n",
    ...         encoding="utf-8")
    ...     open_questions(Path(d))
    ['Does WAL survive NFS?']
    """
    try:
        text = (run / "index.md").read_text(encoding="utf-8")
    except OSError:
        return []
    section = re.search(r"^## Open questions\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if not section:
        return []
    items = re.findall(r"^\s*[-*] \[ \] (.+?)\s*$", section[1], re.MULTILINE)
    return [str(i) for i in t.cast("list[object]", items)]


def cmd_status(a: Args) -> int:
    """Every topic under the root: latest run, sources by state, open questions."""
    root = resolve_root(a.root)
    today = parse_date(a.date)
    topics: dict[tuple[str, str], list[tuple[str, Path]]] = {}
    days = [d for d in root.iterdir() if d.is_dir() and is_date(d.name)] if root.is_dir() else []
    for run in (r for day in days for r in day.glob("*/*")):
        ns = run.parent.name
        managed = (run / "index.md").is_file() and not run.name.startswith((".", "_"))
        if managed and (a.namespace is None or slugify(a.namespace) == ns):
            topics.setdefault((ns, run.name), []).append((run.parent.parent.name, run))
    out: list[Row] = []
    for (ns, topic), runs in sorted(topics.items()):
        day, run = max(runs)
        meta = read_meta(run)
        counts: dict[str, int] = {}
        for state in source_states(run, today).values():
            counts[state] = counts.get(state, 0) + 1
        out.append({
            "namespace": ns, "topic": topic, "latest": day,
            "runs": sorted((d for d, _ in runs), reverse=True), "run_dir": str(run),
            "mode": meta.get("mode"), "subject": meta.get("subject"), "sources": counts,
            "open_questions": open_questions(run), "report": (run / "report.md").is_file(),
            "cards_without_notes": unannotated(run),
            "criteria_gaps": criteria_gaps(run),
            "moving_pins": sorted(
                _str(r, "id") for r in current(read_jsonl(run / MANIFEST))
                if pin_warnings(_str(r, "url"), _str(r, "ref") or None)
            ),
        })  # fmt: skip
    emit({"root": str(root), "topics": out})
    return 0


# --- privacy -------------------------------------------------------------------


def scan_text(
    text: str, audience: str, redact: list[str], home: str = ""
) -> list[tuple[int, str, str]]:
    r"""``(line, kind, match)`` for each leak in ``text`` at an audience.

    Examples
    --------
    >>> scan_text("see /home/tony/x and a@b.io", "private", [])
    [(1, 'home-path', '/home/tony'), (1, 'email', 'a@b.io')]
    >>> scan_text("https://example.com/home/about git@github.com:o/r.git", "public", [])
    []
    >>> scan_text(r"\\wsl$\Ubuntu\home\bob\notes", "private", [])
    [(1, 'home-path', '\\\\wsl$\\Ubuntu\\home\\bob')]
    >>> scan_text("Jane Doe filed ABC-123", "internal", ["Jane Doe"])
    [(1, 'name', 'Jane Doe')]
    >>> scan_text("Jane Doe filed ABC-123", "public", ["Jane Doe"])
    [(1, 'name', 'Jane Doe'), (1, 'ticket', 'ABC-123')]
    >>> scan_text("GPT-4 on RAID-5", "public", [])
    []
    """
    found: list[tuple[int, str, str]] = []
    in_fence = False
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        hits = [(n, kind, m[0].rstrip()) for kind, pat in LEAKS for m in pat.finditer(line)]
        if len(home) > 1 and home in line and not hits:
            hits.append((n, "home-path", home))
        if audience in ("internal", "public"):
            hits.extend((n, "name", name) for name in redact if name and _has_word(line, name))
        if audience == "public" and not in_fence:
            hits.extend(
                (n, "ticket", m[0]) for m in TICKET.finditer(line) if m[1] not in NOT_TICKETS
            )
        found.extend(hits)
    return found


def audience_of(meta: Row, arg: str | None) -> str:
    """Return ``--audience``, else the run's audience; an unknown value counts as public.

    Examples
    --------
    >>> [audience_of(m, None) for m in ({"audience": "internal"}, {}, {"audience": "pubic"})]
    ['internal', 'private', 'public']
    """
    value = arg or _str(meta, "audience") or "private"
    return value if value in AUDIENCES else "public"


def _has_word(line: str, word: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", line, re.IGNORECASE) is not None


def hide_redact(text: str) -> str:
    r"""Blank the ``redact:`` line of the frontmatter, so the list does not flag itself.

    Examples
    --------
    >>> hide_redact('---\nredact: ["Jane"]\n---\nredact: Jane\n')
    '---\n\n---\nredact: Jane\n'
    """
    head = re.match(r"---\r?\n.*?\r?\n---", text, re.DOTALL)
    if not head:
        return text
    return re.sub(r"(?m)^redact: .*$", "", head[0]) + text[head.end() :]


def cmd_scan(a: Args) -> int:
    """Scan the text files a run ships at its audience; exit 1 when it must not ship.

    Source cards under ``references/`` and report snapshots under ``history/`` are
    working material, skipped unless ``--include-references`` is given; ``raw/``
    is never scanned.
    """
    run = run_dir(a.run)
    meta = read_meta(run)
    audience = audience_of(meta, a.audience)
    redact = _strs(meta.get("redact")) + list(a.redact or [])
    findings: list[Row] = []
    for path in sorted(p for p in run.rglob("*") if p.suffix in SCANNED_SUFFIXES):
        rel = path.relative_to(run)
        working = rel.parts[0] in (REFS, "history")
        if "raw" in rel.parts[:-1] or (working and not a.include_references):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if rel.as_posix() == "index.md":
            text = hide_redact(text)
        findings.extend(
            {"file": rel.as_posix(), "line": line, "kind": kind, "match": match}
            for line, kind, match in scan_text(text, audience, redact, str(Path.home()))
        )
    emit({"audience": audience, "findings": findings})
    return 1 if findings else 0


# --- verify --------------------------------------------------------------------


def plain_of(data: bytes) -> str:
    r"""Readable text of a capture, case kept: HTML tags stripped, entities decoded, spacing folded.

    Examples
    --------
    >>> plain_of(b"<p>Readers  proceed&nbsp;while <code>a writer</code> appends.</p>")
    'Readers proceed while a writer appends.'
    >>> plain_of(b"numpy; python_full_version < '3.11'")
    "numpy; python_full_version < '3.11'"
    >>> plain_of(b'<p align="center">Logo</p>\nUse List<String> when a < b && c > d.')
    'Logo Use List<String> when a < b && c > d.'
    """
    raw = data.decode("utf-8", errors="replace")
    if not re.search(r"(?i)<(?:!doctype|html|body|p|div|span|a)[\s>]", raw[:4096]):
        return plain(raw)
    raw = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw)
    return plain(html.unescape(HTML_TAG.sub(" ", raw)))


def text_of(data: bytes) -> str:
    """Searchable text of a capture: `plain_of`, case folded."""
    return plain_of(data).lower()


def plain(text: str) -> str:
    r"""Drop markdown code and emphasis marks and fold spacing, including before punctuation.

    Examples
    --------
    >>> plain("Use `uv.lock` ,\n  **now** ( soon ) .")
    'Use uv.lock, now (soon).'
    """
    text = re.sub(r"\s+", " ", re.sub(r"[`*]", "", text))
    return re.sub(r"\s+([.,;:!?)\]])", r"\1", re.sub(r"([(\[])\s+", r"\1", text)).strip()


def normalize(text: str) -> str:
    """Fold a quote or capture for matching: `plain`, case folded."""
    return plain(text).lower()


def missing_quotes(quotes: list[str], data: bytes) -> list[str]:
    """Return the quotes that do not appear in ``data`` once both are normalized."""
    text = text_of(data)
    return [q for q in quotes if normalize(q) not in text]


def check_capture(run: Path, row: Row) -> tuple[str, str, bytes | None]:
    """Offline check of a source's capture: ``(status, detail, bytes)``."""
    rel = _str(row, "file")
    if not rel:
        return "unchecked", "no capture to check offline", None
    path = run / REFS / rel
    if not path.is_file():
        return "vanished", f"capture {rel} missing", None
    data = path.read_bytes()
    if sha256(data) != row.get("sha256"):
        return "changed", "capture bytes differ from the recorded sha256", data
    missing = missing_quotes(quotes_of(row), data)
    if missing:
        return "misquoted", f"not in the capture: {missing[0]!r}", data
    return "ok", "capture intact", data


def check_live(row: Row, fetch: Fetch) -> tuple[str, str, Row]:
    """Online check of a source's URL: ``(status, detail, extra fields)``."""
    url = _str(row, "url")
    status, final, body = fetch(url)
    extra: Row = {"http": status}
    if status in (404, 410):
        return "vanished", f"HTTP {status}", extra
    if status == 0 or status >= 400:  # noqa: PLR2004
        return (
            "unreachable",
            f"HTTP {status}" if status else "no response (offline, DNS, or timeout)",
            extra,
        )
    if ascii_url(final).rstrip("/") != ascii_url(fetch_url(url)).rstrip("/"):
        return "moved", "redirected", {**extra, "final_url": final}
    if row.get("capture") == "fetch" and sha256(body) != row.get("sha256"):
        return (
            "changed",
            "live bytes differ from the capture",
            {**extra, "live_sha256": sha256(body)},
        )
    missing = missing_quotes(quotes_of(row), body)
    if missing:
        return "misquoted", f"not on the live page: {missing[0]!r}", extra
    return "ok", "live", extra


def version_key(row: Row) -> str:
    """Short hash of what a check tests: the url, ref, capture hash, and quotes.

    Examples
    --------
    >>> a = {"url": "u", "sha256": "x", "quotes": ["q"]}
    >>> version_key(a) == version_key({**a, "title": "t"})
    True
    >>> version_key(a) == version_key({**a, "quotes": []})
    False
    """
    parts = [_str(row, "url"), _str(row, "ref"), _str(row, "sha256"), *quotes_of(row)]
    return sha256(json.dumps(parts).encode())[:12]


def check_source(run: Path, row: Row, fetch: Fetch | None) -> Row:
    """Check one source offline, then live when ``fetch`` is given; the first failure wins."""
    status, detail, _ = check_capture(run, row)
    extra: Row = {}
    measured = _str(row, "url").startswith("measured:")
    if status in ("ok", "unchecked") and fetch is not None and not measured:
        status, detail, extra = check_live(row, fetch)
    head: Row = {"id": _str(row, "id"), "version": version_key(row), "checked": now_utc()}
    head.update(url=_str(row, "url"), live=fetch is not None or measured)
    return {**head, "status": status, "detail": detail, **extra}


def check_all(run: Path, rows: list[Row], fetch: Fetch | None) -> list[Row]:
    """Check sources in manifest order: hosts in parallel, one request at a time per host.

    Serial per host keeps a run with many sources on one site from tripping its rate
    limit, which would report reachable pages as unreachable.
    """
    by_host: dict[str, list[int]] = {}
    for i, row in enumerate(rows):
        by_host.setdefault(host(_str(row, "url")), []).append(i)
    results: list[Row] = [{} for _ in rows]

    def work(indexes: list[int]) -> None:
        for i in indexes:
            results[i] = check_source(run, rows[i], fetch)

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(by_host) or 1)) as pool:
        _ = list(pool.map(work, by_host.values()))
    return results


def cmd_verify(a: Args, fetch: Fetch = http_fetch) -> int:
    """Check a run's current sources and append the results to checks.jsonl."""
    run = run_dir(a.run)
    wanted = set(a.ids or [])
    every = current(read_jsonl(run / MANIFEST))
    unknown = sorted(wanted - {_str(r, "id") for r in every})
    if unknown:
        msg = f"--id {', '.join(unknown)}: no current source with that id"
        raise ValueError(msg)
    rows = [r for r in every if not wanted or _str(r, "id") in wanted]
    results = check_all(run, rows, None if a.offline else fetch)
    append_jsonl(run / CHECKS, results)
    counts: dict[str, int] = {}
    for r in results:
        counts[_str(r, "status")] = counts.get(_str(r, "status"), 0) + 1
    failures = [r for r in results if r.get("status") in FAILURES]
    emit({"checked": len(results), "counts": counts, "failures": failures})
    return 1 if failures else 0


def urls_in(path: Path) -> list[str]:
    r"""Outbound URLs in a capture or card; HTML contributes only link targets.

    Examples
    --------
    >>> with tempfile.TemporaryDirectory() as d:
    ...     page = Path(d) / "p.html"
    ...     _ = page.write_text('<svg xmlns="http://www.w3.org/2000/svg"/><a href="https://a.io/x">x</a>')
    ...     urls_in(page)
    ['https://a.io/x']
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix in (".html", ".htm"):
        found = [html.unescape(m[1]) for m in re.finditer(r"""href=["'](https?://[^"'#]+)""", text)]
    else:
        found = [m[0] for m in URL_RE.finditer(text)]
    out: list[str] = []
    for url in found:
        clean = url.rstrip(".,;:").split("#", 1)[0]
        host = re.sub(r"^https?://(www\.)?", "", clean).split("/", 1)[0].lower()
        asset = clean.lower().split("?", 1)[0].endswith(ASSET_SUFFIXES)
        if not asset and host not in NOISE_HOSTS:
            out.append(clean)
    return out


def host(url: str) -> str:
    """Lowercase host of ``url`` without ``www.``.

    Examples
    --------
    >>> host("https://www.GitHub.com/features"), host("measured:x.log")
    ('github.com', '')
    """
    m = re.match(r"https?://(?:www\.)?([^/:]+)", url, re.IGNORECASE)
    return m[1].lower() if m else ""


def cmd_links(a: Args) -> int:
    """URLs that captures and cards mention but the manifest lacks: leads for missed sources."""
    run = run_dir(a.run)
    rows = read_jsonl(run / MANIFEST)
    known = {url_key(_str(r, "url")) for r in rows}
    host_of = {_str(r, "file"): host(_str(r, "url")) for r in rows if _str(r, "file")}
    seen: dict[str, int] = {}
    for path in sorted((run / REFS).rglob("*")):
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            own = host_of.get(path.relative_to(run / REFS).as_posix(), "")
            for url in urls_in(path):
                path_part = url.split("://", 1)[-1].rstrip("/").partition("/")[2]
                chrome = host(url) == own and "/" not in path_part and "." not in path_part
                if url_key(url) not in known and not chrome:
                    seen[url] = seen.get(url, 0) + 1
    ranked = sorted(seen.items(), key=lambda kv: (-kv[1], kv[0]))
    emit([{"url": u, "mentions": n} for u, n in ranked])
    return 0


def find_in(text: str, needle: str, width: int = 80) -> list[str]:
    """Snippets of ``text`` around each match of ``needle``, in the text's own case.

    Examples
    --------
    >>> find_in("Readers proceed while A Writer appends", "a writer", width=8)
    ['…d while A Writer appends']
    """
    text = plain(text)
    hay, pin = text.lower(), normalize(needle)
    out: list[str] = []
    start = hay.find(pin)
    while start != -1 and pin:
        lo, hi = max(0, start - width), start + len(pin) + width
        out.append(("…" if lo else "") + text[lo:hi] + ("…" if hi < len(hay) else ""))
        start = hay.find(pin, start + len(pin))
    return out


def cmd_find(a: Args) -> int:
    """Search the run's captures for text: to find a quote, or which sources mention a term."""
    run = run_dir(a.run)
    hits: list[Row] = []
    for row in current(read_jsonl(run / MANIFEST)):
        path = run / REFS / _str(row, "file")
        if _str(row, "file") and path.is_file():
            snippets = find_in(plain_of(path.read_bytes()), a.pattern, a.width)
            if snippets:
                hits.append(
                    {"id": _str(row, "id"), "title": row.get("title"), "snippets": snippets[:5]}
                )
    emit(hits)
    return 0


# --- reports -------------------------------------------------------------------


def sources_table(rows: list[Row], states: dict[str, str]) -> str:
    """Markdown table of current sources for a report's Sources section.

    Examples
    --------
    >>> row = {"id": "S1", "title": "WAL", "author": "SQLite", "url": "https://x.io/wal",
    ...        "ref": "3.46.0", "retrieved": "2026-01-08T10:00:00Z", "capture": "fetch"}
    >>> print(sources_table([row], {"S1": "verified"}).splitlines()[2])
    | S1 | [WAL](https://x.io/wal) | SQLite |  | 3.46.0 | 2026-01-08 | fetched | verified |
    """
    captures = {"fetch": "fetched", "file": "provided"}
    head = "| Id | Source | Author | Kind | Ref | Retrieved | Capture | Check |"
    lines = [head, "|---|---|---|---|---|---|---|---|"]
    for r in current(rows):
        title = (_str(r, "title") or _str(r, "url")).replace("|", "\\|")
        cells = [
            _str(r, "id"),
            title if _str(r, "url").startswith("measured:") else f"[{title}]({_str(r, 'url')})",
            _str(r, "author").replace("|", "\\|"),
            _str(r, "kind"),
            _str(r, "ref"),
            _str(r, "retrieved")[:10],
            captures.get(_str(r, "capture"), "none"),
            states.get(_str(r, "id"), "unchecked"),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join([*lines, ""])


def cmd_sources(a: Args) -> int:
    """Print the run's current sources as a markdown table; --write puts it under ## Sources."""
    run = run_dir(a.run)
    table = sources_table(read_jsonl(run / MANIFEST), source_states(run, parse_date(None)))
    if a.write:
        report = run / "report.md"
        text = report.read_text(encoding="utf-8")
        if not re.search(r"(?m)^## Sources\s*$", text):
            msg = f"{report} has no ## Sources section"
            raise ValueError(msg)
        text = re.sub(
            r"(?ms)^## Sources\s*$.*?(?=^## |\Z)", lambda _m: f"## Sources\n\n{table}\n", text
        )
        atomic_write(report, text.rstrip("\n").encode() + b"\n")
    print(table, end="")
    return 0


def claim_lines(text: str, rows: list[Row]) -> Row:
    r"""Each line of ``text`` that cites a source, and each cited source's quotes once.

    Examples
    --------
    >>> rows = [{"id": "S1", "title": "WAL", "quotes": ["readers do not block writers"]}]
    >>> out = claim_lines("# T\n\nReaders never wait [S1].\n", rows)
    >>> out["lines"]
    [{'line': 3, 'text': 'Readers never wait [S1].', 'cites': ['S1']}]
    >>> out["quotes"]
    {'S1': ['readers do not block writers']}
    """
    by_id = {_str(r, "id"): r for r in current(rows)}
    lines: list[Row] = []
    quotes: dict[str, list[str]] = {}
    for n, line in enumerate(strip_fences(text).splitlines(), 1):
        ids = list(dict.fromkeys(m[1] for m in CITE_RE.finditer(line)))
        if ids:
            lines.append({"line": n, "text": line.strip(), "cites": ids})
            for sid in ids:
                if sid not in quotes:
                    quotes[sid] = quotes_of(by_id.get(sid, {}))
    return {"lines": lines, "quotes": quotes}


def cmd_claims(a: Args) -> int:
    """List every cited claim beside its sources' quotes; --reviewed logs that you checked them."""
    report = Path(a.report)
    rows = read_jsonl(report.parent / MANIFEST)
    out = claim_lines(report.read_text(encoding="utf-8"), rows)
    lines = t.cast("list[Row]", out["lines"])
    if a.reviewed:
        stamp = sha256(report.read_bytes())[:8]
        count = f"{len(lines)} cited line{'' if len(lines) == 1 else 's'}"
        index = report.parent / "index.md"
        earlier = rf"(?m)^- \S+: reviewed \d+ cited lines? in {re.escape(report.name)} \(\w+\)\n"
        atomic_write(index, re.sub(earlier, "", index.read_text(encoding="utf-8")).encode())
        append_log(
            report.parent, f"{parse_date(None)}: reviewed {count} in {report.name} ({stamp})"
        )
    emit(out)
    return 0


def claims_reviewed(report: Path) -> bool:
    """Whether index.md logs a claims review of this exact version of ``report``."""
    stamp = sha256(report.read_bytes())[:8]
    index = report.parent / "index.md"
    return index.is_file() and f"in {report.name} ({stamp})" in index.read_text(encoding="utf-8")


def headings(text: str) -> list[tuple[int, int, str]]:
    r"""``(line, level, title)`` for each ATX heading outside fenced code.

    Examples
    --------
    >>> headings("# A\n```\n# not\n```\n## B\n")
    [(1, 1, 'A'), (5, 2, 'B')]
    """
    out: list[tuple[int, int, str]] = []
    for n, line in enumerate(strip_fences(text).splitlines(), 1):
        m = re.match(r"(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if m:
            out.append((n, len(m[1]), m[2]))
    return out


def strip_fences(text: str) -> str:
    """``text`` with fenced code blanked out, line numbers kept."""
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        fence = line.lstrip().startswith(("```", "~~~"))
        out.append("" if fence or in_fence else line)
        in_fence ^= fence
    return "\n".join(out)


def section_key(title: str) -> str:
    """Canonical name of a report section, empty for sections outside the standard.

    Examples
    --------
    >>> section_key("Since 2026-01-08"), section_key("Open questions"), section_key("Notes")
    ('since', 'open questions', '')
    """
    low = title.lower()
    return next((k for k in SECTION_ORDER if low == k or low.startswith(f"{k} ")), "")


def lint_structure(text: str) -> list[Row]:
    r"""Shape findings: answer title, summary first, standard order, takeaway headings.

    Examples
    --------
    >>> [f["rule"] for f in lint_structure("# Report\n\n## Notes\n\nx\n")]
    ['title-answer', 'summary-first', 'missing-section']
    """
    found: list[Row] = []
    heads = headings(text)
    lines = text.splitlines()
    h1 = [(n, s) for n, level, s in heads if level == 1]
    h2 = [(n, s) for n, level, s in heads if level == 2]  # noqa: PLR2004
    if not h1:
        found.append(_finding("error", "title", 1, "no '# ' title; state the answer in it"))
    elif ABSOLUTES.search(h1[0][1]):
        detail = f"'{h1[0][1]}' makes an absolute claim; check it against the findings"
        found.append(_finding("warn", "title-absolute", h1[0][0], detail))
    if h1 and len(h1[0][1].split()) < MIN_TITLE_WORDS:
        detail = f"'{h1[0][1]}' names the subject; make the title the answer"
        found.append(_finding("warn", "title-answer", h1[0][0], detail))
    keys = [(n, section_key(s)) for n, s in h2]
    if not keys or keys[0][1] != "summary":
        detail = "the first '## ' section must be Summary"
        found.append(_finding("error", "summary-first", keys[0][0] if keys else 1, detail))
    ranks = [(n, SECTION_ORDER.index(k)) for n, k in keys if k]
    for i in range(1, len(ranks)):
        if ranks[i][1] < ranks[i - 1][1]:
            order = " > ".join(SECTION_ORDER)
            found.append(_finding("error", "section-order", ranks[i][0], f"order is {order}"))
    if "findings" not in {k for _, k in keys}:
        found.append(_finding("error", "missing-section", 1, "no '## Findings' section"))
    at = next((i for i, (_, k) in enumerate(keys) if k == "summary"), None)
    if at is not None:
        start, end = keys[at][0], keys[at + 1][0] - 1 if at + 1 < len(keys) else len(lines)
        summary = "\n".join(lines[start:end])
        words = len(re.findall(r"\b\w[\w'-]*\b", summary))
        if words > SUMMARY_WORDS:
            detail = f"summary is {words} words; keep it under {SUMMARY_WORDS}"
            found.append(_finding("warn", "summary-length", start, detail))
        if URL_RE.search(summary) or CITE_RE.search(summary):
            detail = "no links or source ids in the summary; cite in Findings"
            found.append(_finding("error", "summary-citations", start, detail))
    section = ""
    for n, level, title in heads:
        section = section_key(title) if level == 2 else section  # noqa: PLR2004
        if level == 3 and section == "findings" and len(title.split()) < MIN_TITLE_WORDS:  # noqa: PLR2004
            detail = f"'{title}' reads as a label; make the heading the finding"
            found.append(_finding("warn", "takeaway-heading", n, detail))
        if level in (1, 3) and title.endswith("."):
            found.append(
                _finding("warn", "heading-period", n, "drop the period ending the heading")
            )
        if re.search(EMOJI, title):
            found.append(_finding("warn", "emoji-heading", n, "emoji in a heading"))
    return found


def lint_prose(
    text: str, known_ids: set[str] | None, replaced: dict[str, str] | None = None
) -> list[Row]:
    r"""Citation and prose findings: unknown or uncited sources, slop words and patterns.

    Examples
    --------
    >>> [f["detail"] for f in lint_prose("Let's delve into it [S9].\n", {"S1"})]
    ['[S9] is not in the manifest', "'delve'", 'S1 is never cited']
    """
    found: list[Row] = []
    body = strip_fences(text)
    section = ""
    dashes = 0
    for n, line in enumerate(body.splitlines(), 1):
        section = section_key(line[3:]) if line.startswith("## ") else section
        unknown = [
            m[1] for m in CITE_RE.finditer(line) if known_ids is not None and m[1] not in known_ids
        ]
        for sid in unknown:
            by = (replaced or {}).get(sid)
            if by and section == "since":
                continue
            detail = (
                f"[{sid}] was replaced by {by}; cite {by}"
                if by
                else f"[{sid}] is not in the manifest"
            )
            found.append(_finding("error", "unknown-source", n, detail))
        if section == "sources":
            continue
        dashes += line.count("\u2014")
        low = line.lower()
        found.extend(
            _finding("warn", "slop-word", n, f"'{w}'")
            for w in SLOP_WORDS
            if re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", low)
        )
        found.extend(
            _finding("warn", "slop-pattern", n, name) for name, p in SLOP_PATTERNS if p.search(line)
        )
    if dashes > MAX_EM_DASHES:
        detail = f"{dashes} em dashes; use commas, periods, or parentheses"
        found.append(_finding("warn", "em-dash", 1, detail))
    uncited = sorted(
        (known_ids or set()) - {m[1] for m in CITE_RE.finditer(body)}, key=lambda s: int(s[1:])
    )
    found.extend(_finding("warn", "uncited-source", 1, f"{sid} is never cited") for sid in uncited)
    return found


def content_words(text: str) -> set[str]:
    """Words a claim and its quote should share: four letters or more, minus filler.

    Examples
    --------
    Words compare by their first five letters after common suffixes drop, so
    "hashes" meets "hash" and "pinned" meets "pins".

    >>> sorted(content_words("Both tools can pin hashes [S2]."))
    ['hash', 'tool']
    """
    found = [
        m[0].lower().rstrip(".")
        for m in re.finditer(r"[A-Za-z][A-Za-z0-9_.-]{3,}", CITE_RE.sub(" ", text))
    ]
    return {re.sub(r"(?:ing|ed|es|s)$", "", w)[:5] for w in found if w not in STOPWORDS}


def lint_citations(text: str, rows: list[Row]) -> list[Row]:
    r"""Warnings for citations a reader cannot check or that their quotes do not touch.

    A cited source needs a recorded quote, a capture, a pinned version, and a real
    address. A prose line under Findings that shares no content word with a cited
    source's quotes is flagged for a closer look.

    Examples
    --------
    >>> row = {"id": "S1", "url": "https://a.io/x", "file": "raw/x"}
    >>> rows = [{**row, "quotes": ["readers never wait"]}]
    >>> [f["rule"] for f in lint_citations("## Findings\n\nuv pins exported hashes [S1].", rows)]
    ['weak-coverage']
    >>> lint_citations("## Findings\n\nReaders never wait for writers [S1].", rows)
    []
    """
    by_id = {_str(r, "id"): r for r in rows}
    found: list[Row] = []
    flagged: set[str] = set()
    section = ""
    for n, line in enumerate(strip_fences(text).splitlines(), 1):
        section = section_key(line[3:]) if line.startswith("## ") else section
        for sid in dict.fromkeys(m[1] for m in CITE_RE.finditer(line)):
            row = by_id.get(sid)
            if row is None:
                continue
            quotes = quotes_of(row)
            words = content_words(line)
            claim = section == "findings" and not line.lstrip().startswith("|") and len(words) >= 3  # noqa: PLR2004
            if claim and quotes and not words & content_words(" ".join(quotes)):
                detail = f"line shares no words with {sid}'s quotes; check the claim against them"
                found.append(_finding("warn", "weak-coverage", n, detail))
            if sid in flagged:
                continue
            flagged.add(sid)
            found.extend(
                _finding("warn", rule, n, f"{sid}: {msg}") for rule, msg in source_issues(row)
            )
    return found


def source_issues(row: Row) -> list[tuple[str, str]]:
    """List what keeps a reader from checking a source: quote, capture, pin, or address.

    Examples
    --------
    >>> [r for r, _ in source_issues({"url": "https://x.invalid/a", "ref": "main"})]
    ['unquoted-source', 'uncaptured-source', 'unpinned-source', 'placeholder-url']
    """
    url = _str(row, "url")
    out: list[tuple[str, str]] = []
    if not quotes_of(row):
        out.append(("unquoted-source", "cited but records no quote"))
    if not _str(row, "file"):
        out.append(("uncaptured-source", "no capture to check"))
    out.extend(("unpinned-source", w) for w in pin_warnings(url, _str(row, "ref") or None))
    if re.match(r"https?://[^/]*\.(?:invalid|example|test|localhost)(?:[:/]|$)", url):
        out.append(
            ("placeholder-url", "the address is a placeholder; a measured source needs no URL")
        )
    return out


def lint_assessment(text: str, run: Path, rows: list[Row]) -> list[Row]:
    """Assessment checks: sensitivity and flip conditions stated; ratings backed by evidence."""
    found: list[Row] = []
    low = text.lower()
    if "sensitiv" not in low:
        detail = "say whether the verdict survives one rating moving"
        found.append(_finding("warn", "no-sensitivity", 1, detail))
    if "flip" not in low:
        found.append(_finding("warn", "no-flip", 1, "say what evidence would flip the verdict"))
    path = run / "data" / "criteria.csv"
    if path.is_file():
        by_id = {_str(r, "id"): r for r in rows}
        found += lint_criteria(path.read_text(encoding="utf-8"), by_id)
    return found


def lint_criteria(csv_text: str, by_id: dict[str, Row]) -> list[Row]:
    r"""Check each criterion's rating against its evidence.

    A rated criterion cites at least one known source; high confidence needs a
    source that is not the vendor's own; a note admitting missing evidence
    contradicts a rating.

    Examples
    --------
    >>> rows = {"S1": {"id": "S1", "kind": "vendor"}}
    >>> head = "criterion,rating,confidence,sources,note\n"
    >>> body = "Speed,strong,high,S1,\nCost,weak,low,,unsourced\nRisk,strong,high,,\n"
    >>> [f["rule"] for f in lint_criteria(head + body, rows)]
    ['vendor-only-high', 'unsourced-rating', 'note-contradicts-rating', 'unsourced-rating']
    """
    found: list[Row] = []
    table = csv_rows(csv_text)
    for n, r in enumerate(table, 2):
        ratings = [v.strip().lower() for v in r.values() if v and v.strip().lower() in RATINGS]
        rated = any(x != "unknown" for x in ratings)
        ids = [i for i in re.split(r"[;,\s]+", r.get("sources") or "") if i]
        known = [by_id[i] for i in ids if i in by_id]
        name = r.get("criterion") or f"row {n}"
        high = (r.get("confidence") or "").strip().lower() == "high"
        outside = [k for k in known if _str(k, "kind") in ("independent", "measured")]
        if rated and high and known and not outside:
            detail = f"{name}: high confidence on vendor sources only; cap it at medium"
            found.append(_finding("warn", "vendor-only-high", n, detail))
        elif rated and high and len(outside) == 1:
            detail = (
                f"{name}: high confidence on one outside source, a sample of one; cap it at medium"
            )
            found.append(_finding("warn", "sample-of-one-high", n, detail))
        if rated and not known:
            detail = f"{name}: rated with no known source"
            found.append(_finding("warn", "unsourced-rating", n, detail))
        if rated and MISSING_EVIDENCE.search(r.get("note") or ""):
            detail = f"{name}: the note says the evidence is missing"
            found.append(_finding("warn", "note-contradicts-rating", n, detail))
    return found


def _finding(level: str, rule: str, line: int, detail: str) -> Row:
    return {"level": level, "rule": rule, "line": line, "detail": detail}


def cmd_lint_report(a: Args) -> int:
    """Lint a report beside its run's manifest; exit 1 on any error."""
    report = Path(a.report)
    run = report.parent
    text = report.read_text(encoding="utf-8")
    manifest = run / MANIFEST
    known = {_str(r, "id") for r in current(read_jsonl(manifest))} if manifest.is_file() else None
    meta = read_meta(run)
    audience = audience_of(meta, a.audience)
    level = "warn" if audience == "private" else "error"
    rows = current(read_jsonl(manifest))
    replaced = {_str(r, "replaces"): _str(r, "id") for r in rows if _str(r, "replaces")}
    findings = lint_structure(text) + lint_prose(text, known, replaced) + lint_citations(text, rows)
    if meta.get("mode") == "assessment":
        findings += lint_assessment(text, run, rows)
    if CITE_RE.search(text) and not claims_reviewed(report):
        detail = "no claims review of this version; run claims --reviewed after the last edit"
        findings.append(_finding("warn", "claims-unreviewed", 1, detail))
    findings.extend(
        _finding(level, f"leak-{kind}", line, match)
        for line, kind, match in scan_text(
            text, audience, _strs(meta.get("redact")), str(Path.home())
        )
    )
    emit({"report": report.name, "audience": audience, "findings": findings})
    failing = ("error", "warn") if a.strict else ("error",)
    return 1 if any(f["level"] in failing for f in findings) else 0


# --- charts --------------------------------------------------------------------

SVG_STYLE = (
    "text{font:13px system-ui,sans-serif;fill:#333}.t{font-size:15px;font-weight:600}"
    ".n{fill:#666;font-size:11px}rect{fill:#4c78a8}line{stroke:#bbb}"
    "@media (prefers-color-scheme:dark){text{fill:#ddd}.n{fill:#aaa}rect{fill:#6b9bd1}"
    "line{stroke:#555}}"
)
SERIES_COLORS = ("#4c78a8", "#f58518", "#54a24b", "#e45756")


def _svg(width: int, height: int, title: str, body: list[str], note: str) -> str:
    esc = html.escape
    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{esc(title)}">'
    )
    foot = [f'<text class="n" x="8" y="{height - 12}">{esc(note)}</text>'] if note else []
    title_el = f'<text class="t" x="8" y="24">{esc(title)}</text>'
    return "\n".join([head, f"<style>{SVG_STYLE}</style>", title_el, *body, *foot, "</svg>", ""])


def _text(x: float, y: float, s: str, attrs: str = "") -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}"{attrs}>{html.escape(s)}</text>'


def bar_svg(
    title: str,
    labels: list[str],
    series: dict[str, list[float]],
    note: str = "",
    rating: bool = False,
) -> str:
    """Horizontal bar chart as standalone SVG; several series draw grouped bars with a legend.

    Examples
    --------
    >>> svg = bar_svg("Readers never wait", ["WAL", "Rollback"], {"score": [3.0, 1.0]})
    >>> svg.startswith("<svg") and "WAL" in svg and svg.count("<rect") == 2
    True
    >>> svg = bar_svg("uv leads on reproducibility", ["Lockfile", "Migration"],
    ...               {"uv": [3.0, 2.0], "pip-tools": [1.0, 3.0]}, rating=True)
    >>> svg.count("<rect"), "pip-tools" in svg
    (6, True)

    Negative values hang left of the zero line instead of leaving the canvas.

    >>> 'x="-' in bar_svg("Latency change", ["p50", "p99"], {"ms": [-30.0, 10.0]})
    False
    """
    width, label_w, top = 720, 220, 48
    many = len(series) > 1
    bar_h, gap = (16, 14) if many else (22, 10)
    group_h = bar_h * len(series) + gap
    values = [v for vs in series.values() for v in vs]
    low, high = min([0.0, *values]), max([0.0, *values])
    scale = (width - label_w - 90) / ((high - low) or 1.0)
    zero = label_w - low * scale
    legend_h = 22 if many else 0
    height = top + legend_h + len(labels) * group_h + (40 if note else 16)
    names = {v: k for k, v in RATINGS.items()}
    body: list[str] = []
    if many:
        x = label_w
        for k, name in enumerate(series):
            color = SERIES_COLORS[k % len(SERIES_COLORS)]
            body.append(
                f'<rect x="{x}" y="{top - 6}" width="12" height="12" style="fill:{color}"/>'
            )
            body.append(_text(x + 18, top + 5, name))
            x += 30 + 8 * len(name)
    for i, label in enumerate(labels):
        y0 = top + legend_h + i * group_h
        body.append(
            _text(label_w - 8, y0 + bar_h * len(series) / 2 + 5, label[:34], ' text-anchor="end"')
        )
        for k, vs in enumerate(series.values()):
            value = vs[i]
            y = y0 + k * bar_h
            w = abs(value) * scale
            shown = names.get(value, f"{value:g}") if rating else f"{value:g}"
            style = f' style="fill:{SERIES_COLORS[k % len(SERIES_COLORS)]}"' if many else ""
            if w:
                h, wide = bar_h - (2 if many else 0), max(1.0, w)
                left = zero + min(value, 0.0) * scale
                body.append(
                    f'<rect x="{left:.1f}" y="{y}" width="{wide:.1f}" height="{h}" rx="2"{style}/>'
                )
            body.append(_text(zero + max(value, 0.0) * scale + 6, y + bar_h - 5, shown))
    return _svg(width, height, title, body, note)


def line_svg(
    title: str, xs: list[str], series: dict[str, list[float | None]], note: str = ""
) -> str:
    """Line chart as standalone SVG, one labelled line per series.

    Examples
    --------
    >>> svg = line_svg("Latency fell by two thirds", ["Jan", "Feb", "Mar"], {"p50": [26.0, 14.0, 9.0]})
    >>> svg.count("<polyline"), "Mar" in svg
    (1, True)
    """  # noqa: E501
    width, height, left, right, top = 720, 360, 56, 120, 48
    bottom = 56 + (16 if note else 0)
    values = [v for vs in series.values() for v in vs if v is not None]
    lo, hi = min([0.0, *values]), max([1.0, *values])
    plot_w, plot_h = width - left - right, height - top - bottom

    def px(i: int) -> float:
        return left + plot_w * i / max(1, len(xs) - 1)

    def py(v: float) -> float:
        return top + plot_h - plot_h * (v - lo) / ((hi - lo) or 1.0)

    base = top + plot_h
    body = [
        f'<line x1="{left}" y1="{base}" x2="{left + plot_w}" y2="{base}"/>',
        _text(left - 6, py(hi) + 4, f"{hi:g}", ' text-anchor="end"'),
        _text(left - 6, py(lo) + 4, f"{lo:g}", ' text-anchor="end"'),
    ]
    body.extend(_text(px(i), base + 18, x[:12], ' text-anchor="middle"') for i, x in enumerate(xs))
    for k, (name, vs) in enumerate(series.items()):
        color = SERIES_COLORS[k % len(SERIES_COLORS)]
        pts = [(i, v) for i, v in enumerate(vs) if v is not None]
        coords = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in pts)
        body.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="2.5" points="{coords}"/>'
        )
        if pts:
            body.append(
                _text(px(pts[-1][0]) + 8, py(pts[-1][1]) + 4, name, f' style="fill:{color}"')
            )
    return _svg(width, height, title, body, note)


def number(cell: str) -> float | None:
    """Numeric value of a CSV cell; rating words map to 3, 2, 1, 0.

    Examples
    --------
    >>> number("1,204"), number("79%"), number("Strong"), number("n/a")
    (1204.0, 79.0, 3.0, None)
    """
    cell = cell.strip().lower()
    if cell in RATINGS:
        return RATINGS[cell]
    try:
        return float(cell.replace(",", "").rstrip("%"))
    except ValueError:
        return None


def cmd_chart(a: Args) -> int:
    """Draw a CSV as an SVG exhibit."""
    with Path(a.csv).open(encoding="utf-8", newline="") as fh:
        table = csv_rows(fh.read())
    if not table:
        msg = f"{a.csv} has no rows"
        raise ValueError(msg)
    cols = list(table[0])
    label = a.label or cols[0]
    missing = [c for c in [label, *(a.value or [])] if c not in cols]
    if missing:
        msg = f"{a.csv} has no column {missing[0]!r}; columns are {', '.join(cols)}"
        raise ValueError(msg)
    if len(cols) < 2:  # noqa: PLR2004
        msg = f"{a.csv} needs a label column and at least one value column"
        raise ValueError(msg)
    title = a.title or Path(a.csv).stem.replace("-", " ").capitalize()
    note = a.note or f"Data: {Path(a.csv).name}"
    if a.kind == "line":
        ys = a.value or [c for c in cols if c != label]
        series = {y: [number(r.get(y) or "") for r in table] for y in ys}
        svg = line_svg(title, [r.get(label) or "" for r in table], series, note)
    else:
        others = [c for c in cols if c != label]
        picked = a.value or ["rating" if "rating" in others else others[0]]
        series = {v: [number(r.get(v) or "") or 0.0 for r in table] for v in picked}
        cells = [(r.get(v) or "").strip().lower() for r in table for v in picked]
        rating = all(c in RATINGS for c in cells)
        svg = bar_svg(title, [r.get(label) or "" for r in table], series, note, rating=rating)
    atomic_write(Path(a.out), svg.encode())
    emit({"chart": a.out, "rows": len(table), "kind": a.kind})
    return 0


# --- cli -----------------------------------------------------------------------


def emit(obj: object) -> None:
    """Print ``obj`` as JSON on stdout."""
    print(json.dumps(obj, indent=2, ensure_ascii=False))


COMMANDS: dict[str, Callable[[Args], int]] = {
    "open": cmd_open,
    "add": cmd_add,
    "prior": cmd_prior,
    "status": cmd_status,
    "scan": cmd_scan,
    "verify": cmd_verify,
    "links": cmd_links,
    "find": cmd_find,
    "sources": cmd_sources,
    "claims": cmd_claims,
    "lint-report": cmd_lint_report,
    "chart": cmd_chart,
}


def build_parser() -> argparse.ArgumentParser:  # noqa: PLR0915 - one statement per option
    """CLI parser, one subcommand per verb.

    Examples
    --------
    >>> build_parser().parse_args(["prior", "--topic", "t"], namespace=Args()).namespace
    'research'
    """
    p = argparse.ArgumentParser(prog="topic.py", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    root_help = "topics root; default Documents (the Windows one on WSL)"

    o = sub.add_parser("open", help="open today's run, carrying sources from the last one")
    _ = o.add_argument("--root", help=root_help)
    _ = o.add_argument(
        "--namespace", default="research", help="topic owner: research, business, ..."
    )
    _ = o.add_argument("--topic", required=True)
    _ = o.add_argument("--date", help="run date, default today")
    _ = o.add_argument("--subject", help="human title, default the topic")
    _ = o.add_argument("--mode", choices=MODES, help="default: the prior run's, else research")
    _ = o.add_argument(
        "--audience", choices=AUDIENCES, help="default: the prior run's, else private"
    )
    _ = o.add_argument("--resume", action="store_true", help="keep working in the latest run")
    _ = o.add_argument(
        "--new-topic", action="store_true", help="start even if similar topics exist"
    )

    ad = sub.add_parser("add", help="record a source and its capture")
    _ = ad.add_argument("--run", required=True)
    _ = ad.add_argument("--url", default="", help="omit only for --kind measured with --file")
    _ = ad.add_argument("--ref", help="tag, commit, edition, or version the claim rests on")
    _ = ad.add_argument("--title")
    _ = ad.add_argument("--author")
    grp = ad.add_mutually_exclusive_group()
    _ = grp.add_argument("--file", help="a capture you saved")
    _ = grp.add_argument("--fetch", action="store_true", help="download the capture now")
    _ = ad.add_argument("--quote", action="append", help="exact text a claim rests on (repeatable)")
    _ = ad.add_argument("--set-quotes", action="store_true", help="replace the recorded quotes")
    _ = ad.add_argument("--replaces", help="id of a moved or vanished source this one retires")
    _ = ad.add_argument(
        "--kind",
        dest="source_kind",
        choices=KINDS,
        help="vendor (the subject's own), independent, measured",
    )

    pr = sub.add_parser("prior", help="a topic's runs, newest first")
    _ = pr.add_argument("--root", help=root_help)
    _ = pr.add_argument("--namespace", default="research")
    _ = pr.add_argument("--topic", required=True)

    st = sub.add_parser("status", help="every topic: latest run, source states, open questions")
    _ = st.add_argument("--root", help=root_help)
    _ = st.add_argument("--namespace")
    _ = st.add_argument("--date", help="today, for staleness")

    sc = sub.add_parser("scan", help="leaks in authored markdown at the run's audience")
    _ = sc.add_argument("--run", required=True)
    _ = sc.add_argument("--audience", choices=AUDIENCES)
    _ = sc.add_argument("--redact", action="append", help="name to flag at internal and public")
    _ = sc.add_argument(
        "--include-references", action="store_true", help="also scan source cards and history/"
    )

    ve = sub.add_parser("verify", help="re-check sources: vanished, moved, changed, misquoted")
    _ = ve.add_argument("--run", required=True)
    _ = ve.add_argument("--offline", action="store_true", help="captures only, no network")
    _ = ve.add_argument("--id", dest="ids", action="append", help="one source id (repeatable)")

    li = sub.add_parser("links", help="URLs the captures mention that the manifest lacks")
    _ = li.add_argument("--run", required=True)

    fi = sub.add_parser("find", help="search capture text: find a quote, or which sources say X")
    _ = fi.add_argument("--run", required=True)
    _ = fi.add_argument("pattern", help="text to find; whitespace and case are ignored")
    _ = fi.add_argument("--width", type=int, default=80, help="characters of context each side")

    so = sub.add_parser("sources", help="current sources as a markdown table for the report")
    _ = so.add_argument("--run", required=True)
    _ = so.add_argument(
        "--write", action="store_true", help="replace the report's ## Sources section"
    )

    cl = sub.add_parser("claims", help="each cited claim beside its sources' quotes")
    _ = cl.add_argument("report")
    _ = cl.add_argument("--reviewed", action="store_true", help="log that you checked every pair")

    lr = sub.add_parser("lint-report", help="report shape, citations, prose, and leaks")
    _ = lr.add_argument("report")
    _ = lr.add_argument("--audience", choices=AUDIENCES)
    _ = lr.add_argument("--strict", action="store_true", help="fail on warnings too")

    ch = sub.add_parser("chart", help="draw a CSV as an SVG exhibit")
    _ = ch.add_argument("--csv", required=True)
    _ = ch.add_argument("--out", required=True)
    _ = ch.add_argument("--kind", choices=("bar", "line"), default="bar")
    _ = ch.add_argument("--label", help="label or x column, default the first")
    _ = ch.add_argument(
        "--value",
        action="append",
        help="value column, repeatable for grouped bars; rating words map to 3-0",
    )
    _ = ch.add_argument("--title", help="the takeaway, not the metric name")
    _ = ch.add_argument("--note", help="source line under the chart")
    return p


def main(argv: list[str] | None = None) -> int:
    """Run the CLI; exit 2 on bad input."""
    args = build_parser().parse_args(argv, namespace=Args())
    try:
        return COMMANDS[args.cmd](args)
    except (ValueError, OSError) as e:
        emit({"error": str(e)})
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
