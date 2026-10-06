#!/usr/bin/env python3
"""Arithmetic and gates for the pytest-optimizer phases.

Each command prints one JSON object on stdout. Exit codes: 0 success, 1 a
reported failure (the JSON says why), 2 a usage error. Standard library only.

Commands: run, band, compare, order, token, hash, impact, score, memory-dir.
Run ``measure.py <command> --help`` for arguments.
"""

# pyright: reportAny=false, reportExplicitAny=false, reportUnusedCallResult=false
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import platform
import re
import statistics
import subprocess
import sys
import time
import typing as t

if t.TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

TRUST_FLOOR = 0.05
DEFAULT_K = 3.0
MEMORY_DIRNAME = ".pytest-optimizer"

WEIGHTS = {
    "safety": 0.35,
    "impact": 0.30,
    "effort": 0.15,
    "confidence": 0.12,
    "reversibility": 0.08,
}
SAFETY_CUTOFF = 0.4

_OUTCOME = re.compile(r"(\d+) (passed|failed|skipped|xfailed|xpassed|errors?)\b")
_SUMMARY = re.compile(r" in [\d.]+s")


def median_mad(values: Sequence[float]) -> tuple[float, float]:
    """Return the median and the median absolute deviation.

    >>> median_mad([12.0, 12.5, 13.0, 12.4, 12.6])
    (12.5, 0.1)
    >>> median_mad([1.0, 1.0, 1.0])
    (1.0, 0.0)
    >>> median_mad([])
    Traceback (most recent call last):
    ...
    ValueError: no values
    """
    if not values:
        msg = "no values"
        raise ValueError(msg)
    med = statistics.median(values)
    return round(med, 6), round(statistics.median(abs(v - med) for v in values), 6)


def noise_band(mad: float, k: float = DEFAULT_K, floor: float = TRUST_FLOOR) -> float:
    """Return ``max(k * mad, floor)``; identical runs give MAD 0, never a zero band.

    >>> noise_band(0.0)
    0.05
    >>> noise_band(0.1)
    0.3
    >>> noise_band(0.01, floor=0.2)
    0.2
    """
    return round(max(k * mad, floor), 6)


def parse_summary(output: str) -> dict[str, int]:
    r"""Count outcomes from the last pytest summary line (``-q`` or verbose).

    >>> parse_summary("....\n2 passed, 1 skipped, 3 deselected in 0.05s")
    {'passed': 2, 'skipped': 1, 'total': 3}
    >>> parse_summary("=== 1 failed, 4 passed, 1 warning in 0.10s ===")
    {'failed': 1, 'passed': 4, 'total': 5}
    >>> parse_summary("no tests ran in 0.01s")
    {'total': 0}
    """
    line = next(
        (ln for ln in reversed(output.splitlines()) if _SUMMARY.search(ln)),
        "",
    )
    counts: dict[str, int] = {}
    for number, word in _OUTCOME.findall(line):
        key = "error" if word.startswith("error") else word
        counts[key] = counts.get(key, 0) + int(number)
    counts["total"] = sum(counts.values())
    return counts


def run_once(argv: Sequence[str], cwd: str | None = None) -> dict[str, t.Any]:
    """Run a command once; return wall seconds, exit code, and outcome counts.

    >>> r = run_once([sys.executable, "-c", "print('2 passed in 0.01s')"])
    >>> (r["exit"], r["passed"], r["total"])
    (0, 2, 2)
    >>> run_once([sys.executable, "-c", "raise SystemExit(3)"])["exit"]
    3
    >>> run_once(["no-such-command-here"])["exit"]
    127
    """
    start = time.perf_counter()
    try:
        proc = subprocess.run(  # noqa: S603
            list(argv),
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return {"seconds": 0.0, "exit": 127, "passed": 0, "total": 0}
    seconds = time.perf_counter() - start
    counts = parse_summary(proc.stdout + "\n" + proc.stderr)
    return {
        "seconds": round(seconds, 4),
        "exit": proc.returncode,
        "passed": counts.get("passed", 0),
        "total": counts["total"],
    }


def _validity(runs: Sequence[dict[str, t.Any]]) -> str | None:
    """Return why a set of runs cannot be timed, or None when they can.

    >>> ok = {"seconds": 1.0, "exit": 0, "passed": 5, "total": 5}
    >>> _validity([ok, ok])
    >>> _validity([ok, {**ok, "exit": 1}])
    'a run exited 1, not 0'
    >>> _validity([ok, {**ok, "passed": 4}])
    'passed/total counts differ between runs'
    >>> _validity([])
    'no runs'
    """
    if not runs:
        return "no runs"
    bad = next((r["exit"] for r in runs if r["exit"] != 0), None)
    if bad is not None:
        return f"a run exited {bad}, not 0"
    if len({(r["passed"], r["total"]) for r in runs}) > 1:
        return "passed/total counts differ between runs"
    return None


def band(
    runs: Sequence[dict[str, t.Any]],
    k: float = DEFAULT_K,
    floor: float = TRUST_FLOOR,
) -> dict[str, t.Any]:
    """Summarize baseline runs into the ``baseline.json`` noise fields.

    >>> rs = [{"seconds": s, "exit": 0, "passed": 5, "total": 5} for s in (1.0, 1.0, 1.0)]
    >>> out = band(rs)
    >>> (out["valid"], out["noise"]["median"], out["noise"]["mad"], out["noise"]["band"])
    (True, 1.0, 0.0, 0.05)
    >>> out["tests"]
    {'passed': 5, 'total': 5}
    >>> band([{"seconds": 1.0, "exit": 2, "passed": 0, "total": 0}])["valid"]
    False
    """
    reason = _validity(runs)
    if reason is not None:
        return {"valid": False, "reason": reason}
    med, mad = median_mad([r["seconds"] for r in runs])
    return {
        "valid": True,
        "runs": [{"wall_seconds": r["seconds"]} for r in runs],
        "noise": {
            "median": med,
            "mad": mad,
            "floor": floor,
            "k": k,
            "band": noise_band(mad, k, floor),
        },
        "tests": {"passed": runs[0]["passed"], "total": runs[0]["total"]},
    }


def compare(
    baseline: dict[str, t.Any],
    runs: Sequence[dict[str, t.Any]],
    expect_total: int | None = None,
) -> dict[str, t.Any]:
    """Decide whether candidate runs beat the baseline noise band.

    A candidate counts only when every run exits 0 and the collected-test
    counts match the baseline (or ``expect_total`` for a count-changing change).

    >>> base = band([{"seconds": s, "exit": 0, "passed": 5, "total": 5} for s in (10.0, 10.0)])
    >>> fast = [{"seconds": 7.0, "exit": 0, "passed": 5, "total": 5}] * 3
    >>> out = compare(base, fast)
    >>> (out["clears_noise"], out["median_delta"])
    (True, 3.0)
    >>> jitter = [{"seconds": 9.98, "exit": 0, "passed": 5, "total": 5}] * 3
    >>> compare(base, jitter)["clears_noise"]
    False
    >>> broken = [{"seconds": 1.0, "exit": 1, "passed": 3, "total": 5}] * 3
    >>> compare(base, broken)["reason"]
    'a run exited 1, not 0'
    >>> skipping = [{"seconds": 1.0, "exit": 0, "passed": 2, "total": 5}] * 3
    >>> compare(base, skipping)["reason"]
    'passed/total 2/5 differs from baseline 5/5'
    >>> fewer = [{"seconds": 7.0, "exit": 0, "passed": 4, "total": 4}] * 3
    >>> compare(base, fewer)["reason"]
    'passed/total 4/4 differs from baseline 5/5'
    >>> compare(base, fewer, expect_total=4)["clears_noise"]
    True
    """
    reason = _validity(runs)
    tests = baseline["tests"]
    if reason is None and expect_total is not None:
        if runs[0]["total"] != expect_total:
            reason = f"collected count {runs[0]['total']} differs from expected {expect_total}"
    elif reason is None and (runs[0]["total"], runs[0]["passed"]) != (
        tests["total"],
        tests["passed"],
    ):
        reason = (
            f"passed/total {runs[0]['passed']}/{runs[0]['total']} differs from "
            f"baseline {tests['passed']}/{tests['total']}"
        )
    if reason is not None:
        return {"valid": False, "clears_noise": False, "reason": reason}
    med, _ = median_mad([r["seconds"] for r in runs])
    delta = baseline["noise"]["median"] - med
    limit = baseline["noise"]["band"]
    return {
        "valid": True,
        "median": med,
        "median_delta": round(delta, 4),
        "band": limit,
        "clears_noise": delta > limit,
        "reason": None,
    }


def _nodeids(text: str) -> list[str]:
    r"""Return collected node ids in order, dropping the footer and blank lines.

    >>> _nodeids("a.py::t1\na.py::t2\n\n2 tests collected in 0.02s\n")
    ['a.py::t1', 'a.py::t2']
    """
    return [ln for ln in text.splitlines() if "::" in ln and not ln.startswith((" ", "="))]


def order(a: str, b: str) -> dict[str, t.Any]:
    r"""Compare two ``--collect-only -q`` outputs in collection order.

    >>> old = "x::1\nx::2\n3 tests collected in 0.02s"
    >>> order(old, old.replace("0.02", "0.09"))
    {'same': True, 'count': 2, 'first_difference': None}
    >>> order("x::1\nx::2", "x::2\nx::1")["same"]
    False
    >>> order("x::1\nx::2", "x::2\nx::1")["first_difference"]
    0
    >>> order("x::1", "x::1\nx::2")["first_difference"]
    1
    """
    na, nb = _nodeids(a), _nodeids(b)
    diff = next(
        (i for i, (x, y) in enumerate(zip(na, nb, strict=False)) if x != y),
        None,
    )
    if diff is None and len(na) != len(nb):
        diff = min(len(na), len(nb))
    return {"same": na == nb, "count": len(na), "first_difference": diff}


def env_fingerprint() -> str:
    """Return a short machine-and-interpreter fingerprint.

    >>> env_fingerprint().count("|")
    2
    """
    return f"{platform.python_version()}|{platform.platform()}|{platform.machine()}"


def token(head: str, collection: str, versions: Sequence[str], env: str) -> str:
    r"""Return the idempotency token: HEAD, sorted node ids, versions, environment.

    >>> a = token("abc", "x::2\nx::1", ["pytest=9.0"], "env")
    >>> a == token("abc", "x::1\nx::2", ["pytest=9.0"], "env")
    True
    >>> a == token("abd", "x::1\nx::2", ["pytest=9.0"], "env")
    False
    >>> len(a)
    64
    """
    digest = hashlib.sha256()
    for part in (head, "\n".join(sorted(_nodeids(collection))), *sorted(versions), env):
        digest.update(part.encode())
        digest.update(b"\0")
    return digest.hexdigest()


def impact(delta: float, baseline: float, clears_noise: bool) -> float:
    """Map a measured saving to the rubric's ``impact`` anchor.

    >>> impact(0.1, 10.0, clears_noise=False)
    0.0
    >>> impact(0.3, 10.0, clears_noise=True)
    0.25
    >>> impact(1.0, 10.0, clears_noise=True)
    0.5
    >>> impact(2.2, 10.0, clears_noise=True)
    0.75
    >>> impact(4.5, 10.0, clears_noise=True)
    1.0
    """
    if not clears_noise or baseline <= 0:
        return 0.0
    share = delta / baseline
    if share > 0.40:  # noqa: PLR2004
        return 1.0
    if share >= 0.15:  # noqa: PLR2004
        return 0.75
    if share >= 0.05:  # noqa: PLR2004
        return 0.5
    return 0.25


def score(dims: dict[str, float]) -> dict[str, t.Any]:
    """Weight the five dimensions and apply the hard gates.

    >>> out = score(
    ...     {"safety": 0.9, "impact": 0.75, "effort": 1.0, "confidence": 0.9, "reversibility": 0.9}
    ... )
    >>> (out["total"], out["dropped"])
    (0.87, None)
    >>> score({"safety": 0.1, "impact": 0.5, "effort": 1, "confidence": 1, "reversibility": 1})[
    ...     "dropped"
    ... ]
    'safety below 0.4'
    >>> score({"safety": 1, "impact": 0, "effort": 1, "confidence": 1, "reversibility": 1})[
    ...     "dropped"
    ... ]
    'impact is 0'
    """
    total = round(sum(WEIGHTS[name] * dims[name] for name in WEIGHTS), 3)
    dropped = None
    if dims["safety"] < SAFETY_CUTOFF:
        dropped = "safety below 0.4"
    elif dims["impact"] == 0:
        dropped = "impact is 0"
    return {"total": total, "dropped": dropped, **dims}


def memory_dir(
    explicit: str | None,
    repo_root: pathlib.Path,
    environ: Mapping[str, str],
    remote: str = "",
) -> dict[str, t.Any]:
    """Resolve the memory directory: explicit, in-tree, then per-user cache.

    The first location that exists wins. When none exists the in-tree path is
    returned with ``source`` ``new``; ``00-scan`` creates it, or the per-user
    path (``cache_path``) when the tree is read-only or the user declines.

    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as d:
    ...     root = pathlib.Path(d)
    ...     env = {"XDG_CACHE_HOME": str(root / "xdg")}
    ...     first = memory_dir(None, root, env)
    ...     (root / ".pytest-optimizer").mkdir()
    ...     second = memory_dir(None, root, env)
    ...     third = memory_dir(str(root / "x"), root, env)
    >>> (first["source"], second["source"], third["source"])
    ('new', 'in-tree', 'explicit')
    """
    repo_root = repo_root.resolve()
    in_tree = repo_root / MEMORY_DIRNAME
    repo_id = hashlib.sha256(f"{repo_root}\0{remote}".encode()).hexdigest()[:12]
    if os.name == "nt" and "LOCALAPPDATA" in environ:
        base = pathlib.Path(environ["LOCALAPPDATA"])
    else:
        base = pathlib.Path(environ.get("XDG_CACHE_HOME") or pathlib.Path.home() / ".cache")
    cache = base / "pytest-optimizer" / repo_id
    if explicit:
        path, source = pathlib.Path(explicit), "explicit"
    elif in_tree.is_dir():
        path, source = in_tree, "in-tree"
    elif cache.is_dir():
        path, source = cache, "cache"
    else:
        path, source = in_tree, "new"
    return {
        "path": str(path),
        "source": source,
        "exists": path.is_dir(),
        "cache_path": str(cache),
    }


def _read_runs(path: str) -> list[dict[str, t.Any]]:
    text = sys.stdin.read() if path == "-" else pathlib.Path(path).read_text(encoding="utf-8")
    return [json.loads(ln) for ln in text.splitlines() if ln.strip()]


def _read_text(path: str) -> str:
    return pathlib.Path(path).read_text(encoding="utf-8")


def _emit(obj: dict[str, t.Any], ok: bool = True) -> int:
    print(json.dumps(obj, sort_keys=True))
    return 0 if ok else 1


def _git_remote(root: pathlib.Path) -> str:
    proc = subprocess.run(  # noqa: S603
        ["git", "-C", str(root), "config", "--get", "remote.origin.url"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip()


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="time one command and count its outcomes")
    p.add_argument("--cwd")
    p.add_argument("argv", nargs=argparse.REMAINDER, help="after --, the command")

    p = sub.add_parser("band", help="noise fields from a JSONL file of baseline runs")
    p.add_argument("runs", help="JSONL file from `run`, or - for stdin")
    p.add_argument("--k", type=float, default=DEFAULT_K)
    p.add_argument("--floor", type=float, default=TRUST_FLOOR)

    p = sub.add_parser("compare", help="judge candidate runs against baseline.json")
    p.add_argument("baseline", help="baseline.json")
    p.add_argument("runs", help="JSONL file from `run`, or - for stdin")
    p.add_argument("--expect-total", type=int)

    p = sub.add_parser("order", help="compare two collect-only outputs in order")
    p.add_argument("a")
    p.add_argument("b")

    p = sub.add_parser("token", help="idempotency token")
    p.add_argument("--head", required=True)
    p.add_argument("--collection", required=True, help="collect-only -q output file")
    p.add_argument("--version", action="append", default=[], help="NAME=VERSION")

    p = sub.add_parser("hash", help="sha256 of a file, for plan_hash")
    p.add_argument("file")

    p = sub.add_parser("impact", help="rubric impact anchor for a measured saving")
    p.add_argument("--delta", type=float, required=True)
    p.add_argument("--baseline", type=float, required=True)
    p.add_argument("--clears-noise", action="store_true")

    p = sub.add_parser("score", help="weighted rubric total and hard gates")
    for name in WEIGHTS:
        p.add_argument(f"--{name}", type=float, required=True)

    p = sub.add_parser("memory-dir", help="resolve the memory directory")
    p.add_argument("--memory-dir", dest="explicit")
    p.add_argument("--repo-root", default=".")
    return parser


def main(argv: Sequence[str] | None = None) -> int:  # noqa: PLR0911
    """Dispatch one command.

    >>> main(["impact", "--delta", "5", "--baseline", "10", "--clears-noise"])
    {"impact": 1.0}
    0
    """
    args = build_parser().parse_args(argv)
    cmd = args.command
    if cmd == "run":
        cmdline = [a for a in args.argv if a != "--"] if args.argv[:1] == ["--"] else args.argv
        if not cmdline:
            print("run: give the command after --", file=sys.stderr)
            return 2
        return _emit(run_once(cmdline, args.cwd))
    if cmd == "band":
        out = band(_read_runs(args.runs), args.k, args.floor)
        return _emit(out, out["valid"])
    if cmd == "compare":
        baseline = json.loads(_read_text(args.baseline))
        out = compare(baseline, _read_runs(args.runs), args.expect_total)
        return _emit(out, out["valid"])
    if cmd == "order":
        out = order(_read_text(args.a), _read_text(args.b))
        return _emit(out, out["same"])
    if cmd == "token":
        digest = token(args.head, _read_text(args.collection), args.version, env_fingerprint())
        return _emit({"token": digest})
    if cmd == "hash":
        return _emit({"hash": hashlib.sha256(pathlib.Path(args.file).read_bytes()).hexdigest()})
    if cmd == "impact":
        return _emit({"impact": impact(args.delta, args.baseline, args.clears_noise)})
    if cmd == "score":
        return _emit(score({name: getattr(args, name) for name in WEIGHTS}))
    root = pathlib.Path(args.repo_root)
    return _emit(memory_dir(args.explicit, root, os.environ, _git_remote(root)))


if __name__ == "__main__":
    sys.exit(main())
