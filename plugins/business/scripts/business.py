#!/usr/bin/env python3
"""Deterministic checks for business run packages (stdlib only).

Subcommands:

- ``stats``: median, IQR, and a seeded BCa bootstrap interval for the median.
- ``scan``: tier-3 sanitization scan of a draft for identifiers and money terms.
- ``assumptions``: required-field check of an ``assumptions.yaml`` register.
- ``runs``: list run directories newest first, ordered by the date in the path.
- ``project``: the org-wide projection and scenarios from register ids.
- ``breakeven``: net per-instance saving, net period saving, and break-even from register ids.
- ``gate``: the completeness gate for one run package, with figures recomputed from ``raw/``.
- ``collect-prs``: per-PR cycle-time rows from ``gh api graphql`` pull-request pages.

Run ``business.py <command> --help`` for each command.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as dt
import json
import math
import random
import re
import statistics
import sys
import typing as t
from pathlib import Path

if t.TYPE_CHECKING:
    from collections.abc import Callable, Collection, Sequence

DIRECTIONAL_BELOW = 20
MIN_OBSERVATIONS = 2
MIN_INTERVAL_N = 5

SCAN_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ticket-id", re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")),
    ("url", re.compile(r"https?://\S+|\bwww\.\S+")),
    ("path", re.compile(r"(?:/home/|/Users/|/mnt/[a-z]/|~/|[A-Za-z]:\\Users\\)\S*")),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("currency", re.compile(r"[$€£¥]|\b(?:USD|EUR|GBP|JPY)\b")),
    (
        "money-term",
        re.compile(r"\b(?:ROI|dollars?|cost savings?|monetiz\w*|payback)\b", re.IGNORECASE),
    ),
)

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
FIGURE = re.compile(rf"\d(?:\.\d+)?[\s-]?(?:%|(?:{_TIME_UNITS}|PRs?|engineers?)\b)", re.IGNORECASE)
UNIT_START = re.compile(r"\s*(?:[-*]|\d+\.|\|)\s?")
CHECK_LINE = re.compile(r"\s*(?:[-*]\s*)?check:", re.IGNORECASE)
CHECK_SPEC = re.compile(
    r"\s*(?:[-*]\s*)?check:\s*(median|mean|min|max|n)\s+(\S+)\s+(\S+)\s*=\s*(-?\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)
SOURCE_FIELDS = (
    ("query", re.compile(r"^\W*(?:query|command)\s*:\s*\S", re.IGNORECASE)),
    ("timestamp", re.compile(r"^\W*(?:executed|timestamp|run at)\s*:\s*\d{4}-", re.IGNORECASE)),
    ("tool version", re.compile(r"^\W*(?:tool )?version\s*:\s*\S", re.IGNORECASE)),
    ("output file", re.compile(r"^\W*output(?: file)?\s*:\s*\S", re.IGNORECASE)),
)
OUTPUT_LINE = re.compile(r"^\W*output(?: file)?\s*:\s*(.+)$", re.IGNORECASE)
CHECK_TOLERANCE = 0.005
UNKNOWN_DATA = re.compile(r"\b(?:resolve|needs?|requires?|data|exports?)\b", re.IGNORECASE)


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
    return {
        "n": n,
        "median": _median(values),
        "q1": q1,
        "q3": q3,
        **interval,
        "seed": seed,
        "resamples": resamples,
        "label": "DIRECTIONAL" if n < DIRECTIONAL_BELOW else "ok",
    }


def parse_numbers(text: str) -> list[float]:
    r"""Parse one number per line, skipping blanks and ``#`` comments.

    Examples
    --------
    >>> parse_numbers("1\n# c\n\n2.5\n")
    [1.0, 2.5]
    """
    return [float(line.split("#")[0]) for line in text.splitlines() if line.split("#")[0].strip()]


def scan_text(
    text: str,
    deny: Sequence[str] = (),
    allow: Sequence[str] = (),
    allow_url: Sequence[str] = (),
    rules: Sequence[str] = (),
) -> list[tuple[int, int, str, str]]:
    """Return ``(line, column, kind, match)`` for every tier-3 exclusion in ``text``.

    ``allow`` skips hits whose text equals an entry; ``allow_url`` skips URLs that
    start with an entry; a non-empty ``rules`` keeps only those kinds.

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
    >>> [h[3] for h in scan_text("GPT-4 and UTF-8.", allow=["UTF-8"])]
    ['GPT-4']
    >>> scan_text("See https://arxiv.org/abs/2507.09089", allow_url=["https://arxiv.org/"])
    []
    >>> [h[2:] for h in scan_text("ROI at https://x.example, $5", rules=["currency"])]
    [('currency', '$')]
    """
    patterns = [
        *SCAN_RULES,
        *(("denied-name", re.compile(re.escape(d), re.IGNORECASE)) for d in deny),
    ]
    if rules:
        patterns = [(kind, pattern) for kind, pattern in patterns if kind in rules]
    hits: list[tuple[int, int, str, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in patterns:
            hits.extend(
                (number, m.start() + 1, kind, m.group())
                for m in pattern.finditer(line)
                if m.group() not in allow
                and not (kind == "url" and m.group().startswith(tuple(allow_url)))
            )
    return sorted(hits)


def _is_date(text: str) -> bool:
    try:
        _ = dt.date.fromisoformat(text)
    except ValueError:
        return False
    return True


def _is_number(text: str) -> bool:
    try:
        _ = float(text)
    except ValueError:
        return False
    return True


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
    ['no entries']
    """
    entries = _parse_register(text)
    if not entries:
        return ["no entries"]
    problems: list[str] = []
    for index, entry in enumerate(entries, start=1):
        name = entry.get("id") or f"#{index}"
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
    ("t", "baseline-minutes"),
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
    falls back to ``value``. ``a`` and ``r`` must lie strictly between 0 and 1.

    Examples
    --------
    >>> reg = "\n".join(
    ...     f"- id: {i}\n  value: {v}\n  low: {lo}\n  high: {hi}"
    ...     for i, v, lo, hi in [
    ...         ("addressable-population", 40, 30, 50),
    ...         ("instances-per-person-year", 100, 100, 100),
    ...         ("baseline-minutes", 30, 25, 40),
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
    """
    entries = {e.get("id", ""): e for e in _parse_register(register)}
    problems: list[str] = []
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
        except (KeyError, ValueError):
            problems.append(f"{ident}: value, low, and high must be numbers")
            continue
        if not low <= base <= high:
            problems.append(f"{ident}: need low <= value <= high")
        if symbol in ("a", "r"):
            problems.extend(
                f"{ident}: {name} {x} must be strictly between 0 and 1"
                for name, x in (("value", base), ("low", low), ("high", high))
                if not 0 < x < 1
            )
        elif symbol == "s" and not 0 < high <= 1:
            problems.append(f"{ident}: high {high} must be in (0, 1]")
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

    figures: dict[str, float] = {
        "conservative": hours(at(0)),
        "base": hours(at(1)),
        "upside": hours(at(2)),
        "addressable": hours(at(1), "s"),
        "served": hours(at(1), "a"),
        "realized": hours(at(1)),
    }
    for symbol, _ in FACTORS:
        swing = hours(lambda sym, s=symbol: levels[sym][2 if sym == s else 1]) - hours(
            lambda sym, s=symbol: levels[sym][0 if sym == s else 1]
        )
        figures[f"swing_{symbol}"] = swing
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
        except (KeyError, ValueError):
            problems.append(f"{ident}: value, low, and high must be numbers")
            continue
        if not low <= base <= high:
            problems.append(f"{ident}: need low <= value <= high")
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
            figures[f"{scenario}_s_net"] = round(v["N"] * s_inst / MINUTES_PER_HOUR - upkeep, 2)
    return figures, list(dict.fromkeys(missing)), []


def list_runs(roots: Sequence[Path]) -> list[Path]:
    """List ``<root>/<date>/business/<workflow>`` directories, newest date first.

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
    """
    found: list[Path] = []
    for root in roots:
        try:
            found.extend(
                run
                for run in root.glob("*/business/*")
                if run.is_dir() and DATE_DIR.fullmatch(run.parent.parent.name)
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
            found = OUTPUT_LINE.match(line)
            if not found:
                continue
            for raw in found.group(1).split(","):
                target = raw.strip().strip("`")
                if target and not (run / target).is_file():
                    problems.append(f"sources.md entry {name}: output {target} does not exist")
    return problems


def _check_figures(label: str, text: str, names: Collection[str]) -> list[str]:
    problems: list[str] = []
    for unit in _units(text):
        if CHECK_LINE.match(unit):
            continue
        if not any(tag in unit for tag in TAGS):
            if FIGURE.search(unit):
                problems.append(f"{label}: figure without a provenance tag: {unit[:60]}")
            continue
        if "MEASURED" not in unit:
            continue
        cited: list[str] = CITATION.findall(unit)
        if not cited:
            problems.append(f"{label}: MEASURED figure cites no sources.md entry: {unit[:60]}")
        problems.extend(
            f"{label}: cited sources.md entry {c} does not exist" for c in cited if c not in names
        )
    return problems


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
            return [float(r[expr]) for r in rows if (r[expr] or "").strip()]
        left, _, right = expr.partition("-")
        if left in fields and right in fields:
            return [
                float(r[left]) - float(r[right])
                for r in rows
                if (r[left] or "").strip() and (r[right] or "").strip()
            ]
    except (ValueError, TypeError):
        return None
    return None


def _read_csv_column(path: Path, expr: str) -> list[float] | None:
    with path.open(encoding="utf-8", newline="") as handle:
        return _column(list(csv.DictReader(handle)), expr)


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
        for label, text in (
            *((k, v.read_text(encoding="utf-8")) for k, v in docs.items()),
            ("findings.md", findings),
        ):
            problems.extend(_check_figures(label, text, set(entries)))
            problems.extend(
                f"{label}:{line}: currency {match!r}; value is hours, never money"
                for line, _, kind, match in scan_text(text)
                if kind == "currency"
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
        if UNIT_START.match(unit) and not UNKNOWN_DATA.search(unit)
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
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


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
    it is blank when there is none. A PR whose ``reviews.pageInfo.hasNextPage`` is
    true appends a line to ``warnings``. Logins are read to compare author and
    reviewer and never written to the rows.

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
    """
    lo = dt.datetime.fromisoformat(f"{start}T00:00:00+00:00")
    hi = dt.datetime.fromisoformat(f"{end}T00:00:00+00:00") + dt.timedelta(days=1)
    rows: list[dict[str, str]] = []
    for doc in _json_documents(text):
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
                    "reopened": str(_obj(pr.get("reopened")).get("filteredCount", 0)),
                    "additions": str(pr.get("additions", 0)),
                    "deletions": str(pr.get("deletions", 0)),
                }
            )
    return sorted(rows, key=lambda r: int(r["number"]))


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
        ("s_net", "S_net (engineer-hours per period)"),
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
    if args.csv_file:
        values = _read_csv_column(Path(args.csv_file), args.column) or []
    else:
        values = parse_numbers(_read(args.files))
    if len(values) < MIN_OBSERVATIONS:
        print("need at least 2 observations", file=sys.stderr)
        return 2
    for key, value in summarize(values, seed=args.seed, resamples=args.resamples).items():
        print(f"{key}: {value}")
    return 0


def _scan_command(args: Args) -> int:
    hits = scan_text(
        _read(args.files),
        args.deny,
        args.allow,
        args.allow_url,
        [r for r in args.rules.split(",") if r],
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
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(PR_COLUMNS)
    writer.writerows([row[c] for c in PR_COLUMNS] for row in rows)
    return 0


def _runs_command(args: Args) -> int:
    for run in list_runs([Path(r) for r in args.root] or default_roots()):
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


def main(argv: list[str] | None = None) -> int:
    """Run the command line."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

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

    p_break = sub.add_parser(
        "breakeven", help="S_inst, S_net, and break-even per scenario from assumptions.yaml"
    )
    _ = p_break.add_argument("run", help="run directory")

    p_assume = sub.add_parser("assumptions", help="check required fields of assumptions.yaml")
    _ = p_assume.add_argument("file")

    p_runs = sub.add_parser("runs", help="list runs newest first")
    _ = p_runs.add_argument("--root", action="append", default=[], help="run root; repeatable")

    args = parser.parse_args(argv, namespace=Args())
    handlers: dict[str, Callable[[Args], int]] = {
        "stats": _stats_command,
        "scan": _scan_command,
        "collect-prs": _collect_prs_command,
        "assumptions": lambda a: _assumptions_command(Path(a.file)),
        "gate": lambda a: _gate_command(Path(a.run)),
        "project": lambda a: _project_command(Path(a.run)),
        "breakeven": _breakeven_command,
        "runs": _runs_command,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
