#!/usr/bin/env python3
"""Deterministic checks for business run packages (stdlib only).

Subcommands:

- ``stats``: median, IQR, and a seeded BCa bootstrap interval for the median.
- ``scan``: tier-3 sanitization scan of a draft for identifiers, secrets, names, and money terms.
- ``trace``: check that every figure in a derived text appears in its source text.
- ``stamp`` and ``fresh``: record, then verify, the inputs each written report derives from.
- ``source``: write a ``sources.md`` entry (path, clock time, hash) for an output file.
- ``init``: create a run directory, refusing to reuse one that holds raw snapshots.
- ``assumptions``: required-field check of an ``assumptions.yaml`` register.
- ``runs``: list run directories newest first, ordered by the date in the path.
- ``project``: the org-wide projection and scenarios from register ids.
- ``breakeven``: net per-instance saving, net period saving, and break-even from register ids.
- ``gate``: the completeness gate for one run package, with figures recomputed from ``raw/``.
- ``collect-prs``: per-PR cycle-time rows from ``gh api graphql`` pull-request pages.

Run ``business.py <command> --help`` for each command.
"""

import argparse
import collections
import contextlib
import csv
import datetime as dt
import decimal
import hashlib
import io
import json
import math
import random
import re
import statistics
import sys
import time
import typing as t
from pathlib import Path
from urllib.parse import urlsplit

if t.TYPE_CHECKING:
    from collections.abc import Callable, Collection, Sequence

    Subparsers = argparse._SubParsersAction[argparse.ArgumentParser]  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]

DIRECTIONAL_BELOW = 20
MIN_OBSERVATIONS = 2
MIN_INTERVAL_N = 5
REGISTER_INDENT = 2
TIER_PUBLIC = 3
README_FIELDS = ("Scope:", "Window:", "Instruments:", "Timezone: UTC", "Names:", "People:")

_NOT_TICKETS = "ISO|SHA|UTF|GPT|COVID|RFC|CVE|CWE|PEP|AES|RSA|TLS|SSL|UTC|GMT"
_HOST_SUFFIXES = (
    "local|localdomain|internal|corp|lan|intranet|home|private|example|test|invalid|localhost"
    "|com|net|org|io|dev|co|ai|app|cloud|gov|edu"
)
_SECRET_FORMS = (
    r"\bgh[pousr]_[A-Za-z0-9]{20,}",
    r"\bgithub_pat_\w{20,}",
    r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
    r"\bxox[abposr]-[A-Za-z0-9-]{10,}",
    r"\bsk-[A-Za-z0-9_-]{20,}",
    r"\bglpat-[\w-]{20,}",
    r"\bAIza[\w-]{35}\b",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
)
_PATH_FORMS = (
    r"(?:/home/|/Users/|/mnt/[a-z]/|~/)\S*",
    r"\b[A-Za-z]:[\\/][\w$.-]+\S*",
    r"\\\\[\w.$-]+\\\S*",
    r"(?<![\w/.:~-])/(?:opt|srv|var|etc|usr|root|data|tmp|workspace|app|Volumes)/\S*",
)
_MONEY_FORMS = (
    "ROI",
    "dollars?",
    "cost[- ]?savings?",
    r"monetiz\w*",
    "payback",
    "salar(?:y|ies)",
    "wages?",
    "payroll",
    "budgets?",
    "pric(?:e|es|ed|ing)",
    "euros?",
    "bucks?",
    "yen",
    "rupees?",
    "pesos?",
    "francs?",
    "revenue",
    r"profit\w*",
    "cents?",
)
_MONEY_WORDS = "|".join(_MONEY_FORMS)
_REPO_NAME = r"[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*"
_OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"

SCAN_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ticket-id",
        re.compile(rf"\b(?!(?:{_NOT_TICKETS})-)(?![HQ][1-4]-|FY\d)[A-Z][A-Z0-9]+-\d+\b"),
    ),
    ("url", re.compile(r"https?://\S+|\bwww\.\S+")),
    (
        "secret",
        re.compile("|".join(_SECRET_FORMS)),
    ),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    (
        "path",
        re.compile("|".join(_PATH_FORMS)),
    ),
    (
        "host",
        re.compile(
            rf"(?<![\w@/.-])(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+(?:{_HOST_SUFFIXES})(?![\w-])"
        ),
    ),
    ("commit-sha", re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b")),
    ("ip", re.compile(rf"(?<![\w.])(?:{_OCTET}\.){{3}}{_OCTET}(?!\w|\.\d)")),
    ("handle", re.compile(r"(?<![\w.+@-])@[A-Za-z0-9][A-Za-z0-9_-]{0,38}(?![\w@]|\.\w)")),
    (
        "repo-slug",
        re.compile(
            rf"(?<![\w/.:@~-])[A-Za-z][A-Za-z0-9-]{{2,38}}/(?=[\w.-]{{3}}){_REPO_NAME}(?![\w/])"
        ),
    ),
    (
        "currency",
        re.compile(r"[$€£¥\uff04\uffe5\uffe1₹₩₽¢]|\b(?:USD|EUR|GBP|JPY|CAD|AUD|CHF|CNY|INR)\b"),
    ),
    (
        "money-term",
        re.compile(
            rf"\b(?:{_MONEY_WORDS})\b",
            re.IGNORECASE,
        ),
    ),
)
COVERING_KINDS = frozenset({"url", "email", "path", "secret"})
COVERED_KINDS = frozenset({"host", "ip", "handle", "repo-slug", "commit-sha"})
COMMON_PAIRS = frozenset(
    {
        "read/write", "input/output", "client/server", "true/false", "pass/fail", "before/after",
        "start/end", "build/test", "request/response", "producer/consumer", "source/target",
        "pros/cons", "and/or", "either/or", "his/her", "he/she", "yes/no", "on/off", "tcp/ip",
        "stdin/stdout", "http/https", "create/update", "push/pull", "pull/push", "win/loss",
        "cause/effect", "plan/act", "buy/build", "over/under", "left/right", "up/down",
    }
)  # fmt: skip
MIN_NAME_WORD = 3
NAME_STOPWORDS = frozenset(
    {"the", "and", "for", "inc", "llc", "ltd", "corp", "co", "team", "group", "org", "project"}
)
PEOPLE_LINE = re.compile(r"^People:[ \t]*\S", re.MULTILINE)

ASSUMPTION_FIELDS = (
    "id",
    "description",
    "value",
    "unit",
    "source_type",
    "confidence",
    "rationale",
    "source_ref",
    "retrieved",
    "owner",
    "updated",
)
QUANTITY_ALIASES = {"baseline-minutes": "manual-minutes"}
SAVINGS_RATE_TOLERANCE = 0.01
_SAVING_IDS = (
    "manual-minutes",
    "ai-minutes",
    "verify-minutes",
    "rework-probability",
    "rework-minutes",
)
SOURCE_TYPES = ("MEASURED", "DERIVED", "BENCHMARKED", "ESTIMATED")
CONFIDENCES = ("high", "medium", "low")
DATE_DIR = re.compile(r"\d{4}-\d{2}-\d{2}")
NAMES_LINE = re.compile(r"^Names:[ \t]*\S", re.MULTILINE)
DATE_RANGE = re.compile(r"\d{4}-\d{2}-\d{2}\s*(?:\.\.|to|\u2013|-)\s*\d{4}-\d{2}-\d{2}")
TAGS = ("MEASURED", "DERIVED", "BENCHMARKED", "ESTIMATED")
CITATION = re.compile(r"sources\.md(?:#|\s+`)([\w-]+)")
_TIME_UNITS = (
    "ms|s|secs?|seconds?|mins?|minutes?|h|hrs?|hours?|days?|weeks?|months?|quarters?|years?"
)
FIGURE = re.compile(
    rf"\d(?:\.\d+)?[\s-]?(?:%|(?:{_TIME_UNITS}|PRs?|engineers?|tasks?|drafts?|instances?)\b)",
    re.IGNORECASE,
)
PINNED_LINK = re.compile(r"https?://\S+|\bdoi:\s*\S+|\b10\.\d{4,9}/\S+|\barXiv:\s*\d{4}\.\d{4,5}")
SENTENCE_END = re.compile(r"(?<=[.!?;])\s+(?=[A-Z])")
_GATE_MONEY_FORMS = (
    "roi", "dollars?", "cost[- ]?savings?", r"monetiz\w*", "payback", "salar(?:y|ies)",
    "wages?", "payroll", "revenue", r"profit\w*", "euros?", "bucks?",
)  # fmt: skip
GATE_MONEY = re.compile("|".join(_GATE_MONEY_FORMS), re.IGNORECASE)
UNIT_START = re.compile(r"\s*(?:[-*]|\d+\.|\|)\s?")
CHECK_LINE = re.compile(r"\s*(?:[-*]\s*)?check:", re.IGNORECASE)
CHECK_SPEC = re.compile(
    r"\s*(?:[-*]\s*)?check:\s*(median|mean|min|max|n)\s+(\S+)\s+(\S+)\s*=\s*(-?\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)
SOURCE_FIELDS = (
    ("query", re.compile(r"^\W*(?:query|command)\s*:\s*\S", re.IGNORECASE)),
    ("timestamp", re.compile(r"^\W*(?:executed|timestamp|run at)\s*:\s*\S", re.IGNORECASE)),
    ("tool version", re.compile(r"^\W*(?:tool )?version\s*:\s*\S", re.IGNORECASE)),
    ("output file", re.compile(r"^\W*output(?: file)?\s*:\s*\S", re.IGNORECASE)),
)
TIMESTAMP_VALUE = re.compile(r"^\W*(?:executed|timestamp|run at)\s*:\s*(.+?)\s*$", re.IGNORECASE)
OUTPUT_LINE = re.compile(r"^\W*output(?: file)?\s*:\s*(.+)$", re.IGNORECASE)
CHECK_TOLERANCE = 0.005
UNKNOWN_DATA = re.compile(r"\b(?:resolve|needs?|requires?|data|exports?)\b", re.IGNORECASE)
_RESOLVERS = r"(?:resolve|needs?|requires?|data|exports?)"
NO_DATA = re.compile(
    rf"\b(?:no|not|without|lacks?|lacking|nothing|none)\s+(?:\w+\s+){{0,2}}?{_RESOLVERS}\b",
    re.IGNORECASE,
)


def _median(values: list[float]) -> float:
    return float(statistics.median(values))


def bca_interval(
    values: list[float],
    *,
    seed: int,
    resamples: int = 10000,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Return the BCa bootstrap interval for the median, deterministic per seed.

    Examples
    --------
    >>> bca_interval([1, 2, 3, 4, 5, 6, 7, 8], seed=1, resamples=2000)
    (2.0, 7.0)
    >>> bca_interval([1, 2, 3, 4, 5, 6, 7, 8], seed=1, resamples=2000) == bca_interval(
    ...     [1, 2, 3, 4, 5, 6, 7, 8], seed=1, resamples=2000
    ... )
    True
    >>> bca_interval([5.0, 5.0, 5.0], seed=1, resamples=500)
    (5.0, 5.0)
    """
    n = len(values)
    if n < MIN_OBSERVATIONS:
        msg = "need at least 2 observations"
        raise ValueError(msg)
    rng = random.Random(seed)
    boots = sorted(_median(rng.choices(values, k=n)) for _ in range(resamples))
    theta = _median(values)
    below = sum(b < theta for b in boots) + 0.5 * sum(b == theta for b in boots)
    frac = min(max(below / resamples, 0.5 / resamples), 1 - 0.5 / resamples)
    norm = statistics.NormalDist()
    z0 = norm.inv_cdf(frac)
    jack = [_median(values[:i] + values[i + 1 :]) for i in range(n)]
    mean_j = sum(jack) / n
    num = sum((mean_j - j) ** 3 for j in jack)
    spread = sum((mean_j - j) ** 2 for j in jack)
    den = 6.0 * spread * math.sqrt(spread)
    accel = num / den if den else 0.0
    ends: list[float] = []
    for p in (alpha / 2, 1 - alpha / 2):
        z = norm.inv_cdf(p)
        adj = norm.cdf(z0 + (z0 + z) / (1 - accel * (z0 + z)))
        ends.append(boots[min(resamples - 1, max(0, int(adj * resamples)))])
    return ends[0], ends[1]


def summarize(values: list[float], *, seed: int, resamples: int = 10000) -> dict[str, object]:
    """Summarize observations as median, IQR, interval, and a DIRECTIONAL flag.

    Below ``MIN_INTERVAL_N`` observations a bootstrap interval is only the
    range, so ``range_lo``/``range_hi`` replace ``ci95_lo``/``ci95_hi``.

    Examples
    --------
    >>> out = summarize([float(x) for x in range(1, 31)], seed=7, resamples=1000)
    >>> (out["n"], out["median"], out["q1"], out["q3"], out["label"])
    (30, 15.5, 8.25, 22.75, 'ok')
    >>> summarize([1.0, 2.0, 9.0], seed=7, resamples=500)["label"]
    'DIRECTIONAL'
    >>> small = summarize([10.0, 36.0], seed=7, resamples=500)
    >>> (small["range_lo"], small["range_hi"], "ci95_lo" in small)
    (10.0, 36.0, False)
    """
    if not all(math.isfinite(value) for value in values):
        msg = "observations must be finite numbers"
        raise ValueError(msg)
    q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
    n = len(values)
    if n < MIN_INTERVAL_N:
        interval: dict[str, object] = {
            "range_lo": min(values),
            "range_hi": max(values),
            "method": f"range only; n < {MIN_INTERVAL_N}, no 95% interval",
        }
    else:
        lo, hi = bca_interval(values, seed=seed, resamples=resamples)
        interval = {
            "ci95_lo": lo,
            "ci95_hi": hi,
            "method": "BCa bootstrap of the median",
        }
    summary: dict[str, object] = {
        "n": n,
        "median": _median(values),
        "q1": q1,
        "q3": q3,
        **interval,
        "seed": seed,
        "resamples": resamples,
        "label": "DIRECTIONAL" if n < DIRECTIONAL_BELOW else "ok",
    }
    if any(isinstance(value, float) and not math.isfinite(value) for value in summary.values()):
        msg = "statistics exceed the supported numeric range"
        raise ValueError(msg)
    return summary


def parse_numbers(text: str) -> list[float]:
    r"""Parse one number per line, skipping blanks and ``#`` comments.

    Examples
    --------
    >>> parse_numbers("1\n# c\n\n2.5\n")
    [1.0, 2.5]
    """
    return [float(line.split("#")[0]) for line in text.splitlines() if line.split("#")[0].strip()]


def parse_names(text: str, label: str = "Names") -> list[str]:
    r"""Return the names on the ``Names:`` (or ``label:``) lines of a README.

    ``none`` means no names.

    Examples
    --------
    >>> parse_names("Window: x\nNames: Acme, `lean-tighten`; Priya Raman\n")
    ['Acme', 'lean-tighten', 'Priya Raman']
    >>> parse_names("Names: none\n")
    []
    >>> parse_names("Names: Acme\nPeople: Priya Raman\n", "People")
    ['Priya Raman']
    """
    names: list[str] = []
    for match in re.finditer(rf"^{label}:[ \t]*(.*)$", text, re.MULTILINE):
        names.extend(n.strip().strip("`'\"*_ ") for n in re.split(r"[,;]", match.group(1)))
    names = [n for n in names if n]
    return [] if [n.lower() for n in names] == ["none"] else names


def name_patterns(names: Sequence[str]) -> list[re.Pattern[str]]:
    """Return case-insensitive patterns that deny each name and its separator variants.

    A name matches whole, with any run of separators or none between its parts
    (``lean-tighten``, ``LeanTighten``, ``lean tighten``). A name written as
    several words also denies each word of three or more letters on its own.

    Examples
    --------
    >>> [bool(p.search("Hey PRIYA")) for p in name_patterns(["Priya Raman"])]
    [False, True, False]
    >>> any(p.search("a lean_tighten run") for p in name_patterns(["LeanTighten"]))
    True
    >>> any(p.search("the Atlassian suite") for p in name_patterns(["Atlas"]))
    False
    """
    patterns: list[re.Pattern[str]] = []
    for name in names:
        parts = [w for w in re.split(r"[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])", name.strip()) if w]
        if not parts:
            continue
        pieces = ["[\\W_]*".join(re.escape(w) for w in parts)]
        if len(name.split()) > 1:
            pieces.extend(
                re.escape(w)
                for w in parts
                if len(w) >= MIN_NAME_WORD and w.lower() not in NAME_STOPWORDS
            )
        patterns.extend(
            re.compile(rf"(?<![A-Za-z0-9]){piece}(?![A-Za-z0-9])", re.IGNORECASE)
            for piece in pieces
        )
    return patterns


def scan_text(
    text: str,
    deny: Sequence[str] = (),
    allow: Sequence[str] = (),
    allow_url: Sequence[str] = (),
    rules: Sequence[str] = (),
) -> list[tuple[int, int, str, str]]:
    """Return ``(line, column, kind, match)`` for every tier-3 exclusion in ``text``.

    ``deny`` names match whole-word, case-insensitively, with separator variants
    (see ``name_patterns``). ``allow`` skips hits whose text equals an entry;
    ``allow_url`` skips URLs that start with an entry, and bare hosts of those
    URLs; a non-empty ``rules`` keeps only those kinds. A host, address, handle,
    or repository slug inside a URL, email, path, or secret is not reported again.

    Examples
    --------
    >>> [h[2:] for h in scan_text("See PROJ-123, https://corp.example/x, /home/ann/n.")]
    [('ticket-id', 'PROJ-123'), ('url', 'https://corp.example/x,'), ('path', '/home/ann/n.')]
    >>> scan_text("Saved 40 hours; no ROI claim.")
    [(1, 20, 'money-term', 'ROI')]
    >>> scan_text("Acme shipped it.", deny=["acme"])
    [(1, 1, 'denied-name', 'Acme')]
    >>> scan_text("Median fell from 26 h to 9 h (MEASURED, n=41).")
    []
    >>> scan_text("GPT-4, SHA-256 and Q2-2026 are not tickets.")
    []
    >>> [h[3] for h in scan_text("PROJ-4 and ABC-8.", allow=["ABC-8"])]
    ['PROJ-4']
    >>> scan_text("See https://arxiv.org/abs/2507.09089", allow_url=["https://arxiv.org/"])
    []
    >>> [h[2:] for h in scan_text("ROI at https://x.example, $5", rules=["currency"])]
    [('currency', '$')]
    >>> [h[2] for h in scan_text("wiki.acme.example, 10.2.3.4, @ann-dev, acme/widgets")]
    ['host', 'ip', 'handle', 'repo-slug']
    """
    patterns = [
        *SCAN_RULES,
        *(("denied-name", pattern) for pattern in name_patterns(deny)),
    ]
    if rules:
        patterns = [(kind, pattern) for kind, pattern in patterns if kind in rules]
    allowed_hosts = {urlsplit(prefix).hostname for prefix in allow_url}
    hits: set[tuple[int, int, str, str]] = set()
    for number, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in patterns:
            for m in pattern.finditer(line):
                found = m.group()
                if found in allow or (kind == "url" and found.startswith(tuple(allow_url))):
                    continue
                if kind == "host" and found in allowed_hosts:
                    continue
                if kind == "repo-slug" and found.lower() in COMMON_PAIRS:
                    continue
                hits.add((number, m.start() + 1, kind, found))
    return sorted(h for h in hits if not _covered(h, hits))


def _covered(hit: tuple[int, int, str, str], hits: Collection[tuple[int, int, str, str]]) -> bool:
    line, col, kind, found = hit
    for other in hits:
        o_line, o_col, o_kind, o_found = other
        if other == hit or o_line != line:
            continue
        inside = o_col <= col and col + len(found) <= o_col + len(o_found)
        if not inside:
            continue
        if kind in COVERED_KINDS and o_kind in COVERING_KINDS:
            return True
        if kind == o_kind == "denied-name" and len(o_found) > len(found):
            return True
    return False


def _is_date(text: str) -> bool:
    try:
        _ = dt.date.fromisoformat(text)
    except ValueError:
        return False
    return True


def _is_timestamp(text: str) -> bool:
    """Return whether ``text`` is an ISO 8601 date and time of day.

    Examples
    --------
    >>> [_is_timestamp(x) for x in ("2026-06-30T10:00:00Z", "2026-06-30", "2026-invented")]
    [True, False, False]
    """
    value = text.strip().strip("`")
    if not re.search(r"\d{2}:\d{2}", value):
        return False
    try:
        _ = dt.datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_number(text: str) -> bool:
    try:
        value = float(text)
    except ValueError:
        return False
    return math.isfinite(value)


def _parse_register(text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        body = line.lstrip()
        if body.startswith("- "):
            entries.append({})
            body = body[2:]
        if ":" in body and entries:
            key, _, value = body.partition(":")
            entries[-1][key.strip()] = value.strip()
    return entries


def _register_format_problems(text: str, entries: Sequence[dict[str, str]]) -> list[str]:
    problems: list[str] = []
    index = -1
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        body = line.lstrip()
        if not body or body.startswith("#"):
            continue
        indent = len(line) - len(body)
        if body.startswith("- ") and indent == 0:
            index += 1
            body = body[2:]
        elif body.startswith("- ") or indent > REGISTER_INDENT:
            problems.append(f"line {number}: nested structure; write flat key: value lines")
            continue
        name = (entries[index].get("id") if 0 <= index < len(entries) else None) or f"#{index + 1}"
        key, _, value = body.partition(":")
        value = value.strip()
        if value[:1] in ("'", '"'):
            problems.append(f"entry {name}: line {number}: {key.strip()} is quoted; write it bare")
        elif re.search(r"\s#", value):
            problems.append(f"entry {name}: line {number}: {key.strip()} has a trailing # comment")
    return problems


def check_assumptions(text: str, sources: Collection[str] | None = None) -> list[str]:
    r"""Return problems in an ``assumptions.yaml`` register of flat ``key: value`` entries.

    ``value`` must be numeric, dates ISO, and a MEASURED ``source_ref`` must be
    ``sources.md#<name>``; with ``sources`` given, that name must be in it.

    Examples
    --------
    >>> vals = {
    ...     "source_type": "MEASURED",
    ...     "confidence": "low",
    ...     "value": "0.6",
    ...     "retrieved": "2026-06-30",
    ...     "updated": "2026-06-30",
    ...     "source_ref": "sources.md#seats",
    ... }
    >>> keys = ASSUMPTION_FIELDS[1:]
    >>> good = "\n".join(["- id: a", *[f"  {k}: {vals.get(k, 'x')}" for k in keys]])
    >>> check_assumptions(good)
    []
    >>> check_assumptions(good, sources=["other"])
    ['entry a: source_ref names no entry in sources.md']
    >>> check_assumptions(good.replace("0.6", "most"))
    ["entry a: value 'most' is not a number"]
    >>> check_assumptions("- id: a\n  value: 1")[0]
    'entry a: missing description'
    >>> check_assumptions("")
    []
    """
    entries = _parse_register(text)
    problems = _register_format_problems(text, entries)
    seen: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        name = entry.get("id") or f"#{index}"
        if name in seen:
            problems.append(f"entry {name}: duplicate id")
        seen.add(name)
        problems.extend(f"entry {name}: missing {k}" for k in ASSUMPTION_FIELDS if not entry.get(k))
        if entry.get("source_type") and entry["source_type"] not in SOURCE_TYPES:
            problems.append(
                f"entry {name}: source_type {entry['source_type']!r} is not one of {SOURCE_TYPES}"
            )
        if entry.get("confidence") and entry["confidence"] not in CONFIDENCES:
            problems.append(
                f"entry {name}: confidence {entry['confidence']!r} is not one of {CONFIDENCES}"
            )
        problems.extend(_check_entry_values(name, entry, sources))
    problems.extend(_check_quantities({e.get("id", ""): e for e in entries}))
    return problems


def _alias_problems(entries: Collection[str]) -> list[str]:
    return [
        f"{alias}: same quantity as {canon}; register only {canon}"
        for alias, canon in QUANTITY_ALIASES.items()
        if alias in entries
    ]


def _check_quantities(entries: dict[str, dict[str, str]]) -> list[str]:
    """Return problems where one quantity is registered under two ids.

    ``savings-rate`` is ``S_inst / manual-minutes``; when its parts are registered
    too, the stated rate must match the one they imply.
    """
    problems = _alias_problems(entries)
    try:
        v = {i: float(entries[i]["value"]) for i in _SAVING_IDS}
        rate = float(entries["savings-rate"]["value"])
    except KeyError, ValueError:
        return problems
    if v["manual-minutes"] > 0:
        implied = (
            v["manual-minutes"]
            - v["ai-minutes"]
            - v["verify-minutes"]
            - v["rework-probability"] * v["rework-minutes"]
        ) / v["manual-minutes"]
        if abs(implied - rate) > SAVINGS_RATE_TOLERANCE:
            problems.append(
                f"savings-rate: {rate:g} disagrees with the {implied:.3g} its parts imply"
            )
    return problems


def _check_entry_values(
    name: str, entry: dict[str, str], sources: Collection[str] | None
) -> list[str]:
    problems: list[str] = []
    value = entry.get("value")
    if value and not _is_number(value):
        problems.append(f"entry {name}: value {value!r} is not a number")
    problems.extend(
        f"entry {name}: {k} {entry[k]!r} is not an ISO date"
        for k in ("retrieved", "updated")
        if entry.get(k) and not _is_date(entry[k])
    )
    if entry.get("source_type") == "MEASURED" and entry.get("source_ref"):
        match = re.fullmatch(r"sources\.md#([\w-]+)", entry["source_ref"])
        if not match:
            problems.append(f"entry {name}: MEASURED source_ref must be sources.md#<name>")
        elif sources is not None and match.group(1) not in sources:
            problems.append(f"entry {name}: source_ref names no entry in sources.md")
    return problems


FACTORS = (
    ("V", "addressable-population"),
    ("F", "instances-per-person-year"),
    ("t", "manual-minutes"),
    ("s", "savings-rate"),
    ("a", "adoption-rate"),
    ("r", "realization-rate"),
)
MINUTES_PER_HOUR = 60


def project(register: str) -> tuple[dict[str, float], list[str]]:
    r"""Project annual engineer-hours from register ids; return ``(figures, problems)``.

    Each factor is the register entry named in ``FACTORS``; its optional ``low``
    and ``high`` fields bound the scenarios. The conservative scenario takes every
    factor at ``low``, base at ``value``, upside at ``high``; a missing bound
    falls back to ``value``. ``a`` and ``r`` must lie strictly between 0 and 1. A
    negative ``savings-rate`` is a measured loss and projects a negative figure; its
    conservative scenario takes the high-volume factors.

    Examples
    --------
    >>> reg = "\n".join(
    ...     f"- id: {i}\n  value: {v}\n  low: {lo}\n  high: {hi}"
    ...     for i, v, lo, hi in [
    ...         ("addressable-population", 40, 30, 50),
    ...         ("instances-per-person-year", 100, 100, 100),
    ...         ("manual-minutes", 30, 25, 40),
    ...         ("savings-rate", 0.4, 0.3, 0.6),
    ...         ("adoption-rate", 0.5, 0.3, 0.7),
    ...         ("realization-rate", 0.6, 0.4, 0.8),
    ...     ]
    ... )
    >>> figures, problems = project(reg)
    >>> (problems, figures["base"], figures["conservative"], figures["upside"])
    ([], 240.0, 45.0, 1120.0)
    >>> (figures["addressable"], figures["served"], figures["realized"])
    (800.0, 400.0, 240.0)
    >>> sorted((k for k in figures if k.startswith("swing_")), key=lambda k: -figures[k])[:2]
    ['swing_a', 'swing_s']
    >>> "adoption-rate: value 1.0 must be strictly between 0 and 1" in project(
    ...     "- id: adoption-rate\n  value: 1"
    ... )[1]
    True
    >>> rate = "value: 0.4\n  low: 0.3\n  high: 0.6"
    >>> loss = reg.replace(rate, "value: -0.2\n  low: -0.3\n  high: -0.1")
    >>> figures, problems = project(loss)
    >>> (problems, figures["conservative"], figures["base"], figures["upside"])
    ([], -560.0, -120.0, -15.0)
    """
    entries = {e.get("id", ""): e for e in _parse_register(register)}
    problems = _alias_problems(entries)
    levels: dict[str, tuple[float, float, float]] = {}
    for symbol, ident in FACTORS:
        entry = entries.get(ident)
        if entry is None:
            problems.append(f"{ident}: missing from the assumptions register")
            continue
        try:
            base = float(entry["value"])
            low = float(entry.get("low") or base)
            high = float(entry.get("high") or base)
        except KeyError, ValueError:
            problems.append(f"{ident}: value, low, and high must be finite numbers")
            continue
        if not all(math.isfinite(x) for x in (low, base, high)):
            problems.append(f"{ident}: value, low, and high must be finite numbers")
            continue
        if not low <= base <= high:
            problems.append(f"{ident}: need low <= value <= high")
        if low < 0 and symbol != "s":
            problems.append(f"{ident}: value, low, and high must be nonnegative")
        if symbol in ("a", "r"):
            problems.extend(
                f"{ident}: {name} {x} must be strictly between 0 and 1"
                for name, x in (("value", base), ("low", low), ("high", high))
                if not 0 < x < 1
            )
        elif symbol == "s" and high > 1:
            problems.append(f"{ident}: high {high} must be at most 1")
        levels[symbol] = (low, base, high)
    if problems:
        return {}, problems

    def hours(pick: Callable[[str], float], upto: str = "r") -> float:
        total = 1.0
        for symbol, _ in FACTORS:
            total *= pick(symbol) / (MINUTES_PER_HOUR if symbol == "t" else 1)
            if symbol == upto:
                break
        return total

    def at(index: int) -> Callable[[str], float]:
        return lambda sym: levels[sym][index]

    def with_savings(volume: int, rate: int) -> Callable[[str], float]:
        return lambda sym: levels[sym][rate if sym == "s" else volume]

    figures: dict[str, float] = {
        "conservative": min(hours(with_savings(0, 0)), hours(with_savings(2, 0))),
        "base": hours(at(1)),
        "upside": max(hours(with_savings(2, 2)), hours(with_savings(0, 2))),
        "addressable": hours(at(1), "s"),
        "served": hours(at(1), "a"),
        "realized": hours(at(1)),
    }
    for symbol, _ in FACTORS:
        swing = hours(lambda sym, s=symbol: levels[sym][2 if sym == s else 1]) - hours(
            lambda sym, s=symbol: levels[sym][0 if sym == s else 1]
        )
        figures[f"swing_{symbol}"] = abs(swing)
    if not all(math.isfinite(value) for value in figures.values()):
        return {}, ["projection exceeds the supported numeric range"]
    return {k: round(v, 2) for k, v in figures.items()}, []


BREAKEVEN_INPUTS = (
    ("t_manual", "manual-minutes", "benefit"),
    ("t_ai", "ai-minutes", "cost"),
    ("t_verify", "verify-minutes", "cost"),
    ("p_fail", "rework-probability", "cost"),
    ("t_rework", "rework-minutes", "cost"),
    ("N", "instances-in-period", "benefit"),
    ("C_build", "build-hours", "cost"),
    ("C_maint", "maintenance-hours-per-period", "cost"),
    ("periods", "periods", "fixed"),
)
_SAVING_INPUTS = ("t_manual", "t_ai", "t_verify", "p_fail", "t_rework")
_UPKEEP_INPUTS = ("C_build", "C_maint", "periods")
SCENARIOS = ("conservative", "base", "upside")


def breakeven(register: str) -> tuple[dict[str, float | None], list[str], list[str]]:
    r"""Compute ``S_inst``, ``S_net``, and ``N_breakeven`` per scenario from register ids.

    Returns ``(figures, missing, problems)``. Figure keys are ``<scenario>_<name>``:
    ``s_inst`` in minutes, ``s_net`` in hours, ``n_breakeven`` in instances (``None``
    when ``S_inst`` is not positive). Benefit inputs sit at ``low`` and cost inputs at
    ``high`` in the conservative scenario, the reverse in the upside; a figure whose
    inputs are not all registered is absent and its ids are in ``missing``.
    With negative ``S_inst``, high volume is conservative and low volume is upside.

    Examples
    --------
    >>> reg = "\n".join(
    ...     f"- id: {i}\n  value: {v}\n  low: {lo}\n  high: {hi}"
    ...     for i, v, lo, hi in [
    ...         ("manual-minutes", 30, 28, 40),
    ...         ("ai-minutes", 10, 8, 12),
    ...         ("verify-minutes", 4, 3, 6),
    ...         ("rework-probability", 0.2, 0.1, 0.3),
    ...         ("rework-minutes", 20, 10, 30),
    ...         ("instances-in-period", 600, 500, 700),
    ...         ("build-hours", 20, 15, 30),
    ...         ("maintenance-hours-per-period", 2, 1, 4),
    ...         ("periods", 4, 4, 4),
    ...     ]
    ... )
    >>> figures, missing, problems = breakeven(reg)
    >>> (missing, problems)
    ([], [])
    >>> (figures["base_s_inst"], figures["base_s_net"], figures["base_n_breakeven"])
    (12.0, 92.0, 140.0)
    >>> (figures["conservative_s_inst"], figures["conservative_s_net"])
    (1.0, -37.67)
    >>> figures["conservative_n_breakeven"]
    2760.0
    >>> breakeven("- id: manual-minutes\n  value: 30")[1][:2]
    ['ai-minutes', 'verify-minutes']
    """
    entries = {e.get("id", ""): e for e in _parse_register(register)}
    problems: list[str] = []
    levels: dict[str, tuple[float, float, float]] = {}
    missing: list[str] = []
    for symbol, ident, _kind in BREAKEVEN_INPUTS:
        entry = entries.get(ident)
        if entry is None:
            missing.append(ident)
            continue
        try:
            base = float(entry["value"])
            low = float(entry.get("low") or base)
            high = float(entry.get("high") or base)
        except KeyError, ValueError:
            problems.append(f"{ident}: value, low, and high must be finite numbers")
            continue
        if not all(math.isfinite(x) for x in (low, base, high)):
            problems.append(f"{ident}: value, low, and high must be finite numbers")
            continue
        if not low <= base <= high:
            problems.append(f"{ident}: need low <= value <= high")
        if low < 0:
            problems.append(f"{ident}: value, low, and high must be nonnegative")
        if symbol == "p_fail" and not 0 <= high <= 1:
            problems.append(f"{ident}: high {high} must be in [0, 1]")
        levels[symbol] = (low, base, high)
    if problems:
        return {}, missing, problems
    kinds = {symbol: kind for symbol, _, kind in BREAKEVEN_INPUTS}

    def pick(symbol: str, scenario: str) -> float:
        low, base, high = levels[symbol]
        if scenario == "base" or kinds[symbol] == "fixed":
            return base
        benefit = kinds[symbol] == "benefit"
        return low if (scenario == "conservative") == benefit else high

    figures: dict[str, float | None] = {}
    for scenario in SCENARIOS:
        if any(sym not in levels for sym in _SAVING_INPUTS):
            break
        v = {sym: pick(sym, scenario) for sym in levels}
        s_inst = (v["t_manual"] - (v["t_ai"] + v["t_verify"])) - v["p_fail"] * v["t_rework"]
        figures[f"{scenario}_s_inst"] = round(s_inst, 2)
        if any(sym not in levels for sym in _UPKEEP_INPUTS):
            continue
        upkeep = v["C_build"] + v["C_maint"] * v["periods"]
        figures[f"{scenario}_n_breakeven"] = (
            round(upkeep * MINUTES_PER_HOUR / s_inst, 2) if s_inst > 0 else None
        )
        if "N" in levels:
            volume = v["N"]
            if s_inst < 0 and scenario != "base":
                volume = levels["N"][2 if scenario == "conservative" else 0]
            figures[f"{scenario}_s_net"] = round(volume * s_inst / MINUTES_PER_HOUR - upkeep, 2)
    if any(value is not None and not math.isfinite(value) for value in figures.values()):
        return {}, missing, ["break-even exceeds the supported numeric range"]
    return figures, list(dict.fromkeys(missing)), []


def list_runs(roots: Sequence[Path], workflow: str = "") -> list[Path]:
    """List ``<root>/<date>/business/<workflow>`` directories, newest date first.

    A non-empty ``workflow`` keeps only runs of that slug, so the first is its newest.

    Examples
    --------
    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as d:
    ...     for p in ("2026-02-01/business/b", "2026-01-15/business/a"):
    ...         Path(d, p).mkdir(parents=True)
    ...     for p in ("2026-02-01/business/a", "x/business/z"):
    ...         Path(d, p).mkdir(parents=True)
    ...     [str(r.relative_to(d)) for r in list_runs([Path(d)])]
    ['2026-02-01/business/b', '2026-02-01/business/a', '2026-01-15/business/a']
    >>> with tempfile.TemporaryDirectory() as d:
    ...     for p in ("2026-02-01/business/b", "2026-01-15/business/a", "2026-01-20/business/a"):
    ...         Path(d, p).mkdir(parents=True)
    ...     [str(r.relative_to(d)) for r in list_runs([Path(d)], "a")]
    ['2026-01-20/business/a', '2026-01-15/business/a']
    """
    found: list[Path] = []
    for root in roots:
        try:
            found.extend(
                run
                for run in root.glob("*/business/*")
                if run.is_dir()
                and DATE_DIR.fullmatch(run.parent.parent.name)
                and (not workflow or run.name == workflow)
            )
        except OSError:
            continue
    return sorted(found, key=lambda p: (p.parent.parent.name, p.name), reverse=True)


def _units(text: str) -> list[str]:
    """Split markdown into figure-sized units: a bullet, table row, or paragraph."""
    units: list[str] = []
    current: list[str] = []
    for line in [*text.splitlines(), ""]:
        if not line.strip() or line.startswith("#") or UNIT_START.match(line):
            if current:
                units.append(" ".join(current))
                current = []
            if line.strip() and not line.startswith("#"):
                current.append(line.strip())
        else:
            current.append(line.strip())
    return units


def _source_entries(text: str) -> dict[str, list[str]]:
    entries: dict[str, list[str]] = {}
    name = ""
    for line in text.splitlines():
        if line.startswith("## "):
            name = line[3:].strip().strip("`")
            entries[name] = []
        elif name:
            entries[name].append(line)
    return entries


def _check_sources(run: Path, entries: dict[str, list[str]]) -> list[str]:
    if not entries:
        return ["sources.md has no entries (one `## <name>` heading each)"]
    problems: list[str] = []
    for name, lines in entries.items():
        problems.extend(
            f"sources.md entry {name}: missing {label}"
            for label, pattern in SOURCE_FIELDS
            if not any(pattern.match(line) for line in lines)
        )
        for line in lines:
            recorded = SHA_LINE.match(line)
            if recorded:
                target = run / recorded.group(2)
                if not target.is_file():
                    problems.append(
                        f"sources.md entry {name}: hashed file {recorded.group(2)} is gone"
                    )
                elif file_sha256(target) != recorded.group(1):
                    problems.append(
                        f"sources.md entry {name}: {recorded.group(2)} does not match its sha256"
                    )
            stamp = TIMESTAMP_VALUE.match(line)
            if stamp and not _is_timestamp(stamp.group(1)):
                problems.append(
                    f"sources.md entry {name}: executed {stamp.group(1)!r} is not an ISO timestamp"
                )
            found = OUTPUT_LINE.match(line)
            if not found:
                continue
            for raw in found.group(1).split(","):
                target = raw.strip().strip("`")
                if target and not (run / target).is_file():
                    problems.append(f"sources.md entry {name}: output {target} does not exist")
    return problems


def _check_figures(
    label: str, text: str, names: Collection[str], unchecked: Collection[str] = ()
) -> list[str]:
    """Check tags per sentence; ``unchecked`` names CSV-backed entries no ``check:`` line covers."""
    problems: list[str] = []
    for unit in _units(text):
        if CHECK_LINE.match(unit):
            continue
        problems.extend(
            f"{label}: figure without a provenance tag: {sentence[:60]}"
            for sentence in SENTENCE_END.split(unit)
            if FIGURE.search(sentence)
            and not any(tag in sentence for tag in TAGS)
            and any(tag in unit for tag in TAGS)
        )
        if not any(tag in unit for tag in TAGS):
            if FIGURE.search(unit):
                problems.append(f"{label}: figure without a provenance tag: {unit[:60]}")
            continue
        if "BENCHMARKED" in unit and not PINNED_LINK.search(unit):
            problems.append(f"{label}: BENCHMARKED figure has no pinned link: {unit[:60]}")
        if "MEASURED" not in unit:
            continue
        cited: list[str] = CITATION.findall(unit)
        if not cited:
            problems.append(f"{label}: MEASURED figure cites no sources.md entry: {unit[:60]}")
        problems.extend(
            f"{label}: cited sources.md entry {c} does not exist" for c in cited if c not in names
        )
        problems.extend(
            f"{label}: MEASURED figure has no check: line over the CSV of {c}: {unit[:60]}"
            for c in cited
            if c in unchecked
        )
    return problems


def _csv_outputs(lines: Sequence[str]) -> set[str]:
    outputs: set[str] = set()
    for line in lines:
        found = OUTPUT_LINE.match(line)
        if found:
            outputs.update(
                x.strip().strip("`")
                for x in found.group(1).split(",")
                if x.strip().endswith(".csv")
            )
    return outputs


def _column(rows: list[dict[str, str]], expr: str) -> list[float] | None:
    """Return a CSV column or ``a-b`` row difference; rows with a blank needed cell drop out.

    Examples
    --------
    >>> _column([{"a": "5", "b": "2"}, {"a": "4", "b": ""}], "a-b")
    [3.0]
    >>> _column([{"a": "x"}], "a") is None
    True
    """
    fields: set[str] = set(rows[0]) if rows else set()
    try:
        if expr in fields:
            values = [float(r[expr]) for r in rows if (r[expr] or "").strip()]
        else:
            left, _, right = expr.partition("-")
            if left not in fields or right not in fields:
                return None
            values = [
                float(r[left]) - float(r[right])
                for r in rows
                if (r[left] or "").strip() and (r[right] or "").strip()
            ]
    except ValueError, TypeError:
        return None
    return values if all(math.isfinite(value) for value in values) else None


def _read_csv_column(path: Path, expr: str) -> list[float] | None:
    with path.open(encoding="utf-8", newline="") as handle:
        return _column(list(csv.DictReader(handle)), expr)


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def file_sha256(path: Path) -> str:
    """Return the hex SHA-256 of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


SHA_LINE = re.compile(r"^\W*sha256\s*:\s*(\S+)\s+(\S+)\s*$", re.IGNORECASE)


ENTRY_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
CONTROL_CHAR = re.compile(r"[\x00-\x1f\x7f]")


def entry_has(sources: Path, entry: str, pattern: str) -> bool:
    """Whether ``entry`` in ``sources`` already has a line matching ``pattern``."""
    if not sources.is_file():
        return False
    lines = sources.read_text(encoding="utf-8").splitlines()
    inside = False
    for line in lines:
        if line.startswith("## "):
            inside = line[3:].strip().strip("`") == entry
        elif inside and re.match(pattern, line, re.IGNORECASE):
            return True
    return False


def record_source(
    sources: Path, entry: str, output: Path, query: str = "", tool_version: str = ""
) -> None:
    r"""Write ``output`` (relative to ``sources``), its hash, and a clock time into an entry.

    The entry is created when absent. A given ``query`` or ``tool_version`` is written
    unless the entry already has that line.

    Examples
    --------
    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as d:
    ...     _ = (Path(d) / "snap.csv").write_text("a")
    ...     record_source(Path(d) / "sources.md", "snap", Path(d) / "snap.csv")
    ...     [line.split(":")[0] for line in (Path(d) / "sources.md").read_text().splitlines()]
    ['## snap', '- output', '- executed', '- sha256']
    >>> with tempfile.TemporaryDirectory() as d:
    ...     _ = (Path(d) / "snap.csv").write_text("a")
    ...     record_source(Path(d) / "sources.md", "snap", Path(d) / "snap.csv", "cat x", "cat 9")
    ...     [x.split(":")[0] for x in (Path(d) / "sources.md").read_text().splitlines()]
    ['## snap', '- output', '- executed', '- query', '- tool version', '- sha256']
    """
    if not ENTRY_NAME.match(entry):
        msg = f"entry name {entry!r} must be a citable slug (a-z, 0-9, '.', '_', '-')"
        raise ValueError(msg)
    for field, value in (("query", query), ("tool version", tool_version)):
        if CONTROL_CHAR.search(value):
            msg = f"{field} holds a line break or control character"
            raise ValueError(msg)
    try:
        rel = output.resolve().relative_to(sources.resolve().parent).as_posix()
    except ValueError:
        msg = f"{output} is not inside the run"
        raise ValueError(msg) from None
    lines = sources.read_text(encoding="utf-8").splitlines() if sources.is_file() else []
    start = next(
        (
            i
            for i, x in enumerate(lines)
            if x.startswith("## ") and x[3:].strip().strip("`") == entry
        ),
        None,
    )
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"## {entry}")
        start = len(lines) - 1
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    body = [
        x for x in lines[start + 1 : end] if not ((m := SHA_LINE.match(x)) and m.group(2) == rel)
    ]
    while body and not body[-1].strip():
        _ = body.pop()
    if not any(OUTPUT_LINE.match(x) for x in body):
        body.append(f"- output: {rel}")
    stamp = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = [x for x in body if not TIMESTAMP_VALUE.match(x)]
    body.insert(min(1, len(body)), f"- executed: {stamp}")
    if query and not any(re.match(r"^\W*(?:query|command)\s*:", x, re.IGNORECASE) for x in body):
        body.append(f"- query: {query}")
    if tool_version and not any(
        re.match(r"^\W*(?:tool )?version\s*:", x, re.IGNORECASE) for x in body
    ):
        body.append(f"- tool version: {tool_version}")
    body.append(f"- sha256: {file_sha256(output)} {rel}")
    lines[start + 1 : end] = [*body, ""] if end < len(lines) else body
    _ = sources.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _recompute(stat: str, values: list[float]) -> float:
    if stat == "n":
        return float(len(values))
    return float(
        {"median": statistics.median, "mean": statistics.fmean, "min": min, "max": max}[stat](
            values
        )
    )


def _check_recomputed(run: Path, label: str, text: str) -> list[str]:
    problems: list[str] = []
    for line in text.splitlines():
        if not CHECK_LINE.match(line):
            continue
        spec = CHECK_SPEC.match(line)
        if not spec:
            problems.append(f"{label}: unparseable check line: {line.strip()[:60]}")
            continue
        stat, rel, expr, claimed = spec.groups()
        target = (run / rel).resolve()
        if not target.is_relative_to(run.resolve()) or not target.is_file():
            problems.append(f"{label}: check file {rel} does not exist in the run")
            continue
        values = _read_csv_column(target, expr)
        if not values:
            problems.append(f"{label}: check {rel} has no numeric column {expr}")
            continue
        actual = _recompute(stat.lower(), values)
        if abs(actual - float(claimed)) > CHECK_TOLERANCE:
            problems.append(
                f"{label}: {stat} of {expr} in {rel} is {actual:g}, claimed {float(claimed):g}"
            )
    return problems


def check_run(run: Path) -> list[str]:
    """Return the completeness-gate problems of a run package; empty means it passes.

    Examples
    --------
    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as d:
    ...     check_run(Path(d))[0]
    'README.md is missing'
    """
    problems: list[str] = []

    def read(name: str) -> str | None:
        path = run / name
        return path.read_text(encoding="utf-8") if path.is_file() else None

    readme = read("README.md")
    if readme is None:
        problems.append("README.md is missing")
    elif not any(
        "window" in line.lower() and DATE_RANGE.search(line) for line in readme.splitlines()
    ):
        problems.append("README.md states no pinned window (start..end dates on a Window line)")
    if readme is not None and not NAMES_LINE.search(readme):
        problems.append("README.md has no Names: line (write `Names: none` when there are none)")
    if readme is not None and not PEOPLE_LINE.search(readme):
        problems.append("README.md has no People: line (write `People: none` when there are none)")
    sources = read("sources.md")
    entries: dict[str, list[str]] = {}
    if sources is None:
        problems.append("sources.md is missing")
    else:
        entries = _source_entries(sources)
        problems.extend(_check_sources(run, entries))
    register = read("assumptions.yaml")
    if register is None:
        problems.append("assumptions.yaml is missing")
    else:
        problems.extend(f"assumptions.yaml: {p}" for p in check_assumptions(register, set(entries)))
    docs = {f"measurements/{p.name}": p for p in sorted((run / "measurements").glob("*.md"))}
    findings = read("findings.md")
    if findings is None:
        problems.append("findings.md is missing")
    else:
        texts = [
            *((k, v.read_text(encoding="utf-8")) for k, v in docs.items()),
            ("findings.md", findings),
        ]
        checked = {
            Path(m.group(2)).as_posix()
            for _, text in texts
            for line in text.splitlines()
            if (m := CHECK_SPEC.match(line))
        }
        unchecked = {
            name
            for name, lines in entries.items()
            if any(Path(c).as_posix() not in checked for c in _csv_outputs(lines))
        }
        for label, text in texts:
            problems.extend(_check_figures(label, text, set(entries), unchecked))
            problems.extend(
                f"{label}:{line}: currency {match!r}; value is hours, never money"
                for line, _, kind, match in scan_text(text)
                if kind == "currency"
            )
            problems.extend(
                f"{label}:{line}: money framing {match!r}; value is hours, never money"
                for line, _, _, match in scan_text(text, rules=["money-term"])
                if GATE_MONEY.fullmatch(match)
            )
            problems.extend(_check_recomputed(run, label, text))
        problems.extend(_check_unknowns(findings))
    return problems


def _check_unknowns(findings: str) -> list[str]:
    section: list[str] = []
    inside = False
    for line in findings.splitlines():
        if line.startswith("#"):
            inside = "unknown" in line.lstrip("#").lower()
        elif inside:
            section.append(line)
    return [
        f"findings.md: unknown without the data that would resolve it: {unit[:60]}"
        for unit in _units("\n".join(section))
        if UNIT_START.match(unit) and not UNKNOWN_DATA.search(NO_DATA.sub("", unit))
    ]


PR_COLUMNS = (
    "number",
    "created_at",
    "merged_at",
    "cycle_hours",
    "first_review_hours",
    "reopened",
    "additions",
    "deletions",
)


def _timestamp(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text)


def _json_documents(text: str) -> list[object]:
    """Split concatenated JSON documents, as ``gh api graphql --paginate`` prints them."""
    decoder = json.JSONDecoder()
    docs: list[object] = []
    pos = 0
    while True:
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text):
            return docs
        doc: object
        doc, pos = decoder.raw_decode(text, pos)  # pyright: ignore[reportAny]
        docs.append(doc)


def _obj(value: object) -> dict[str, object]:
    return t.cast("dict[str, object]", value) if isinstance(value, dict) else {}


def _items(value: object) -> list[object]:
    return t.cast("list[object]", value) if isinstance(value, list) else []


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


_COUNT_COLUMNS = ("reopened", "additions", "deletions")


def _count(value: object) -> str:
    return str(value) if isinstance(value, int) and not isinstance(value, bool) else ""


def _first_review_hours(pr: dict[str, object]) -> str:
    author = _text(_obj(pr.get("author")).get("login"))
    stamps: list[str] = []
    for node in _items(_obj(pr.get("reviews")).get("nodes")):
        review = _obj(node)
        who = _obj(review.get("author"))
        login = _text(who.get("login"))
        if (
            _text(review.get("submittedAt"))
            and login not in ("", author)
            and _text(who.get("__typename")) != "Bot"
        ):
            stamps.append(_text(review.get("submittedAt")))
    if not stamps:
        return ""
    delta = _timestamp(min(stamps)) - _timestamp(_text(pr.get("createdAt")))
    return f"{delta.total_seconds() / 3600:.2f}"


def collect_prs(
    text: str, start: str, end: str, warnings: list[str] | None = None
) -> list[dict[str, str]]:
    """Return one row per PR merged in ``start``..``end`` (inclusive dates, UTC).

    Open and closed-unmerged PRs are excluded. ``first_review_hours`` counts the
    earliest submitted review by someone other than the PR author and not a bot;
    it is blank when there is none. A field the page lacks (``reopened``,
    ``additions``, ``deletions``) is blank, never zero, and appends one line to
    ``warnings`` with the row count. A PR whose ``reviews.pageInfo.hasNextPage``
    is true also appends a line. Logins are read to compare author and reviewer
    and never written to the rows.

    Examples
    --------
    >>> page = {"data": {"repository": {"pullRequests": {"nodes": [{
    ...     "number": 7, "createdAt": "2026-04-02T00:00:00Z",
    ...     "mergedAt": "2026-04-03T12:00:00Z", "additions": 5, "deletions": 1,
    ...     "author": {"login": "ann"},
    ...     "reviews": {"nodes": [
    ...         {"submittedAt": "2026-04-02T01:00:00Z",
    ...          "author": {"login": "ann", "__typename": "User"}},
    ...         {"submittedAt": "2026-04-02T02:00:00Z",
    ...          "author": {"login": "ci", "__typename": "Bot"}},
    ...         {"submittedAt": "2026-04-02T06:00:00Z",
    ...          "author": {"login": "bo", "__typename": "User"}}]},
    ...     "reopened": {"filteredCount": 0}}]}}}}
    >>> rows = collect_prs(json.dumps(page), "2026-04-01", "2026-04-03")
    >>> (rows[0]["cycle_hours"], rows[0]["first_review_hours"])
    ('36.00', '6.00')
    >>> collect_prs(json.dumps(page), "2026-04-01", "2026-04-02")
    []
    >>> page["data"]["repository"]["pullRequests"]["nodes"][0]["reviews"]["pageInfo"] = {
    ...     "hasNextPage": True
    ... }
    >>> notes: list[str] = []
    >>> _ = collect_prs(json.dumps(page), "2026-04-01", "2026-04-03", notes)
    >>> notes
    ['PR #7: reviews truncated at 3; first_review_hours may be wrong']
    >>> bare_pr = {
    ...     "number": 8, "createdAt": "2026-04-02T00:00:00Z", "mergedAt": "2026-04-03T00:00:00Z"
    ... }
    >>> bare = {"data": {"repository": {"pullRequests": {"nodes": [bare_pr]}}}}
    >>> notes = []
    >>> rows = collect_prs(json.dumps(bare), "2026-04-01", "2026-04-03", notes)
    >>> ([rows[0][c] for c in ("reopened", "additions", "deletions")], notes[0])
    (['', '', ''], '1 of 1 rows lack reopened; left blank, not zero')
    """
    lo = dt.datetime.fromisoformat(f"{start}T00:00:00+00:00")
    hi = dt.datetime.fromisoformat(f"{end}T00:00:00+00:00") + dt.timedelta(days=1)
    rows: list[dict[str, str]] = []
    absent: collections.Counter[str] = collections.Counter()
    docs = _json_documents(text)
    if not docs:
        msg = "no pages on input"
        raise ValueError(msg)
    for doc in docs:
        repo = _obj(_obj(doc).get("data")).get("repository")
        nodes = _items(_obj(_obj(repo).get("pullRequests")).get("nodes"))
        if not isinstance(repo, dict):
            msg = "no data.repository in a page"
            raise ValueError(msg)  # noqa: TRY004
        for node in nodes:
            pr = _obj(node)
            if not _text(pr.get("mergedAt")):
                continue
            merged = _timestamp(_text(pr["mergedAt"]))
            if not lo <= merged < hi:
                continue
            reviews = _obj(pr.get("reviews"))
            if warnings is not None and _obj(reviews.get("pageInfo")).get("hasNextPage") is True:
                kept = len(_items(reviews.get("nodes")))
                number = pr.get("number")
                warnings.append(
                    f"PR #{number}: reviews truncated at {kept}; first_review_hours may be wrong"
                )
            created = _text(pr.get("createdAt"))
            cycle = (merged - _timestamp(created)).total_seconds() / 3600
            rows.append(
                {
                    "number": str(pr.get("number")),
                    "created_at": created,
                    "merged_at": _text(pr["mergedAt"]),
                    "cycle_hours": f"{cycle:.2f}",
                    "first_review_hours": _first_review_hours(pr),
                    "reopened": _count(_obj(pr.get("reopened")).get("filteredCount")),
                    "additions": _count(pr.get("additions")),
                    "deletions": _count(pr.get("deletions")),
                }
            )
    absent.update(c for row in rows for c in _COUNT_COLUMNS if not row[c])
    if warnings is not None:
        warnings.extend(
            f"{absent[c]} of {len(rows)} rows lack {c}; left blank, not zero"
            for c in _COUNT_COLUMNS
            if absent[c]
        )
    return sorted(rows, key=lambda r: int(r["number"]))


STAMP_FILE = ".provenance.json"
RUN_INPUTS = ("README.md", "sources.md", "assumptions.yaml", "findings.md")
PUBLIC_STUDY = "case-study-public.md"


def _input_hashes(run: Path, report: str) -> dict[str, str]:
    """Hash the files a report is derived from: the public case study for a release."""
    if report == "pr-release.md":
        files = [run / "reports" / PUBLIC_STUDY]
    else:
        files = [
            *(run / name for name in RUN_INPUTS),
            *sorted((run / "measurements").glob("*.md")),
            *sorted(p for p in (run / "raw").rglob("*") if p.is_file()),
        ]
    return {
        f.relative_to(run).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
        for f in files
        if f.is_file()
    }


def _load_stamps(run: Path) -> dict[str, dict[str, str]]:
    path = run / "reports" / STAMP_FILE
    if not path.is_file():
        return {}
    return t.cast("dict[str, dict[str, str]]", json.loads(path.read_text(encoding="utf-8")))


def stamp_report(run: Path, report: str) -> None:
    """Record the hashes of the files ``report`` was written from.

    Examples
    --------
    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as d:
    ...     (Path(d) / "reports").mkdir()
    ...     _ = (Path(d) / "reports" / "leadership.md").write_text("r")
    ...     _ = (Path(d) / "findings.md").write_text("a")
    ...     stamp_report(Path(d), "leadership.md")
    ...     stale_reports(Path(d))
    ...     _ = (Path(d) / "findings.md").write_text("b")
    ...     [r.split(":")[0] for r in stale_reports(Path(d))]
    []
    ['leadership.md']
    """
    stamps = _load_stamps(run)
    stamps[report] = _input_hashes(run, report)
    target = run / "reports" / STAMP_FILE
    _ = target.write_text(json.dumps(stamps, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def stale_reports(run: Path) -> list[str]:
    """Return one line per report that is unstamped or whose recorded inputs changed."""
    stamps = _load_stamps(run)
    problems: list[str] = []
    # A dotfile under reports/ is scratch (a reply check), not a report.
    for report in sorted(
        p.name for p in (run / "reports").glob("*.md") if not p.name.startswith(".")
    ):
        recorded = stamps.get(report)
        if recorded is None:
            problems.append(f"{report}: no recorded inputs; stamp it after writing")
            continue
        now = _input_hashes(run, report)
        changed = sorted(k for k in now.keys() | recorded.keys() if now.get(k) != recorded.get(k))
        if changed:
            problems.append(f"{report}: stale; changed since it was written: {', '.join(changed)}")
    return problems


_NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")
_LIST_MARKER = re.compile(r"^\s*(?:#+\s*)?(?:\d+\.|[-*])\s+")


def run_figure_source(run: Path) -> str:
    """Return the text a report's figures may come from: script output and the run's records.

    That is the ``project`` and ``breakeven`` output, plus the README, index, source
    manifest, register, findings, and measurements.
    """
    chunks: list[str] = []
    for command in (lambda: _project_command(run), lambda: _breakeven_command(Args(run=str(run)))):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
            _ = command()
        chunks.append(buffer.getvalue())
    for name in ("index.md", *RUN_INPUTS):
        path = run / name
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8"))
    chunks.extend(
        p.read_text(encoding="utf-8") for p in sorted((run / "measurements").glob("*.md"))
    )
    return "\n".join(chunks)


def _canonical_number(token: str) -> str:
    try:
        return format(decimal.Decimal(token.replace(",", "")).normalize(), "f")
    except decimal.InvalidOperation:
        return token


def untraced_figures(text: str, source: str) -> list[tuple[int, int, str]]:
    """Return ``(line, column, number)`` for each number in ``text`` absent from ``source``.

    A number matches by value, so ``1,200`` and ``1200`` agree; list markers and
    heading numbers are not figures.

    Examples
    --------
    >>> untraced_figures("Median 18 min, n=41, 12.50%.", "Median 18 min (n=41), 12.5%.")
    []
    >>> untraced_figures("1. Saved 30 min of 41 PRs", "Saved 18 min of 41 PRs")
    [(1, 10, '30')]
    """
    known = {_canonical_number(m.group()) for m in _NUMBER.finditer(source)}
    known |= {
        _canonical_number(str(decimal.Decimal(n) * 100))
        for n in known
        if decimal.Decimal(n) < 1 and "." in n
    }
    found: list[tuple[int, int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        marker = _LIST_MARKER.match(line)
        offset = marker.end() if marker else 0
        found.extend(
            (number, m.start() + offset + 1, m.group())
            for m in _NUMBER.finditer(line[offset:])
            if _canonical_number(m.group()) not in known
        )
    return found


KEBAB = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def init_run(root: Path, workflow: str, date: str) -> Path:
    """Create ``<root>/<date>/business/<workflow>`` and return it.

    Existing files are never rewritten. A run whose ``raw/`` already holds a
    snapshot is refused with ``FileExistsError``.

    Examples
    --------
    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as d:
    ...     run = init_run(Path(d), "lean-tighten", "2026-06-30")
    ...     _ = (run / "raw" / "a.csv").write_text("x")
    ...     try:
    ...         init_run(Path(d), "lean-tighten", "2026-06-30")
    ...     except FileExistsError as exc:
    ...         print(exc)
    raw/ of 2026-06-30/business/lean-tighten already holds 1 snapshot(s)
    """
    if not KEBAB.fullmatch(workflow):
        msg = f"workflow {workflow!r} is not a kebab-case slug"
        raise ValueError(msg)
    if not _is_date(date):
        msg = f"date {date!r} is not YYYY-MM-DD"
        raise ValueError(msg)
    run = root / date / "business" / workflow
    snapshots = [p for p in (run / "raw").rglob("*") if p.is_file()] if run.is_dir() else []
    if snapshots:
        msg = f"raw/ of {date}/business/{workflow} already holds {len(snapshots)} snapshot(s)"
        raise FileExistsError(msg)
    for sub in ("raw", "measurements", "reports"):
        (run / sub).mkdir(parents=True, exist_ok=True)
    skeletons = {
        "index.md": f"---\nnamespace: business\ntopic: {workflow}\ndate: {date}\n---\n",
        "README.md": f"# {workflow}\n\n" + "\n".join(README_FIELDS) + "\n",
    }
    for name, body in skeletons.items():
        with contextlib.suppress(FileExistsError), (run / name).open("x", encoding="utf-8") as fh:
            _ = fh.write(body)
    return run


def default_roots() -> list[Path]:
    """Return the default run roots: the home Documents folder and WSL Windows Documents.

    An unreadable ``/mnt/c/Users`` yields no Windows roots instead of raising.

    Examples
    --------
    >>> Path.home() / "Documents" in default_roots()
    True
    """
    roots = [Path.home() / "Documents"]
    with contextlib.suppress(OSError):
        roots.extend(sorted(Path("/mnt/c/Users").glob("*/Documents")))
    return roots


def _read(paths: list[str]) -> str:
    if not paths:
        return sys.stdin.read()
    return "\n".join(Path(p).read_text(encoding="utf-8") for p in paths)


def _assumptions_command(file: Path) -> int:
    problems = check_assumptions(file.read_text(encoding="utf-8"))
    for problem in problems:
        print(problem)
    if not problems:
        print("ok")
    return 1 if problems else 0


def _project_command(run: Path) -> int:
    register = run / "assumptions.yaml"
    if not register.is_file():
        print(f"no assumptions.yaml in {run}", file=sys.stderr)
        return 2
    figures, problems = project(register.read_text(encoding="utf-8"))
    for problem in problems:
        print(problem)
    if problems:
        return 1
    swings = sorted((k for k in figures if k.startswith("swing_")), key=lambda k: -figures[k])
    for key, value in figures.items():
        if not key.startswith("swing_"):
            print(f"{key}: {value:g}")
    if figures["base"] < 0:
        print(f"net loss: the base case loses {-figures['base']:g} engineer-hours per year")
    elif figures["conservative"] < 0:
        print(f"net loss possible: the conservative case loses {-figures['conservative']:g} hours")
    print("sensitivity (low-to-high swing, engineer-hours per year, largest first):")
    for key in swings:
        print(f"  {key.removeprefix('swing_')}: {figures[key]:g}")
    return 0


def _breakeven_command(args: Args) -> int:
    register = Path(args.run) / "assumptions.yaml"
    if not register.is_file():
        print(f"no assumptions.yaml in {args.run}", file=sys.stderr)
        return 2
    figures, missing, problems = breakeven(register.read_text(encoding="utf-8"))
    for problem in problems:
        print(problem)
    if problems:
        return 1
    labels = (
        ("s_inst", "S_inst (minutes per instance)"),
        ("s_net", "S_net (engineer-hours over horizon)"),
        ("n_breakeven", "N_breakeven (instances)"),
    )
    for scenario in SCENARIOS:
        for key, label in labels:
            name = f"{scenario}_{key}"
            if name in figures:
                value = figures[name]
                shown = "none, no positive saving" if value is None else f"{value:g}"
                print(f"{scenario} {label}: {shown}")
    print("committed figures: the conservative lines")
    for ident in missing:
        print(f"missing: {ident}")
    return 0 if figures else 1


def _gate_command(run: Path) -> int:
    if not run.is_dir():
        print(f"no run directory at {run}", file=sys.stderr)
        return 2
    problems = check_run(run)
    for problem in problems:
        print(problem)
    if not problems:
        print("ok")
    return 1 if problems else 0


def _stats_command(args: Args) -> int:
    try:
        extra: dict[str, object] = {}
        if args.csv_file:
            rows = _csv_rows(Path(args.csv_file))
            column = _column(rows, args.column)
            if column is None:
                print(
                    f"column {args.column!r} not found or not numeric in {args.csv_file}",
                    file=sys.stderr,
                )
                return 2
            values = column
            extra = {
                "rows": len(rows),
                "dropped_blank": len(rows) - len(values),
                "input_sha256": file_sha256(Path(args.csv_file)),
            }
        else:
            values = parse_numbers(_read(args.files))
        if len(values) < MIN_OBSERVATIONS:
            print("need at least 2 observations", file=sys.stderr)
            return 2
        summary = summarize(values, seed=args.seed, resamples=args.resamples)
    except (ValueError, OverflowError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for key, value in {**summary, **extra}.items():
        print(f"{key}: {value}")
    return 0


def _names_for_scan(args: Args) -> list[str] | str:
    """Return the names to deny, or an error message."""
    names = list(args.deny)
    if args.run:
        readme = Path(args.run) / "README.md"
        if not readme.is_file():
            return f"no README.md in {args.run}"
        text = readme.read_text(encoding="utf-8")
        if args.tier == TIER_PUBLIC:
            if not NAMES_LINE.search(text):
                return "README.md has no Names: line (write `Names: none` when there are none)"
            names.extend(parse_names(text))
            names.extend(parse_names(text, "People"))
        elif not PEOPLE_LINE.search(text):
            return "README.md has no People: line (write `People: none` when there are none)"
        else:
            names.extend(parse_names(text, "People"))
    if args.names_file:
        listed = Path(args.names_file)
        if not listed.is_file():
            return f"no names file at {args.names_file}"
        names.extend(
            n.strip()
            for line in listed.read_text(encoding="utf-8").splitlines()
            for n in re.split(r"[,;]", line)
            if n.strip() and n.strip().lower() != "none"
        )
    return names


def _scan_command(args: Args) -> int:
    names = _names_for_scan(args)
    if isinstance(names, str):
        print(names, file=sys.stderr)
        return 2
    hits = scan_text(
        _read(args.files),
        names,
        args.allow,
        args.allow_url,
        [r for r in args.rules.split(",") if r] if args.tier == TIER_PUBLIC else ["denied-name"],
    )
    for line, col, kind, match in hits:
        print(f"{line}:{col}: {kind}: {match}")
    if not hits:
        print("clean")
    return 1 if hits else 0


def _collect_prs_command(args: Args) -> int:
    try:
        warnings: list[str] = []
        rows = collect_prs(_read(args.files), args.start, args.end, warnings)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"not gh api graphql pull-request pages: {exc}", file=sys.stderr)
        return 2
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(PR_COLUMNS)
    writer.writerows([row[c] for c in PR_COLUMNS] for row in rows)
    if bool(args.sources) != bool(args.entry) or (args.sources and not args.output):
        print("--sources and --entry go together and need --output", file=sys.stderr)
        return 2
    if not args.output:
        _ = sys.stdout.write(buffer.getvalue())
        return 0
    try:
        with Path(args.output).open("x", encoding="utf-8", newline="") as handle:
            _ = handle.write(buffer.getvalue())
    except FileExistsError:
        print(f"refusing to overwrite the snapshot {args.output}", file=sys.stderr)
        return 2
    if args.sources:
        record_source(Path(args.sources), args.entry, Path(args.output))
    return 0


def _source_command(args: Args) -> int:
    run = Path(args.run)
    output = Path(args.output_file)
    if not run.is_dir() or not output.is_file():
        print(f"need a run directory and an existing output file: {args.run}", file=sys.stderr)
        return 2
    sources = run / "sources.md"
    for flag, value, pattern in (
        ("--query", args.query, r"^\W*(?:query|command)\s*:"),
        ("--tool-version", args.tool_version, r"^\W*(?:tool )?version\s*:"),
    ):
        if not value and not entry_has(sources, args.entry, pattern):
            print(f"entry {args.entry} has no {flag[2:]} line; pass {flag}", file=sys.stderr)
            return 2
    try:
        record_source(sources, args.entry, output, args.query, args.tool_version)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


def _trace_command(args: Args) -> int:
    if not (args.against or args.run):
        print("trace needs --against or --run", file=sys.stderr)
        return 2
    try:
        text = Path(args.file).read_text(encoding="utf-8")
        source = Path(args.against).read_text(encoding="utf-8") if args.against else ""
        if args.run:
            source += run_figure_source(Path(args.run))
    except OSError:
        print(f"cannot read {args.file}, {args.against}, or the run {args.run}", file=sys.stderr)
        return 2
    missing = untraced_figures(text, source)
    for line, col, number in missing:
        print(f"{line}:{col}: figure not in the source text: {number}")
    if not missing:
        print("ok")
    return 1 if missing else 0


def _stamp_command(args: Args) -> int:
    run = Path(args.run)
    report = Path(args.report).name
    if not (run / "reports" / report).is_file():
        print(f"no reports/{report} in {args.run}", file=sys.stderr)
        return 2
    stamp_report(run, report)
    return 0


def _fresh_command(args: Args) -> int:
    run = Path(args.run)
    if not (run / "reports").is_dir():
        print(f"no reports/ in {args.run}", file=sys.stderr)
        return 2
    problems = stale_reports(run)
    for problem in problems:
        print(problem)
    if not problems:
        print("ok")
    return 1 if problems else 0


def _init_command(args: Args) -> int:
    try:
        run = init_run(Path(args.root[0]), args.workflow, args.date or time.strftime("%Y-%m-%d"))
    except (ValueError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(run)
    return 0


def _runs_command(args: Args) -> int:
    for run in list_runs([Path(r) for r in args.root] or default_roots(), args.workflow):
        print(run)
    return 0


class Args(argparse.Namespace):
    """Typed view of the parsed command line."""

    command: str = ""
    files: list[str] = []  # noqa: RUF012
    seed: int = 1
    resamples: int = 10000
    deny: list[str] = []  # noqa: RUF012
    file: str = ""
    root: list[str] = []  # noqa: RUF012
    allow: list[str] = []  # noqa: RUF012
    allow_url: list[str] = []  # noqa: RUF012
    rules: str = ""
    run: str = ""
    csv_file: str = ""
    column: str = ""
    start: str = ""
    end: str = ""
    output: str = ""
    sources: str = ""
    output_file: str = ""
    query: str = ""
    tool_version: str = ""
    entry: str = ""
    names_file: str = ""
    tier: int = 3
    against: str = ""
    report: str = ""
    workflow: str = ""
    date: str = ""


def _add_text_parsers(sub: Subparsers) -> None:
    p_stats = sub.add_parser("stats", help="median, IQR, BCa interval; one number per line")
    _ = p_stats.add_argument("files", nargs="*", help="files of numbers; stdin when omitted")
    _ = p_stats.add_argument(
        "--seed", type=int, default=1, help="resampling seed, recorded in the output"
    )
    _ = p_stats.add_argument("--resamples", type=int, default=10000)
    _ = p_stats.add_argument(
        "--csv", dest="csv_file", default="", help="read a CSV column instead; needs --column"
    )
    _ = p_stats.add_argument("--column", default="", help="header, or a-b for a row difference")

    p_scan = sub.add_parser("scan", help="tier-3 scan; exit 1 when any exclusion is found")
    _ = p_scan.add_argument("files", nargs="*", help="draft files; stdin when omitted")
    _ = p_scan.add_argument(
        "--deny", action="append", default=[], help="a name that must not appear; repeatable"
    )

    _ = p_scan.add_argument(
        "--run", default="", help="run directory; its README.md Names: line is the deny list"
    )
    _ = p_scan.add_argument(
        "--tier",
        type=int,
        choices=(1, 2, 3),
        default=3,
        help="3 (default): every rule, denying Names and People; 1 or 2: only the People line",
    )
    _ = p_scan.add_argument(
        "--names-file", default="", help="file of names to deny, one per line or comma-separated"
    )
    _ = p_scan.add_argument(
        "--allow", action="append", default=[], help="a false-positive match to skip; repeatable"
    )
    _ = p_scan.add_argument(
        "--allow-url",
        action="append",
        default=[],
        help="skip URLs starting with this prefix (citation links); repeatable",
    )

    _ = p_scan.add_argument(
        "--rules",
        default="",
        help="comma-separated kinds to check, e.g. currency,money-term; all when omitted",
    )


def _add_run_parsers(sub: Subparsers) -> None:
    p_gate = sub.add_parser("gate", help="completeness gate for a run; exit 1 on any problem")
    _ = p_gate.add_argument("run", help="run directory")

    p_project = sub.add_parser(
        "project", help="org-wide projection, scenarios, and sensitivity from assumptions.yaml"
    )
    _ = p_project.add_argument("run", help="run directory")

    p_prs = sub.add_parser(
        "collect-prs",
        help="CSV of PRs merged in a window from gh api graphql pages (stdin or files)",
    )
    _ = p_prs.add_argument("files", nargs="*", help="saved pages; stdin when omitted")
    _ = p_prs.add_argument("--start", required=True, help="first merged date, YYYY-MM-DD")
    _ = p_prs.add_argument("--end", required=True, help="last merged date, inclusive")
    _ = p_prs.add_argument(
        "--output",
        default="",
        help="write the CSV here, refusing to overwrite; stdout when omitted",
    )

    _ = p_prs.add_argument(
        "--sources", default="", help="sources.md to record the output, its hash, and the time in"
    )
    _ = p_prs.add_argument("--entry", default="", help="sources.md entry name for --sources")

    p_trace = sub.add_parser(
        "trace", help="list numbers in a text that its source text or run does not contain"
    )
    _ = p_trace.add_argument("file", help="derived text, such as the PR release or a report")
    _ = p_trace.add_argument("--against", default="", help="source text, such as the case study")
    _ = p_trace.add_argument(
        "--run",
        default="",
        help="run directory: project and breakeven output, README, findings, measurements",
    )

    p_source = sub.add_parser(
        "source",
        help="write a sources.md entry for an output file: path, clock time, sha256, query",
    )
    _ = p_source.add_argument("run", help="run directory")
    _ = p_source.add_argument("entry", help="stable entry name")
    _ = p_source.add_argument("output_file", help="the file the command produced, inside the run")
    _ = p_source.add_argument("--query", default="", help="the command that produced it, verbatim")
    _ = p_source.add_argument("--tool-version", default="", help="e.g. 'gh 2.60.1'")

    p_stamp = sub.add_parser(
        "stamp", help="record the hashes of the files a written report was derived from"
    )
    _ = p_stamp.add_argument("run", help="run directory")
    _ = p_stamp.add_argument("report", help="report file name under reports/, e.g. leadership.md")

    p_fresh = sub.add_parser(
        "fresh", help="exit 1 when a report is unstamped or its inputs changed since it was written"
    )
    _ = p_fresh.add_argument("run", help="run directory")

    p_init = sub.add_parser(
        "init", help="create a run directory; refuse one whose raw/ holds snapshots"
    )
    _ = p_init.add_argument("workflow", help="kebab-case slug of the measured workflow")
    _ = p_init.add_argument(
        "--root", action="append", required=True, help="run root the user chose"
    )
    _ = p_init.add_argument("--date", default="", help="YYYY-MM-DD; today when omitted")

    p_break = sub.add_parser(
        "breakeven", help="S_inst, S_net, and break-even per scenario from assumptions.yaml"
    )
    _ = p_break.add_argument("run", help="run directory")

    p_assume = sub.add_parser("assumptions", help="check required fields of assumptions.yaml")
    _ = p_assume.add_argument("file")

    p_runs = sub.add_parser("runs", help="list runs newest first")
    _ = p_runs.add_argument("--root", action="append", default=[], help="run root; repeatable")
    _ = p_runs.add_argument(
        "--workflow", default="", help="only runs of this workflow slug; the first line is newest"
    )


def main(argv: list[str] | None = None) -> int:
    """Run the command line."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    _add_text_parsers(sub)
    _add_run_parsers(sub)
    args = parser.parse_args(argv, namespace=Args())
    handlers: dict[str, Callable[[Args], int]] = {
        "stats": _stats_command,
        "scan": _scan_command,
        "collect-prs": _collect_prs_command,
        "trace": _trace_command,
        "stamp": _stamp_command,
        "source": _source_command,
        "fresh": _fresh_command,
        "init": _init_command,
        "assumptions": lambda a: _assumptions_command(Path(a.file)),
        "gate": lambda a: _gate_command(Path(a.run)),
        "project": lambda a: _project_command(Path(a.run)),
        "breakeven": _breakeven_command,
        "runs": _runs_command,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
