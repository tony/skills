#!/usr/bin/env python3
"""Dated research topics with source provenance.

A topic lives in ``<root>/<YYYY-MM-DD>/<namespace>/<topic>/``, one directory per
run. The run's source manifest records what it rests on and is
append-only; cards and ``index.md`` frontmatter are views of it. A run on an
earlier date takes no new evidence or authored state unless ``open --resume``
reopened it today: a later run carries its sources forward. Release, decision,
export, and check records about a run are still written to it.

Run ``topic.py <command> --help`` for each command.
"""

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
import ipaddress
import json
import os
import platform
import re
import shlex
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import typing as t
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

if t.TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    Fetch = Callable[[str], tuple[int, str, bytes, dict[str, str]]]

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
SEARCHES = REFS + "/searches.jsonl"
CONFLICTS = REFS + "/conflicts.jsonl"
RELEASES = REFS + "/releases.jsonl"
DECISIONS = REFS + "/decisions.jsonl"
RAW_DIR = REFS + "/raw"
STALE_DAYS = 180
SIMILAR_RATIO = 0.75
MIN_CONTAINED = 4
SUMMARY_WORDS = 150
MAX_EM_DASHES = 2
MIN_TITLE_WORDS = 4
MAX_FETCH_BYTES = 25 * 1024 * 1024
MAX_REDIRECTS = 5
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

SEARCH_FAILURES = ("error", "rate-limit", "auth", "blocked")
EXPORTS = REFS + "/exports.jsonl"

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
    ("secret", re.compile(r"\bgh[po]_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{30,}")),
    ("secret", re.compile(r"\bAKIA(?![0-9A-Z]*EXAMPLE)[0-9A-Z]{16}\b")),
    ("secret", re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}")),
    ("secret", re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----")),
)
INTERNAL_HOSTS = (
    re.compile(
        r"(?<![\w.-])(?:[A-Za-z0-9-]+\.)+(?:internal|corp|local|lan|intranet|home\.arpa)(?![\w-]|\.\w)",
        re.IGNORECASE,
    ),
    re.compile(r"(?<![\w.-])localhost\b", re.IGNORECASE),
)
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w]|\.\d)")
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
UNVERIFIED_RE = re.compile(r"\[unverified\]", re.IGNORECASE)
LEVEL = r"(high|medium|moderate|low)(?:\s*[-/\u2013]\s*(?:high|medium|moderate|low))?"
CONFIDENCE_RE = re.compile(
    rf"""
      \b{LEVEL}\s+confidence\b
    | \bconfidence(?:\s+(?:is|level|of))?[\s:(\u2013\u2014-]*{LEVEL}\b
    """,
    re.IGNORECASE | re.VERBOSE,
)
ITEM_RE = re.compile(r"(?:[-*]|\d+[.)])\s")
RESPONSE_HEADERS = ("content-type", "last-modified", "etag", "date")
PROSE_RULES = Path(__file__).resolve().parent.parent / "references" / "prose-rules.md"


def parse_slop_words(text: str) -> tuple[str, ...]:
    """Read the banned words and quoted phrases from the "Cut these words" section."""
    m = re.search(r"^## Cut these words\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if not m:
        msg = "prose-rules.md has no 'Cut these words' section"
        raise ValueError(msg)
    words: list[str] = []
    for para in re.split(r"\n\s*\n", m[1].strip()):
        flat = " ".join(para.split())
        head, sep, rest = flat.partition(": ")
        if not sep:
            continue
        if head.startswith("Inflation"):
            words.extend(w.strip(" .") for w in rest.split(","))
        else:
            words.extend(t.cast("list[str]", re.findall(r'"([^"]+)"', rest)))
    found = tuple(dict.fromkeys(w.lower() for w in words if w))
    if not found:
        msg = "'Cut these words' section lists no words"
        raise ValueError(msg)
    return found


SLOP_WORDS = parse_slop_words(PROSE_RULES.read_text(encoding="utf-8"))
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
FAILED_STATES = ("vanished", "moved", "changed", "misquoted", "unreachable", "unverifiable")
FAILURES = frozenset(FAILED_STATES)
SOURCE_STATES = (
    "fresh", "unverified", "stale", "unchecked", "unretrieved", "intact", "reachable", "verified",
    *FAILED_STATES,
)  # fmt: skip
TABLE_STATES = {"verified": "checked", "intact": "checked", "reachable": "unchecked"}
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
MISSING_EVIDENCE_PHRASES = ("unsourced", "no source", "not sourced", "untested", "no evidence")
MISSING_EVIDENCE = re.compile("|".join(map(re.escape, MISSING_EVIDENCE_PHRASES)), re.IGNORECASE)
STOPWORDS = frozenset({
    "that", "this", "with", "from", "have", "were", "they", "their", "there", "than", "then",
    "when", "what", "which", "will", "would", "could", "should", "does", "into", "only", "also",
    "each", "both", "more", "most", "some", "such", "been", "being", "over", "under", "about",
    "after", "before", "while", "because", "these", "those", "other", "every", "same", "very",
})  # fmt: skip
SECTION_ORDER = (
    "summary", "findings", "recommendations", "conflicts", "since", "open questions", "method",
    "exhibits", "sources",
)  # fmt: skip
MIN_CLAIM_WORDS = 10
MIN_BRIEF_WORDS = 4
REDACT_STEP = "set redact in index.md: the names to hide, or [] when there are none"


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
    allow_offline: bool = False
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
    unretrieved: str | None = None
    query: str = ""
    where: str | None = None
    results: int | None = None
    name: str = ""
    output: list[str] | None = None
    command: list[str] | None = None
    timeout: float | None = None
    sources: list[str] | None = None
    conflict: str | None = None
    about: str | None = None
    weight: str | None = None
    why: str | None = None
    settle: str | None = None
    to: str = ""
    decision: str = ""
    by: str = ""
    release: str | None = None
    revisit: str | None = None
    bag: str | None = None
    digest: str | None = None
    fields: str | None = None
    link: str | None = None
    failed: str | None = None
    markdown: bool = False
    words: list[str] | None = None
    stdin: bool = False


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
    >>> docs = [Path(f"/mnt/c/Users/{u}/Documents") for u in ("Public", "WsiAccount", "alice")]
    >>> pick_root(Path("/h/u"), docs).as_posix()
    '/mnt/c/Users/alice/Documents'
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
    >>> windows_users("/usr/bin:/mnt/c/Users/alice/AppData/Local/Microsoft/WindowsApps")
    ['alice']
    """
    found = re.findall(r"(?:^|:)/mnt/[a-z]/Users/([^/:]+)/", path_env)
    return sorted({str(name) for name in t.cast("list[object]", found)})


def resolve_root(
    arg: str | None,
    env: Mapping[str, str] | None = None,
    proc_version: Path | None = None,
    windows_users_dir: Path | None = None,
    home: Path | None = None,
) -> Path:
    """Return ``--root``, else ``RESEARCH_ROOT``, else the detected default (never the temp dir).

    The keyword arguments stand in for the process environment, ``/proc/version``,
    ``/mnt/c/Users``, and the home directory.
    """
    env = os.environ if env is None else env
    explicit = arg or env.get("RESEARCH_ROOT")
    if explicit:
        return Path(explicit).expanduser()
    try:
        version = (proc_version or Path("/proc/version")).read_text(encoding="utf-8")
        wsl = "microsoft" in version.lower()
    except OSError:
        wsl = False
    users = windows_users_dir or Path("/mnt/c/Users")
    found = sorted(users.glob("*/Documents")) if wsl else None
    hints = windows_users(env.get("PATH", ""))
    if wsl:
        with contextlib.suppress(KeyError, OSError):  # < 3.13: no login name, no passwd entry
            hints.append(getpass.getuser())
    root = pick_root(home or Path.home(), found, hints)
    temp = Path(tempfile.gettempdir()).resolve()
    if root.resolve() == temp or temp in root.resolve().parents:
        msg = f"default root {root} is a temp directory; pass --root"
        raise ValueError(msg)
    return root


def now_utc() -> str:
    """Return the current UTC time as ``YYYY-MM-DDTHH:MM:SSZ``."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    r"""Append rows with one ``write`` each, so concurrent appenders interleave whole lines.

    A last line left unterminated is closed first; gluing a row to it would lose both.

    Examples
    --------
    >>> with tempfile.TemporaryDirectory() as d:
    ...     p = Path(d) / "s.jsonl"
    ...     _ = p.write_text('{"id": "S1"}', encoding="utf-8")
    ...     append_jsonl(p, [{"id": "S2"}])
    ...     [r["id"] for r in read_jsonl(p)]
    ['S1', 'S2']
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as fh:
        if fh.tell():
            _ = fh.seek(-1, os.SEEK_END)
            if fh.read(1) != b"\n":
                _ = fh.write(b"\n")
        for row in rows:
            _ = fh.write(dumps(row).encode())


class LedgerError(ValueError):
    """A ledger row that is not a JSON object."""


def read_jsonl(path: Path) -> list[Row]:
    r"""Read JSON-lines rows, skipping blank lines; a damaged row raises `LedgerError`.

    A row dropped silently would hand its id to the next source.

    Examples
    --------
    >>> with tempfile.TemporaryDirectory() as d:
    ...     p = Path(d) / "s.jsonl"
    ...     _ = p.write_text('{"id": "S1"}\n\nnot json\n', encoding="utf-8")
    ...     try:
    ...         _ = read_jsonl(p)
    ...     except LedgerError as e:
    ...         print(e)
    s.jsonl line 3 is damaged; repair or delete that line

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
    for n, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        if not line.strip():
            continue
        try:
            value = t.cast("object", json.loads(line))
        except json.JSONDecodeError:
            value = None
        if not isinstance(value, dict):
            msg = f"{path.name} line {n} is damaged; repair or delete that line"
            raise LedgerError(msg)
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
    log = f"- {parse_date(None)}: opened"
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
    Sources carry forward, conclusions do not: the report stays behind, and of
    ``data/`` only the ``*.csv`` files come across, to be updated. The search log
    and the recorded conflicts carry with the sources they concern.
    """
    for table in sorted((prior_run / "data").glob("*.csv")):
        dest = run / "data" / table.name
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            _ = shutil.copyfile(table, dest)
    for ledger in (SEARCHES, CONFLICTS):
        kept = [{**r, "carried_from": prior_date} for r in read_jsonl(prior_run / ledger)]
        if kept:
            atomic_write(run / ledger, "".join(dumps(r) for r in kept).encode())
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


def require_root(root: Path) -> Path:
    """``root`` when it is a readable directory; a missing one is not an empty one."""
    if not root.is_dir() or not os.access(root, os.R_OK | os.X_OK):
        msg = f"root {root} is missing or unreadable; pass --root or set RESEARCH_ROOT"
        raise ValueError(msg)
    return root


def cmd_open(a: Args) -> int:
    """Open today's run of a topic; a same-day rerun returns the same run unchanged."""
    root = resolve_root(a.root)
    namespace, topic, day = slugify(a.namespace or "research"), slugify(a.topic), parse_date(a.date)
    runs = list_runs(root, namespace, topic)
    if a.resume and runs:
        run = runs[0][1]
        meta = read_meta(run)
        for flag, given in (("mode", a.mode), ("audience", a.audience)):
            if given and given != _str(meta, flag):
                kept = _str(meta, flag)
                msg = f"--resume keeps the run's {flag} ({kept}); drop --{flag} or open a new run"
                raise ValueError(msg)
        today = parse_date(None)
        log = (run / "index.md").read_text(encoding="utf-8")
        if f"- {today}: resumed" not in log and f"- {today}: opened" not in log:
            snapshot_report(run)
            append_log(run, f"{today}: resumed")
        emit(open_result(run, runs, created=False, resumed=True, carried=0))
        return 0
    run = root / day / namespace / topic
    if (run / "index.md").is_file():
        meta = read_meta(run)
        differs = [
            f
            for f, given in (("mode", a.mode), ("audience", a.audience))
            if given and given != _str(meta, f)
        ]
        if differs:
            have = f"mode {_str(meta, 'mode')}, audience {_str(meta, 'audience')}"
            msg = (
                f"the run for {day} exists with {have}; drop --{' and --'.join(differs)} to keep it"
            )
            raise ValueError(msg)
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
    if isinstance(prior_meta.get("redact"), list):
        meta["redact"] = prior_meta["redact"]
    run.mkdir(parents=True, exist_ok=True)
    carried = carry(prior_run, prior_day, run) if prior_run else 0
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
    root = require_root(resolve_root(a.root))
    runs = list_runs(root, slugify(a.namespace or "research"), slugify(a.topic))
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
    "id", "title", "author", "url", "ref", "retrieved", "sha256", "file", "response",
    "unretrieved", "command", "exit", "outputs", "quotes", "kind", "carried_from", "replaces",
    "replaced_by", "requested_url",
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


Resolver = t.Callable[[str], list[str]]


def resolve_host(name: str) -> list[str]:
    """Addresses ``name`` resolves to; empty when it does not resolve."""
    try:
        infos = socket.getaddrinfo(name, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror, UnicodeError, OSError:
        return []
    return sorted({str(i[4][0]).split("%")[0] for i in infos})


def is_public_host(name: str, resolve: Resolver = resolve_host) -> bool:
    """Return whether every address of ``name`` is globally routable.

    Loopback, private, link-local, and other reserved ranges are refused so a
    captured page cannot steer a fetch at the reader's own network.

    Examples
    --------
    >>> is_public_host("example.org", lambda _: ["93.184.216.34"])
    True
    >>> is_public_host("example.org", lambda _: ["93.184.216.34", "10.0.0.5"])
    False
    >>> is_public_host("169.254.169.254", lambda n: [n])
    False
    >>> is_public_host("nowhere.invalid", lambda _: [])
    False
    """
    addrs = resolve(name)
    try:
        return bool(addrs) and all(ipaddress.ip_address(a).is_global for a in addrs)
    except ValueError:
        return False


@t.final
class PublicRedirects(urllib.request.HTTPRedirectHandler):
    """Follow at most ``MAX_REDIRECTS`` redirects, each to a public http(s) host."""

    max_redirections: t.ClassVar[int] = MAX_REDIRECTS

    def __init__(self, resolve: Resolver) -> None:
        """Keep ``resolve`` for checking each redirect target."""
        super().__init__()
        self.resolve: Resolver = resolve

    def redirect_request(  # noqa: PLR0913, PLR0917  # pyright: ignore[reportImplicitOverride]
        self,
        req: urllib.request.Request,
        fp: t.IO[bytes],
        code: int,
        msg: str,
        headers: http.client.HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        """Refuse a redirect to a non-http(s) scheme or a non-public host."""
        parts = urllib.parse.urlsplit(newurl)
        if parts.scheme in ("http", "https") and is_public_host(parts.hostname or "", self.resolve):
            return super().redirect_request(req, fp, code, msg, headers, newurl)
        reason = f"redirect to a non-public address: {newurl}"
        raise urllib.error.URLError(reason)


def connect_vetted(host: str, port: int, resolve: Resolver, timeout: float | None) -> socket.socket:
    """Open a socket to a public address of ``host``, resolving once.

    The connection goes to the address that was vetted, so a second DNS answer
    cannot redirect it.
    """
    addrs = resolve(host)
    if not is_public_host(host, lambda _: addrs):
        reason = f"{host} does not resolve to a public address"
        raise OSError(reason)
    err: OSError | None = None
    for addr in addrs:
        try:
            return socket.create_connection((addr, port), timeout)
        except OSError as e:
            err = e
    raise err or OSError(host)


@t.final
class VettedHTTPHandler(urllib.request.HTTPHandler):
    """Plain-HTTP handler whose connections go to the vetted address."""

    def __init__(self, resolve: Resolver) -> None:
        """Keep ``resolve`` for each connection."""
        super().__init__()
        self.resolve: Resolver = resolve

    def http_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:  # pyright: ignore[reportImplicitOverride]
        """Open ``req`` over a connection pinned to the vetted address."""
        resolve = self.resolve

        @t.final
        class Conn(http.client.HTTPConnection):
            def connect(self) -> None:  # pyright: ignore[reportImplicitOverride]
                self.sock = connect_vetted(self.host, self.port, resolve, self.timeout)

        return self.do_open(Conn, req)


@t.final
class VettedHTTPSHandler(urllib.request.HTTPSHandler):
    """HTTPS handler whose connections go to the vetted address, verified by host name."""

    def __init__(self, resolve: Resolver) -> None:
        """Keep ``resolve`` for each connection."""
        super().__init__(context=ssl.create_default_context())
        self.resolve: Resolver = resolve

    def https_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:  # pyright: ignore[reportImplicitOverride]
        """Open ``req`` over a TLS connection pinned to the vetted address."""
        resolve = self.resolve

        @t.final
        class Conn(http.client.HTTPSConnection):
            def connect(self) -> None:  # pyright: ignore[reportImplicitOverride]
                sock = connect_vetted(self.host, self.port, resolve, self.timeout)
                self.sock = self._context.wrap_socket(sock, server_hostname=self.host)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]

        return self.do_open(Conn, req, context=ssl.create_default_context())


def http_fetch(
    url: str, resolve: Resolver = resolve_host
) -> tuple[int, str, bytes, dict[str, str]]:
    """GET ``url``; return ``(status, final_url, body, headers)``, status 0 on failure.

    Status 0 also covers a refusal: a non-http(s) scheme, a host that resolves to a
    non-public address (also on each redirect), and a body over ``MAX_FETCH_BYTES``.
    Connections go straight to the vetted address and ignore proxy settings.
    """
    if not url.startswith(("https://", "http://")):
        return 0, url, b"", {}
    try:
        target = ascii_url(fetch_url(url))
        if not is_public_host(urllib.parse.urlsplit(target).hostname or "", resolve):
            return 0, url, b"", {}
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            VettedHTTPHandler(resolve),
            VettedHTTPSHandler(resolve),
            PublicRedirects(resolve),
        )
        req = urllib.request.Request(target, headers={"User-Agent": USER_AGENT})  # noqa: S310
        with t.cast("http.client.HTTPResponse", opener.open(req, timeout=20)) as resp:
            body = resp.read(MAX_FETCH_BYTES + 1)
            if len(body) > MAX_FETCH_BYTES:
                return 0, url, b"", {}
            return resp.status, resp.url or url, body, dict(resp.headers.items())
    except urllib.error.HTTPError as e:
        return e.code, url, b"", {}
    except urllib.error.URLError, http.client.HTTPException, OSError, ValueError:
        return 0, url, b"", {}


def response_record(status: int, asked: str, final: str, headers: dict[str, str]) -> Row:
    """Summarize the server's answer for a capture: status, final address, dating headers.

    Examples
    --------
    >>> response_record(200, "https://a.io/x", "https://a.io/x/",
    ...                 {"Content-Type": "text/html", "ETag": '"7f"', "Server": "nginx"})
    {'status': 200, 'content_type': 'text/html', 'etag': '"7f"'}
    """
    low = {k.lower(): v for k, v in headers.items()}
    out: Row = {"status": status}
    if final.rstrip("/") != asked.rstrip("/"):
        out["final_url"] = final
    out.update({h.replace("-", "_"): low[h] for h in RESPONSE_HEADERS if low.get(h)})
    return out


def read_capture(a: Args, fetch: Fetch) -> tuple[bytes, str, str, Row] | None:
    """Read the capture ``add`` was given: ``(bytes, suffix, how, response)``, or None."""
    if a.file:
        return Path(a.file).read_bytes(), Path(a.file).suffix or ".txt", "file", {}
    if not a.fetch:
        return None
    status, final, data, headers = fetch(a.url)
    if status != 200:  # noqa: PLR2004
        msg = (
            f"fetch {a.url} returned {status or 'no response'}; save what you can read and"
            " pass --file, or record why with --unretrieved"
        )
        raise ValueError(msg)
    asked = ascii_url(fetch_url(a.url))
    response = response_record(status, asked, final, headers)
    return data, url_suffix(fetch_url(a.url)), "fetch", response


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


VERSION_KEYS = (
    "ref", "sha256", "capture", "title", "author", "quotes", "replaces", "kind", "unretrieved",
)  # fmt: skip


def run_dir(arg: str) -> Path:
    """``--run`` as a path, refusing anything that is not a topic run."""
    run = Path(arg)
    if not (run / "index.md").is_file():
        msg = f"{run} is not a run (no index.md); open it first or pass the run directory"
        raise ValueError(msg)
    return run


def writable_run(arg: str) -> Path:
    """``--run`` for a command that adds evidence or edits authored state.

    A run is writable when its date is today or later, or its log shows ``open``
    created it or ``open --resume`` reopened it today. A run opened on an earlier
    day is read-only; release, decision, export, and check records are not such writes.
    """
    run = run_dir(arg)
    day, today = run.parent.parent.name, parse_date(None)
    if is_date(day) and day < today:
        log = (run / "index.md").read_text(encoding="utf-8")
        if f"- {today}: resumed" not in log and f"- {today}: opened" not in log:
            msg = (
                f"{run.parent.name}/{run.name} is dated {day}, before today ({today}); "
                "open the topic to carry its sources into today's run, "
                "or reopen it with open --resume"
            )
            raise ValueError(msg)
    return run


def enclosing_run(path: Path) -> Path | None:
    """Return the topic run that holds ``path``, if any."""
    return next(
        (
            p
            for p in path.resolve().parents
            if (p / "index.md").is_file() and is_date(p.parent.parent.name)
        ),
        None,
    )


FIELD_KEYS = {"add": ("quote", "title", "author"), "run": ("quote",), "searched": ("query",)}


def apply_fields(a: Args, command: str) -> None:
    """Fold a ``--fields`` JSON file into the options it names; a scalar given both ways is refused.

    Page text goes in the file, written with a file tool, so no shell parses it.
    """
    if not a.fields:
        return
    name, allowed = Path(a.fields).name, FIELD_KEYS[command]
    try:
        data = t.cast("object", json.loads(Path(a.fields).read_text(encoding="utf-8")))
    except (OSError, ValueError) as e:
        msg = f"--fields {name}: cannot read it as JSON ({e})"
        raise ValueError(msg) from e
    if not isinstance(data, dict):
        msg = f"--fields {name}: expected a JSON object with {', '.join(allowed)}"
        raise ValueError(msg)  # noqa: TRY004 - every refusal exits 2 through ValueError
    fields = t.cast("Row", data)
    unknown = sorted(set(fields) - set(allowed))
    if unknown:
        msg = (
            f"--fields {name}: {unknown[0]!r} is not a field of {command}; use {', '.join(allowed)}"
        )
        raise ValueError(msg)
    for key, value in fields.items():
        items = t.cast("list[object]", value) if isinstance(value, list) else [value]
        if not all(isinstance(x, str) for x in items) or (len(items) != 1 and key != "quote"):
            msg = f"--fields {name}: {key!r} must be a string" + (
                " or a list of strings" if key == "quote" else ""
            )
            raise ValueError(msg)
        given = [str(x) for x in items]
        if key == "quote":
            a.quote = [*(a.quote or []), *given]
        elif getattr(a, key):
            msg = f"--fields {name}: {key!r} is also given as --{key}; give it once"
            raise ValueError(msg)
        else:
            setattr(a, key, given[0])


RUN_FIELDS = ("command", "exit", "wall_seconds", "outputs")


def add_guards(a: Args, prev: Row, latest: dict[str, Row]) -> None:
    """Refuse an ``add`` that would record a contradiction."""
    if a.replaces and a.replaces not in latest:
        msg = f"--replaces {a.replaces}: no such source"
        raise ValueError(msg)
    if a.replaces and a.replaces == _str(prev, "id"):
        msg = f"--replaces {a.replaces}: that is this URL's own id; re-add without --replaces"
        raise ValueError(msg)
    if a.unretrieved and prev.get("file"):
        msg = (
            f"{_str(prev, 'id')} has a capture; --unretrieved is for a source you could not capture"
        )
        raise ValueError(msg)
    capturing = bool(a.file or a.fetch)
    if a.quote and (a.unretrieved or (prev.get("unretrieved") and not capturing)):
        msg = "an unretrieved source has no capture to hold a quote; capture what you read"
        raise ValueError(msg)


def cmd_add(a: Args, fetch: Fetch = http_fetch, extra: Row | None = None) -> int:
    """Record a source, or a new version of one; an unchanged re-add is a no-op.

    One id per URL. New bytes, a fetched capture of bytes you supplied, a new ref,
    or a corrected title, author, or quote append a version under the same id. A
    re-add without a capture keeps the old one, along with whether it was carried.
    ``extra`` carries fields only ``run`` records: the command, its exit, its outputs.
    A fetch that followed a redirect records the final address as the source's
    ``url`` and keeps the address asked for as ``requested_url``.
    """
    run = writable_run(a.run)
    apply_fields(a, "add")
    resolve_link(a, run)
    if not a.url and a.source_kind == "measured" and a.file:
        a.url = f"measured:{measured_name(run, Path(a.file))}"
    if not re.match(r"https?://|measured:", a.url):
        msg = "--url must be http(s); a measured source with --kind measured and --file may omit it"
        raise ValueError(msg)
    rows = read_jsonl(run / MANIFEST)
    ref = a.ref or None
    latest = latest_by_id(rows)
    empty: Row = {}
    matches = (
        r
        for r in current(rows)
        if same_url(_str(r, "url"), a.url) or same_url(_str(r, "requested_url"), a.url)
    )
    prev = next(matches, empty)
    add_guards(a, prev, latest)
    got = read_capture(a, fetch)
    final = _str(got[3], "final_url") if got else ""
    requested = a.url if final else _str(prev, "requested_url")
    url = final or (_str(prev, "url") if requested else a.url)
    row: Row = {
        "id": _str(prev, "id") or next_id(rows),
        "url": url,
        "ref": ref or prev.get("ref"),
        "title": a.title or prev.get("title"),
        "author": a.author or prev.get("author"),
        "retrieved": now_utc() if got else prev.get("retrieved", now_utc()),
        "sha256": sha256(got[0]) if got else prev.get("sha256"),
        "capture": got[2] if got else prev.get("capture"),
        "response": (got[3] or None) if got else prev.get("response"),
        "unretrieved": None if got else a.unretrieved or prev.get("unretrieved"),
        "quotes": merge_quotes([] if a.set_quotes else quotes_of(prev), a.quote or []),
        "added": prev.get("added") if prev and not got else _str(read_meta(run), "date") or None,
        "carried_from": prev.get("carried_from") if prev and not got else None,
        "replaces": a.replaces or prev.get("replaces"),
        "kind": a.source_kind or prev.get("kind"),
        **({} if got else {k: prev[k] for k in RUN_FIELDS if k in prev}),
        **({"requested_url": requested} if requested else {}),
        **(extra or {}),
    }
    data = got[0] if got else None
    if got:
        row["file"] = f"raw/{capture_name(_str(row, 'title'), got[0], url, got[1])}"
    elif prev.get("file"):
        row["file"] = prev["file"]
        data = (run / REFS / _str(prev, "file")).read_bytes()
    missing = missing_quotes(quotes_of(row), data) if data is not None else []
    if missing:
        hint = "copy quotes verbatim from the capture"
        if got and prev and not a.set_quotes:
            hint += "; after a new capture, --set-quotes replaces the old quotes"
        msg = f"quote not in the capture of {url}: {missing[0]!r}; {hint}"
        raise ValueError(msg)
    if prev and all(prev.get(k) == row.get(k) for k in VERSION_KEYS):
        emit({**prev, "duplicate": True})
        return 0
    row["card"] = _str(prev, "card") or f"{row['id']}-{_stem(_str(row, 'title'), url)}.md"
    if got:
        atomic_write(run / REFS / _str(row, "file"), got[0])
    append_jsonl(run / MANIFEST, [row])
    rewrite_card(run, row)
    if a.replaces:
        rewrite_card(run, latest[a.replaces], replaced_by=row["id"])
    version = sum(r.get("id") == row["id"] for r in rows) + 1
    warnings = pin_warnings(url, _str(row, "ref") or None)
    warnings += capture_warnings(row, got, prev)
    if data is not None and ref_unseen(_str(row, "ref"), url, data):
        warnings.append(f"ref {row['ref']} is not in the URL or the capture; confirm the pin")
    emit({**row, "duplicate": False, "version": version, "warnings": warnings})
    return 0


LINK_RE = re.compile(r"(S\d+):(\d+)")


def source_links(run: Path, row: Row) -> list[str]:
    """Return a source's capture URLs in page order: the numbering ``--link`` counts by."""
    path = run / REFS / _str(row, "file")
    if not _str(row, "file") or path.suffix not in TEXT_SUFFIXES or not path.is_file():
        return []
    return list(dict.fromkeys(urls_in(path)))


def resolve_link(a: Args, run: Path) -> None:
    """Set ``a.url`` from ``--link S<n>:<k>``: that source's k-th URL, as ``links`` numbers it."""
    if not a.link:
        return
    if a.url:
        msg = "give --url or --link, not both"
        raise ValueError(msg)
    m = LINK_RE.fullmatch(a.link)
    if not m:
        msg = f"--link {a.link}: expected S<n>:<k>, as links prints it"
        raise ValueError(msg)
    row = latest_by_id(read_jsonl(run / MANIFEST)).get(m[1])
    if row is None:
        msg = f"--link {a.link}: no source {m[1]}"
        raise ValueError(msg)
    found = source_links(run, row)
    if not 1 <= int(m[2]) <= len(found):
        msg = f"--link {a.link}: {m[1]}'s capture lists {len(found)} links"
        raise ValueError(msg)
    a.url = found[int(m[2]) - 1]


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


def run_log(
    cmd: list[str], proc: subprocess.CompletedProcess[bytes], started: str, wall: float
) -> str:
    r"""Render the log ``run`` keeps: the command, how it ended, where it ran, then its output.

    Examples
    --------
    >>> proc = subprocess.CompletedProcess(["echo", "hi"], 0, b"hi\n", b"")
    >>> print(run_log(["echo", "hi"], proc, "2026-01-08T10:00:00Z", 0.01).splitlines()[0])
    $ echo hi
    """
    head = [
        f"$ {shlex.join(cmd)}",
        f"exit: {proc.returncode}",
        f"started: {started}",
        f"wall_seconds: {wall}",
        f"platform: {platform.platform()}; Python {platform.python_version()}",
    ]
    out, err = (s.decode("utf-8", errors="replace") for s in (proc.stdout, proc.stderr))
    return "\n".join([*head, "", "--- stdout ---", out, "--- stderr ---", err])


def cmd_run(a: Args) -> int:
    """Run a command and keep it as a measured source: argv, exit, timing, output, file hashes.

    Only ever run a command you chose; never re-run one read from someone else's manifest.
    """
    run = writable_run(a.run)
    apply_fields(a, "run")
    a.fields = None
    cmd = (a.command or [])[1:] if (a.command or [])[:1] == ["--"] else a.command or []
    if not cmd:
        msg = "give the command after --, for example: run --run <dir> --name bench -- make bench"
        raise ValueError(msg)
    outputs = [Path(p) for p in a.output or []]
    outside = [p for p in outputs if not p.resolve().is_relative_to(run.resolve())]
    if outside:
        msg = f"--output {outside[0]} is outside the run; write outputs under its data/"
        raise ValueError(msg)
    (run / "data").mkdir(exist_ok=True)
    before = {p: p.stat().st_mtime_ns for p in outputs if p.is_file()}
    started, clock = now_utc(), time.monotonic()
    try:
        proc = subprocess.run(  # noqa: S603 - the user's own command, given on this call
            cmd, capture_output=True, check=False, stdin=subprocess.DEVNULL, timeout=a.timeout
        )
    except subprocess.TimeoutExpired as e:
        msg = f"{shlex.join(cmd)} ran past --timeout {a.timeout}s"
        raise ValueError(msg) from e
    wall = round(time.monotonic() - clock, 3)
    log = run / "data" / f"{slugify(a.name)}.log"
    atomic_write(log, run_log(cmd, proc, started, wall).encode())
    unwritten = [p for p in outputs if not p.is_file() or before.get(p) == p.stat().st_mtime_ns]
    if unwritten:
        msg = f"the command did not write --output {unwritten[0]}; it is missing or left as it was"
        raise ValueError(msg)
    hashes = {measured_name(run, p): sha256(p.read_bytes()) for p in outputs}
    a.url, a.file, a.fetch, a.source_kind = "", str(log), False, "measured"
    a.set_quotes = True
    a.title = a.title or a.name
    extra: Row = {"command": cmd, "exit": proc.returncode, "wall_seconds": wall}
    if hashes:
        extra["outputs"] = hashes
    return cmd_add(a, extra=extra)


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


def ref_unseen(ref: str, url: str, data: bytes) -> bool:
    """Return whether ``ref`` appears in neither ``url`` nor the capture.

    Examples
    --------
    >>> ref_unseen("3.46.0", "https://x.io/v3.46.0/a", b"")
    False
    >>> ref_unseen("3.46.0", "https://x.io/a", b"SQLite 3.46.0 docs")
    False
    >>> ref_unseen("9.9", "https://x.io/a", b"SQLite 3.46.0 docs")
    True
    >>> ref_unseen("", "https://x.io/a", b"")
    False
    """
    needle = ref.lower()
    return bool(needle) and needle not in url.lower() and needle not in text_of(data)


def capture_warnings(row: Row, got: tuple[bytes, str, str, Row] | None, prev: Row) -> list[str]:
    """Warnings about how a source was captured and typed."""
    out: list[str] = []
    if got and _str(got[3], "final_url"):
        out.append(
            f"redirected: recorded the final URL {row['url']}; you asked for {row['requested_url']}"
        )
    if got and got[2] == "file" and not prev and not _str(row, "url").startswith("measured:"):
        out.append("you supplied this capture; make sure it is what the URL serves, or use --fetch")
    if row.get("unretrieved"):
        out.append("not retrieved: list it as a gap; it cannot support a claim")
    elif not got and not row.get("sha256"):
        out.append("no capture: verify can only check the URL, never the claim")
    if not row.get("kind") and not row.get("unretrieved"):
        out.append("no --kind; confidence is capped by the kind of evidence")
    if row.get("exit") not in (None, 0):
        out.append(f"the command exited {row['exit']}; say so wherever its output is cited")
    return out


# --- status --------------------------------------------------------------------


def days_between(start: str, end: str) -> int | None:
    """Days from ``start`` to ``end`` (ISO dates), None when either is not a date."""
    try:
        return (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days
    except ValueError:
        return None


def source_states(run: Path, today: str) -> dict[str, str]:
    """State of each current source, one of ``SOURCE_STATES``.

    Fresh sources were added in this run; carried ones stay unverified until a
    check in this run passes, and turn stale past ``STALE_DAYS``. A check counts
    only for the version it tested. Verified needs a live check that compared
    content (the fetched bytes, or a quote on the live page); an offline pass on
    its own leaves the source intact, and a live answer with nothing to compare
    leaves it reachable.
    """
    every = read_jsonl(run / CHECKS)
    checks = latest_by_id(every)
    passed_live = {
        (_str(c, "id"), _str(c, "version"))
        for c in every
        if c.get("live") and c.get("status") == "ok"
    }
    states: dict[str, str] = {}
    for row in current(read_jsonl(run / MANIFEST)):
        sid, last, key = _str(row, "id"), checks.get(_str(row, "id"), {}), version_key(row)
        check = _str(last, "status") if last.get("version") == key else ""
        age = days_between(_str(row, "retrieved"), today)
        if row.get("unretrieved") and not _str(row, "file"):
            states[sid] = "unretrieved"
        elif check == "ok":
            states[sid] = "verified" if (sid, key) in passed_live else "intact"
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
    return question_items(run, " ")


def question_items(run: Path, mark: str) -> list[str]:
    """Items under ``## Open questions`` whose box holds ``mark``: a space is open, ``x`` ticked."""
    try:
        text = (run / "index.md").read_text(encoding="utf-8")
    except OSError:
        return []
    section = re.search(r"^## Open questions\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if not section:
        return []
    box = r"\[ \]" if mark == " " else r"\[[xX]\]"
    items = re.findall(rf"^\s*[-*] {box} (.+?)\s*$", section[1], re.MULTILINE)
    return [str(i) for i in t.cast("list[object]", items)]


def ticked_since_prior(run: Path) -> int:
    r"""Count the carried run's open questions that this run has ticked.

    Examples
    --------
    >>> with tempfile.TemporaryDirectory() as d:
    ...     old, new = (Path(d) / day / "research" / "wal" for day in ("2026-01-08", "2026-01-15"))
    ...     old.mkdir(parents=True)
    ...     new.mkdir(parents=True)
    ...     q = "## Open questions\n\n- [{}] Does WAL survive NFS?\n"
    ...     _ = (old / "index.md").write_text(q.format(" "), encoding="utf-8")
    ...     _ = (new / "index.md").write_text("---\nprior: 2026-01-08\n---\n" + q.format("x"))
    ...     ticked_since_prior(new)
    1
    """
    prior_day = _str(read_meta(run), "prior")
    if not prior_day:
        return 0
    prior = run.parent.parent.parent / prior_day / run.parent.name / run.name
    carried = {normalize(q) for q in open_questions(prior)}
    return sum(normalize(q) in carried for q in question_items(run, "x"))


def updated_on(run: Path, day: str) -> str:
    r"""Return the latest date the run was worked on: its own, or its last dated log entry.

    Examples
    --------
    >>> with tempfile.TemporaryDirectory() as d:
    ...     log = "## Log\n\n- 2026-01-08: opened\n- 2026-02-01: resumed\n"
    ...     _ = (Path(d) / "index.md").write_text(log)
    ...     updated_on(Path(d), "2026-01-08")
    '2026-02-01'
    """
    try:
        log = (run / "index.md").read_text(encoding="utf-8")
    except OSError:
        return day
    return max([day, *re.findall(r"(?m)^- (\d{4}-\d{2}-\d{2}):", log)])


def next_step(row: Row) -> tuple[int, str]:
    """``(urgency, action)`` for a topic's ``status`` row; urgency 1 is the most urgent.

    Examples
    --------
    >>> next_step({"sources": {"moved": 1}, "open_questions": ["x"], "report": True})
    (2, 'verify')
    >>> next_step({"sources": {"intact": 3}, "open_questions": [], "report": False})
    (7, 'report')
    """
    counts = t.cast("dict[str, int]", row["sources"])
    failed = any(state in FAILURES for state in counts)
    aging = any(state in ("stale", "unverified", "unchecked") for state in counts)
    ladder = (
        (bool(row.get("releases_affected")), "continue"),
        (failed, "verify"),
        (bool(row.get("conflicts_open")), "continue"),
        (aging, "continue"),
        (bool(row.get("open_questions") or row.get("criteria_gaps")), "continue --fill"),
        (bool(row.get("moving_pins")), "add"),
        (not row.get("report"), "report"),
    )
    return next(
        ((n, act) for n, (hit, act) in enumerate(ladder, 1) if hit), (len(ladder) + 1, "none")
    )


def topic_status(ns: str, topic: str, runs: list[tuple[str, Path]], today: str) -> Row:
    """One ``status`` row: a topic's latest run, source states, and what to do next."""
    day, run = max(runs)
    meta = read_meta(run)
    states = source_states(run, today)
    counts: dict[str, int] = {}
    for state in states.values():
        counts[state] = counts.get(state, 0) + 1
    row: Row = {
        "namespace": ns, "topic": topic, "latest": day, "updated": updated_on(run, day),
        "runs": sorted((d for d, _ in runs), reverse=True), "run_dir": str(run),
        "mode": meta.get("mode"), "subject": meta.get("subject"), "sources": counts,
        "open_questions": open_questions(run), "report": (run / "report.md").is_file(),
        "cards_without_notes": unannotated(run),
        "criteria_gaps": criteria_gaps(run),
        "moving_pins": sorted(
            _str(r, "id") for r in current(read_jsonl(run / MANIFEST))
            if pin_warnings(_str(r, "url"), _str(r, "ref") or None)
        ),
        "conflicts_open": [_str(c, "about") for c in latest_conflicts(run) if not c.get("weight")],
        "releases_affected": affected_releases(runs, run, states),
    }  # fmt: skip
    row["urgency"], row["next_action"] = next_step(row)
    return row


def cmd_status(a: Args) -> int:
    """Every topic under the root, most urgent first: latest run, sources by state, next action.

    ``recent`` names the topic worked on last. A topic with a damaged ledger is listed
    with its ``error``, and the exit is 1.
    """
    root = require_root(resolve_root(a.root))
    today = parse_date(a.date)
    topics: dict[tuple[str, str], list[tuple[str, Path]]] = {}
    for run in (
        r for day in root.iterdir() if day.is_dir() and is_date(day.name) for r in day.glob("*/*")
    ):
        ns = run.parent.name
        managed = (run / "index.md").is_file() and not run.name.startswith((".", "_"))
        if managed and (a.namespace is None or slugify(a.namespace) == ns):
            topics.setdefault((ns, run.name), []).append((run.parent.parent.name, run))
    out: list[Row] = []
    for (ns, topic), runs in sorted(topics.items()):
        try:
            out.append(topic_status(ns, topic, runs, today))
        except LedgerError as e:
            out.append(
                {
                    "namespace": ns,
                    "topic": topic,
                    "latest": max(runs)[0],
                    "error": str(e),
                    "urgency": 0,
                }
            )
    out.sort(key=lambda r: str(r.get("updated", r["latest"])), reverse=True)
    out.sort(key=lambda r: t.cast("int", r["urgency"]))
    recent = max(
        (r for r in out if "updated" in r),
        key=lambda r: (_str(r, "updated"), _str(r, "namespace"), _str(r, "topic")),
        default=None,
    )
    emit({
        "root": str(root),
        "recent": f"{_str(recent, 'namespace')}/{_str(recent, 'topic')}" if recent else None,
        "topics": out,
    })  # fmt: skip
    return 1 if any("error" in r for r in out) else 0


# --- privacy -------------------------------------------------------------------


def scan_text(
    text: str, audience: str, redact: list[str], home: str = ""
) -> list[tuple[int, str, str]]:
    r"""``(line, kind, match)`` for each leak in ``text`` at an audience.

    Examples
    --------
    >>> scan_text("see /home/alice/x and a@b.io", "private", [])
    [(1, 'home-path', '/home/alice'), (1, 'email', 'a@b.io')]
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

    Secrets show at every audience; internal hosts and addresses only at public.

    >>> scan_text("key AKIAABCDEFGHIJKLMNOP", "private", [])
    [(1, 'secret', 'AKIAABCDEFGHIJKLMNOP')]
    >>> scan_text("see wiki.acme.internal and 10.0.0.5, not 8.8.8.8", "public", [])
    [(1, 'internal-host', 'wiki.acme.internal'), (1, 'internal-host', '10.0.0.5')]
    >>> scan_text("see wiki.acme.internal", "internal", [])
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
        if audience == "public":
            hits.extend((n, "internal-host", host_) for host_ in internal_hosts(line))
        if audience == "public" and not in_fence:
            hits.extend(
                (n, "ticket", m[0]) for m in TICKET.finditer(line) if m[1] not in NOT_TICKETS
            )
        found.extend(hits)
    return found


def internal_hosts(line: str) -> list[str]:
    """List internal host names and private or loopback IPv4 addresses in ``line``."""
    found = [(m.start(), m[0]) for pat in INTERNAL_HOSTS for m in pat.finditer(line)]
    for m in IPV4.finditer(line):
        try:
            ip = ipaddress.ip_address(m[0])
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            found.append((m.start(), m[0]))
    return [text for _, text in sorted(found)]


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
    audience = audience_of(read_meta(run), a.audience)
    findings = scan_run(run, audience, a.redact or [], a.include_references)
    emit({"audience": audience, "findings": findings})
    return 1 if findings else 0


def scan_run(run: Path, audience: str, redact: list[str], include_references: bool) -> list[Row]:
    """Leaks in the text files a run ships, at ``audience``; ``raw/`` is never scanned."""
    names = _strs(read_meta(run).get("redact")) + redact
    findings: list[Row] = []
    for path in sorted(p for p in run.rglob("*") if p.suffix in SCANNED_SUFFIXES):
        rel = path.relative_to(run)
        working = rel.parts[0] in (REFS, "history", "releases")
        if "raw" in rel.parts[:-1] or (working and not include_references):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if rel.as_posix() == "index.md":
            text = hide_redact(text)
        findings.extend(
            {"file": rel.as_posix(), "line": line, "kind": kind, "match": match}
            for line, kind, match in scan_text(text, audience, names, str(Path.home()))
        )
    return findings


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
    if rel.lower().endswith(".pdf") and quotes_of(row):
        return "unverifiable", "PDF text is not extracted; capture the text you read as .txt", data
    missing = missing_quotes(quotes_of(row), data)
    if missing:
        return "misquoted", f"not in the capture: {missing[0]!r}", data
    return "ok", "capture intact", data


def check_live(row: Row, fetch: Fetch) -> tuple[str, str, Row]:
    """Online check of a source's URL: ``(status, detail, extra fields)``.

    ``ok`` means live content matched the fetched capture or the recorded quotes;
    a 200 with neither to compare is only ``reachable``.
    """
    url = _str(row, "url")
    status, final, body, _ = fetch(url)
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
    compared = row.get("capture") == "fetch" or bool(quotes_of(row))
    state = (
        ("ok", "live")
        if compared
        else ("reachable", "answered; nothing fetched or quoted to compare")
    )
    return state[0], state[1], extra


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


def check_outputs(run: Path, row: Row) -> tuple[str, str]:
    r"""Check the files a recorded command wrote still hold what it wrote: ``(status, detail)``.

    Outputs belong to the run that produced them, so a carried row is not checked.

    Examples
    --------
    >>> with tempfile.TemporaryDirectory() as d:
    ...     _ = (Path(d) / "n.csv").write_text("a,1\n", encoding="utf-8")
    ...     row = {"outputs": {"n.csv": sha256(b"a,1\n"), "gone.csv": "0"}}
    ...     check_outputs(Path(d), row)
    ('vanished', 'gone.csv is missing; the command wrote it')
    """
    if row.get("carried_from"):
        return "ok", ""
    outputs = t.cast("dict[str, str]", row.get("outputs") or {})
    for rel, digest in outputs.items():
        path = run / rel
        if not path.is_file():
            return "vanished", f"{rel} is missing; the command wrote it"
        if sha256(path.read_bytes()) != digest:
            return "changed", f"{rel} changed after the command wrote it; rerun the command"
    return "ok", ""


def check_source(run: Path, row: Row, fetch: Fetch | None) -> Row:
    """Check one source offline, then live when ``fetch`` is given; the first failure wins."""
    head: Row = {"id": _str(row, "id"), "version": version_key(row), "checked": now_utc()}
    head["url"] = _str(row, "url")
    if row.get("unretrieved") and not _str(row, "file"):
        detail = f"never retrieved: {_str(row, 'unretrieved')}"
        return {**head, "live": False, "status": "unretrieved", "detail": detail}
    status, detail, _ = check_capture(run, row)
    extra: Row = {}
    measured = _str(row, "url").startswith("measured:")
    if status == "ok" and measured:
        status, detail = check_outputs(run, row)
        detail = detail or "capture intact"
    compared = not row.get("carried_from") if measured else fetch is not None
    if status in ("ok", "unchecked") and fetch is not None and not measured:
        offline = status
        status, detail, extra = check_live(row, fetch)
        if status == "reachable" and offline == "ok":
            status, detail, compared = "ok", "capture intact; the live page was not compared", False
    head["live"] = compared
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
    results, failures = verify_rows(run, rows, None if a.offline else fetch)
    counts: dict[str, int] = {}
    for r in results:
        counts[_str(r, "status")] = counts.get(_str(r, "status"), 0) + 1
    emit({"checked": len(results), "counts": counts, "failures": failures})
    return 1 if failures else 0


def verify_rows(run: Path, rows: list[Row], fetch: Fetch | None) -> tuple[list[Row], list[Row]]:
    """Check ``rows``, append the results to checks.jsonl: ``(results, failures)``."""
    results = check_all(run, rows, fetch)
    append_jsonl(run / CHECKS, results)
    return results, [r for r in results if r.get("status") in FAILURES]


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
    """URLs that captures and cards mention but the manifest lacks: leads for missed sources.

    ``from`` gives each lead as ``S<n>:<k>``, the k-th link of that source's capture:
    ``add --link S<n>:<k>`` records it, so a page's address never passes through a shell.
    """
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
    refs: dict[str, list[str]] = {}
    for row in current(rows):
        for k, url in enumerate(source_links(run, row), 1):
            if url in seen:
                refs.setdefault(url, []).append(f"{_str(row, 'id')}:{k}")
    ranked = sorted(seen.items(), key=lambda kv: (-kv[1], kv[0]))
    emit([{"url": u, "mentions": n, "from": refs.get(u, [])} for u, n in ranked])
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
        title = cell(_str(r, "title") or _str(r, "url"))
        capture = captures.get(_str(r, "capture"), "none")
        if r.get("unretrieved"):
            capture = f"not retrieved: {cell(_str(r, 'unretrieved'))}"
        cells = [
            _str(r, "id"),
            title if _str(r, "url").startswith("measured:") else f"[{title}]({_str(r, 'url')})",
            cell(_str(r, "author")),
            _str(r, "kind"),
            _str(r, "ref"),
            _str(r, "retrieved")[:10],
            capture,
            states.get(_str(r, "id"), "unchecked"),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join([*lines, ""])


def cell(text: str) -> str:
    """``text`` safe inside a markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ")


def searches_table(rows: list[Row]) -> str:
    """Markdown table of logged searches, oldest first, empty when there are none.

    Examples
    --------
    >>> row = {"at": "2026-01-08T10:00:00Z", "where": "web", "query": "wal fsync", "results": 40}
    >>> print(searches_table([row]).splitlines()[4])
    | 2026-01-08 | web | wal fsync | 40 |  |
    """
    if not rows:
        return ""
    lines = [
        "### Searches",
        "",
        "| Date | Where | Query | Results | Note |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        count = f"failed: {_str(r, 'failure')}" if r.get("status") == "failed" else ""
        count = count or ("" if r.get("results") is None else str(r["results"]))
        cells = [_str(r, "at")[:10], _str(r, "where"), _str(r, "query"), count, _str(r, "note")]
        lines.append("| " + " | ".join(cell(c) for c in cells) + " |")
    return "\n".join([*lines, ""])


def sources_section(run: Path) -> str:
    """Body of a report's ``## Sources`` section: the sources table, then the search log.

    The ledgers keep what was recorded; the section is scrubbed for the run's audience.
    The Check column reads the same after an offline check and a live one:
    ``TABLE_STATES`` folds verified and intact into checked.
    """
    states = {k: TABLE_STATES.get(v, v) for k, v in source_states(run, parse_date(None)).items()}
    table = sources_table(read_jsonl(run / MANIFEST), states)
    searches = searches_table(read_jsonl(run / SEARCHES))
    meta = read_meta(run)
    body = table + (f"\n{searches}" if searches else "")
    return scrub(body, audience_of(meta, None), _strs(meta.get("redact")))


def scrub(text: str, audience: str, redact: list[str]) -> str:
    """Return ``text`` with each leak ``scan`` would flag at ``audience`` replaced.

    Examples
    --------
    >>> scrub("| Jane Doe outage ABC-12 |", "public", ["Jane Doe"])
    '| [redacted] outage [redacted] |'
    """
    for _, _, match in scan_text(text, audience, redact, str(Path.home())):
        text = text.replace(match, "[redacted]")
    return text


def cmd_searched(a: Args) -> int:
    """Log a search: what was asked, where, and how many results came back, or why it failed.

    A failed search found nothing and shows nothing: it is a gap, never an absence.
    """
    run = writable_run(a.run)
    apply_fields(a, "searched")
    if not a.query:
        msg = "give the query with --query, or as query in --fields"
        raise ValueError(msg)
    if a.failed and a.results is not None:
        msg = "--failed and --results conflict: a failed search has no result count"
        raise ValueError(msg)
    row: Row = {"at": now_utc(), "query": a.query, "where": a.where, "results": a.results}
    row["note"] = a.note
    if a.failed:
        row.update(status="failed", failure=a.failed)
    row = {k: v for k, v in row.items() if v not in (None, "")}
    append_jsonl(run / SEARCHES, [row])
    emit(row)
    return 0


def cmd_sources(a: Args) -> int:
    """Print the run's current sources as a markdown table; --write puts it under ## Sources."""
    run = writable_run(a.run) if a.write else run_dir(a.run)
    table = write_sources(run) if a.write else sources_section(run)
    print(table, end="")
    return 0


def write_sources(run: Path) -> str:
    """Put the sources table under the report's ``## Sources`` heading and return it."""
    report = run / "report.md"
    if not report.is_file():
        msg = f"{run.name} has no report.md; write it first"
        raise ValueError(msg)
    text = report.read_text(encoding="utf-8")
    if not re.search(r"(?m)^## Sources\s*$", text):
        msg = f"{report.name} has no ## Sources section"
        raise ValueError(msg)
    table = sources_section(run)
    text = re.sub(
        r"(?ms)^## Sources\s*$.*?(?=^## |\Z)", lambda _m: f"## Sources\n\n{table}\n", text
    )
    atomic_write(report, text.rstrip("\n").encode() + b"\n")
    return table


def cmd_prepare(a: Args, fetch: Fetch = http_fetch) -> int:
    """Run the report pipeline's first two steps in order: verify, then write the Sources table.

    Exit 1 when a source failed; the table is still written, so it shows the failure.
    Then run ``claims --reviewed``, then ``check``.
    """
    run = writable_run(a.run)
    if not (run / "report.md").is_file():
        msg = f"{run.name} has no report.md; write it first"
        raise ValueError(msg)
    results, failures = verify_rows(
        run, current(read_jsonl(run / MANIFEST)), None if a.offline else fetch
    )
    _ = write_sources(run)
    counts: dict[str, int] = {}
    for r in results:
        counts[_str(r, "status")] = counts.get(_str(r, "status"), 0) + 1
    emit({
        "checked": len(results), "counts": counts, "failures": failures,
        "sources_table": "written", "next": "claims --reviewed, then check",
    })  # fmt: skip
    return 1 if failures else 0


def claim_lines(text: str, rows: list[Row]) -> Row:
    r"""Each line of ``text`` that cites a source, each cited source's quotes, and unverified lines.

    Examples
    --------
    >>> rows = [{"id": "S1", "title": "WAL", "quotes": ["readers do not block writers"]}]
    >>> out = claim_lines("# T\n\nReaders never wait [S1].\n\nIt predates 3.7.[unverified]\n", rows)
    >>> out["lines"]
    [{'line': 3, 'text': 'Readers never wait [S1].', 'cites': ['S1']}]
    >>> out["quotes"]
    {'S1': ['readers do not block writers']}
    >>> out["unverified"]
    [{'line': 5, 'text': 'It predates 3.7.[unverified]'}]
    """
    by_id = {_str(r, "id"): r for r in current(rows)}
    lines: list[Row] = []
    unverified: list[Row] = []
    quotes: dict[str, list[str]] = {}
    for n, line in enumerate(strip_fences(text).splitlines(), 1):
        ids = list(dict.fromkeys(m[1] for m in CITE_RE.finditer(line)))
        if UNVERIFIED_RE.search(line):
            unverified.append({"line": n, "text": line.strip()})
        if ids:
            lines.append({"line": n, "text": line.strip(), "cites": ids})
            for sid in ids:
                if sid not in quotes:
                    quotes[sid] = quotes_of(by_id.get(sid, {}))
    return {"lines": lines, "quotes": quotes, "unverified": unverified}


def review_stamp(report: Path) -> str:
    """Short hash of what a claims review covers: the report and the brief beside it."""
    brief = report.parent / "brief.md"
    extra = b"\0" + brief.read_bytes() if brief.is_file() else b""
    return sha256(report.read_bytes() + extra)[:8]


def cmd_claims(a: Args) -> int:
    """List every cited claim beside its sources' quotes; --reviewed logs that you checked them.

    A ``brief.md`` beside the report is listed too, its lines marked ``"from": "brief.md"``
    under ``brief``, and the review covers both.
    """
    report = Path(a.report)
    rows = read_jsonl(report.parent / MANIFEST)
    out = claim_lines(report.read_text(encoding="utf-8"), rows)
    lines = t.cast("list[Row]", out["lines"])
    brief = report.parent / "brief.md"
    if brief.is_file():
        extra = claim_lines(brief.read_text(encoding="utf-8"), rows)
        from_brief = [{**r, "from": "brief.md"} for r in t.cast("list[Row]", extra["lines"])]
        out["brief"] = from_brief
        out["quotes"] = {**t.cast("Row", extra["quotes"]), **t.cast("Row", out["quotes"])}
        out["unverified"] = [
            *t.cast("list[Row]", out["unverified"]),
            *({**r, "from": "brief.md"} for r in t.cast("list[Row]", extra["unverified"])),
        ]
        lines = [*lines, *from_brief]
    if a.reviewed:
        _ = writable_run(str(report.parent))
        stamp = review_stamp(report)
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
    """Whether index.md logs a claims review of this exact version of ``report`` and its brief."""
    stamp = review_stamp(report)
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
    text: str,
    known_ids: set[str] | None,
    replaced: dict[str, str] | None = None,
    gaps: frozenset[str] | None = None,
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
    cited = {m[1] for m in CITE_RE.finditer(body)}
    uncited = sorted((known_ids or set()) - cited - (gaps or set()), key=lambda s: int(s[1:]))
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
    if row.get("unretrieved"):
        reason = _str(row, "unretrieved")
        return [("unretrieved-source", f"never retrieved ({reason}); it cannot support a claim")]
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


def confidence_of(text: str) -> str:
    """Return the confidence ``text`` states: high, medium, or low; empty when it states none.

    Markdown emphasis is ignored, and a range reads as its lower end.

    Examples
    --------
    >>> [confidence_of(s) for s in ("**Confidence:** moderate.", "High confidence [S1].", "fast")]
    ['medium', 'high', '']
    >>> confidence_of("Medium-high confidence"), confidence_of("Confidence (low)")
    ('medium', 'low')
    """
    m = CONFIDENCE_RE.search(plain(text))
    if not m:
        return ""
    level = (m[1] or m[2]).lower()
    return "medium" if level == "moderate" else level


def overconfidence(level: str, cited: list[Row]) -> tuple[str, str]:
    """``(rule, detail)`` when ``level`` claims more than ``cited`` can carry, else empty.

    One source is a report and two independent ones corroborate; a vendor speaks for itself.

    Examples
    --------
    >>> overconfidence("high", [{"kind": "vendor"}])[0]
    'vendor-only-high'
    >>> overconfidence("high", [{"kind": "independent"}, {"kind": "measured"}])
    ('', '')
    """
    outside = [r for r in cited if _str(r, "kind") in ("independent", "measured")]
    if level != "high" or not cited:
        return "", ""
    if not outside:
        return "vendor-only-high", "high confidence with no independent or measured source"
    if len(outside) == 1:
        return "sample-of-one-high", "high confidence on one outside source, a sample of one"
    return "", ""


def chunks(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Group report lines into paragraphs and list items: ``(first line, joined text)``.

    A wrapped line joins its paragraph, and an indented line or sub-bullet joins its item.

    Examples
    --------
    >>> chunks([(1, "1. Keep WAL [S1]."), (2, "   - Confidence: medium."), (3, ""), (4, "Next")])
    [(1, '1. Keep WAL [S1]. - Confidence: medium.'), (4, 'Next')]
    """
    out: list[tuple[int, list[str]]] = []
    joining = False
    for n, line in lines:
        s = line.strip()
        if not s or s.startswith(("#", "|", "![")):
            joining = False
            continue
        if out and not ITEM_RE.match(line) and (joining or line[:1].isspace()):
            out[-1][1].append(s)
        else:
            out.append((n, [s]))
        joining = True
    return [(n, " ".join(parts)) for n, parts in out]


def is_claim(text: str) -> bool:
    """Whether a paragraph or list item makes a claim that needs a declared source.

    Examples
    --------
    >>> is_claim("WAL lets readers proceed while one writer appends to the log file.")
    True
    >>> is_claim("**Confidence:** medium, as only one benchmark exists and nobody repeated it.")
    False
    """
    s = text.strip()
    if not s or s.startswith(("#", "|", "![", ">")) or CITE_RE.search(s) or UNVERIFIED_RE.search(s):
        return False
    if re.match(r"(?i)\W*(?:(?:high|medium|moderate|low)\s+)?confidence\b", plain(s)):
        return False
    return len(re.findall(r"\b\w[\w'-]*\b", s)) >= MIN_CLAIM_WORDS


def lint_analysis(text: str, rows: list[Row], conflicts: list[Row] | None = None) -> list[Row]:
    r"""Analytic checks on Findings and Recommendations.

    Each finding and recommendation states a confidence its sources can carry, every
    claim cites a source or is marked ``[unverified]``, a source in an unweighed
    conflict caps a finding at medium, and a summary over unverified claims says so.

    Examples
    --------
    >>> body = ("## Summary\n\nYes.\n\n## Findings\n\n### Readers never wait on the writer\n\n"
    ...         "Readers proceed while a writer appends [S1]. High confidence.\n\n"
    ...         "Checkpoints slow down when many readers\nhold old snapshots open for long.\n")
    >>> [f["rule"] for f in lint_analysis(body, [{"id": "S1", "kind": "vendor"}])]
    ['uncited-claim', 'vendor-only-high']
    """
    by_id = {_str(r, "id"): r for r in rows}
    contested = {
        sid for c in conflicts or [] if not c.get("weight") for sid in _strs(c.get("sources"))
    }
    found: list[Row] = []
    section, summary = "", ""
    parts: dict[str, list[tuple[int, str]]] = {}
    blocks: list[tuple[int, list[str]]] = []
    for n, line in enumerate(strip_fences(text).splitlines(), 1):
        if line.startswith("## "):
            section = section_key(line[3:])
            continue
        summary += f"{line}\n" if section == "summary" else ""
        if section not in ("findings", "recommendations"):
            continue
        parts.setdefault(section, []).append((n, line))
        if section == "findings" and line.startswith("### "):
            blocks.append((n, [line]))
        elif section == "findings" and blocks:
            blocks[-1][1].append(line)
    for section, lines in parts.items():
        for n, chunk in chunks(lines):
            if is_claim(chunk):
                detail = "cite a source, mark it [unverified], or move it to Open questions"
                found.append(_finding("warn", "uncited-claim", n, detail))
            if section == "recommendations" and ITEM_RE.match(chunk) and not confidence_of(chunk):
                detail = "state this recommendation's confidence"
                found.append(_finding("warn", "recommendation-confidence", n, detail))
    for n, lines in blocks:
        block = "\n".join(lines)
        level = confidence_of(block)
        if not level:
            detail = "state the finding's confidence: high, medium, or low, and why"
            found.append(_finding("warn", "finding-confidence", n, detail))
        ids = list(dict.fromkeys(m[1] for m in CITE_RE.finditer(block)))
        rule, detail = overconfidence(level, [by_id[i] for i in ids if i in by_id])
        if rule:
            found.append(_finding("warn", rule, n, f"{detail}; cap it at medium"))
        disputed = [i for i in ids if i in contested]
        if level == "high" and disputed:
            detail = f"high confidence on {', '.join(disputed)}, in a conflict not yet weighed"
            found.append(_finding("warn", "contested-high", n, f"{detail}; cap it at medium"))
        if level == "high" and UNVERIFIED_RE.search(block):
            detail = "high confidence on an unverified claim"
            found.append(_finding("warn", "unverified-high", n, detail))
    unverified = any(UNVERIFIED_RE.search(ln) for lines in parts.values() for _, ln in lines)
    if unverified and "unverified" not in summary.lower():
        detail = "Findings carry [unverified] claims; say so in the summary"
        found.append(_finding("warn", "unverified-undisclosed", 1, detail))
    return found


def lint_conflicts(
    text: str, conflicts: list[Row], replaced: dict[str, str] | None = None
) -> list[Row]:
    r"""Each recorded disagreement set out under Conflicts, on a line citing every side.

    A side since replaced by another source is cited by its replacement.

    Examples
    --------
    >>> c = [{"id": "C1", "sources": ["S1", "S2"], "about": "checkpoint size"}]
    >>> [f["rule"] for f in lint_conflicts("## Findings\n\n1000 pages [S1] or 100 [S2].\n", c)]
    ['conflict-unreported']
    >>> lint_conflicts("## Conflicts\n\n1000 pages [S1] against 100 [S2].\n", c)
    []
    >>> lint_conflicts("## Conflicts\n\n1000 pages [S1] against 100 [S9].\n", c, {"S2": "S9"})
    []
    """
    found: list[Row] = []
    lines = sections(strip_fences(text)).get("Conflicts", "").splitlines()
    for c in conflicts:
        ids = [(replaced or {}).get(i, i) for i in _strs(c.get("sources"))]
        if not any(all(f"[{i}]" in ln for i in ids) for ln in lines):
            sides = " and ".join(ids)
            detail = (
                f"{sides} disagree on {_str(c, 'about')}; under Conflicts, open with one line"
                " citing every side, then each reading"
            )
            found.append(_finding("warn", "conflict-unreported", 1, detail))
    if "Conflicts" in sections(text) and not conflicts:
        detail = "## Conflicts lists disagreements no record holds; record each with conflict"
        found.append(_finding("warn", "conflict-unrecorded", 1, detail))
    return found


def latest_conflicts(run: Path) -> list[Row]:
    """Return the newest record of each conflict in ``run``."""
    return list(latest_by_id(read_jsonl(run / CONFLICTS)).values())


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
        rule, detail = overconfidence((r.get("confidence") or "").strip().lower(), known)
        if rated and rule:
            found.append(_finding("warn", rule, n, f"{name}: {detail}; cap it at medium"))
        if rated and not known:
            detail = f"{name}: rated with no known source"
            found.append(_finding("warn", "unsourced-rating", n, detail))
        if rated and MISSING_EVIDENCE.search(r.get("note") or ""):
            detail = f"{name}: the note says the evidence is missing"
            found.append(_finding("warn", "note-contradicts-rating", n, detail))
    return found


LADDER = ("unknown", "weak", "adequate", "strong")
NON_OPTIONS = frozenset({"criterion", "weight", "confidence", "sources", "note"})


def tally_criteria(csv_text: str) -> Row:
    r"""Count each option's ratings, and test whether the leader survives one rating moving one grade.

    The leader has the highest unweighted rating total (strong 3, adequate 2, weak 1, unknown
    0), used only to find which single move changes the leader; it is not reported as a score.
    A blank or unrecognised cell counts as unknown.

    Examples
    --------
    >>> text = "criterion,a,b,sources\nSpeed,strong,weak,S1\nCost,adequate,adequate,S2\nRisk,strong,unknown,\n"
    >>> out = tally_criteria(text)
    >>> out["leader"], out["tally"]["a"]["strong"], out["tally"]["b"]["unknown"], out["criteria"]
    ('a', 2, 1, 3)
    >>> out["sensitivity"]["survives"]
    True
    >>> tally_criteria("criterion,a,b\nSpeed,strong,adequate\nCost,weak,weak\n")["sensitivity"]["flips"][0]
    {'criterion': 'Speed', 'option': 'a', 'from': 'strong', 'to': 'adequate', 'then': 'tie'}
    """  # noqa: E501
    table = csv_rows(csv_text)

    def grade(cell: str | None) -> str:
        word = (cell or "").strip().lower()
        return word if word in RATINGS else "unknown"

    options = option_columns(table)
    grid = {o: [grade(r.get(o)) for r in table] for o in options}
    names = [r.get("criterion") or f"row {n}" for n, r in enumerate(table, 2)]

    def leader_of(g: dict[str, list[str]]) -> str | None:
        totals = {o: sum(RATINGS[x] for x in v) for o, v in g.items()}
        top = max(totals.values(), default=0.0)
        best = [o for o, total in totals.items() if total == top]
        return best[0] if len(best) == 1 else None

    leader = leader_of(grid)
    flips: list[Row] = []
    for o in options:
        for i, name in enumerate(names):
            at = LADDER.index(grid[o][i])
            for step in (at - 1, at + 1):
                if 0 <= step < len(LADDER) and leader is not None:
                    moved = {k: [*v] for k, v in grid.items()}
                    moved[o][i] = LADDER[step]
                    after = leader_of(moved)
                    if after != leader:
                        flips.append({
                            "criterion": name, "option": o, "from": grid[o][i],
                            "to": LADDER[step], "then": after or "tie",
                        })  # fmt: skip
    return {
        "criteria": len(table),
        "tally": {o: {g: grid[o].count(g) for g in reversed(LADDER)} for o in options},
        "leader": leader,
        "sensitivity": None
        if len(options) < 2  # noqa: PLR2004
        else {"survives": leader is not None and not flips, "flips": flips},
    }


def criteria_markdown(csv_text: str, by_id: dict[str, Row]) -> str:
    r"""Render the ``## Criteria`` section: one line per criterion, from the CSV and the manifest.

    Examples
    --------
    >>> text = "criterion,uv,pip,confidence,sources\nLock,strong,adequate,high,S2;S9\n"
    >>> print(criteria_markdown(text, {"S2": {"id": "S2", "kind": "independent"}}))
    ## Criteria
    <BLANKLINE>
    - Lock: uv strong, pip adequate; high confidence; S2 (independent), S9 (not in the manifest).
    """
    table = csv_rows(csv_text)
    options = option_columns(table)
    lines = ["## Criteria", ""]
    for n, r in enumerate(table, 2):
        ids = [i for i in re.split(r"[;,\s]+", r.get("sources") or "") if i]
        cited = ", ".join(
            f"{i} ({_str(by_id[i], 'kind') or 'no kind'})"
            if i in by_id
            else f"{i} (not in the manifest)"
            for i in ids
        )
        rated = ", ".join(f"{o} {(r.get(o) or 'unknown').strip().lower()}" for o in options)
        confidence = (r.get("confidence") or "").strip()
        parts = [
            rated,
            f"{confidence} confidence" if confidence else "confidence not stated",
            cited or "no source",
        ]
        lines.append(f"- {r.get('criterion') or f'row {n}'}: " + "; ".join(parts) + ".")
    return "\n".join(lines)


def option_columns(table: list[dict[str, str]]) -> list[str]:
    """List the columns of a criteria table that rate an option: any with a rating word in it."""
    cols = list(table[0]) if table else []
    return [
        c
        for c in cols
        if c not in NON_OPTIONS and any((r.get(c) or "").strip().lower() in RATINGS for r in table)
    ]


def cmd_tally(a: Args) -> int:
    """Print an assessment's tally and sensitivity, or with ``--markdown`` its Criteria section."""
    run = run_dir(a.run)
    path = run / "data" / "criteria.csv"
    if not path.is_file():
        msg = "no data/criteria.csv in the run"
        raise ValueError(msg)
    text = path.read_text(encoding="utf-8")
    if a.markdown:
        print(
            criteria_markdown(text, {_str(r, "id"): r for r in current(read_jsonl(run / MANIFEST))})
        )
    else:
        emit(tally_criteria(text))
    return 0


def _finding(level: str, rule: str, line: int, detail: str) -> Row:
    return {"level": level, "rule": rule, "line": line, "detail": detail}


def search_gaps(rows: list[Row]) -> list[Row]:
    """Failed searches that no later search of the same query made good.

    Examples
    --------
    >>> log = [{"query": "wal nfs", "status": "failed", "failure": "blocked"},
    ...        {"query": "wal fsync", "status": "failed", "failure": "auth"},
    ...        {"query": "WAL  NFS", "results": 3}]
    >>> [g["query"] for g in search_gaps(log)]
    ['wal fsync']
    """
    out: list[Row] = []
    for i, row in enumerate(rows):
        key = normalize(_str(row, "query"))
        retried = any(
            r.get("status") != "failed" and normalize(_str(r, "query")) == key
            for r in rows[i + 1 :]
        )
        if row.get("status") == "failed" and not retried:
            out.append({k: row.get(k) for k in ("query", "where", "failure")})
    return out


def lint_searches(text: str, gaps: list[Row]) -> list[Row]:
    """Each unretried failed search must appear under Open questions: a gap, never an absence."""
    listed = normalize(sections(strip_fences(text)).get("Open questions", ""))
    return [
        _finding(
            "warn",
            "failed-search",
            1,
            f"search {_str(g, 'query')!r} failed ({_str(g, 'failure')}): rerun it or list the gap",
        )
        for g in gaps
        if normalize(_str(g, "query")) not in listed
    ]


def brief_sentences(text: str) -> list[tuple[int, str]]:
    r"""List ``(line, sentence)`` for each statement in a brief, not headings, tables, or labels.

    A sentence is a statement from ``MIN_BRIEF_WORDS`` words up, once links are dropped.

    Examples
    --------
    >>> brief_sentences("# T\n\nWAL lets readers proceed during writes.\nIt wins [S1].")
    [(3, 'WAL lets readers proceed during writes.')]
    """
    out: list[tuple[int, str]] = []
    para: list[str] = []
    first = 0
    for n, line in enumerate([*strip_fences(text).splitlines(), ""], 1):
        s = line.strip()
        if s and not s.startswith(("#", "|", "![")):
            first = first or n
            para.append(s)
            continue
        joined = re.sub(r"\[([^\]]*)\]\([^)]*\)", "", " ".join(para))
        out.extend(
            (first, x.strip())
            for x in re.split(r"(?<=[.!?])\s+", joined)
            if len(x.split()) >= MIN_BRIEF_WORDS
        )
        para, first = [], 0
    return out


def lint_brief(run: Path, report_text: str) -> list[Row]:
    """Flag what a brief adds to the report: a citation or an uncited sentence it lacks."""
    brief = run / "brief.md"
    if not brief.is_file():
        return []
    body = strip_fences(report_text)
    cited = {m[1] for m in CITE_RE.finditer(body)}
    known = " ".join(re.sub(r"\s*\[(?:S\d+|unverified)\]", "", body).split())
    text = brief.read_text(encoding="utf-8")
    found: list[Row] = []
    for n, line in enumerate(strip_fences(text).splitlines(), 1):
        found.extend(
            _finding("error", "brief-citation", n, f"[{sid}] is not cited in report.md")
            for sid in dict.fromkeys(m[1] for m in CITE_RE.finditer(line))
            if sid not in cited
        )
    for n, sentence in brief_sentences(text):
        if not CITE_RE.search(sentence) and " ".join(sentence.split()) not in known:
            detail = f"{sentence[:60]!r} is not in report.md; the brief adds no claim"
            found.append(_finding("error", "brief-new-claim", n, detail))
    return found


def lint_report(report: Path, audience_arg: str | None = None) -> tuple[str, list[Row]]:
    """Lint a report beside its run's manifest: ``(audience, findings)``."""
    run = report.parent
    text = report.read_text(encoding="utf-8")
    manifest = run / MANIFEST
    known = {_str(r, "id") for r in current(read_jsonl(manifest))} if manifest.is_file() else None
    meta = read_meta(run)
    audience = audience_of(meta, audience_arg)
    level = "warn" if audience == "private" else "error"
    rows = current(read_jsonl(manifest))
    replaced = {_str(r, "replaces"): _str(r, "id") for r in rows if _str(r, "replaces")}
    gaps = frozenset(_str(r, "id") for r in rows if r.get("unretrieved"))
    findings = lint_structure(text) + lint_prose(text, known, replaced, gaps)
    conflicts = latest_conflicts(run)
    findings += lint_citations(text, rows) + lint_analysis(text, rows, conflicts)
    findings += lint_conflicts(text, conflicts, replaced)
    findings += lint_searches(text, search_gaps(read_jsonl(run / SEARCHES)))
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
    return audience, findings


def cmd_lint_report(a: Args) -> int:
    """Lint a report beside its run's manifest; exit 1 on an error, or a warning with --strict."""
    report = Path(a.report)
    audience, findings = lint_report(report, a.audience)
    emit({"report": report.name, "audience": audience, "findings": findings})
    failing = ("error", "warn") if a.strict else ("error",)
    return 1 if any(f["level"] in failing for f in findings) else 0


# --- trace ---------------------------------------------------------------------


def cmd_conflict(a: Args) -> int:
    """Record where sources disagree, or, with ``--id``, how a recorded disagreement was weighed."""
    run = writable_run(a.run)
    latest = latest_by_id(read_jsonl(run / CONFLICTS))
    prev: Row = latest.get(a.conflict or "", {})
    if a.conflict and not prev:
        msg = f"--id {a.conflict}: no such conflict; omit --id to record a new one"
        raise ValueError(msg)
    ids = _strs(prev.get("sources")) or list(dict.fromkeys(a.sources or []))
    if not prev:
        known = {_str(r, "id") for r in current(read_jsonl(run / MANIFEST))}
        unknown = [i for i in ids if i not in known]
        if len(ids) < 2 or not a.about or unknown:  # noqa: PLR2004
            msg = (
                "name two or more current sources with --source, and what they dispute with --about"
            )
            raise ValueError(msg)
    if a.weight and a.weight not in ids:
        msg = f"--weight {a.weight} is not one of {', '.join(ids)}"
        raise ValueError(msg)
    if a.weight and not (a.why or prev.get("why")):
        msg = "say --why that source carries more weight"
        raise ValueError(msg)
    row: Row = {"id": a.conflict or f"C{len(latest) + 1}", "sources": ids, "at": now_utc()}
    for key in ("about", "weight", "why", "settle"):
        value = t.cast("str | None", getattr(a, key)) or prev.get(key)
        if value:
            row[key] = value
    append_jsonl(run / CONFLICTS, [row])
    emit(row)
    return 0


def report_open_questions(text: str) -> list[str]:
    r"""List the unticked items under the report's ``## Open questions``.

    Examples
    --------
    >>> report_open_questions("## Open questions\n\n- Does WAL hold?\n- [x] Done\n- [ ] Why?\n")
    ['Does WAL hold?', 'Why?']
    """
    body = sections(strip_fences(text)).get("Open questions", "")
    item = r"^\s*(?:[-*]|\d+[.)])\s+(?!\[[xX]\])(?:\[ \]\s+)?(.+?)\s*$"
    items = re.findall(item, body, re.MULTILINE)
    return [str(i) for i in t.cast("list[object]", items)]


def reconcile_questions(in_index: list[str], in_report: list[str]) -> list[str]:
    """Merge two lists of open questions; one that starts with the other is the same question.

    Examples
    --------
    >>> reconcile_questions(["Does WAL hold?"], ["does wal hold? A test would settle it.", "Why?"])
    ['Does WAL hold?', 'Why?']
    """
    merged = list(in_index)
    for item in in_report:
        key = normalize(item)
        if not any(key.startswith(normalize(m)) or normalize(m).startswith(key) for m in merged):
            merged.append(item)
    return merged


def report_counts(run: Path, text: str, states: dict[str, str]) -> Row:
    r"""Count what a hero quotes: findings, sources, carried sources, open and ticked questions.

    ``open_questions`` merges index.md's unchecked items with the report's ``## Open questions``.

    Examples
    --------
    >>> with tempfile.TemporaryDirectory() as d:
    ...     body = "## Findings\n\n### A finding holds up\n\nx\n\n### Another finding holds\n"
    ...     report_counts(Path(d), body, {"S1": "verified", "S2": "fresh"})["findings"]
    2
    """
    rows = current(read_jsonl(run / MANIFEST))
    section = ""
    findings = 0
    for _, level, title in headings(text):
        section = section_key(title) if level == 2 else section  # noqa: PLR2004
        findings += level == 3 and section == "findings"  # noqa: PLR2004
    by_state: dict[str, int] = {}
    for state in states.values():
        by_state[state] = by_state.get(state, 0) + 1
    in_index = open_questions(run)
    in_report = report_open_questions(text)
    failed = sum(n for state, n in by_state.items() if state in FAILURES)
    open_count = len(reconcile_questions(in_index, in_report))
    return {
        "findings": findings, "sources": len(rows),
        "carried": sum(bool(r.get("carried_from")) for r in rows),
        "states": by_state, "open_questions": open_count,
        "open_in_index": len(in_index), "open_in_report": len(in_report),
        "failed_sources": failed, "open_items": open_count + failed,
        "ticked": ticked_since_prior(run),
    }  # fmt: skip


def gate(run: Path, fetch: Fetch | None) -> Row:
    """Run every ship check fresh: sources, Sources table, claims review, lint, brief, redact, scan.

    ``ok`` is the only verdict: a report ships when every check passes in this call.
    ``next`` lists the fixes in pipeline order and ``first_failing`` names the first
    prerequisite that failed: verify, sources, claims, lint, redact, or scan.
    """
    report = run / "report.md"
    if not report.is_file():
        msg = f"{run.name} has no report.md; write it first"
        raise ValueError(msg)
    results, failures = verify_rows(run, current(read_jsonl(run / MANIFEST)), fetch)
    text = report.read_text(encoding="utf-8")
    body = sections(text).get("Sources", "")
    table = "current" if body.strip() == sources_section(run).strip() else "stale"
    audience, lint = lint_report(report)
    unreviewed = [f for f in lint if f["rule"] == "claims-unreviewed"]
    lint_rest = [f for f in lint if f["rule"] != "claims-unreviewed"]
    brief = lint_brief(run, text)
    decided = isinstance(read_meta(run).get("redact"), list)
    public = audience == "public"
    leaks = scan_run(run, audience, [], include_references=False)
    steps = [
        ("verify", failures, "fix each failed source as verify.md says"),
        ("sources", table == "stale", "prepare: verify, then sources --write"),
        ("claims", unreviewed, "claims --reviewed"),
        ("lint", lint_rest or brief, "fix the lint and brief findings, then claims --reviewed"),
        ("redact", public and not decided, REDACT_STEP),
        ("scan", leaks, "remove what scan lists"),
    ]  # fmt: skip
    todo = [(name, step) for name, failed, step in steps if failed]
    states = source_states(run, parse_date(None))
    return {
        "ok": not todo,
        "at": now_utc(), "live": fetch is not None, "sha256": sha256(report.read_bytes()),
        "audience": audience, "sources": {"checked": len(results), "failures": failures},
        "sources_table": table, "lint": lint, "brief": brief, "scan": leaks,
        "redact_decision": "recorded" if decided else "missing" if public else "not needed",
        "search_gaps": search_gaps(read_jsonl(run / SEARCHES)),
        "counts": report_counts(run, text, states),
        "first_failing": todo[0][0] if todo else None,
        "next": [*(step for _, step in todo), "check again"] if todo else [],
    }  # fmt: skip


def cmd_check(a: Args, fetch: Fetch = http_fetch) -> int:
    """Run every ship check fresh; exit 1 unless all pass."""
    result = gate(run_dir(a.run), None if a.offline else fetch)
    emit(result)
    return 0 if result["ok"] else 1


def evidence_key(row: Row) -> str:
    """Short hash of what a claim rests on: the address, the pin, and the captured bytes.

    Examples
    --------
    >>> a = {"url": "u", "ref": "1.0", "sha256": "x", "quotes": ["q"]}
    >>> evidence_key(a) == evidence_key({**a, "quotes": ["q", "r"]})
    True
    """
    return sha256(json.dumps([_str(row, k) for k in ("url", "ref", "sha256")]).encode())[:12]


def cmd_release(a: Args, fetch: Fetch = http_fetch) -> int:
    """Release the report: pass every check fresh, keep that exact version, log who got it.

    ``--audience`` is the reader's, and must equal the run's.
    """
    run = run_dir(a.run)
    held = audience_of(read_meta(run), None)
    if a.audience != held:
        msg = f"the run's audience is {held}, but release asked for a {a.audience} reader"
        raise ValueError(msg)
    if a.offline and not a.allow_offline:
        msg = "release needs a live check; pass --allow-offline to release on captures alone"
        raise ValueError(msg)
    result = gate(run, None if a.offline else fetch)
    if not result["ok"]:
        emit({**result, "released": False})
        return 1
    digest = _str(result, "sha256")
    kept: dict[str, str] = {}
    for name in ("report.md", "brief.md"):
        src = run / name
        if src.is_file():
            dest = run / "releases" / f"{src.stem}-{sha256(src.read_bytes())[:8]}.md"
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                _ = shutil.copy2(src, dest)
            kept[name] = dest.relative_to(run).as_posix()
    by_id = {_str(r, "id"): r for r in current(read_jsonl(run / MANIFEST))}
    text = (run / "report.md").read_text(encoding="utf-8")
    cited = dict.fromkeys(m[1] for m in CITE_RE.finditer(text))
    row: Row = {
        "at": _str(result, "at"), "sha256": digest, "report": kept["report.md"],
        "brief": kept.get("brief.md"), "to": a.to, "audience": result["audience"],
        "live": result["live"], "note": a.note,
        "cites": {sid: evidence_key(by_id[sid]) for sid in cited if sid in by_id},
    }  # fmt: skip
    row = {k: v for k, v in row.items() if v not in (None, "")}
    append_jsonl(run / RELEASES, [row])
    append_log(run, f"{parse_date(None)}: released report ({digest[:8]})")
    emit({**row, "released": True})
    return 0


def cmd_decide(a: Args) -> int:
    """Record a decision taken on a released report, by whom, and what would reopen it."""
    run = run_dir(a.run)
    releases = read_jsonl(run / RELEASES)
    picked = [r for r in releases if _str(r, "sha256").startswith(a.release or "")]
    if not picked:
        msg = (
            f"--release {a.release}: no release with that hash"
            if releases
            else "nothing released yet; release the report so the decision traces to what was read"
        )
        raise ValueError(msg)
    digest = _str(picked[-1], "sha256")
    row: Row = {"at": now_utc(), "decision": a.decision, "by": a.by, "release": digest}
    row.update({k: v for k, v in (("revisit", a.revisit), ("note", a.note)) if v})
    append_jsonl(run / DECISIONS, [row])
    append_log(run, f"{parse_date(None)}: recorded a decision on report ({digest[:8]})")
    emit(row)
    return 0


def affected_releases(
    runs: list[tuple[str, Path]], latest: Path, states: dict[str, str]
) -> list[Row]:
    """Latest release to each reader that rests on a source since changed, failed, or retired.

    A later release to the same reader supersedes an earlier one, so re-releasing clears it.
    """
    rows = {_str(r, "id"): r for r in current(read_jsonl(latest / MANIFEST))}
    newest: dict[str, tuple[str, Path, Row]] = {}
    for day, run in sorted(runs):
        for rel in sorted(read_jsonl(run / RELEASES), key=lambda r: _str(r, "at")):
            newest[_str(rel, "to")] = (day, run, rel)
    out: list[Row] = []
    for day, run, rel in newest.values():
        cites = t.cast("dict[str, str]", rel.get("cites") or {})
        moved = sorted(
            sid
            for sid, key in cites.items()
            if sid not in rows or evidence_key(rows[sid]) != key or states.get(sid) in FAILURES
        )
        if moved:
            digest = _str(rel, "sha256")
            decisions = read_jsonl(run / DECISIONS)
            taken = [d.get("decision") for d in decisions if d.get("release") == digest]
            out.append({
                "date": day, "report": digest[:8], "to": rel.get("to"), "sources": moved,
                "decisions": taken,
            })  # fmt: skip
    return out


def bag_path(path: str) -> str:
    r"""``path`` as a BagIt manifest writes it: ``%``, CR, and LF percent-encoded (RFC 8493 2.1.3).

    Examples
    --------
    >>> bag_path("data/data/50%.csv"), bag_path("a\nb")
    ('data/data/50%25.csv', 'a%0Ab')
    >>> unbag_path(bag_path("50%0A\r"))
    '50%0A\r'
    """
    return path.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def unbag_path(path: str) -> str:
    """Inverse of `bag_path`; the escapes may be written in either case."""
    codes = {"25": "%", "0d": "\r", "0a": "\n"}
    return re.sub(r"%(25|0[dD]|0[aA])", lambda m: codes[m[1].lower()], path)


def write_bag(run: Path, out: Path) -> Row:
    r"""Pack every file of ``run`` into a zipped BagIt bag (RFC 8493) at ``out``.

    Examples
    --------
    >>> with tempfile.TemporaryDirectory() as d:
    ...     run = Path(d) / "2026-01-08" / "research" / "wal"
    ...     run.mkdir(parents=True)
    ...     _ = (run / "index.md").write_text("---\ntopic: wal\n---\n", encoding="utf-8")
    ...     bag = write_bag(run, Path(d) / "wal.zip")
    ...     (bag["files"], check_bag(Path(d) / "wal.zip")["ok"])
    (1, True)
    """
    meta = read_meta(run)
    day = _str(meta, "date") or run.parent.parent.name
    top = f"{_str(meta, 'topic') or run.name}-{day}"
    entries = [(f"data/{p.relative_to(run).as_posix()}", p) for p in sorted(run.rglob("*"))]
    entries = [(arc, p) for arc, p in entries if p.is_file()]
    size = sum(p.stat().st_size for _, p in entries)
    ident = f"{_str(meta, 'namespace') or run.parent.name}/{run.name}/{day}"
    tags = {
        "bagit.txt": "BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n",
        "bag-info.txt": (
            f"Bagging-Date: {parse_date(None)}\nBag-Software-Agent: {USER_AGENT}\n"
            f"External-Identifier: {ident}\nPayload-Oxum: {size}.{len(entries)}\n"
        ),
        "manifest-sha256.txt": "".join(
            f"{sha256(p.read_bytes())}  {bag_path(arc)}\n" for arc, p in entries
        ),
    }
    tags["tagmanifest-sha256.txt"] = "".join(
        f"{sha256(body.encode())}  {name}\n" for name, body in tags.items()
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=out.parent, prefix=f".{out.name}.")
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, strict_timestamps=False) as z:
            for name, body in tags.items():
                z.writestr(f"{top}/{name}", body)
            for arc, p in entries:
                z.write(p, f"{top}/{arc}")
        _ = Path(tmp).replace(out)
    finally:
        if Path(tmp).exists():
            Path(tmp).unlink()
    return {"bag": out.name, "files": len(entries), "bytes": size}


def check_bag(path: Path, expected: str | None = None) -> Row:
    """Re-hash a bag against both its manifests: files missing, changed, or unlisted.

    The manifests sit inside the zip, so they catch damage, not a rewrite of the
    files and both manifests together. ``expected`` is the zip's own SHA-256, kept
    elsewhere when the bag was made; a different zip fails.

    Examples
    --------
    >>> with tempfile.TemporaryDirectory() as d:
    ...     with zipfile.ZipFile(Path(d) / "x.zip", "w") as z:
    ...         z.writestr("x/readme.txt", "hi")
    ...     check_bag(Path(d) / "x.zip")
    Traceback (most recent call last):
    ...
    ValueError: x.zip is not a BagIt bag: no x/manifest-sha256.txt
    """
    try:
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if not n.endswith("/")]
            top = names[0].split("/", 1)[0] + "/" if names else ""
            files = {n[len(top) :] for n in names}
            manifests: dict[str, dict[str, str]] = {}
            for name in ("manifest-sha256.txt", "tagmanifest-sha256.txt"):
                if name not in files:
                    msg = f"{path.name} is not a BagIt bag: no {top}{name}"
                    raise ValueError(msg)
                body = z.read(top + name).decode("utf-8")
                manifests[name] = {
                    unbag_path(rel): digest
                    for digest, _, rel in (
                        ln.partition("  ") for ln in re.split(r"\r\n|\r|\n", body) if ln
                    )
                }
            listed = {**manifests["manifest-sha256.txt"], **manifests["tagmanifest-sha256.txt"]}
            changed = [
                r for r in sorted(set(listed) & files) if sha256(z.read(top + r)) != listed[r]
            ]
    except zipfile.BadZipFile as e:
        msg = f"{path.name} is not a zip file"
        raise ValueError(msg) from e
    payload = {f for f in files if f.startswith("data/")}
    missing = sorted(set(listed) - files)
    extra = sorted(payload - set(manifests["manifest-sha256.txt"]))
    digest = sha256(path.read_bytes())
    return {
        "bag": path.name,
        "ok": not (missing or extra or changed) and expected in (None, digest),
        "sha256": digest,
        "files": len(manifests["manifest-sha256.txt"]),
        "missing": missing,
        "changed": changed,
        "extra": extra,
        **({"sha256_expected": expected} if expected and expected != digest else {}),
    }


def cmd_export(a: Args) -> int:
    """Pack a run as a zipped BagIt bag beside it, or ``--check`` an existing bag's fixity.

    Never overwrites a bag. The written bag is re-opened and checked before success is
    reported, and its SHA-256 goes to ``exports.jsonl`` and the run's log, so the
    release trail can carry it.
    """
    if a.bag:
        result = check_bag(Path(a.bag), a.digest)
        emit(result)
        return 0 if result["ok"] else 1
    if not a.run:
        msg = "give --run to pack a run, or --check <bag> to check one"
        raise ValueError(msg)
    run = run_dir(a.run)
    out = Path(a.out) if a.out else run.parent / f"{run.name}-{run.parent.parent.name}.zip"
    if out.resolve().is_relative_to(run.resolve()):
        msg = "--out is inside the run; the bag would pack itself"
        raise ValueError(msg)
    if out.exists():
        msg = f"{out.name} already exists; pass --out with another name, or remove it first"
        raise ValueError(msg)
    packed = write_bag(run, out)
    verdict = check_bag(out)
    if not verdict["ok"]:
        out.unlink()
        bad = [x for k in ("missing", "changed", "extra") for x in t.cast("list[str]", verdict[k])]
        msg = f"{out.name} failed its own check and was removed (first problem: {bad[0]})"
        raise ValueError(msg)
    digest = _str(verdict, "sha256")
    append_jsonl(run / EXPORTS, [{"at": now_utc(), **packed, "sha256": digest}])
    append_log(run, f"{parse_date(None)}: exported bag {out.name} (sha256 {digest[:8]})")
    emit({**packed, "sha256": digest, "checked": True})
    return 0


# --- routing -------------------------------------------------------------------

STEPS = {
    "assess": ("start.md", "assessment.md"),
    "status": ("status.md",),
    "continue": ("continue.md",),
    "verify": ("verify.md",),
    "report": ("report.md",),
    "release": ("release.md",),
}
ROUTE_FLAGS: dict[str, tuple[str, ...]] = {
    "mode": MODES, "audience": AUDIENCES, "namespace": (), "root": (), "date": (), "expand": (),
    "to": (), "resume": (), "fill": (), "offline": (),
}  # fmt: skip
ROUTE_BOOLS = frozenset({"resume", "fill", "offline"})
# A quoted phrase is one token only when the quote opens a word, so an apostrophe
# ("don't") never starts one.
ROUTE_TOKEN = re.compile(r"""(?<!\S)(--[\w-]+=)?(['"])(.*?)\2[.,;:!?)]*(?=\s|$)|\S+""", re.DOTALL)
SENTENCE_TAIL = ".,;:!?)"


def route_tokens(text: str) -> list[str]:
    """Split free text into words, keeping a quoted phrase whole and never failing.

    >>> route_tokens("report wal. Use --to 'the platform team', don't wait")
    ['report', 'wal.', 'Use', '--to', 'the platform team', "don't", 'wait']
    >>> route_tokens('status --root="/srv/a b".')
    ['status', '--root=/srv/a b']
    """
    return [
        (m.group(1) or "") + m.group(3) if m.group(2) else m.group(0)
        for m in ROUTE_TOKEN.finditer(text)
    ]


def strip_tail(value: str) -> str:
    """Drop sentence punctuation after a value, never from a path made of dots.

    >>> strip_tail("2026-01-15."), strip_tail("."), strip_tail("../.."), strip_tail("out,")
    ('2026-01-15', '.', '../..', 'out')
    """
    if set(value) <= set("./"):
        return value
    return value.rstrip(SENTENCE_TAIL)


def route_flags(tokens: list[str]) -> tuple[dict[str, str | bool], list[str]]:
    """Split tokens into validated ``--flag[=value]`` options and the remaining words.

    Sentence punctuation after a flag or its value is dropped, so a request written
    as prose ("Use --date 2026-01-15.") reads the same as a bare command line.
    """
    flags: dict[str, str | bool] = {}
    words: list[str] = []
    i = 0
    while i < len(tokens):
        token, i = tokens[i], i + 1
        if not token.startswith("--") or len(token.rstrip(SENTENCE_TAIL)) <= 2:  # noqa: PLR2004
            words.append(token)
            continue
        name, eq, value = token[2:].partition("=")
        name = name.rstrip(SENTENCE_TAIL)
        if name not in ROUTE_FLAGS:
            msg = f"unknown option --{name}; known: {', '.join(f'--{k}' for k in ROUTE_FLAGS)}"
            raise ValueError(msg)
        if name in ROUTE_BOOLS:
            if eq:
                msg = f"--{name} takes no value"
                raise ValueError(msg)
            flags[name] = True
            continue
        if not eq and i < len(tokens) and not tokens[i].startswith("--"):
            value, i = tokens[i], i + 1
        if value[:1] in {"'", '"'}:
            msg = f"--{name}: unterminated quote in {value!r}"
            raise ValueError(msg)
        value = strip_tail(value)
        if not value:
            msg = f"--{name} needs a value"
            raise ValueError(msg)
        if name in flags:
            msg = f"--{name} is given twice"
            raise ValueError(msg)
        choices = ROUTE_FLAGS[name]
        if choices and value not in choices:
            msg = f"--{name} {value!r}: use one of {', '.join(choices)}"
            raise ValueError(msg)
        if name == "date" and not is_date(value):
            msg = f"--date {value!r}: expected YYYY-MM-DD"
            raise ValueError(msg)
        flags[name] = value
    return flags, words


def route_arguments(text: str) -> Row:
    r"""Parse a foray argument string: the step word, the flags, and the request left over.

    ``topic`` is set only when the rest is one name or one quoted phrase; otherwise the
    request is prose and the agent reads the topic from ``request``.

    Examples
    --------
    >>> out = route_arguments("continue sqlite-wal --fill --root=/r")
    >>> out["step"], out["topic"], out["flags"]
    ('continue', 'sqlite-wal', {'fill': True, 'root': '/r'})
    >>> out = route_arguments("report wal. Use --root out and --date 2026-01-15.")
    >>> out["step"], out["topic"], out["flags"], out["request"]
    ('report', None, {'root': 'out', 'date': '2026-01-15'}, 'wal. Use and')
    >>> route_arguments("sqlite-wal --fill.")["step"]
    'continue'
    """
    tokens = route_tokens(text)
    first = tokens[0].rstrip(SENTENCE_TAIL) if tokens else ""
    step = first if first in STEPS else ""
    flags, words = route_flags(tokens[1:] if step else tokens)
    if "fill" in flags and "expand" in flags:
        msg = "--fill and --expand are alternatives; pick one"
        raise ValueError(msg)
    inferred = not step and ("fill" in flags or "expand" in flags)
    step = "continue" if inferred else step
    rest = [w.rstrip(SENTENCE_TAIL) if len(words) == 1 else w for w in words]
    out: Row = {
        "step": step or None,
        "topic": rest[0] if len(rest) == 1 and rest[0] else None,
        "request": " ".join(words),
        "flags": flags,
        "references": list(STEPS[step]) if step else [],
    }
    if inferred:
        out["inferred"] = "continue, from --fill or --expand"
    return out


def cmd_route(a: Args) -> int:
    """Parse the arguments a foray skill received (from ``--stdin`` or after ``--``) into JSON."""
    words = a.words or []
    text = (
        sys.stdin.read()
        if a.stdin
        else " ".join(shlex.quote(w) for w in words[words[:1] == ["--"] :])
    )
    emit(route_arguments(text))
    return 0


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
    home = enclosing_run(Path(a.out).parent)
    if home:
        _ = writable_run(str(home))
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
    "searched": cmd_searched,
    "run": cmd_run,
    "conflict": cmd_conflict,
    "check": cmd_check,
    "release": cmd_release,
    "decide": cmd_decide,
    "export": cmd_export,
    "tally": cmd_tally,
    "prepare": cmd_prepare,
    "route": cmd_route,
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
    _ = ad.add_argument("--link", metavar="S<n>:<k>", help="the k-th URL links lists for S<n>")
    _ = ad.add_argument(
        "--fields", metavar="FILE", help="JSON object with quote (string or list), title, author"
    )
    _ = ad.add_argument("--ref", help="tag, commit, edition, or version the claim rests on")
    _ = ad.add_argument("--title")
    _ = ad.add_argument("--author")
    grp = ad.add_mutually_exclusive_group()
    _ = grp.add_argument("--file", help="a capture you saved")
    _ = grp.add_argument("--fetch", action="store_true", help="download the capture now")
    _ = grp.add_argument(
        "--unretrieved", metavar="REASON", help="could not capture it: paywall, login, removed, ..."
    )
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

    se = sub.add_parser("searched", help="log a search: the query, where, and the result count")
    _ = se.add_argument("--run", required=True)
    _ = se.add_argument("--query", default="", help="the query exactly as run")
    _ = se.add_argument("--fields", metavar="FILE", help="JSON object with query")
    _ = se.add_argument(
        "--failed",
        choices=SEARCH_FAILURES,
        help="the search failed, so it found nothing and shows nothing: a gap, not an absence",
    )
    _ = se.add_argument("--where", help="search engine, site, index, or archive")
    _ = se.add_argument("--results", type=int, help="how many results came back")
    _ = se.add_argument("--note", help="what the search found or missed")

    ru = sub.add_parser("run", help="run a command and keep it as a measured source")
    _ = ru.add_argument("--run", required=True)
    _ = ru.add_argument("--name", required=True, help="slug for data/<name>.log")
    _ = ru.add_argument("--title")
    _ = ru.add_argument("--output", action="append", help="file under data/ it writes (repeatable)")
    _ = ru.add_argument("--quote", action="append", help="exact output a claim rests on")
    _ = ru.add_argument("--fields", metavar="FILE", help="JSON object with quote (string or list)")
    _ = ru.add_argument("--timeout", type=float, help="seconds before the command is stopped")
    _ = ru.add_argument("command", nargs=argparse.REMAINDER, help="-- then the command")

    co = sub.add_parser("conflict", help="record where sources disagree, or how it was weighed")
    _ = co.add_argument("--run", required=True)
    _ = co.add_argument("--source", dest="sources", action="append", help="a side (repeatable)")
    _ = co.add_argument("--about", help="what the sources dispute")
    _ = co.add_argument("--id", dest="conflict", help="update a recorded conflict")
    _ = co.add_argument("--weight", help="the source that carries more weight")
    _ = co.add_argument("--why", help="why it carries more weight")
    _ = co.add_argument("--settle", help="what evidence would settle it")

    ck = sub.add_parser("check", help="every ship check, fresh: sources, table, lint, scan")
    _ = ck.add_argument("--run", required=True)
    _ = ck.add_argument("--offline", action="store_true", help="captures only, no network")

    rl = sub.add_parser("release", help="pass check, keep the exact report, log who got it")
    _ = rl.add_argument("--run", required=True)
    _ = rl.add_argument("--to", required=True, help="who receives it, as a role or group")
    _ = rl.add_argument(
        "--audience", required=True, choices=AUDIENCES, help="the reader's; must equal the run's"
    )
    _ = rl.add_argument("--note")
    _ = rl.add_argument("--offline", action="store_true", help="captures only, no network")
    _ = rl.add_argument(
        "--allow-offline", action="store_true", help="let --offline release; recorded as offline"
    )

    de = sub.add_parser("decide", help="record a decision taken on a released report")
    _ = de.add_argument("--run", required=True)
    _ = de.add_argument("--decision", required=True)
    _ = de.add_argument("--by", required=True, help="who decided, as a role")
    _ = de.add_argument("--release", help="the release's hash prefix, default the latest")
    _ = de.add_argument("--revisit", help="what would reopen the decision")
    _ = de.add_argument("--note")

    ex = sub.add_parser("export", help="pack a run as a zipped BagIt bag, or check one")
    _ = ex.add_argument("--run")
    _ = ex.add_argument("--out", default="", help="bag path, default beside the run")
    _ = ex.add_argument("--check", dest="bag", help="check a bag's fixity instead")
    _ = ex.add_argument(
        "--sha256", dest="digest", help="with --check: the zip's SHA-256 printed when it was packed"
    )

    ta = sub.add_parser("tally", help="an assessment's rating counts and one-grade sensitivity")
    _ = ta.add_argument("--run", required=True)
    _ = ta.add_argument(
        "--markdown", action="store_true", help="print the report's ## Criteria section instead"
    )

    pp = sub.add_parser("prepare", help="verify, then write the report's Sources table")
    _ = pp.add_argument("--run", required=True)
    _ = pp.add_argument("--offline", action="store_true", help="captures only, no network")

    ro = sub.add_parser("route", help="parse a foray argument string into step, topic, and flags")
    _ = ro.add_argument("--stdin", action="store_true", help="read the arguments from stdin")
    _ = ro.add_argument("words", nargs=argparse.REMAINDER, help="-- then the arguments")
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
