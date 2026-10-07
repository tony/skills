#!/usr/bin/env python3
"""Deterministic checks for business run packages (stdlib only).

Subcommands:

- ``stats``: median, IQR, and a seeded BCa bootstrap interval for the median.
- ``scan``: tier-3 sanitization scan of a draft for identifiers and money terms.
- ``assumptions``: required-field check of an ``assumptions.yaml`` register.
- ``runs``: list run directories newest first, ordered by the date in the path.
- ``gate``: the completeness gate for one run package, with figures recomputed from ``raw/``.

Run ``business.py <command> --help`` for each command.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as dt
import math
import random
import re
import statistics
import sys
import typing as t
from pathlib import Path

if t.TYPE_CHECKING:
    from collections.abc import Collection, Sequence

DIRECTIONAL_BELOW = 20
MIN_OBSERVATIONS = 2

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
DATE_RANGE = re.compile(r"\d{4}-\d{2}-\d{2}\s*(?:\.\.|to|\u2013|-)\s*\d{4}-\d{2}-\d{2}")
TAGS = ("MEASURED", "DERIVED", "BENCHMARKED", "ESTIMATED")
CITATION = re.compile(r"sources\.md(?:#|\s+`)([\w-]+)")
FIGURE = re.compile(r"\d(?:\.\d+)?\s*(?:%|min\b|h\b|hours?\b|days?\b|PRs?\b|engineers?\b)")
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

    Examples
    --------
    >>> out = summarize([float(x) for x in range(1, 31)], seed=7, resamples=1000)
    >>> (out["n"], out["median"], out["q1"], out["q3"], out["label"])
    (30, 15.5, 8.25, 22.75, 'ok')
    >>> summarize([1.0, 2.0, 9.0], seed=7, resamples=500)["label"]
    'DIRECTIONAL'
    """
    q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
    lo, hi = bca_interval(values, seed=seed, resamples=resamples)
    return {
        "n": len(values),
        "median": _median(values),
        "q1": q1,
        "q3": q3,
        "ci95_lo": lo,
        "ci95_hi": hi,
        "method": "BCa bootstrap of the median",
        "seed": seed,
        "resamples": resamples,
        "label": "DIRECTIONAL" if len(values) < DIRECTIONAL_BELOW else "ok",
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
) -> list[tuple[int, int, str, str]]:
    """Return ``(line, column, kind, match)`` for every tier-3 exclusion in ``text``.

    ``allow`` skips hits whose text equals an entry; ``allow_url`` skips URLs that
    start with an entry.

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
    """
    rules = [*SCAN_RULES, *(("denied-name", re.compile(re.escape(d), re.IGNORECASE)) for d in deny)]
    hits: list[tuple[int, int, str, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in rules:
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
    fields: set[str] = set(rows[0]) if rows else set()
    try:
        if expr in fields:
            return [float(r[expr]) for r in rows]
        left, _, right = expr.partition("-")
        if left in fields and right in fields:
            return [float(r[left]) - float(r[right]) for r in rows]
    except (ValueError, TypeError):
        return None
    return None


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
        with target.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        values = _column(rows, expr)
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
            problems.extend(_check_recomputed(run, label, text))
        problems.extend(_check_unknowns(findings))
    return problems


def _check_unknowns(findings: str) -> list[str]:
    section: list[str] = []
    inside = False
    for line in findings.splitlines():
        if line.startswith("#"):
            inside = line.lstrip("#").strip().lower().startswith("unknown")
        elif inside:
            section.append(line)
    return [
        f"findings.md: unknown without the data that would resolve it: {unit[:60]}"
        for unit in _units("\n".join(section))
        if UNIT_START.match(unit) and "resolve" not in unit.lower()
    ]


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
    run: str = ""


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

    p_gate = sub.add_parser("gate", help="completeness gate for a run; exit 1 on any problem")
    _ = p_gate.add_argument("run", help="run directory")

    p_assume = sub.add_parser("assumptions", help="check required fields of assumptions.yaml")
    _ = p_assume.add_argument("file")

    p_runs = sub.add_parser("runs", help="list runs newest first")
    _ = p_runs.add_argument("--root", action="append", default=[], help="run root; repeatable")

    args = parser.parse_args(argv, namespace=Args())
    if args.command == "stats":
        values = parse_numbers(_read(args.files))
        if len(values) < MIN_OBSERVATIONS:
            print("need at least 2 observations", file=sys.stderr)
            return 2
        for key, value in summarize(values, seed=args.seed, resamples=args.resamples).items():
            print(f"{key}: {value}")
        return 0
    if args.command == "scan":
        hits = scan_text(_read(args.files), args.deny, args.allow, args.allow_url)
        for line, col, kind, match in hits:
            print(f"{line}:{col}: {kind}: {match}")
        if not hits:
            print("clean")
        return 1 if hits else 0
    if args.command == "assumptions":
        problems = check_assumptions(Path(args.file).read_text(encoding="utf-8"))
        for problem in problems:
            print(problem)
        if not problems:
            print("ok")
        return 1 if problems else 0
    if args.command == "gate":
        return _gate_command(Path(args.run))
    roots = [Path(r) for r in args.root] or default_roots()
    for run in list_runs(roots):
        print(run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
