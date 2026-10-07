#!/usr/bin/env python3
"""Measure what adopting ruff's default rule set would add to a repository.

Runs ``<ruff command> check --statistics`` as configured, then again with the
binary's default codes added through ``--extend-select``, and prints one
``code<TAB>configured<TAB>with-defaults<TAB>delta`` line per rule plus a
``total`` line. The ruff command follows ``--`` and must end in ``ruff``. The
default codes come from ``--isolated --show-settings`` run on a scratch file;
exits 2 when that output lists no codes.

With ``--new-since "<old ruff command>"`` it instead prints the codes the
command reports now that the old command did not, one ``code<TAB>count`` line
each, so a version bump commits only rules the previous version never raised.
"""

# ruff: noqa: S603
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

_CODE = re.compile(r"\(([A-Z]+[0-9]+)\)")


def default_codes(show_settings: str) -> list[str]:
    r"""Return the codes in the ``linter.rules.enabled`` block.

    >>> text = "linter.rules.enabled = [\n x (E401),\n y (F401),\n]\nz = [\n w (A1),\n]"
    >>> default_codes(text)
    ['E401', 'F401']
    """
    block: list[str] = []
    inside = False
    for line in show_settings.splitlines():
        if line.startswith("linter.rules.enabled"):
            inside = True
        elif inside and line.startswith("]"):
            break
        elif inside:
            block.append(line)
    return _CODE.findall("\n".join(block))


def counts(statistics_json: str) -> dict[str, int]:
    """Map rule code to finding count from ``--statistics --output-format json``.

    >>> counts('[{"code": "F401", "count": 3}]')
    {'F401': 3}
    """
    text = statistics_json.strip()
    return {row["code"]: row["count"] for row in json.loads(text)} if text else {}


def _ruff(cmd: list[str], *args: str, cwd: str, ok: tuple[int, ...] = (0, 1)) -> str:
    done = subprocess.run([*cmd, *args], cwd=cwd, capture_output=True, text=True, check=False)
    if done.returncode not in ok:
        sys.stderr.write(done.stderr)
        raise SystemExit(2)
    return done.stdout


def measure(cmd: list[str], cwd: str) -> list[tuple[str, int, int]]:
    """Return ``(code, configured, with_defaults)`` sorted by code."""
    with tempfile.TemporaryDirectory() as scratch:
        probe = Path(scratch, "probe.py")
        probe.write_text("x = 1\n")
        shown = _ruff(
            cmd,
            "check",
            "--isolated",
            "--no-cache",
            "--show-settings",
            str(probe),
            cwd=cwd,
        )
    codes = default_codes(shown)
    if not codes:
        sys.stderr.write("no default rule codes found in --show-settings output\n")
        raise SystemExit(2)
    base = ("check", "--no-cache", "--statistics", "--output-format", "json")
    configured = counts(_ruff(cmd, *base, cwd=cwd))
    widened = counts(_ruff(cmd, *base, "--extend-select", ",".join(codes), cwd=cwd))
    return [(c, configured.get(c, 0), widened[c]) for c in sorted(widened)]


def new_codes(old_cmd: list[str], cmd: list[str], cwd: str) -> list[tuple[str, int]]:
    """Return ``(code, count)`` for codes ``cmd`` reports and ``old_cmd`` does not."""
    base = ("check", "--no-cache", "--statistics", "--output-format", "json")
    before = counts(_ruff(old_cmd, *base, cwd=cwd))
    after = counts(_ruff(cmd, *base, cwd=cwd))
    return [(c, n) for c, n in sorted(after.items()) if n > 0 and before.get(c, 0) == 0]


def render(rows: list[tuple[str, int, int]]) -> str:
    """Format rows as tab-separated lines ending in a total.

    >>> render([("F401", 1, 4)]).split()
    ['F401', '1', '4', '3', 'total', '1', '4', '3']
    """
    lines = [f"{c}\t{a}\t{b}\t{b - a}" for c, a, b in rows]
    a_sum = sum(a for _, a, _ in rows)
    b_sum = sum(b for _, _, b in rows)
    lines.append(f"total\t{a_sum}\t{b_sum}\t{b_sum - a_sum}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    """Parse arguments, measure, and print the table."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="repository to measure")
    parser.add_argument(
        "--new-since",
        metavar="OLD_RUFF_COMMAND",
        help="list codes this ruff reports that the quoted old command does not",
    )
    parser.add_argument("ruff", nargs=argparse.REMAINDER, help="-- <ruff command>")
    args = parser.parse_args(argv)
    cmd = args.ruff[1:] if args.ruff[:1] == ["--"] else args.ruff
    if not cmd:
        parser.error("give the ruff command after --")
    if args.new_since:
        rows = new_codes(shlex.split(args.new_since), cmd, args.cwd)
        print("\n".join(f"{c}\t{n}" for c, n in rows))
        return 0
    print(render(measure(cmd, args.cwd)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
