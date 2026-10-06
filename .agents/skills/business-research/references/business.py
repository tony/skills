#!/usr/bin/env python3
"""Deterministic checks for business run packages (stdlib only).

Subcommands:

- ``stats``: median, IQR, and a seeded BCa bootstrap interval for the median.
- ``scan``: tier-3 sanitization scan of a draft for identifiers and money terms.
- ``assumptions``: required-field check of an ``assumptions.yaml`` register.
- ``runs``: list run directories newest first, ordered by the date in the path.

Run ``business.py <command> --help`` for each command.
"""

from __future__ import annotations

import argparse
import math
import random
import re
import statistics
import sys
import typing as t
from pathlib import Path

if t.TYPE_CHECKING:
    from collections.abc import Sequence

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


def scan_text(text: str, deny: Sequence[str] = ()) -> list[tuple[int, int, str, str]]:
    """Return ``(line, column, kind, match)`` for every tier-3 exclusion in ``text``.

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
    """
    rules = [*SCAN_RULES, *(("denied-name", re.compile(re.escape(d), re.IGNORECASE)) for d in deny)]
    hits: list[tuple[int, int, str, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in rules:
            hits.extend((number, m.start() + 1, kind, m.group()) for m in pattern.finditer(line))
    return sorted(hits)


def check_assumptions(text: str) -> list[str]:
    r"""Return problems in an ``assumptions.yaml`` register of flat ``key: value`` entries.

    Examples
    --------
    >>> vals = {"source_type": "MEASURED", "confidence": "low"}
    >>> keys = ASSUMPTION_FIELDS[1:]
    >>> good = "\n".join(["- id: a", *[f"  {k}: {vals.get(k, 'x')}" for k in keys]])
    >>> check_assumptions(good)
    []
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
    found = [
        run
        for root in roots
        for run in root.glob("*/business/*")
        if run.is_dir() and DATE_DIR.fullmatch(run.parent.parent.name)
    ]
    return sorted(found, key=lambda p: (p.parent.parent.name, p.name), reverse=True)


def default_roots() -> list[Path]:
    """Return the default run roots: the home Documents folder and WSL Windows Documents."""
    roots = [Path.home() / "Documents"]
    roots.extend(
        sorted(Path("/mnt/c/Users").glob("*/Documents")) if Path("/mnt/c/Users").is_dir() else []
    )
    return roots


def _read(paths: list[str]) -> str:
    if not paths:
        return sys.stdin.read()
    return "\n".join(Path(p).read_text(encoding="utf-8") for p in paths)


class Args(argparse.Namespace):
    """Typed view of the parsed command line."""

    command: str = ""
    files: list[str] = []  # noqa: RUF012
    seed: int = 1
    resamples: int = 10000
    deny: list[str] = []  # noqa: RUF012
    file: str = ""
    root: list[str] = []  # noqa: RUF012


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
        hits = scan_text(_read(args.files), args.deny)
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
    roots = [Path(r) for r in args.root] or default_roots()
    for run in list_runs(roots):
        print(run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
