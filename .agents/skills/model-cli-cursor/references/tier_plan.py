#!/usr/bin/env python3
"""Choose the next tier to run, or stop, from the tiers already run.

Usage: tier_plan.py --prompt-file FILE --timeout SECONDS|none [--plan]
       --tier BINARY ...

--tier lists the tiers in order (repeat once per tier). The tiers already run
are read from FILE.ledger, which run_tier.py writes. A tier whose binary is
not found on PATH (or at the given path) counts as missing. Prints one JSON
object: `next` (1-based tier number or null) and `stop` (null, "budget",
"empty", "no-tier", or "retry-cap").

--retry N asks to run tier N again: it prints `next` N unless the ledger
already holds two rows for N, or any tier holds more than two, which stops
with "retry-cap".

A tier is
skipped when an earlier run on the same binary ended in missing, rate-limit,
auth, untrusted, credit, crash or unsupported-flag, or with --plan in empty: those
failures belong to the binary, not the model. Elapsed time summing past twice
the timeout stops the run. An empty normal run stops it (the CLI already
acted); a second empty plan run also stops it.

>>> plan(["codex", "agent", "agent"], [], timeout=540.0)
{'next': 1, 'stop': None}
>>> plan(["codex", "agent", "agent"], [(1, "auth", 1.0)], timeout=540.0)
{'next': 2, 'stop': None}
>>> plan(["agent", "agent"], [(1, "rate-limit", 1.0)], timeout=540.0)
{'next': None, 'stop': 'no-tier'}
>>> plan(["agent", "agent"], [(1, "timeout", 540.0)], timeout=540.0)
{'next': 2, 'stop': None}
>>> plan(["agy", "agent", "agy"], [(1, "timeout", 600.0), (2, "timeout", 600.0)], timeout=540.0)
{'next': None, 'stop': 'budget'}
"""

import argparse
import json
import math
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import cast

MAX_RUNS_PER_TIER = 2
BINARY_FAILURES = frozenset(
    {"missing", "rate-limit", "auth", "untrusted", "credit", "crash", "unsupported-flag"}
)


def plan(
    tiers: list[str],
    ran: list[tuple[int, str, float]],
    *,
    timeout: float | None,
    plan_mode: bool = False,
    retry: int | None = None,
) -> dict[str, object]:
    """Return the next tier number, or the reason to stop."""
    counts = Counter(n for n, _, _ in ran)
    capped = max(counts.values(), default=0) > MAX_RUNS_PER_TIER or (
        retry is not None and counts[retry] >= MAX_RUNS_PER_TIER
    )
    if capped:
        return {"next": None, "stop": "retry-cap"}
    if retry is not None:
        return {"next": retry, "stop": None}
    if timeout is not None and sum(elapsed for _, _, elapsed in ran) > 2 * timeout:
        return {"next": None, "stop": "budget"}
    empties = [n for n, cls, _ in ran if cls == "empty"]
    if empties and (not plan_mode or len(empties) > 1):
        return {"next": None, "stop": "empty"}
    blocked = BINARY_FAILURES | (frozenset({"empty"}) if plan_mode else frozenset[str]())
    bad = {tiers[n - 1] for n, cls, _ in ran if cls in blocked}
    done = {n for n, _, _ in ran}
    for number in range(1, len(tiers) + 1):
        if number not in done and tiers[number - 1] not in bad:
            return {"next": number, "stop": None}
    return {"next": None, "stop": "no-tier"}


def read_ledger(path: Path) -> list[tuple[int, str, float]]:
    """Read (tier, class, elapsed) rows; a missing ledger means nothing has run."""
    if not path.exists():
        return []
    rows: list[tuple[int, str, float]] = []
    for line in path.read_text().splitlines():
        entry = cast("dict[str, object]", json.loads(line))
        rows.append(
            (
                int(cast("int", entry["tier"])),
                str(entry["class"]),
                float(cast("float", entry["elapsed"])),
            )
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and print the decision."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--prompt-file", required=True, type=Path)
    _ = parser.add_argument("--timeout", default="540")
    _ = parser.add_argument("--plan", action="store_true")
    _ = parser.add_argument("--tier", action="append", required=True)
    _ = parser.add_argument("--retry", type=int)
    args = parser.parse_args(argv)
    raw = cast("str", args.timeout)
    try:
        timeout = None if raw == "none" else float(raw)
    except ValueError:
        parser.error(f"invalid --timeout {raw!r}")
    if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
        parser.error(f"invalid --timeout {raw!r}")
    tiers = cast("list[str]", args.tier)
    prompt_file = cast("Path", args.prompt_file)
    ran = read_ledger(prompt_file.with_name(prompt_file.name + ".ledger"))
    ran += [(n, "missing", 0.0) for n, tier in enumerate(tiers, 1) if shutil.which(tier) is None]
    json.dump(
        plan(
            tiers,
            ran,
            timeout=timeout,
            plan_mode=cast("bool", args.plan),
            retry=cast("int | None", args.retry),
        ),
        sys.stdout,
    )
    _ = sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
