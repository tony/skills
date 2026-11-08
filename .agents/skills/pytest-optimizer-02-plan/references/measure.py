#!/usr/bin/env python3
"""Arithmetic and gates for the pytest-optimizer phases.

Each command prints one JSON object on stdout. Exit codes: 0 success, 1 a
reported failure (the JSON says why), 2 a usage error. Standard library only.

Commands: run, band, compare, expected-total, ids, order, token, hash, impact,
score, memory-dir, chain, baseline, record, state, run-id, budget, totals, regress,
runs-dir, exclude, hyp-id, pending, plan-build, log.
`run` exits 0 whenever it timed the command; read `exit` in its JSON for the
suite's own status.
Run ``measure.py <command> --help`` for arguments.
"""

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import platform
import re
import secrets
import signal
import statistics
import subprocess
import sys
import tempfile
import time
import typing as t

if t.TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

TRUST_FLOOR = 0.05
REL_FLOOR = 0.01
DEFAULT_K = 3.0
MAD_SCALE = 1.4826
MEMORY_DIRNAME = ".pytest-optimizer"
MIN_RUNS = 3
PHASES = ("scan", "benchmark", "plan", "execute")
BUDGET_LIMITS = {"scan": 900.0, "benchmark": 1800.0}
TIMEOUT_FACTOR = 4
DEFAULT_TIMEOUT = 1800.0
OUTPUT_TAIL = 1 << 20
TIMED_OUT = 124

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
    """Return ``max(k * MAD_SCALE * mad, floor)``; MAD 0 never gives a zero band.

    >>> noise_band(0.0)
    0.05
    >>> noise_band(0.1)
    0.44478
    >>> noise_band(0.01, floor=0.2)
    0.2
    """
    return round(max(k * MAD_SCALE * mad, floor), 6)


def trust_floor(median: float) -> float:
    """Return the larger of 50 ms and 1% of the median.

    >>> trust_floor(1.0)
    0.05
    >>> trust_floor(120.0)
    1.2
    """
    return round(max(TRUST_FLOOR, REL_FLOOR * median), 6)


def parse_summary(output: str) -> dict[str, int] | None:
    r"""Count the last pytest outcome summary, or return None when unavailable.

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
    if not counts and "no tests ran" not in line:
        return None
    counts["total"] = sum(counts.values())
    return counts


def _stop(proc: subprocess.Popen[bytes]) -> None:
    """Kill the command and every process it started."""
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except OSError:
        pass
    proc.wait()


def run_once(
    argv: Sequence[str],
    cwd: str | None = None,
    timeout: float | None = DEFAULT_TIMEOUT,
) -> dict[str, t.Any]:
    """Run a command once; return wall seconds, exit code, and outcome counts.

    Output goes to a temporary file and only its last mebibyte is parsed, so a
    chatty or undecodable run cannot exhaust memory or break the JSON contract.
    A run past ``timeout`` seconds is killed and reports ``exit`` 124.
    Unrecognized summaries produce null counts, refused by band and compare.

    >>> r = run_once([sys.executable, "-c", "print('2 passed in 0.01s')"])
    >>> (r["exit"], r["passed"], r["total"])
    (0, 2, 2)
    >>> run_once([sys.executable, "-c", "raise SystemExit(3)"])["exit"]
    3
    >>> run_once(["no-such-command-here"])["exit"]
    127
    >>> slow = run_once([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.2)
    >>> (slow["exit"], slow["reason"])
    (124, 'timed out after 0.2s')
    """
    start = time.perf_counter()
    with tempfile.TemporaryFile() as sink:
        try:
            proc = subprocess.Popen(  # noqa: S603
                list(argv),
                cwd=cwd,
                stdout=sink,
                stderr=subprocess.STDOUT,
                start_new_session=os.name == "posix",
            )
        except OSError:
            return {"seconds": 0.0, "exit": 127, "passed": None, "total": None}
        timed_out = False
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _stop(proc)
            code, timed_out = TIMED_OUT, True
        seconds = time.perf_counter() - start
        size = sink.seek(0, os.SEEK_END)
        sink.seek(max(0, size - OUTPUT_TAIL))
        text = sink.read().decode("utf-8", "replace")
    counts = parse_summary(text)
    result: dict[str, t.Any] = {
        "seconds": round(seconds, 4),
        "exit": code,
        "passed": counts.get("passed", 0) if counts is not None else None,
        "total": counts["total"] if counts is not None else None,
    }
    if timed_out:
        result["reason"] = f"timed out after {timeout}s"
    elif counts is None:
        result["reason"] = "test outcome summary unavailable"
    return result


def _count_error(counts: object) -> str | None:
    """Reject absent, empty or internally inconsistent outcome evidence."""
    if not isinstance(counts, dict):
        return "test outcome counts unavailable"
    record = t.cast("dict[str, object]", counts)
    passed, total = record.get("passed"), record.get("total")
    if (
        not isinstance(passed, int)
        or isinstance(passed, bool)
        or not isinstance(total, int)
        or isinstance(total, bool)
    ):
        return "test outcome counts must be observed integers"
    if total <= 0:
        return "no test outcomes were reported"
    if not 0 <= passed <= total:
        return "passed count must be between zero and total"
    return None


def _validity(runs: Sequence[dict[str, t.Any]], min_runs: int = 1) -> str | None:  # noqa: PLR0911
    """Return why a set of runs cannot be timed, or None when they can.

    >>> ok = {"seconds": 1.0, "exit": 0, "passed": 5, "total": 5}
    >>> _validity([ok, ok])
    >>> _validity([ok, {**ok, "exit": 1}])
    'a run exited 1, not 0'
    >>> _validity([ok, {**ok, "passed": 4}])
    'passed/total counts differ between runs'
    >>> _validity([])
    'no runs'
    >>> _validity([ok, ok], min_runs=3)
    '2 of 3 required runs recorded'
    """
    if not runs:
        return "no runs"
    if any(r.get("exit") == TIMED_OUT for r in runs):
        return "a run timed out"
    bad = next((r["exit"] for r in runs if r["exit"] != 0), None)
    if bad is not None:
        return f"a run exited {bad}, not 0"
    if len(runs) < min_runs:
        return f"{len(runs)} of {min_runs} required runs recorded"
    for run in runs:
        reason = _count_error(run)
        if reason is not None:
            return reason
    if len({(r["passed"], r["total"]) for r in runs}) > 1:
        return "passed/total counts differ between runs"
    return None


def band(
    runs: Sequence[dict[str, t.Any]],
    k: float = DEFAULT_K,
    floor: float | None = None,
    min_runs: int = MIN_RUNS,
) -> dict[str, t.Any]:
    """Summarize baseline runs into the ``baseline.json`` noise fields.

    Fewer than ``min_runs`` runs cannot estimate a spread and are refused.

    >>> rs = [{"seconds": s, "exit": 0, "passed": 5, "total": 5} for s in (1.0, 1.0, 1.0)]
    >>> band(rs[:2])["reason"]
    '2 of 3 required runs recorded'
    >>> out = band(rs)
    >>> (out["valid"], out["noise"]["median"], out["noise"]["mad"], out["noise"]["band"])
    (True, 1.0, 0.0, 0.05)
    >>> out["tests"]
    {'passed': 5, 'total': 5}
    >>> band([{"seconds": 1.0, "exit": 2, "passed": 0, "total": 0}])["valid"]
    False
    """
    reason = _validity(runs, min_runs)
    if reason is not None:
        return {"valid": False, "reason": reason}
    med, mad = median_mad([r["seconds"] for r in runs])
    if floor is None:
        floor = trust_floor(med)
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
    min_runs: int = MIN_RUNS,
) -> dict[str, t.Any]:
    """Decide whether candidate runs beat the baseline noise band.

    Every run needs observed positive outcome counts and exit 0. A reduced
    ``expect_total`` permits fewer passing tests, preserving non-passing counts.
    A single verification run passes ``min_runs=1`` and reads ``valid`` only.

    >>> base = band([{"seconds": s, "exit": 0, "passed": 5, "total": 5} for s in (10.0,) * 3])
    >>> fast = [{"seconds": 7.0, "exit": 0, "passed": 5, "total": 5}] * 3
    >>> out = compare(base, fast)
    >>> (out["clears_noise"], out["median_delta"])
    (True, 3.0)
    >>> jitter = [{"seconds": 9.98, "exit": 0, "passed": 5, "total": 5}] * 3
    >>> compare(base, jitter)["clears_noise"]
    False
    >>> noisy = [{"seconds": s, "exit": 0, "passed": 5, "total": 5} for s in (7.0, 9.5, 6.0)]
    >>> out = compare(base, noisy)
    >>> (out["median_delta"], out["clears_noise"])
    (3.0, False)
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
    >>> compare(base, fewer[:1], expect_total=4)["reason"]
    '1 of 3 required runs recorded'
    >>> compare(base, fewer[:1], expect_total=4, min_runs=1)["valid"]
    True
    """
    tests = t.cast("dict[str, int]", baseline.get("tests"))
    reason = _count_error(tests)
    if reason is not None:
        reason = f"baseline: {reason}"
    else:
        reason = _validity(runs, min_runs)
    if reason is None and expect_total is not None:
        if _count_error({"passed": 0, "total": expect_total}) is not None:
            reason = "expected total must be a positive integer"
        elif runs[0]["total"] != expect_total:
            reason = f"outcome count {runs[0]['total']} differs from expected {expect_total}"
        elif runs[0]["total"] - runs[0]["passed"] != tests["total"] - tests["passed"]:
            reason = "non-passing count differs from baseline"
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
    med, mad = median_mad([r["seconds"] for r in runs])
    noise = baseline["noise"]
    delta = noise["median"] - med
    spread = math.hypot(noise["mad"], mad)
    limit = noise_band(spread, noise["k"], noise["floor"])
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


def expected_total(
    baseline_total: int,
    plan: Sequence[dict[str, t.Any]],
    applied: Sequence[int],
    through: int | None = None,
) -> int:
    """Collected-test count once the ``applied`` plan orders are in the tree.

    Each plan item's ``expected_total`` is cumulative (the count after it and
    every earlier item apply), so its own change is the difference from the
    previous item. Skipped items contribute nothing. With ``through``, the item
    with that order counts as applied and later items are ignored.

    >>> plan = [
    ...     {"order": 1, "expected_total": 8},
    ...     {"order": 2, "expected_total": 8},
    ...     {"order": 3, "expected_total": 7},
    ... ]
    >>> expected_total(10, plan, [1, 2], through=2)
    8
    >>> expected_total(10, plan, [], through=2)
    10
    >>> expected_total(10, plan, [1, 3], through=3)
    7
    >>> expected_total(10, plan, [1, 2])
    8
    >>> expected_total(10, plan, [])
    10
    """
    running = prev = baseline_total
    for item in sorted(plan, key=lambda i: i["order"]):
        if through is not None and item["order"] > through:
            break
        if item["order"] in applied or item["order"] == through:
            running += int(item["expected_total"]) - prev
        prev = int(item["expected_total"])
    return running


def _applied_orders(log_path: str) -> list[int]:
    """Orders of the applied items in ``execution-log.json``.

    The log does not exist before the first item or under ``--dry-run``.

    >>> _applied_orders("/nonexistent/execution-log.json")
    []
    """
    if not pathlib.Path(log_path).exists():
        return []
    return [e["order"] for e in json.loads(_read_text(log_path)) if e.get("applied")]


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


def _removed_ids(
    plan: Sequence[dict[str, t.Any]], applied: Sequence[int], through: int | None
) -> set[str]:
    """Node ids that the applied (or ``through``) plan items deselect."""
    removed: set[str] = set()
    for item in plan:
        if through is not None and item["order"] > through:
            continue
        if item["order"] in applied or item["order"] == through:
            removed.update(item.get("removed_ids", []))
    return removed


def identity(
    baseline: str,
    candidate: str,
    removed: set[str] | None = None,
) -> dict[str, t.Any]:
    r"""Compare collected node ids, allowing only the approved removals.

    This checks which tests exist, not what they assert.

    >>> base = "a::t1\na::t2\na::t3\n3 tests collected in 0.02s"
    >>> identity(base, "a::t3\na::t1\na::t2")["same"]
    True
    >>> out = identity(base, "a::t1\na::t3\na::t4")
    >>> (out["same"], out["missing"], out["unexpected"])
    (False, ['a::t2'], ['a::t4'])
    >>> identity(base, "a::t1\na::t3", removed={"a::t2"})["same"]
    True
    >>> identity("2 tests collected", "2 tests collected")["reason"]
    'no node ids in the baseline listing'
    """
    old, new = set(_nodeids(baseline)), set(_nodeids(candidate))
    if not old:
        return {
            "same": False,
            "missing": [],
            "unexpected": [],
            "reason": "no node ids in the baseline listing",
        }
    want = old - (removed or set())
    missing, unexpected = sorted(want - new), sorted(new - want)
    return {
        "same": not missing and not unexpected,
        "missing": missing,
        "unexpected": unexpected,
        "reason": None
        if not missing and not unexpected
        else "collected node ids differ from the plan",
    }


def env_fingerprint() -> str:
    """Return a short machine-and-interpreter fingerprint.

    >>> env_fingerprint().count("|")
    2
    """
    return f"{platform.python_version()}|{platform.platform()}|{platform.machine()}"


def token(
    head: str,
    collection: str,
    versions: Sequence[str],
    env: str,
    bound: Sequence[str] = (),
) -> str:
    r"""Return the idempotency token for the measured checkout and command.

    It covers HEAD, sorted node ids, versions, the environment, and the
    ``bound`` parts: the digest of dirty and untracked inputs and the resolved
    test command.

    >>> a = token("abc", "x::2\nx::1", ["pytest=9.0"], "env")
    >>> a == token("abc", "x::1\nx::2", ["pytest=9.0"], "env")
    True
    >>> a == token("abd", "x::1\nx::2", ["pytest=9.0"], "env")
    False
    >>> a == token("abc", "x::1\nx::2", ["pytest=9.0"], "env", ["dirty"])
    False
    >>> a == token("abc", "x::1\nx::2", ["pytest=9.0"], "env", ["", "pytest -x"])
    False
    >>> len(a)
    64
    """
    digest = hashlib.sha256()
    parts = (head, "\n".join(sorted(_nodeids(collection))), *sorted(versions), env, *bound)
    for part in parts:
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


def score(dims: dict[str, float], hygiene: bool = False) -> dict[str, t.Any]:
    """Weight the dimensions and apply the hard gates.

    A hygiene item (typing, parametrize convention) saves no time by design: it
    skips the noise gate and is scored on the other four dimensions, rescaled to 1.

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
    >>> out = score(
    ...     {"safety": 1, "impact": 0, "effort": 1, "confidence": 1, "reversibility": 1},
    ...     hygiene=True,
    ... )
    >>> (out["total"], out["dropped"])
    (1.0, None)
    >>> score({"safety": 2, "impact": 0, "effort": 1, "confidence": 1, "reversibility": 1})
    Traceback (most recent call last):
    ...
    ValueError: safety must be between 0 and 1
    """
    bad = next((n for n in WEIGHTS if not 0 <= dims[n] <= 1), None)
    if bad is not None:
        msg = f"{bad} must be between 0 and 1"
        raise ValueError(msg)
    if hygiene:
        rest = 1 - WEIGHTS["impact"]
        total = round(sum(w * dims[n] for n, w in WEIGHTS.items() if n != "impact") / rest, 3)
    else:
        total = round(sum(WEIGHTS[name] * dims[name] for name in WEIGHTS), 3)
    dropped = None
    if dims["safety"] < SAFETY_CUTOFF:
        dropped = "safety below 0.4"
    elif dims["impact"] == 0 and not hygiene:
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
        path, source = pathlib.Path(explicit).resolve(), "explicit"
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


def run_id(now: dt.datetime | None = None) -> str:
    """Return a branch-safe id for one ``03-execute`` run.

    >>> run_id(dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc))[:19]
    'run-20260102T030405'
    """
    stamp = (now or dt.datetime.now(dt.UTC)).strftime("%Y%m%dT%H%M%S")
    return f"run-{stamp}-{secrets.token_hex(2)}"


def _write_json(path: pathlib.Path, data: object) -> None:
    """Replace ``path`` with ``data`` so a crash leaves the old file or the new one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _load_object(path: pathlib.Path) -> dict[str, t.Any]:
    """Read a JSON object, or an empty one when the file does not exist."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = f"{path.name} is not a JSON object"
        raise TypeError(msg)
    return t.cast("dict[str, t.Any]", data)


def resume(state: Mapping[str, t.Any]) -> dict[str, t.Any]:
    """Name the first phase whose ``completed`` flag is not true.

    >>> resume({})["next"]
    'scan'
    >>> resume({"completed": {"scan": True, "benchmark": True}})["next"]
    'plan'
    >>> resume({"completed": dict.fromkeys(PHASES, True)})["next"]
    """
    done = t.cast("Mapping[str, object]", state.get("completed") or {})
    nxt = next((p for p in PHASES if done.get(p) is not True), None)
    return {"next": nxt, "completed": {p: done.get(p) is True for p in PHASES}}


def complete(state: dict[str, t.Any], phase: str, extra: Mapping[str, t.Any]) -> dict[str, t.Any]:
    """Mark ``phase`` done, clear every later flag, and merge ``extra`` fields.

    >>> out = complete({"completed": {"scan": True, "benchmark": True}}, "scan", {"dirty": False})
    >>> (out["phase"], out["completed"]["benchmark"], out["dirty"])
    ('scan', False, False)
    """
    at = PHASES.index(phase)
    flags = resume(state)["completed"]
    for name in PHASES[at + 1 :]:
        flags[name] = False
    flags[phase] = True
    return {**state, **extra, "phase": phase, "completed": flags}


def baseline_record(
    runs: Sequence[dict[str, t.Any]],
    meta: Mapping[str, t.Any],
    previous: Mapping[str, t.Any] | None = None,
) -> dict[str, t.Any]:
    """Assemble ``baseline.json`` from timed runs; keep fields written by later steps.

    >>> rs = [{"seconds": 1.0, "exit": 0, "passed": 5, "total": 5}] * 3
    >>> out = baseline_record(rs, {"test_command": "pytest"}, {"timings": [1]})
    >>> (out["valid"], out["test_command"], out["timings"], out["tests"]["total"])
    (True, 'pytest', [1], 5)
    >>> baseline_record(rs[:1], {})["valid"]
    False
    """
    out = band(runs)
    if not out["valid"]:
        return out
    stamp = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    return {
        **(previous or {}),
        "captured_at": stamp,
        "python": platform.python_version(),
        **meta,
        **{k: out[k] for k in ("runs", "noise", "tests")},
        "valid": True,
    }


def record(
    entries: Sequence[dict[str, t.Any]],
    entry: dict[str, t.Any],
    state: Mapping[str, t.Any] | None = None,
) -> list[dict[str, t.Any]]:
    """Upsert one entry by id; with ``state``, stamp the scan's token and HEAD.

    >>> st = {"env_token": "tok", "base_head": "abc"}
    >>> out = record([{"id": "a", "median_delta": 1}], {"id": "a", "median_delta": 2}, st)
    >>> out
    [{'id': 'a', 'median_delta': 2, 'env_token': 'tok', 'base_head': 'abc'}]
    >>> [e["id"] for e in record(out, {"id": "b"}, st)]
    ['a', 'b']
    >>> record([], {"id": "h"})
    [{'id': 'h'}]
    """
    stamped = dict(entry)
    if state is not None:
        stamped.update(env_token=state["env_token"], base_head=state["base_head"])
    kept = [stamped if e.get("id") == entry["id"] else e for e in entries]
    return kept if any(e.get("id") == entry["id"] for e in entries) else [*kept, stamped]


_DURATION = re.compile(r"^\s*(\d+(?:\.\d+)?)s\s+(setup|call|teardown)\s+(\S.*?)\s*$")


def parse_durations(text: str) -> list[dict[str, t.Any]]:
    r"""Read ``--durations`` rows, one per ``(nodeid, phase)``, in the order printed.

    >>> rows = parse_durations("4.80s setup  t.py::a\n0.61s call  t.py::a\n4.80s setup  t.py::a")
    >>> [(r["nodeid"], r["phase"], r["seconds"]) for r in rows]
    [('t.py::a', 'setup', 4.8), ('t.py::a', 'call', 0.61)]
    """
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, t.Any]] = []
    for line in text.splitlines():
        match = _DURATION.match(line)
        if match and (match[3], match[2]) not in seen:
            seen.add((match[3], match[2]))
            rows.append({"nodeid": match[3], "phase": match[2], "seconds": float(match[1])})
    return rows


def hyp_id(heuristic: str, files: Sequence[str], evidence: str) -> str:
    """Content-derived hypothesis id: heuristic, sorted target files, evidence digest.

    >>> hyp_id("H10", ["tests/b.py", "tests/a.py"], "x")
    'H10-tests_a.py+tests_b.py-2d711642'
    >>> hyp_id("H10", ["tests/a.py"], "x") == hyp_id("H10", ["tests/a.py"], "y")
    False
    """
    names = "+".join(re.sub(r"[^\w.]+", "_", f) for f in sorted(files))
    digest = hashlib.sha256(evidence.encode()).hexdigest()[:8]
    return f"{heuristic}-{names}-{digest}"


def pending(
    hypotheses: Sequence[dict[str, t.Any]],
    benchmarks: Sequence[dict[str, t.Any]],
    token: str,
    only: str | None = None,
    force: bool = False,
) -> list[str]:
    """Ids still to benchmark: open, selected, and not recorded under the current token.

    >>> hs = [{"id": "a"}, {"id": "b", "status": "open"}, {"id": "c", "status": "rejected"}]
    >>> pending(hs, [{"id": "a", "env_token": "t"}], "t")
    ['b']
    >>> pending(hs, [{"id": "a", "env_token": "old"}], "t", only="a")
    ['a']
    >>> pending(hs, [{"id": "a", "env_token": "t"}], "t", force=True)
    ['a', 'b']
    """
    done = {b["id"] for b in benchmarks if b.get("env_token") == token}
    return [
        h["id"]
        for h in hypotheses
        if h.get("status", "open") == "open"
        and (only is None or h["id"] == only or str(h.get("heuristic")) == only)
        and (force or h["id"] not in done)
    ]


def unchanged(
    state: Mapping[str, t.Any], token: str, hygiene: bool, present: bool
) -> dict[str, t.Any]:
    """Decide whether a finished scan can be skipped.

    >>> st = {"completed": {"scan": True}, "env_token": "t", "hygiene": False}
    >>> unchanged(st, "t", False, True)["unchanged"]
    True
    >>> unchanged(st, "t", True, True)["reason"]
    'hygiene differs from the recorded scan'
    """
    reason = None
    done = t.cast("Mapping[str, object]", state.get("completed") or {})
    if done.get("scan") is not True:
        reason = "no completed scan"
    elif state.get("env_token") != token:
        reason = "the token differs from the recorded scan"
    elif bool(state.get("hygiene")) != hygiene:
        reason = "hygiene differs from the recorded scan"
    elif not present:
        reason = "the scan's output is missing"
    return {"unchanged": reason is None, "reason": reason}


def plan_build(
    draft: Sequence[dict[str, t.Any]],
    benchmarks: Sequence[dict[str, t.Any]],
    state: Mapping[str, t.Any],
    baseline: Mapping[str, t.Any],
) -> dict[str, t.Any]:
    """Assemble ``plan.json`` from the drafted judgment and the recorded benchmarks.

    A draft item gives ``order``, ``id``, ``commit``, ``verify``, ``depends_on`` and
    the four judged dimensions in ``score``. Impact comes from the benchmark entry,
    zero unless it cleared the noise band; items the rubric drops are listed apart.

    >>> st = {"env_token": "t"}
    >>> base = {"noise": {"median": 10.0}, "tests": {"total": 10}}
    >>> bench = [{"id": "a", "env_token": "t", "verdict": "validated", "median_delta": 3.0,
    ...           "clears_noise": True, "files": ["f"], "patch": "p", "patch_sha256": "h"}]
    >>> dims = dict(safety=0.9, effort=1, confidence=0.9, reversibility=0.9)
    >>> out = plan_build([{"order": 1, "id": "a", "score": dims, "commit": {}}], bench, st, base)
    >>> (out["plan"][0]["score"]["impact"], out["plan"][0]["expected_total"], out["dropped"])
    (0.75, 10, [])
    >>> bench[0]["clears_noise"] = False
    >>> plan_build([{"order": 1, "id": "a", "score": dims, "commit": {}}], bench, st, base)[
    ...     "dropped"]
    [{'id': 'a', 'reason': 'impact is 0'}]
    """
    by_id = {b["id"]: b for b in benchmarks}
    plan: list[dict[str, t.Any]] = []
    dropped: list[dict[str, str]] = []
    removes: list[dict[str, t.Any]] = []
    for item in sorted(draft, key=lambda i: i["order"]):
        entry = by_id.get(item["id"])
        if entry is None:
            msg = f"{item['id']} is not in benchmarks.json"
            raise ValueError(msg)
        if entry.get("verdict") != "validated":
            why = entry.get("reason") or "no reason recorded"
            msg = f"{item['id']} is {entry.get('verdict')}, not validated: {why}"
            raise ValueError(msg)
        if entry.get("env_token") != state.get("env_token"):
            msg = f"{item['id']} has a different token"
            raise ValueError(msg)
        hygiene = entry.get("kind") == "hygiene"
        gain = (
            0.0
            if hygiene
            else impact(
                entry["median_delta"], baseline["noise"]["median"], bool(entry.get("clears_noise"))
            )
        )
        graded = score({**item["score"], "impact": gain}, hygiene)
        if graded["dropped"]:
            dropped.append({"id": item["id"], "reason": graded["dropped"]})
            continue
        removes.append({"order": item["order"], "removes_tests": entry.get("removes_tests", 0)})
        plan.append(
            {
                "order": item["order"],
                "id": item["id"],
                "score": {k: graded[k] for k in (*WEIGHTS, "total")},
                "files": entry["files"],
                "commit": item["commit"],
                "env_token": entry["env_token"],
                "patch": entry["patch"],
                "patch_sha256": entry["patch_sha256"],
                "cache": entry.get("cache", "disabled"),
                "removed_ids": entry.get("removed_ids", []),
                "verify": item.get("verify"),
                "depends_on": item.get("depends_on", []),
            }
        )
    for row, total in zip(plan, totals(baseline["tests"]["total"], removes), strict=True):
        row["expected_total"] = total["expected_total"]
    return {"plan": plan, "dropped": dropped}


def _dependents(plan: Sequence[dict[str, t.Any]], seed: Sequence[int]) -> list[int]:
    """Orders that depend, directly or through others, on the ``seed`` orders."""
    ids = {i["order"]: i["id"] for i in plan}
    hit = set(seed)
    grew = True
    while grew:
        grew = False
        for item in plan:
            deps = set(item.get("depends_on") or [])
            if item["order"] not in hit and any(o in deps or ids[o] in deps for o in hit):
                hit.add(item["order"])
                grew = True
    return sorted(hit - set(seed))


def progress(plan: Sequence[dict[str, t.Any]], log: Sequence[dict[str, t.Any]]) -> int:
    """Plan position of the last item in the finished prefix (-1 when none).

    An item is finished once it is committed or skipped; one still pending, or
    reached only by a dependent's skip entry further on, stops the prefix.

    >>> plan = [{"order": 1}, {"order": 2}, {"order": 3}]
    >>> done = {"order": 1, "applied": True}
    >>> progress(plan, [done, {"order": 3, "skip_reason": "x"}])
    0
    >>> progress(plan, [done, {"order": 2, "applied": False, "skip_reason": None}])
    0
    >>> progress(plan, [done, {"order": 2, "skip_reason": "x"}, {"order": 3, "applied": True}])
    2
    """
    seen = {e["order"]: e for e in log if e.get("applied") or e.get("skip_reason")}
    last = -1
    for pos, item in enumerate(sorted(plan, key=lambda i: i["order"])):
        if item["order"] not in seen:
            break
        last = pos
    return last


def log_step(  # noqa: PLR0913, PLR0917
    log: list[dict[str, t.Any]],
    plan: Sequence[dict[str, t.Any]],
    action: str,
    order: int,
    fields: Mapping[str, t.Any],
    propagate: bool = True,
) -> list[dict[str, t.Any]]:
    """Apply one ``execution-log.json`` transition and return the new log.

    ``begin`` records the pending commit, ``commit`` completes it, and ``skip``
    marks the item and every item that depends on it as not applied.

    >>> plan = [{"order": 1, "id": "a"}, {"order": 2, "id": "b", "depends_on": ["a"]}]
    >>> log = log_step([], plan, "begin", 1, {"pending_tree": "T"})
    >>> log = log_step(log, plan, "commit", 1, {"commit_sha": "abc", "seconds": 7.9})
    >>> (log[0]["applied"], log[0]["verify"]["seconds"], "pending_tree" in log[0])
    (True, 7.9, False)
    >>> out = log_step([], plan, "skip", 1, {"reason": "red"})
    >>> [(e["order"], e["skip_reason"]) for e in out]
    [(1, 'red'), (2, 'depends on a skipped item')]
    """
    by_order = {i["order"]: i for i in plan}
    stamp = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    rest = [e for e in log if e["order"] != order]
    old = next((e for e in log if e["order"] == order), {})
    base = {"order": order, "id": by_order[order]["id"], "ts": stamp}
    if action == "begin":
        entry = {**base, "applied": False, "skip_reason": None, **fields}
    elif action == "commit":
        seconds = fields.get("seconds")
        entry = {
            **{k: v for k, v in old.items() if not k.startswith("pending_")},
            **base,
            "applied": True,
            "commit_sha": fields["commit_sha"],
            "verify": {"passed": True, "seconds": seconds, "output_ref": f"verify-{order}.jsonl"},
            "skip_reason": None,
        }
    else:
        entry = {
            **{k: v for k, v in old.items() if not k.startswith("pending_")},
            **base,
            "applied": False,
            "skip_reason": fields["reason"],
        }
    out = [*rest, entry]
    if action == "skip" and propagate:
        for dep in _dependents(plan, [order]):
            out = [e for e in out if e["order"] != dep]
            out.append(
                {
                    "order": dep,
                    "id": by_order[dep]["id"],
                    "applied": False,
                    "skip_reason": "depends on a skipped item",
                    "ts": stamp,
                }
            )
    return sorted(out, key=lambda e: e["order"])


def budget(
    phase: str, seconds: float, runs: int, hypotheses: int = 0, limit: float | None = None
) -> dict[str, t.Any]:
    """Estimate a phase's cost from one run's ``seconds`` and compare it to the limit.

    ``scan`` costs ``runs + 2`` runs. ``benchmark`` costs ``runs + 1`` runs for
    the control and for each hypothesis; ``fits`` counts the hypotheses that fit.

    >>> budget("scan", 10.0, 5)["estimate"]
    70.0
    >>> out = budget("benchmark", 10.0, 5, hypotheses=4, limit=200.0)
    >>> (out["estimate"], out["over"], out["fits"], out["control_fits"])
    (300.0, True, 2, True)
    >>> budget("scan", 10.0, 5)["timeout"]
    40.0
    """
    cap = BUDGET_LIMITS[phase] if limit is None else limit
    if phase == "scan":
        estimate = (runs + 2) * seconds
        fits = 0
    else:
        each = (runs + 1) * seconds
        estimate = each * (1 + hypotheses)
        fits = max(0, min(hypotheses, int(cap // each) - 1)) if each > 0 else hypotheses
    return {
        "estimate": round(estimate, 4),
        "limit": cap,
        "over": estimate > cap,
        "fits": fits,
        "control_fits": phase == "scan" or (runs + 1) * seconds <= cap,
        "timeout": round(TIMEOUT_FACTOR * seconds, 4),
    }


def totals(baseline_total: int, draft: Sequence[dict[str, t.Any]]) -> list[dict[str, int]]:
    """Cumulative ``expected_total`` per plan item from each item's ``removes_tests``.

    >>> totals(10, [{"order": 2, "removes_tests": 1}, {"order": 1, "removes_tests": 2}])
    [{'order': 1, 'expected_total': 8}, {'order': 2, 'expected_total': 7}]
    """
    running = baseline_total
    out: list[dict[str, int]] = []
    for item in sorted(draft, key=lambda i: i["order"]):
        running -= int(item.get("removes_tests") or 0)
        out.append({"order": item["order"], "expected_total": running})
    return out


def regress(control: Mapping[str, t.Any], seconds: Sequence[float]) -> dict[str, t.Any]:
    """Compare verify timings with the control median plus its band.

    One timing over the limit asks for two more (``rerun``); the median of three
    over the limit is a regression.

    >>> ctl = {"noise": {"median": 10.0, "band": 0.5}}
    >>> regress(ctl, [10.2])
    {'limit': 10.5, 'median': 10.2, 'regressed': False, 'rerun': False}
    >>> regress(ctl, [11.0])["rerun"]
    True
    >>> regress(ctl, [11.0, 12.0, 10.0])["regressed"]
    True
    """
    limit = round(control["noise"]["median"] + control["noise"]["band"], 6)
    med = round(statistics.median(seconds), 6)
    over = med > limit
    return {
        "limit": limit,
        "median": med,
        "regressed": over and len(seconds) >= MIN_RUNS,
        "rerun": over and len(seconds) < MIN_RUNS,
    }


def runs_dir(root: pathlib.Path, memory: pathlib.Path) -> dict[str, t.Any]:
    """Pick and create the directory for run files: git dir, memory dir, then a temp dir.

    The git directory is outside ``git status``; a temp directory does not
    outlive the session.

    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as d:
    ...     r = pathlib.Path(d)
    ...     _ = _git(r, "init", "-q")
    ...     out = runs_dir(r, r / "mem")
    >>> out["source"]
    'git'
    """
    proc = _git(root, "rev-parse", "--git-path", "pytest-optimizer-runs")
    candidates = [("memory", memory / "runs")]
    if proc.returncode == 0 and proc.stdout.strip():
        candidates.insert(0, ("git", (root / proc.stdout.strip()).resolve()))
    for source, path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        if os.access(path, os.W_OK):
            return {"path": str(path), "source": source}
    return {"path": tempfile.mkdtemp(prefix="pytest-optimizer-runs."), "source": "temp"}


def exclude(root: pathlib.Path, lines: Sequence[str]) -> dict[str, t.Any]:
    """Append each missing line to the local git exclude file.

    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as d:
    ...     r = pathlib.Path(d)
    ...     _ = _git(r, "init", "-q")
    ...     first = exclude(r, [".pytest-optimizer/"])["added"]
    ...     second = exclude(r, [".pytest-optimizer/"])["added"]
    >>> (first, second)
    (['.pytest-optimizer/'], [])
    """
    proc = _git(root, "rev-parse", "--git-path", "info/exclude")
    if proc.returncode != 0:
        return {"ok": False, "reason": proc.stderr.strip() or "not a git repository"}
    path = (root / proc.stdout.strip()).resolve()
    try:
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        missing = [ln for ln in lines if ln not in current.splitlines()]
        if missing:
            path.parent.mkdir(parents=True, exist_ok=True)
            sep = "" if not current or current.endswith("\n") else "\n"
            path.write_text(current + sep + "\n".join(missing) + "\n", encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "reason": f"exclude file not writable: {exc.strerror}"}
    return {"ok": True, "added": missing}


def _read_runs(path: str) -> list[dict[str, t.Any]]:
    text = sys.stdin.read() if path == "-" else _read_text(path)
    return [json.loads(ln) for ln in text.splitlines() if ln.strip()]


def _read_text(path: str) -> str:
    return pathlib.Path(path).read_text(encoding="utf-8", errors="replace")


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


def _git(root: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", "-C", str(root), *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


def chain(
    root: pathlib.Path,
    base: str,
    logged: Sequence[str],
    head: str = "HEAD",
) -> dict[str, t.Any]:
    """Check that ``head`` is ``base`` plus exactly the logged commits, in order.

    A resumed ``03-execute`` run checks its result branch with this instead of
    the scan-time token, which includes ``HEAD``.

    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as d:
    ...     r = pathlib.Path(d)
    ...     _ = _git(r, "init", "-q")
    ...     _ = _git(r, "config", "user.email", "a@example.com")
    ...     _ = _git(r, "config", "user.name", "a")
    ...     _ = _git(r, "commit", "-q", "--allow-empty", "-m", "base")
    ...     b = _git(r, "rev-parse", "HEAD").stdout.strip()
    ...     _ = _git(r, "commit", "-q", "--allow-empty", "-m", "one")
    ...     c = _git(r, "rev-parse", "--short", "HEAD").stdout.strip()
    ...     ok = chain(r, b, [c])["ok"]
    ...     none_logged = chain(r, b, [])["ok"]
    ...     _ = _git(r, "commit", "-q", "--allow-empty", "-m", "foreign")
    ...     foreign = chain(r, b, [c])["ok"]
    >>> (ok, none_logged, foreign)
    (True, False, False)
    """
    ancestor = _git(root, "merge-base", "--is-ancestor", "--", base, head)
    if ancestor.returncode == 1:
        return {"ok": False, "reason": f"base is not an ancestor of {head}"}
    if ancestor.returncode != 0:
        return {
            "ok": False,
            "reason": ancestor.stderr.strip() or "could not verify base ancestry",
        }
    proc = _git(root, "rev-list", "--reverse", f"{base}..{head}")
    if proc.returncode != 0:
        return {"ok": False, "reason": proc.stderr.strip() or "could not read commit range"}
    actual = proc.stdout.split()
    expected: list[str] = []
    for sha in logged:
        full = _git(root, "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}")
        if full.returncode != 0:
            return {"ok": False, "reason": f"logged commit {sha} does not exist"}
        expected.append(full.stdout.strip())
    if actual != expected:
        return {
            "ok": False,
            "reason": f"{head} is base plus {len(actual)} commits; the log holds {len(expected)}",
        }
    return {"ok": True, "reason": None}


def build_parser() -> argparse.ArgumentParser:  # noqa: PLR0915
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="time one command and count its outcomes")
    p.add_argument("--cwd")
    p.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT, help="seconds before the run is killed"
    )
    p.add_argument("argv", nargs=argparse.REMAINDER, help="after --, the command")

    p = sub.add_parser("band", help="noise fields from a JSONL file of baseline runs")
    p.add_argument("runs", help="JSONL file from `run`, or - for stdin")
    p.add_argument("--k", type=float, default=DEFAULT_K)
    p.add_argument("--floor", type=float, default=None)
    p.add_argument("--min-runs", type=int, default=MIN_RUNS)

    p = sub.add_parser("compare", help="judge candidate runs against baseline.json")
    p.add_argument("baseline", help="baseline.json")
    p.add_argument("runs", help="JSONL file from `run`, or - for stdin")
    p.add_argument("--expect-total", type=int)
    p.add_argument("--min-runs", type=int, default=MIN_RUNS, help="1 for a single verification run")

    p = sub.add_parser("expected-total", help="test count after the applied plan items")
    p.add_argument("baseline", help="baseline.json")
    p.add_argument("plan", help="plan.json")
    p.add_argument("log", help="execution-log.json")
    p.add_argument("--through", type=int, help="order of the item being verified")

    p = sub.add_parser("ids", help="compare collected node ids, allowing the approved removals")
    p.add_argument("baseline", help="collection.txt")
    p.add_argument("candidate", help="collect-only -q output of the candidate")
    p.add_argument("--plan", help="plan.json, for the approved removed_ids")
    p.add_argument("--log", help="execution-log.json, for the applied items")
    p.add_argument("--through", type=int, help="order of the item being verified")

    p = sub.add_parser("order", help="compare two collect-only outputs in order")
    p.add_argument("a")
    p.add_argument("b")

    p = sub.add_parser("token", help="idempotency token")
    p.add_argument("--head", required=True)
    p.add_argument("--collection", required=True, help="collect-only -q output file")
    p.add_argument("--version", action="append", default=[], help="NAME=VERSION")
    p.add_argument("--inputs-digest", default="", help="digest from isolate.py inputs")
    p.add_argument("--command", dest="test_command", default="", help="the resolved test command")

    p = sub.add_parser("hash", help="sha256 of a file, for plan_hash")
    p.add_argument("file")

    p = sub.add_parser("impact", help="rubric impact anchor for a measured saving")
    p.add_argument("--delta", type=float, required=True)
    p.add_argument("--baseline", type=float, required=True)
    p.add_argument("--clears-noise", action="store_true")

    p = sub.add_parser("score", help="weighted rubric total and hard gates")
    for name in WEIGHTS:
        if name != "impact":
            p.add_argument(f"--{name}", type=float, required=True)
    p.add_argument("--delta", type=float, help="measured saving (median_delta)")
    p.add_argument("--baseline", type=float, help="baseline median")
    p.add_argument("--clears-noise", action="store_true", help="the entry's clears_noise is true")
    p.add_argument("--hygiene", action="store_true", help="skip the noise gate (typing items)")

    p = sub.add_parser("chain", help="check a branch is base plus exactly the logged commits")
    p.add_argument("--base", required=True)
    p.add_argument("--head", default="HEAD", help="branch or commit to check")
    p.add_argument("--cwd", default=".")
    p.add_argument("commits", nargs="*", help="logged commit shas, in order")

    p = sub.add_parser("baseline", help="write baseline.json from the timed baseline runs")
    p.add_argument("runs", help="JSONL file from `run`")
    p.add_argument("--out", required=True, help="baseline.json; existing fields are kept")
    p.add_argument("--test-command", required=True)
    p.add_argument("--pytest-version", required=True)
    p.add_argument("--plugin", action="append", default=[], help="NAME=VERSION")
    p.add_argument("--flag", action="append", default=[], help="a measurement flag, repeatable")
    p.add_argument("--capabilities", help="capabilities.json to embed")
    p.add_argument("--durations", help="--durations output to store as timings")

    p = sub.add_parser("record", help="upsert one entry by id into a JSON list")
    p.add_argument("file", help="benchmarks.json or hypotheses.json")
    p.add_argument("--state", help="state.json; stamps env_token and base_head when given")
    p.add_argument("--entry", help="JSON file holding the entry")
    p.add_argument("--id", help="entry id, when --entry is not given or lacks one")
    p.add_argument("--capture-json", help="isolate.py capture output: sets patch, hash, files")
    p.add_argument("--ids-json", help="measure.py ids output: sets removed_ids, removes_tests")
    p.add_argument("--set", dest="fields", action="append", default=[], help="KEY=JSON")

    p = sub.add_parser("hyp-id", help="content-derived hypothesis id")
    p.add_argument("--heuristic", required=True)
    p.add_argument("--file", action="append", default=[], required=True)
    p.add_argument("--evidence", required=True)

    p = sub.add_parser("pending", help="hypothesis ids still to benchmark")
    p.add_argument("--memory-dir", required=True)
    p.add_argument("--only", help="a hypothesis id or heuristic id")
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("plan-build", help="assemble plan.json from the draft and benchmarks")
    p.add_argument("--memory-dir", required=True)
    p.add_argument("--draft", required=True, help="JSON list of drafted items, or - for stdin")
    p.add_argument("--out", help="write the kept items here (plan.json)")

    p = sub.add_parser("log", help="apply one execution-log.json transition")
    p.add_argument("action", choices=("begin", "commit", "skip"))
    p.add_argument("--memory-dir", required=True)
    p.add_argument("--order", type=int, required=True)
    p.add_argument("--set", dest="fields", action="append", default=[], help="KEY=JSON")
    p.add_argument("--gate-json", help="isolate.py gate output: sets pending_parent, pending_tree")
    p.add_argument("--run-json", help="measure.py run output: sets the verify seconds")
    p.add_argument("--no-propagate", action="store_true", help="skip: leave dependents alone")
    p.add_argument("--log-file", help="dry-run log path; state.json is then left alone")

    p = sub.add_parser("state", help="read or advance the phase flags in state.json")
    p.add_argument("action", choices=("resume", "complete", "update", "unchanged"))
    p.add_argument("file", help="state.json")
    p.add_argument("--phase", choices=PHASES, help="phase to mark complete")
    p.add_argument("--token", help="unchanged: the freshly computed env_token")
    p.add_argument("--hygiene", choices=("true", "false"), help="unchanged: this run's flag")
    p.add_argument("--require", action="append", default=[], help="unchanged: output file name")
    p.add_argument("--set", dest="fields", action="append", default=[], help="KEY=JSON")

    sub.add_parser("run-id", help="id for one 03-execute run")

    p = sub.add_parser("budget", help="estimate a phase's cost against its time limit")
    p.add_argument("--phase", choices=tuple(BUDGET_LIMITS), required=True)
    p.add_argument("--seconds", type=float, required=True, help="one run of the test command")
    p.add_argument("--runs", type=int, required=True)
    p.add_argument("--hypotheses", type=int, default=0)
    p.add_argument("--limit", type=float, help="the project's own limit in seconds")

    p = sub.add_parser("totals", help="cumulative expected_total per drafted plan item")
    p.add_argument("baseline", help="baseline.json")
    p.add_argument("draft", help="JSON list of {order, removes_tests}")

    p = sub.add_parser("regress", help="compare verify timings with the control median plus band")
    p.add_argument("control", help="control.json")
    p.add_argument("seconds", type=float, nargs="+", help="one timing, or three after a rerun")

    p = sub.add_parser("runs-dir", help="create the directory for run files")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--memory-dir", required=True)

    p = sub.add_parser("exclude", help="add lines to the local git exclude file")
    p.add_argument("--repo-root", default=".")
    p.add_argument("lines", nargs="+")

    p = sub.add_parser("memory-dir", help="resolve the memory directory")
    p.add_argument("--memory-dir", dest="explicit")
    p.add_argument("--repo-root", default=".")
    return parser


def _strip_separator(argv: Sequence[str]) -> list[str]:
    """Drop only the leading ``--`` so a wrapper's own separator survives.

    >>> _strip_separator(["--", "tox", "-e", "py", "--", "-p", "no:cacheprovider"])
    ['tox', '-e', 'py', '--', '-p', 'no:cacheprovider']
    >>> _strip_separator(["pytest", "-q"])
    ['pytest', '-q']
    """
    return list(argv[1:] if argv[:1] == ["--"] else argv)


_EXTRA = (
    *("record", "hyp-id", "pending", "plan-build", "log"),
    "baseline",
    "state",
    "run-id",
    "budget",
    "totals",
    "regress",
    "runs-dir",
    "exclude",
)


def _record_cmd(args: argparse.Namespace) -> int:
    """Upsert one entry into a benchmarks or hypotheses file."""
    entry: dict[str, t.Any] = json.loads(_read_text(args.entry)) if args.entry else {}
    if args.capture_json:
        cap = json.loads(_read_text(args.capture_json))
        if cap.get("ok") is not True:
            why = cap.get("reason") or "no patch recorded"
            return _emit({"ok": False, "reason": f"capture did not succeed: {why}"}, ok=False)
        rel = os.path.relpath(cap["patch"], pathlib.Path(args.file).resolve().parent)
        entry.update(patch=rel, patch_sha256=cap["sha256"], files=cap["paths"])
    if args.ids_json:
        gone = json.loads(_read_text(args.ids_json)).get("missing", [])
        if gone:
            entry.update(removed_ids=gone, removes_tests=len(gone))
    entry.update({k: json.loads(v) for k, v in (f.split("=", 1) for f in args.fields)})
    if args.id:
        entry["id"] = args.id
    state = _load_object(pathlib.Path(args.state)) if args.state else None
    bound = state is None or (state.get("env_token") and state.get("base_head"))
    if "id" not in entry or not bound:
        reason = "entry needs an id; state needs env_token and base_head"
        return _emit({"ok": False, "reason": reason}, ok=False)
    path = pathlib.Path(args.file)
    current: list[dict[str, t.Any]] = json.loads(_read_text(args.file)) if path.exists() else []
    _write_json(path, record(current, entry, state))
    return _emit({"ok": True, "id": entry["id"]})


_RECORDS = ("record", "hyp-id", "pending", "plan-build", "log")


def _records(args: argparse.Namespace) -> int:  # noqa: PLR0911
    """Run the commands that edit the per-phase record files."""
    cmd = args.command
    if cmd == "record":
        return _record_cmd(args)
    if cmd == "hyp-id":
        return _emit({"id": hyp_id(args.heuristic, args.file, args.evidence)})
    if cmd == "pending":
        mem = pathlib.Path(args.memory_dir)
        state = _load_object(mem / "state.json")
        bench = mem / "benchmarks.json"
        done: list[dict[str, t.Any]] = json.loads(_read_text(str(bench))) if bench.exists() else []
        hyps = json.loads(_read_text(str(mem / "hypotheses.json")))
        ids = pending(hyps, done, state.get("env_token", ""), args.only, args.force)
        return _emit({"ids": ids})
    if cmd == "plan-build":
        mem = pathlib.Path(args.memory_dir)
        try:
            built = plan_build(
                json.loads(sys.stdin.read() if args.draft == "-" else _read_text(args.draft)),
                json.loads(_read_text(str(mem / "benchmarks.json"))),
                _load_object(mem / "state.json"),
                _load_object(mem / "baseline.json"),
            )
        except ValueError as exc:
            return _emit({"valid": False, "reason": str(exc)}, ok=False)
        if args.out:
            _write_json(pathlib.Path(args.out), built["plan"])
        return _emit(built)
    if cmd == "log":
        mem = pathlib.Path(args.memory_dir)
        plan = json.loads(_read_text(str(mem / "plan.json")))
        log_path = pathlib.Path(args.log_file) if args.log_file else mem / "execution-log.json"
        current: list[dict[str, t.Any]] = (
            json.loads(_read_text(str(log_path))) if log_path.exists() else []
        )
        fields: dict[str, t.Any] = {}
        if args.gate_json:
            gate = json.loads(_read_text(args.gate_json))
            if gate.get("ok") is not True or not (gate.get("parent") and gate.get("tree")):
                why = gate.get("reason") or "parent or tree missing"
                return _emit({"ok": False, "reason": f"gate did not pass: {why}"}, ok=False)
            fields.update(pending_parent=gate["parent"], pending_tree=gate["tree"])
        if args.run_json:
            ran = json.loads(_read_text(args.run_json))
            if "seconds" not in ran:
                return _emit({"ok": False, "reason": "run output has no seconds"}, ok=False)
            fields["seconds"] = ran["seconds"]
        fields.update({k: json.loads(v) for k, v in (f.split("=", 1) for f in args.fields)})
        new = log_step(current, plan, args.action, args.order, fields, not args.no_propagate)
        _write_json(log_path, new)
        if not args.log_file:
            state_path = mem / "state.json"
            _write_json(
                state_path,
                {
                    **_load_object(state_path),
                    "phase": "execute",
                    "last_applied_index": len(new) - 1,
                },
            )
        return _emit({"ok": True, "orders": [e["order"] for e in new]})
    return _emit({"ok": False, "reason": f"unknown command {cmd}"}, ok=False)


def _extra(args: argparse.Namespace) -> int:  # noqa: PLR0911
    """Run the commands that read or write the phase files."""
    cmd = args.command
    if cmd == "run-id":
        return _emit({"run_id": run_id()})
    if cmd == "runs-dir":
        root = pathlib.Path(args.repo_root).resolve()
        return _emit(runs_dir(root, pathlib.Path(args.memory_dir).resolve()))
    if cmd == "exclude":
        out = exclude(pathlib.Path(args.repo_root).resolve(), args.lines)
        return _emit(out, out["ok"])
    if cmd == "budget":
        return _emit(budget(args.phase, args.seconds, args.runs, args.hypotheses, args.limit))
    if cmd == "totals":
        total = json.loads(_read_text(args.baseline))["tests"]["total"]
        return _emit({"totals": totals(total, json.loads(_read_text(args.draft)))})
    if cmd == "regress":
        out = regress(json.loads(_read_text(args.control)), args.seconds)
        return _emit(out, not out["regressed"])
    if cmd == "baseline":
        out_path = pathlib.Path(args.out)
        meta: dict[str, t.Any] = {
            "pytest_version": args.pytest_version,
            "plugins": dict(p.split("=", 1) for p in args.plugin),
            "test_command": args.test_command,
            "measurement_flags": args.flag,
        }
        if args.capabilities:
            meta["capabilities"] = json.loads(_read_text(args.capabilities))
        if args.durations:
            meta["timings"] = parse_durations(_read_text(args.durations))
        out = baseline_record(_read_runs(args.runs), meta, _load_object(out_path))
        if out["valid"]:
            _write_json(out_path, {k: v for k, v in out.items() if k != "valid"})
        return _emit(out, out["valid"])
    if cmd in _RECORDS:
        return _records(args)
    path = pathlib.Path(args.file)
    state = _load_object(path)
    if args.action == "resume":
        return _emit(resume(state))
    if args.action == "unchanged":
        here = all((path.parent / name).exists() for name in args.require)
        return _emit(unchanged(state, args.token or "", args.hygiene == "true", here))
    extra = {k: json.loads(v) for k, v in (f.split("=", 1) for f in args.fields)}
    if args.action == "update":
        _write_json(path, {**state, **extra})
        return _emit({"ok": True})
    if not args.phase:
        return _emit({"ok": False, "reason": "complete needs --phase"}, ok=False)
    _write_json(path, complete(state, args.phase, extra))
    return _emit({"ok": True, "next": resume(_load_object(path))["next"]})


def _dispatch(args: argparse.Namespace) -> int:  # noqa: PLR0911
    cmd = args.command
    if cmd == "run":
        cmdline = _strip_separator(args.argv)
        if not cmdline:
            print("run: give the command after --", file=sys.stderr)
            return 2
        return _emit(run_once(cmdline, args.cwd, args.timeout))
    if cmd == "band":
        out = band(_read_runs(args.runs), args.k, args.floor, args.min_runs)
        return _emit(out, out["valid"])
    if cmd == "compare":
        baseline = json.loads(_read_text(args.baseline))
        out = compare(baseline, _read_runs(args.runs), args.expect_total, args.min_runs)
        return _emit(out, out["valid"])
    if cmd == "expected-total":
        done = _applied_orders(args.log)
        total = json.loads(_read_text(args.baseline))["tests"]["total"]
        plan = json.loads(_read_text(args.plan))
        return _emit({"expected_total": expected_total(total, plan, done, args.through)})
    if cmd == "ids":
        plan: list[dict[str, t.Any]] = json.loads(_read_text(args.plan)) if args.plan else []
        done = _applied_orders(args.log) if args.log else []
        removed = _removed_ids(plan, done, args.through)
        out = identity(_read_text(args.baseline), _read_text(args.candidate), removed)
        return _emit(out, out["same"])
    if cmd == "order":
        out = order(_read_text(args.a), _read_text(args.b))
        return _emit(out, out["same"])
    if cmd == "token":
        digest = token(
            args.head,
            _read_text(args.collection),
            args.version,
            env_fingerprint(),
            [args.inputs_digest, args.test_command],
        )
        return _emit({"token": digest})
    if cmd == "hash":
        return _emit({"hash": hashlib.sha256(pathlib.Path(args.file).read_bytes()).hexdigest()})
    if cmd == "impact":
        return _emit({"impact": impact(args.delta, args.baseline, args.clears_noise)})
    if cmd == "score":
        dims = {name: getattr(args, name, 0.0) for name in WEIGHTS}
        if not args.hygiene:
            if args.delta is None or args.baseline is None:
                return _emit(
                    {"valid": False, "reason": "score needs --delta and --baseline"}, ok=False
                )
            dims["impact"] = impact(args.delta, args.baseline, args.clears_noise)
        try:
            return _emit(score(dims, args.hygiene))
        except ValueError as exc:
            return _emit({"valid": False, "reason": str(exc)}, ok=False)
    if cmd == "chain":
        out = chain(pathlib.Path(args.cwd), args.base, args.commits, args.head)
        return _emit(out, out["ok"])
    if cmd in _EXTRA:
        return _extra(args)
    root = pathlib.Path(args.repo_root)
    return _emit(memory_dir(args.explicit, root, os.environ, _git_remote(root)))


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch one command; unreadable or malformed input is a reported failure.

    >>> main(["impact", "--delta", "5", "--baseline", "10", "--clears-noise"])
    {"impact": 1.0}
    0
    >>> main(["band", "/nonexistent/runs.jsonl"])
    {"reason": "unreadable input: FileNotFoundError", "valid": false}
    1
    """
    args = build_parser().parse_args(argv)
    try:
        return _dispatch(args)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        reason = f"unreadable input: {type(exc).__name__}"
        return _emit({"valid": False, "reason": reason}, ok=False)


if __name__ == "__main__":
    sys.exit(main())
